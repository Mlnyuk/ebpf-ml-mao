"""Fresh occurrences with same-node clocks and contemporaneous surrounding data."""
import base64
import copy
import json
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode
from rca.common import Settings,now,stamp,epoch
from rca.store import Store
from rca.telemetry import Telemetry
from rca.context import present_evidence,restore_evidence
from research.capture import stopped,write_new,OperatorKube,kubectl,pod,DRIVER,prom_request
from research.clock_capture import node_clock,prometheus_clock,translate_epoch
from research.evidence import summarize,verify_chain,digest
from scripts.paper_capture_v2 import exported_lines
from research_v4.lab_control import reset_frontend,stop_background,CONTEXT_NAMES
from research_v4.protocol import check


def incident_for(target,start,end):
    status=next(s for s in target['status']['containerStatuses'] if s['name']=='app')
    return {'namespace':'rca-lab','pod':target['metadata']['name'],'pod_uid':target['metadata']['uid'],
        'container_name':'app','container_id':status['containerID'],'node':target['spec']['nodeName'],
        'time':stamp(end),'window_start':stamp(start),'reference_clock':'worker-1','symptom':'HTTP service investigation'}


def telemetry(incident,target,metric_end,prom_clock,end_clock):
    with tempfile.TemporaryDirectory(prefix='rca-next-capture-') as tmp:
        store=Store(str(Path(tmp)/'capture.db'))
        try:
            tool=Telemetry(OperatorKube(),store,Settings());iid,_=store.add(incident,uuid.uuid4().hex)
            tool.capture(iid,target)
            evidence=[e for e in store.all_evidence(iid) if e['tool']!='get_ebpf_summary']
            mi={**incident,'time':stamp(metric_end['midpoint']),'reference_clock':'Prometheus'}
            mid,_=store.add(mi,uuid.uuid4().hex)
            with patch('rca.telemetry.request',prom_request):
                for metric in ['cpu','memory']:
                    e=tool.call(mid,'get_metrics',{'metric':metric,'window_seconds':300})
                    e['source_key']='metrics_'+metric
                    e['clock_alignment']={'source_clock':'Prometheus','incident_clock':'worker-1','query_end_in_source_clock':metric_end,
                        'offset_interval':[prom_clock['offset_interval_seconds'][0]-end_clock['offset_interval_seconds'][1],prom_clock['offset_interval_seconds'][1]-end_clock['offset_interval_seconds'][0]]}
                    evidence.append(e)
        finally:store.db.close()
    for e in evidence:
        e['target']=dict(incident)
        if e['tool']=='get_logs':e['clock_domain']='worker-1'
        if e['tool']=='get_k8s_events':e['clock_domain']='unknown producer offset; no fine ordering'
        e['source_key']=e.get('source_key',e['tool'])
        e['evidence_id']='ev-'+digest(e)[:20]
    return evidence


