"""Clock-domain-aware fresh capture; never changes node clocks or old records."""
import copy
import base64
import json
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch
from rca.common import Settings, now, stamp
from rca.store import Store
from rca.telemetry import Telemetry
from research.capture import write_new, stopped, OperatorKube, prom_request, DRIVER, kubectl, pod
from research.evidence import summarize, verify_chain, digest


def bracket(remote, before, after):
    if after < before: raise ValueError('controller clock stepped backwards')
    return {'remote_epoch':remote,'local_before':before,'local_after':after,
            'offset_interval_seconds':[remote-after,remote-before]}


def translate_epoch(value, source, destination):
    # Difference of interval-valued offsets. This is not an exact clock correction.
    s0,s1=source['offset_interval_seconds'];d0,d1=destination['offset_interval_seconds']
    bounds=[value-s1+d0,value-s0+d1]
    return {'midpoint':sum(bounds)/2,'bounds':bounds,'uncertainty_seconds':(bounds[1]-bounds[0])/2}


def node_clock(name):
    before=time.time()
    remote=json.loads(kubectl('-n','rca-lab','exec',name,'--','python','-c',
        'import time,json; print(json.dumps({"wall":time.time(),"monotonic":time.monotonic()}))',capture=True))
    after=time.time()
    return {**bracket(remote['wall'],before,after),'node':'worker-1','pod':name,'monotonic':remote['monotonic']}


def prometheus_clock():
    before=time.time(); result=prom_request('http://unused/api/v1/query?query=time%28%29')['data'];after=time.time()
    if result['resultType']!='scalar':raise ValueError('unexpected Prometheus clock response')
    return {**bracket(float(result['result'][1]),before,after),'source':'Prometheus time() scalar','raw':result}


