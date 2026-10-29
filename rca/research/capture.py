"""Bounded lab capture. No Agent/probe/collector deployment changes."""
import copy
import json
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch
from rca.common import Settings, epoch, now, stamp
from rca.store import Store
from rca.telemetry import Telemetry
from research.evidence import summarize, digest, verify_chain

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts.capture_network_study import OperatorKube, prom_request, snapshot_pod, DRIVER
from scripts.rcactl import kubectl, pod


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def stopped():
    agent = json.loads(kubectl('-n', 'rca-system', 'get', 'deployment', 'rca-agent', '-o', 'json', capture=True))
    if agent['spec'].get('replicas', 1) != 0:
        raise ValueError('operational Agent must remain stopped')
    return {'replicas': 0, 'env': agent['spec']['template']['spec']['containers'][0].get('env', [])}


def exported_lines(uid):
    # Read existing exports only. Preserve exact bytes of matched lines and
    # source file offsets. A bounded scan is explicitly not kernel completeness.
    code = '''import pathlib,json,base64
uid=UID
records=[]; files=[]; total=0
for p in sorted(pathlib.Path('/tetragon').glob('tetragon.log*')):
 if not p.is_file() or p.suffix=='.gz': continue
 st=p.stat(); start=max(0,st.st_size-16000000); scanned=0
 with p.open('rb') as f:
  f.seek(start)
  if start: f.readline()
  while f.tell()<st.st_size:
   offset=f.tell(); line=f.readline(65537); scanned+=len(line)
   if uid.encode() in line and len(line)<=65536:
    records.append({'path':str(p),'inode':st.st_ino,'offset':offset,'base64':base64.b64encode(line).decode()})
   if len(records)>10000: raise RuntimeError('capture record limit')
 after=p.stat(); files.append({'path':str(p),'inode':st.st_ino,'size_before':st.st_size,'size_after':after.st_size,'start_offset':start,'stable_inode':st.st_ino==after.st_ino,'scan_bytes':scanned})
 total+=scanned
 if total>64000000: break
print(json.dumps({'records':records,'files':files,'scope':'bounded existing export scan; rotation/upstream loss not ruled out'}))
'''.replace('UID', repr(uid))
    return json.loads(kubectl('-n', 'rca-system', 'exec', snapshot_pod(), '--', 'python', '-c', code, capture=True))


