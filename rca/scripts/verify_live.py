#!/usr/bin/env python3
"""Keyless live verification. --faults affects only the deployed sample-service."""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

from rcactl import ROOT, kubectl, pod


def cli(*args):
    return json.loads(kubectl('-n', 'rca-system', 'exec', 'deployment/rca-agent', '-c', 'agent', '--',
                             'python', '-m', 'rca.cli', *args, capture=True))


def wait_for(predicate, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(3)
    raise AssertionError('verification timed out')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--faults', action='store_true')
    args = parser.parse_args()
    result = {'started_at': datetime.now(timezone.utc).isoformat(), 'mode': 'keyless_live_verification'}
    try:
        for name in ('sample-service', 'sample-backend'):
            kubectl('-n', 'rca-lab', 'rollout', 'status', 'deployment/' + name, '--timeout=90s')
        result['health'] = cli('health')
        assert not result['health']['llm_configured'], 'This verifier is keyless; API key is already configured'
        assert result['health']['pod_poll']['ok']
        assert set(result['health']['collectors']) == {'worker-1', 'worker-3'}
        for collector in result['health']['collectors'].values():
            received = datetime.fromisoformat(collector['received_at'].replace('Z', '+00:00'))
            assert (datetime.now(timezone.utc) - received).total_seconds() < 30
            assert collector['source_readable']
        subprocess.run([sys.executable, str(ROOT/'scripts/rcactl.py'), 'traffic'], check=True)
        time.sleep(12)  # complete collector bucket + Prometheus scrape
        result['preflight'] = cli('preflight', pod())
        assert all(e['availability'] == 'available' for e in result['preflight']['evidence']), 'A telemetry source is unavailable'
        print('PASS: all telemetry sources are available', flush=True)
        if args.faults:
            result['faults'] = []
            for mode, expected in [('crash', 'Error'), ('memory', 'OOMKilled'), ('cpu', None)]:
                before = {x['id'] for x in cli('list')}
                subprocess.run([sys.executable, str(ROOT/'scripts/rcactl.py'), 'fault', mode], check=True)
                def find_incident():
                    for row in cli('list'):
                        if row['id'] in before or row['state'] not in ('awaiting_api_key', 'paused'):
                            continue
                        inc = cli('show', row['id'])
                        if inc['data']['pod'] != pod():
                            continue
                        if mode == 'cpu' and inc['data']['symptom'] != 'RcaLabCpuThrottling':
                            continue
                        if mode != 'cpu' and inc['data']['symptom'] != 'ContainerRestart':
                            continue
                        return inc
                inc = wait_for(find_incident)
                time.sleep(17)  # freeze final eBPF bucket before inspecting
                evidence = cli('inspect', inc['id'])
                if expected:
                    status = next(e for e in evidence['evidence'] if e['tool'] == 'get_workload_status')
                    reasons = [s.get('lastState', {}).get('terminated', {}).get('reason') for s in status['data']['container_statuses']]
                    assert expected in reasons, (mode, reasons)
                    logs = next(e for e in evidence['evidence'] if e['tool'] == 'get_logs')
                    assert logs['availability'] == 'available' and logs['lines'], 'Incident logs were not preserved'
                assert inc['result'] is None, 'Unexpected diagnosis without a model'
                result['faults'].append({'mode': mode, 'incident': inc, 'evidence': evidence})
                print('PASS: ' + mode + ' triggered and preserved incident ' + inc['id'], flush=True)
                time.sleep(5)
        result['passed'] = True
    except Exception as e:
        result['passed'] = False
        result['error'] = str(e)
        raise
    finally:
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        (ROOT/'artifacts').mkdir(exist_ok=True)
        (ROOT/'artifacts/live-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print('Saved artifacts/live-verification.json', flush=True)


if __name__ == '__main__':
    main()