def capture(study,protocol,exported_lines):
    write_new(study/'private/cluster-before.json',stopped())
    deployment=json.loads(kubectl('-n','rca-lab','get','deployment','sample-service','-o','json',capture=True))
    app=next(c for c in deployment['spec']['template']['spec']['containers'] if c['name']=='app')
    if any(e['name']=='LOG_DETAIL' and e.get('value')!='opaque' for e in app.get('env',[])):
        raise ValueError('opaque logging required; no implicit environment mutation')
    truth=[];index=[];settings=Settings();settings.llm_enabled=False
    try:
        for trial in protocol['independent_capture_plan']:
            cid=uuid.uuid4().hex[:16]; print(json.dumps({'capture_start':cid,'trial':trial,'clock_basis':'worker-1'}),flush=True)
            kubectl('-n','rca-lab','rollout','restart','deployment/sample-service')
            kubectl('-n','rca-lab','rollout','status','deployment/sample-service','--timeout=120s')
            name=pod(); target=OperatorKube().get('/api/v1/namespaces/rca-lab/pods/'+name)
            services=OperatorKube().get('/api/v1/namespaces/rca-lab/services')
            service=next(s for s in services['items'] if s['metadata']['name']=='sample-backend')
            slices=OperatorKube().get('/apis/discovery.k8s.io/v1/namespaces/rca-lab/endpointslices?labelSelector=kubernetes.io%2Fservice-name%3Dsample-backend')
            declared=json.loads(target['metadata']['annotations']['rca.lab/dependency-contract'])
            if declared['expected_ip']!=service['spec']['clusterIP'] or declared['expected_port'] not in [p['port'] for p in service['spec']['ports']]:
                raise ValueError('stale declared dependency')
            mapping={'captured_at':now(),'contract':declared,'source':'Pod lab annotation + Service + EndpointSlice snapshots',
                     'address_kind':'Service VIP, not backend Pod IP','services':services,'endpoint_slices':slices}
            write_new(study/'private'/cid/'address-mapping.json',mapping)
            time.sleep(15)
            injection={'assigned_fault':trial['fault'],'requested_at_controller_clock':now(),'pod_uid':target['metadata']['uid']}
            if trial['fault']!='normal':
                code='import urllib.request; print(urllib.request.urlopen(urllib.request.Request('+repr('http://127.0.0.1:8080/fault/'+trial['fault'])+',data=b"{}"),timeout=5).read().decode())'
                injection['response']=kubectl('-n','rca-lab','exec',name,'--','python','-c',code,capture=True)
            start_clock=node_clock(name)
            load=json.loads(kubectl('-n','rca-lab','exec','deployment/sample-backend','--','python','-c',
                                   DRIVER.replace('INTERVAL',str(trial['load_interval_seconds'])),capture=True))
            end_clock=node_clock(name)
            duration=end_clock['remote_epoch']-start_clock['remote_epoch']
            if duration<=0 or abs(duration-(end_clock['monotonic']-start_clock['monotonic']))>0.05:
                raise ValueError('observed reference-node clock step during capture')
            prom_clock=prometheus_clock(); metric_end=translate_epoch(end_clock['remote_epoch'],end_clock,prom_clock)
            clocks={'reference_clock':'worker-1 wall clock','window_start':start_clock,'window_end':end_clock,
                    'prometheus_clock':prom_clock,'metric_query_end':metric_end,
                    'driver_finished_epoch_worker3_not_used_as_window_end':load['finished_epoch'],
                    'limitations':['Offset intervals include exec/proxy RTT; midpoint alignment is approximate.',
                                   'No host clock changed. Events from unknown producers cannot establish fine temporal ordering.']}
            write_new(study/'private'/cid/'clocks.json',clocks)
            status=next(s for s in target['status']['containerStatuses'] if s['name']=='app')
            current=OperatorKube().get('/api/v1/namespaces/rca-lab/pods/'+name)
            current_status=next(s for s in current['status']['containerStatuses'] if s['name']=='app')
            if current['metadata']['uid']!=target['metadata']['uid'] or current_status['containerID']!=status['containerID']:
                raise ValueError('container changed during capture')
            incident={'namespace':'rca-lab','pod':name,'pod_uid':target['metadata']['uid'],'container_name':'app',
                      'container_id':status['containerID'],'node':'worker-1','time':stamp(end_clock['remote_epoch']),
                      'window_start':stamp(start_clock['remote_epoch']),'reference_clock':'worker-1',
                      'symptom':'HTTP service investigation'}
            with tempfile.TemporaryDirectory(prefix='paper-clock-capture-') as tmp:
                store=Store(str(Path(tmp)/'capture.db'))
                try:
                    telemetry=Telemetry(OperatorKube(),store,settings);iid,_=store.add(incident,cid)
                    telemetry.capture(iid,current)
                    evidence=[e for e in store.all_evidence(iid) if e['tool']!='get_ebpf_summary']
                    metric_inc={**incident,'time':stamp(metric_end['midpoint']),'reference_clock':'Prometheus'}
                    mid,_=store.add(metric_inc,cid+'-metrics')
                    with patch('rca.telemetry.request',prom_request):
                        for metric in ('cpu','memory'):
                            e=telemetry.call(mid,'get_metrics',{'metric':metric,'window_seconds':300})
                            e['source_key']='metrics_'+metric
                            e['clock_alignment']={'source_clock':'Prometheus','incident_clock':'worker-1',
                                'query_end_in_source_clock':metric_end,'reference_window_end':incident['time'],
                                'prometheus_minus_reference_offset_interval':[
                                    prom_clock['offset_interval_seconds'][0]-end_clock['offset_interval_seconds'][1],
                                    prom_clock['offset_interval_seconds'][1]-end_clock['offset_interval_seconds'][0]],
                                'note':'Raw metric timestamps preserved; do not claim timing finer than alignment uncertainty and scrape cadence.'}
                            e['evidence_id']='ev-'+digest(e)[:20];evidence.append(e)
                finally:store.db.close()
            for e in evidence:
                if e['tool']=='get_logs': e['clock_domain']='worker-1'
                elif e['tool']=='get_k8s_events': e['clock_domain']='producer dependent; unknown offset, no fine causal ordering'
                if e['tool'] in ('get_logs','get_k8s_events'):e['evidence_id']='ev-'+digest(e)[:20]
            state=next(e for e in evidence if e['tool']=='get_workload_status')
            state['data']['expected_destination_source']={'source':mapping['source'],'captured_at':mapping['captured_at'],
                'address_kind':mapping['address_kind'],'service_uid':service['metadata']['uid'],
                'service_resource_version':service['metadata']['resourceVersion'],'mapping_sha256':digest(mapping),
                'backend_pod_addresses':[a for s in slices['items'] for ep in s.get('endpoints',[]) for a in ep.get('addresses',[])]}
            state['evidence_id']='ev-'+digest(state)[:20]
            time.sleep(3);export=exported_lines(incident['pod_uid'])
            lines=[base64.b64decode(r['base64']).decode() for r in export['records']]
            summary,proof=summarize(lines,incident,start_clock['remote_epoch'],end_clock['remote_epoch'])
            verify_chain(summary,proof,lines,incident)
            write_new(study/'private'/cid/'raw-export.json',export);write_new(study/'private'/cid/'summary-proof.json',proof)
            write_new(study/'private'/cid/'capture.json',{'injection':injection,'load':load,'trial':trial})
            write_new(study/'agent-cases'/(cid+'.json'),{'case_id':cid,'incident':incident,'evidence':evidence+[summary]})
            statuses=[r['status'] for r in load['records']]
            observed=bool(statuses) and (all(s==200 for s in statuses) if trial['fault']=='normal' else any(s==503 for s in statuses))
            truth.append({'case_id':cid,'independent_incident_id':cid,'view':'original','trial':trial,'assigned_cause':trial['fault'],
                'injection_effect_observed':observed,'target':{k:incident[k] for k in ('pod_uid','container_id','pod')},
                'expected_destination':declared,'ground_truth_scope':'Assigned lab fault + workload HTTP observations; not universal fault absence'})
            index.append(cid);print(json.dumps({'captured':len(index),'raw_events':len(lines),'attempts_in_window':len(proof['events']),
                                              'effect_observed':observed,'metric_alignment_uncertainty_seconds':metric_end['uncertainty_seconds']}),flush=True)
        parent_truth=[t for t in truth if t['assigned_cause']=='network_port'][-1]
        parent=json.loads((study/'agent-cases'/(parent_truth['case_id']+'.json')).read_text())
        old=json.loads((study/'agent-cases'/(truth[1]['case_id']+'.json')).read_text())
        for condition in protocol['derived_views']:
            case=copy.deepcopy(parent);case['case_id']=uuid.uuid4().hex[:16]
            if condition=='historical_contamination':
                e=next(e for e in case['evidence'] if e['tool']=='get_k8s_events')
                e['historical_context']={'incident':old['incident'],'evidence':[x for x in old['evidence'] if x['tool'] in ('get_logs','get_k8s_events')]}
                e['evidence_id']='ev-'+digest(e)[:20]
            else:
                for i,e in enumerate(case['evidence']):
                    if condition=='insufficient_evidence' or e['tool']=='get_ebpf_summary':
                        missing={'tool':e['tool'],'availability':'unavailable','observation_state':'collection_failed',
                            'target':case['incident'],'error':'source capture unavailable','source_key':e.get('source_key',e['tool'])}
                        missing['evidence_id']='ev-'+digest(missing)[:20];case['evidence'][i]=missing
            write_new(study/'agent-cases'/(case['case_id']+'.json'),case)
            truth.append({**parent_truth,'case_id':case['case_id'],'view':condition,'parent_case_id':parent['case_id'],
                          'synthetic_evidence_transformation':True});index.append(case['case_id'])
        write_new(study/'private/truth.json',{'cases':truth,'independent_capture_count':6,'derived_view_count':3})
        write_new(study/'dataset.json',{'complete':True,'case_ids':index,
            'case_sha256':{cid:digest((study/'agent-cases'/(cid+'.json')).read_bytes()) for cid in index}})
    finally:
        kubectl('-n','rca-lab','rollout','restart','deployment/sample-service')
        kubectl('-n','rca-lab','rollout','status','deployment/sample-service','--timeout=120s')
        write_new(study/'private/cluster-after.json',stopped())