def observe(study,cid,trial,duration=None):
    name=pod();kube=OperatorKube();target=kube.get('/api/v1/namespaces/rca-lab/pods/'+name)
    urls=['/api/v1/namespaces/rca-lab/services','/apis/discovery.k8s.io/v1/namespaces/rca-lab/endpointslices']
    mapping={'at':now(),'source':'Pod annotation + Kubernetes Service/EndpointSlice','contract':json.loads(target['metadata']['annotations']['rca.lab/dependency-contract']),
             'services':kube.get(urls[0]),'endpoint_slices':kube.get(urls[1])}
    control='import urllib.request; print(urllib.request.urlopen(urllib.request.Request('+repr('http://127.0.0.1:8080/fault/'+trial['scenario'])+',data=b"{}"),timeout=5).read().decode())'
    injection={'at':now(),'assigned_scenario':trial['scenario'],'response':kubectl('-n','rca-lab','exec',name,'--','python','-c',control,capture=True)}
    start=node_clock(name)
    script=DRIVER.replace('INTERVAL',str(trial['load_interval_seconds'])).replace('time.monotonic()+30','time.monotonic()+'+str(duration or trial['duration_seconds']))
    load=json.loads(kubectl('-n','rca-lab','exec','deployment/sample-backend','--','python','-c',script,capture=True))
    end=node_clock(name)
    if abs((end['remote_epoch']-start['remote_epoch'])-(end['monotonic']-start['monotonic']))>0.05:raise ValueError('reference clock stepped')
    pc=prometheus_clock();me=translate_epoch(end['remote_epoch'],end,pc)
    current=kube.get('/api/v1/namespaces/rca-lab/pods/'+name)
    inc=incident_for(current,start['remote_epoch'],end['remote_epoch'])
    if inc['pod_uid']!=target['metadata']['uid']:raise ValueError('target replaced during occurrence')
    initial_id=next(s['containerID'] for s in target['status']['containerStatuses'] if s['name']=='app')
    if inc['container_id']!=initial_id:raise ValueError('target restarted during occurrence')
    evidence=telemetry(inc,current,me,pc,end)
    status=next(e for e in evidence if e['tool']=='get_workload_status')
    status['data']['expected_destination_source']={'source':mapping['source'],'at':mapping['at'],'mapping_sha256':digest(mapping),'address_kind':'Service VIP, not backend Pod address','services':[
        {'name':s['metadata']['name'],'uid':s['metadata']['uid'],'resource_version':s['metadata']['resourceVersion'],'cluster_ip':s['spec']['clusterIP'],'ports':s['spec']['ports']} for s in mapping['services']['items']]}
    status['evidence_id']='ev-'+digest(status)[:20]
    time.sleep(2);raw=exported_lines(inc['pod_uid']);lines=[base64.b64decode(r['base64']).decode() for r in raw['records']]
    ebpf,proof=summarize(lines,inc,start['remote_epoch'],end['remote_epoch'],readable=bool(raw['files']))
    verify_chain(ebpf,proof,lines,inc);evidence.append(ebpf)
    context=[]
    for label in CONTEXT_NAMES:
        found=kube.get('/api/v1/namespaces/rca-lab/pods?'+urlencode({'labelSelector':'app='+label}))['items']
        q=next(p for p in found if not p['metadata'].get('deletionTimestamp'))
        ci=incident_for(q,start['remote_epoch'],end['remote_epoch'])
        if ci['node']!='worker-1':raise ValueError('surrounding telemetry clock domain changed')
        for e in telemetry(ci,q,me,pc,end):
            e['source_key']=label+'.'+e['source_key'];e['evidence_id']='ev-'+digest(e)[:20];context.append(e)
    for e in evidence+context:
        if restore_evidence(present_evidence(e,inc,'compact-v4'),inc)!=e:raise ValueError('captured evidence does not roundtrip exactly')
    private=study/'private'/cid
    for filename,value in [('capture.json',{'trial':trial,'injection':injection,'load':load}),('address-mapping.json',mapping),
        ('clocks.json',{'start':start,'end':end,'prometheus':pc,'metric_end':me}),('raw-export.json',raw),('summary-proof.json',proof),
        ('surrounding-evidence.json',context)]:write_new(private/filename,value)
    # K8sGPT sees the live namespace at the same occurrence, not our frozen catalog.
    from research_v4.k8sgpt import native_scan,native_explain
    native_scan(study,cid)
    if (study/'protocol.json').exists():native_explain(study,cid)
    statuses=[r['status'] for r in load['records']]
    expected=200 if trial['scenario'] in ('normal','auxiliary_error') else 503
    effect=bool(statuses) and all(s==expected for s in statuses)
    return inc,evidence,context,{'independent_incident_id':cid,'trial':trial,'assigned_cause':trial['scenario'],
        'injection_effect_observed':effect,'expected_http_status':expected,'target':inc,'view':'original',
        'expected_destination':mapping['contract'],'observed_http_counts':{str(s):statuses.count(s) for s in set(statuses)}}