def capture(study, protocol):
    import base64
    write_new(study / 'private/cluster-before.json', stopped())
    frontend = json.loads(kubectl('-n', 'rca-lab', 'get', 'deployment', 'sample-service', '-o', 'json', capture=True))
    app = next(c for c in frontend['spec']['template']['spec']['containers'] if c['name'] == 'app')
    log_env = next((e for e in app.get('env', []) if e['name'] == 'LOG_DETAIL'), None)
    if log_env and (log_env.get('value', 'opaque') != 'opaque' or 'valueFrom' in log_env):
        raise ValueError('protocol requires existing opaque logging; refusing environment change')
    prom_request('http://unused/api/v1/query?query=up')
    truth, index = [], []
    settings = Settings()
    settings.llm_enabled = False
    try:
        for trial in protocol['independent_capture_plan']:
            case_id = uuid.uuid4().hex[:16]
            print(json.dumps({'capture_start': case_id, 'trial': trial}), flush=True)
            kubectl('-n', 'rca-lab', 'rollout', 'restart', 'deployment/sample-service')
            kubectl('-n', 'rca-lab', 'rollout', 'status', 'deployment/sample-service', '--timeout=120s')
            target = OperatorKube().get('/api/v1/namespaces/rca-lab/pods/' + pod())
            service = OperatorKube().get('/api/v1/namespaces/rca-lab/services/sample-backend')
            slices = OperatorKube().get('/apis/discovery.k8s.io/v1/namespaces/rca-lab/endpointslices?labelSelector=kubernetes.io%2Fservice-name%3Dsample-backend')
            declared = json.loads(target['metadata']['annotations']['rca.lab/dependency-contract'])
            if declared['expected_ip'] != service['spec']['clusterIP'] or declared['expected_port'] not in [p['port'] for p in service['spec']['ports']]:
                raise ValueError('expected destination declaration is stale; preserve failure, do not silently repair')
            mapping = {'captured_at': now(), 'contract': declared, 'source': 'lab Pod annotation + live Service + EndpointSlices',
                       'address_kind': 'Service ClusterIP, NOT backend Pod IP',
                       'service': service, 'endpoint_slices': slices}
            write_new(study / 'private' / case_id / 'address-mapping.json', mapping)
            time.sleep(15)
            injection = {'assigned_fault': trial['fault'], 'requested_at': now(), 'pod_uid': target['metadata']['uid']}
            if trial['fault'] != 'normal':
                code = 'import urllib.request; print(urllib.request.urlopen(urllib.request.Request(' + repr('http://127.0.0.1:8080/fault/' + trial['fault']) + ',data=b"{}"),timeout=5).read().decode())'
                injection['response'] = kubectl('-n', 'rca-lab', 'exec', 'deployment/sample-service', '--', 'python', '-c', code, capture=True)
            start = time.time()
            load = json.loads(kubectl('-n', 'rca-lab', 'exec', 'deployment/sample-backend', '--', 'python', '-c',
                                    DRIVER.replace('INTERVAL', str(trial['load_interval_seconds'])), capture=True))
            end = load['finished_epoch']
            status = next(s for s in target['status']['containerStatuses'] if s['name'] == 'app')
            incident = {'namespace': 'rca-lab', 'pod': target['metadata']['name'], 'pod_uid': target['metadata']['uid'],
                        'container_name': 'app', 'container_id': status['containerID'], 'node': 'worker-1',
                        'time': stamp(end), 'symptom': 'HTTP service investigation',
                        'window_start': stamp(start)}
            with tempfile.TemporaryDirectory(prefix='paper-capture-') as tmp:
                store = Store(str(Path(tmp) / 'capture.db'))
                try:
                    telemetry = Telemetry(OperatorKube(), store, settings)
                    iid, _ = store.add(incident, case_id)
                    telemetry.capture(iid, telemetry.pod(incident['pod']))
                    with patch('rca.telemetry.request', prom_request):
                        for metric in ('cpu', 'memory'):
                            telemetry.call(iid, 'get_metrics', {'metric': metric, 'window_seconds': 300})
                    evidence = [e for e in store.all_evidence(iid) if e['tool'] != 'get_ebpf_summary']
                finally:
                    store.db.close()
            time.sleep(3)
            export = exported_lines(incident['pod_uid'])
            lines = [base64.b64decode(r['base64']).decode() for r in export['records']]
            readable = bool(export['files']) and all(f['stable_inode'] for f in export['files'])
            summary, proof = summarize(lines, incident, start, end, readable)
            verify_chain(summary, proof, lines, incident)
            write_new(study / 'private' / case_id / 'raw-export.json', export)
            write_new(study / 'private' / case_id / 'summary-proof.json', proof)
            write_new(study / 'private' / case_id / 'capture.json', {'injection': injection, 'load': load, 'trial': trial})
            status_e = next(e for e in evidence if e['tool'] == 'get_workload_status')
            status_e['data']['expected_destination_source'] = {'source': mapping['source'], 'captured_at': mapping['captured_at'],
                'address_kind': mapping['address_kind'], 'service_uid': service['metadata']['uid'],
                'service_resource_version': service['metadata']['resourceVersion'], 'mapping_sha256': digest(mapping),
                'backend_pod_addresses': [a for s in slices['items'] for ep in s.get('endpoints', []) for a in ep.get('addresses', [])]}
            status_e['evidence_id'] = 'ev-' + digest(status_e)[:20]
            case = {'case_id': case_id, 'incident': incident, 'evidence': evidence + [summary]}
            write_new(study / 'agent-cases' / (case_id + '.json'), case)
            statuses = [r['status'] for r in load['records']]
            observed = bool(statuses) and (all(s == 200 for s in statuses) if trial['fault'] == 'normal' else any(s == 503 for s in statuses))
            # Failed injections/captures remain in dataset; not relabelled/dropped.
            truth.append({'case_id': case_id, 'independent_incident_id': case_id, 'view': 'original', 'trial': trial,
                          'assigned_cause': trial['fault'], 'injection_effect_observed': observed,
                          'target': {k:incident[k] for k in ('pod_uid', 'container_id', 'pod')},
                          'expected_destination': declared,
                          'ground_truth_scope': 'Assigned lab fault and HTTP outcome; not every alternative root cause excluded'})
            index.append(case_id)
            write_new(study / 'private' / case_id / 'capture-complete.json', {'complete': True, 'effect_observed': observed})
            print(json.dumps({'captured': len(index), 'case_id': case_id, 'effect_observed': observed, 'raw_events': len(lines)}), flush=True)
        parent_truth = [t for t in truth if t['assigned_cause'] == 'network_port'][-1]
        parent = json.loads((study / 'agent-cases' / (parent_truth['case_id'] + '.json')).read_text())
        historical = json.loads((study / 'agent-cases' / (truth[1]['case_id'] + '.json')).read_text())
        for condition in protocol['derived_views']:
            case = copy.deepcopy(parent)
            case['case_id'] = uuid.uuid4().hex[:16]
            if condition == 'historical_contamination':
                e = next(e for e in case['evidence'] if e['tool'] == 'get_k8s_events')
                # Preserve actual timestamps/identity: visibly foreign context,
                # never manufacture an old OOM event as if actually observed.
                e['historical_context'] = {'incident': historical['incident'], 'evidence': [x for x in historical['evidence'] if x['tool'] in ('get_logs', 'get_k8s_events')]}
                e['evidence_id'] = 'ev-' + digest(e)[:20]
            else:
                for i, e in enumerate(case['evidence']):
                    if condition == 'insufficient_evidence' or e['tool'] == 'get_ebpf_summary':
                        missing = {'tool': e['tool'], 'availability': 'unavailable', 'observation_state': 'collection_failed',
                                   'target': case['incident'], 'error': 'source capture unavailable',
                                   'source_key': 'metrics_memory' if 'working_set_bytes' in e.get('series', {}) else 'metrics_cpu' if e['tool'] == 'get_metrics' else e['tool']}
                        missing['evidence_id'] = 'ev-' + digest(missing)[:20]
                        case['evidence'][i] = missing
            write_new(study / 'agent-cases' / (case['case_id'] + '.json'), case)
            truth.append({**parent_truth, 'case_id': case['case_id'], 'view': condition,
                          'parent_case_id': parent['case_id'], 'synthetic_evidence_transformation': True})
            index.append(case['case_id'])
        write_new(study / 'private/truth.json', {'cases': truth, 'independent_capture_count': 6, 'derived_view_count': 3})
        write_new(study / 'dataset.json', {'complete': True, 'case_ids': index,
            'case_sha256': {cid:digest((study / 'agent-cases' / (cid+'.json')).read_bytes()) for cid in index}})
    finally:
        # Bounded faults are TTL-limited; fresh process restores normal routing.
        kubectl('-n', 'rca-lab', 'rollout', 'restart', 'deployment/sample-service')
        kubectl('-n', 'rca-lab', 'rollout', 'status', 'deployment/sample-service', '--timeout=120s')
        write_new(study / 'private/cluster-after.json', stopped())
