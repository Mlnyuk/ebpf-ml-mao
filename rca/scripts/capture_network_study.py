#!/usr/bin/env python3
"""Collect six REAL lab fault instances without starting the RCA Agent/LLM.

Ground truth stays outside incident and evidence. All live mutation is scoped
to rca-lab/sample-service. Faults expire automatically; each trial gets a fresh
Pod UID. Existing global Tetragon/GPU configuration is never touched.
"""
import argparse
import copy
import hashlib
import json
import random
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from rcactl import ROOT, kubectl, pod
sys.path.insert(0, str(ROOT))
from rca.common import Settings, epoch, now, stamp
from rca.store import Store
from rca.telemetry import Telemetry


class OperatorKube:
    def get(self, path, raw=False):
        data = kubectl('get', '--raw', path, capture=True)
        return data if raw else json.loads(data)


def prom_request(url, **kwargs):
    parsed = urlsplit(url)
    path = '/api/v1/namespaces/monitoring/services/http:my-monitoring-kube-prometh-prometheus:9090/proxy'
    return OperatorKube().get(path + parsed.path + '?' + parsed.query)


def snapshot_pod():
    items = json.loads(kubectl('-n', 'rca-system', 'get', 'pods', '-l', 'app=rca-ebpf-summary', '-o', 'json', capture=True))['items']
    return next(p['metadata']['name'] for p in items if p['spec']['nodeName'] == 'worker-1' and not p['metadata'].get('deletionTimestamp'))


def snapshot():
    return json.loads(kubectl('-n', 'rca-system', 'exec', snapshot_pod(), '--', 'python', '-c',
        'import pathlib; print(pathlib.Path("/state/latest.json").read_text())', capture=True))


def resource_sample():
    # /proc/1 measures the aggregator process, excluding the measurement helper.
    code = ('import json,os,time; s=open("/proc/1/stat").read().split(); '
            'print(json.dumps({"monotonic":time.monotonic(),"cpu_seconds":(int(s[13])+int(s[14]))/os.sysconf("SC_CLK_TCK"),'
            '"rss_bytes":int(s[23])*os.sysconf("SC_PAGE_SIZE")}))')
    value = json.loads(kubectl('-n', 'rca-system', 'exec', snapshot_pod(), '--', 'python', '-c', code, capture=True))
    value['observed_at'] = now()
    return value