def smoke(study):
    results=[]
    try:
        reset_frontend('endpoint');time.sleep(16)
        for scenario in ['normal','application_error','mixed_route_error','auxiliary_error','route_error']:
            cid='smoke-'+uuid.uuid4().hex[:12]
            inc,e,context,t=observe(study/'development',cid,{'scenario':scenario,'logging':'endpoint','load_interval_seconds':0.7,'duration_seconds':4})
            write_new(study/'development'/('case-'+cid+'.json'),{'case_id':cid,'incident':inc,'evidence':e})
            results.append({'case_id':cid,'scenario':scenario,'effect_observed':t['injection_effect_observed'],
                'sources':[{ 'tool':x['tool'],'availability':x['availability']} for x in e],
                'attempts':next(x for x in e if x['tool']=='get_ebpf_summary')['network']['tcp_connect_attempts'],
                'context_snapshots':len(context)})
    finally:reset_frontend('opaque')
    write_new(study/'development/observability-smoke.json',{'at':now(),'results':results,'evaluation_data':False})
    if not all(r['effect_observed'] for r in results):raise ValueError('smoke effect check failed; do not collect evaluation data')


def capture(study):
    check(study);spec=json.loads((study/'protocol.json').read_text());write_new(study/'private/cluster-before.json',stopped())
    truths=[];index=[];originals=[];completion={'complete':False,'started_at':now(),'completed_occurrences':[]}
    try:
        for trial in spec['capture_schedule']:
            check(study);cid=uuid.uuid4().hex[:16];print(json.dumps({'capture_start':cid,'trial':trial}),flush=True)
            write_new(study/'private'/cid/'assignment.json',trial)
            reset_frontend(trial['logging']);time.sleep(16)
            inc,e,context,t=observe(study,cid,trial)
            for breadth,extra in [('target_only',[]),('surrounding_3_workloads',context)]:
                vid=cid+'-'+('small' if not extra else 'wide')
                case={'case_id':vid,'incident':inc,'evidence':e+extra}
                write_new(study/'agent-cases'/(vid+'.json'),case)
                truths.append({**t,'case_id':vid,'breadth':breadth});index.append(vid)
            originals.append((cid,inc,e,context,t));completion['completed_occurrences'].append(cid)
            print(json.dumps({'captured':len(originals),'target_attempts':sum(v['attempts'] for v in e[-1]['network']['tcp_connect_attempts']),
                'effect_observed':t['injection_effect_observed']}),flush=True)
        parent=next(x for x in reversed(originals) if x[4]['assigned_cause']=='application_error')
        old=next(x for x in originals if x[4]['assigned_cause']=='route_error' and x[1]['time']<parent[1]['time'])
        for condition in spec['robustness_views']:
            for breadth,extra in [('target_only',[]),('surrounding_3_workloads',parent[3])]:
                e=copy.deepcopy(parent[2]);vid=uuid.uuid4().hex[:16]
                if condition=='historical_contamination':
                    ev=next(x for x in e if x['tool']=='get_k8s_events')
                    ev['historical_context']={'incident':old[1],'evidence':[x for x in old[2] if x['tool'] in ('get_logs','get_k8s_events')]}
                    ev['evidence_id']='ev-'+digest(ev)[:20]
                else:
                    e=[{'tool':x['tool'],'source_key':x.get('source_key',x['tool']),'target':parent[1],'availability':'unavailable','observation_state':'collection_failed','error':'source unavailable'} if x['tool'] in ('get_logs','get_ebpf_summary') else x for x in e]
                    for x in e:
                        if 'evidence_id' not in x:x['evidence_id']='ev-'+digest(x)[:20]
                write_new(study/'agent-cases'/(vid+'.json'),{'case_id':vid,'incident':parent[1],'evidence':e+extra})
                truths.append({**parent[4],'case_id':vid,'view':condition,'breadth':breadth,'synthetic_evidence_transformation':True});index.append(vid)
        write_new(study/'private/truth.json',{'cases':truths,'independent_capture_count':20,'dependent_robustness_views':4})
        write_new(study/'dataset.json',{'complete':True,'case_ids':index,'case_sha256':{cid:digest((study/'agent-cases'/(cid+'.json')).read_bytes()) for cid in index}})
        completion['complete']=True
    except Exception as exc:
        completion['error']=type(exc).__name__+': '+str(exc)[:300];raise
    finally:
        completion['finished_at']=now();write_new(study/'capture-completion.json',completion)
        reset_frontend('opaque');stop_background();write_new(study/'private/cluster-after.json',stopped())