DRIVER = '''import concurrent.futures,json,time,urllib.request,urllib.error
records=[]
def one():
 start=time.monotonic()
 try:
  r=urllib.request.urlopen("http://sample-service:8080/work",timeout=4); status=r.status; r.read()
 except urllib.error.HTTPError as e: status=e.code
 except Exception: status=0
 return {"status":status,"seconds":round(time.monotonic()-start,6)}
deadline=time.monotonic()+30
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 futures=[]
 while time.monotonic()<deadline:
  futures.append(pool.submit(one)); time.sleep(INTERVAL)
 records=[f.result() for f in futures]
print(json.dumps({"records":records,"finished_epoch":time.time()}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/study-20261015/network-fixture.json')
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--log-modes', nargs='+', choices=['opaque', 'endpoint'], default=['opaque'])
    parser.add_argument('--intervals', nargs='+', type=float)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to overwrite an existing fixture')
    if not 1 <= args.trials <= 3 or len(set(args.log_modes)) != len(args.log_modes):
        parser.error('trials must be 1..3 and log modes must be unique')
    intervals = args.intervals or [1.0, 0.75, 0.5][:args.trials]
    if len(intervals) != args.trials or any(not 0.25 <= value <= 2 for value in intervals):
        parser.error('one interval per trial, each 0.25..2 seconds')
    agent = json.loads(kubectl('-n', 'rca-system', 'get', 'deployment', 'rca-agent', '-o', 'json', capture=True))
    if agent['spec'].get('replicas', 1) != 0:
        raise SystemExit('Agent must remain stopped')
    # Check metrics proxy before injecting any fault.
    prom_request('http://unused/api/v1/query?query=up')
    frontend = json.loads(kubectl('-n', 'rca-lab', 'get', 'deployment', 'sample-service', '-o', 'json', capture=True))
    original = next((e for c in frontend['spec']['template']['spec']['containers'] if c['name'] == 'app'
                     for e in c.get('env', []) if e['name'] == 'LOG_DETAIL'), None)
    if original and 'value' not in original:
        raise SystemExit('Refusing to replace LOG_DETAIL valueFrom')
    schedule = []
    rng = random.Random(2816)
    for trial in range(args.trials):
        combinations = [(mode, logging) for mode in ('network_port', 'network_peer') for logging in args.log_modes]
        rng.shuffle(combinations)
        schedule.extend({'trial': trial, 'mode': mode, 'logging': logging, 'interval': intervals[trial]}
                        for mode, logging in combinations)
    report = {'kind': 'real_injected_network_faults', 'started_at': now(), 'cases': [], 'complete': False,
              'method': 'Fresh pod per case, 30 seconds offered load with four-client cap; controlled logging conditions.',
              'schedule': schedule,
              'overhead_scope': 'Aggregator process CPU/RSS only, NOT total eBPF or causal workload overhead.',
              'code_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted((ROOT / 'rca').glob('*.py')) + [Path(__file__).resolve()]}}
    settings = Settings()
    settings.llm_enabled = False
    with tempfile.TemporaryDirectory(prefix='rca-capture-') as directory:
        store = Store(str(Path(directory) / 'capture.sqlite3'))
        telemetry = Telemetry(OperatorKube(), store, settings)
        try:
            for trial_spec in schedule:
                    trial, mode = trial_spec['trial'], trial_spec['mode']
                    print('Starting ' + json.dumps(trial_spec), flush=True)
                    kubectl('-n', 'rca-lab', 'set', 'env', 'deployment/sample-service', 'LOG_DETAIL=' + trial_spec['logging'])
                    kubectl('-n', 'rca-lab', 'rollout', 'restart', 'deployment/sample-service')
                    kubectl('-n', 'rca-lab', 'rollout', 'status', 'deployment/sample-service', '--timeout=120s')
                    target = telemetry.pod(pod())
                    idle_before = resource_sample()
                    print('Warm-up / idle measurement: 20 seconds', flush=True)
                    time.sleep(20)
                    idle_after = resource_sample()
                    subprocess.run([sys.executable, str(ROOT / 'scripts/rcactl.py'), 'fault', mode], check=True)
                    time.sleep(2)
                    before = resource_sample()
                    load = json.loads(kubectl('-n', 'rca-lab', 'exec', 'deployment/sample-backend', '--', 'python', '-c',
                        DRIVER.replace('INTERVAL', str(trial_spec['interval'])), capture=True))
                    after = resource_sample()
                    errors = sum(r['status'] == 503 for r in load['records'])
                    if errors == 0:
                        raise RuntimeError('Injected trial produced no HTTP 503; preserve and inspect rather than label it a success')
                    status = target['status']['containerStatuses'][0]
                    inc = {'namespace': 'rca-lab', 'pod': target['metadata']['name'], 'pod_uid': target['metadata']['uid'],
                           'container_name': status['name'], 'container_id': status['containerID'], 'node': 'worker-1',
                           'time': stamp(load['finished_epoch']), 'symptom': 'ServiceHTTPError: observed HTTP 503 responses'}
                    iid, _ = store.add(inc, 'trial:' + str(trial) + ':' + mode + ':' + trial_spec['logging'])
                    telemetry.capture(iid, telemetry.pod(inc['pod']))
                    print('Freeze final eBPF buckets: 12 seconds', flush=True)
                    time.sleep(12)
                    snap = snapshot()
                    # Ingest only this incident's container, never unrelated lab data.
                    windows = [w for w in snap['windows'] if w['pod_uid'] == inc['pod_uid'] and w['container_id'] == inc['container_id']
                               and w['start'] < epoch(inc['time']) and w['end'] > epoch(inc['time']) - 300]
                    store.ingest({'node': 'worker-1', 'health': snap['health'], 'windows': windows})
                    telemetry.freeze_ebpf(iid)
                    with patch('rca.telemetry.request', prom_request):
                        for metric in ('memory', 'cpu'):
                            telemetry.call(iid, 'get_metrics', {'metric': metric, 'window_seconds': 300})
                    for seconds in (30, 60, 120, 300):
                        telemetry.call(iid, 'get_ebpf_summary', {'window_seconds': seconds})
                    evidence = store.all_evidence(iid)
                    logs = next(e for e in evidence if e['tool'] == 'get_logs')
                    has_endpoint = any('dependency request failed target=' in line for line in logs.get('lines', []))
                    if has_endpoint != (trial_spec['logging'] == 'endpoint'):
                        raise RuntimeError('Captured logs do not match assigned logging condition')
                    # Derive shorter metric views from the exact observed sample
                    # grid; no interpolation or claim that missing points are normal.
                    for item in list(evidence):
                        if item['tool'] != 'get_metrics' or item.get('window_start') is None:
                            continue
                        for seconds in (30, 60, 120):
                            view = copy.deepcopy(item)
                            view['evidence_id'] += '-' + str(seconds)
                            view['window_start'] = stamp(epoch(inc['time']) - seconds)
                            view['source'] += ' (frozen sample-grid subset, no interpolation)'
                            for series in view['series'].values():
                                series['points'] = [p for p in series['points'] if p[0] >= epoch(view['window_start'])]
                                series['samples'] = len(series['points'])
                                series['max'] = max((p[1] for p in series['points']), default=None)
                            view['availability'] = 'available' if any(s['samples'] for s in view['series'].values()) else 'unavailable'
                            evidence.append(view)
                    network = next(e for e in evidence if e['tool'] == 'get_ebpf_summary' and e['window_end'] == inc['time']
                                   and round(epoch(e['window_end']) - epoch(e['window_start'])) == 300)
                    if not network['network']['tcp_connect_attempts']:
                        raise RuntimeError('No captured TCP destinations; cannot evaluate eBPF contribution')
                    report['cases'].append({'mode': mode, 'trial': trial, 'logging': trial_spec['logging'], 'offered_interval_seconds': trial_spec['interval'],
                        'incident': store.get(iid), 'evidence': evidence,
                        'ground_truth_for_evaluation_only': {'injection': mode, 'contract': target['metadata']['annotations']['rca.lab/dependency-contract'],
                            'wrong_port': 9099 if mode == 'network_port' else None,
                            'wrong_service': 'rca-lab/sample-service' if mode == 'network_peer' else None},
                        'load': load, 'resources': {'idle_before': idle_before, 'idle_after': idle_after,
                                                  'load_before': before, 'load_after': after},
                        'ebpf_raw_event_bytes': sum(w['counts'].get('raw_event_bytes', 0) for w in windows),
                        'ebpf_summary_bytes': len(json.dumps(network, ensure_ascii=False, separators=(',', ':')).encode())})
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
                    print('Captured ' + str(len(report['cases'])) + '/' + str(len(schedule)) + ', HTTP503=' + str(errors), flush=True)
            report['complete'] = True
        finally:
            store.db.close()
            report['finished_at'] = now()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            # Reset the scoped experimental process even on partial failure.
            kubectl('-n', 'rca-lab', 'set', 'env', 'deployment/sample-service',
                    'LOG_DETAIL=' + original['value'] if original else 'LOG_DETAIL-')
            kubectl('-n', 'rca-lab', 'rollout', 'restart', 'deployment/sample-service')
            kubectl('-n', 'rca-lab', 'rollout', 'status', 'deployment/sample-service', '--timeout=120s')
            print('Saved ' + str(args.output) + '; lab frontend restored.', flush=True)


if __name__ == '__main__':
    main()
