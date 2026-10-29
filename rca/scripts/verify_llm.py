#!/usr/bin/env python3
"""Bounded real-API replay of incidents captured by verify_live.py --faults.

No new faults; at most three investigations. Semantic accuracy is reviewed by
the operator, not inferred from the agent's completed status.
"""
import json
import time
from datetime import datetime, timezone

from rcactl import ROOT
from verify_live import cli


def main():
    fixture = json.loads((ROOT / 'artifacts/live-verification.json').read_text())
    cases = fixture.get('faults', [])
    assert fixture.get('passed') and 1 <= len(cases) <= 3, 'Need verified live fault incidents'
    report = {'mode': 'real_api_historical_replay', 'started_at': datetime.now(timezone.utc).isoformat(),
              'cases': [], 'passed': False, 'semantic_accuracy': 'requires_manual_review'}
    try:
        report['health'] = cli('health')
        assert report['health']['llm_configured'], 'API key is not mounted'
        assert report['health'].get('llm_enabled'), 'LLM calls are disabled; explicitly enable before paid verification'
        # Start with OOM, then crash, then CPU. The model never receives fault labels.
        for case in sorted(cases, key=lambda c: {'memory': 0, 'crash': 1, 'cpu': 2}[c['mode']]):
            iid = case['incident']['id']
            previous = cli('show', iid)
            previous_run = ((previous.get('result') or {}).get('execution') or {}).get('run_id')
            cli('run', iid)
            print('Started ' + case['mode'] + ': ' + iid, flush=True)
            deadline = time.monotonic() + 330
            next_progress = time.monotonic() + 30
            while time.monotonic() < deadline:
                incident = cli('show', iid)
                execution = (incident.get('result') or {}).get('execution') or {}
                if execution.get('run_id') and execution['run_id'] != previous_run:
                    break
                if time.monotonic() >= next_progress:
                    print(case['mode'] + ': ' + incident['state'], flush=True)
                    next_progress = time.monotonic() + 30
                time.sleep(3)
            else:
                raise AssertionError('Investigation did not finish within 330 seconds: ' + iid)
            report['cases'].append({'mode': case['mode'], 'incident': incident,
                                    'evidence': cli('evidence', iid)})
            print(json.dumps({'mode': case['mode'], 'state': incident['state'], 'execution': execution},
                             ensure_ascii=False), flush=True)
            assert not execution.get('error'), 'API investigation failed; stopping further paid tests'
            assert execution['llm_responses'] > 0 and execution['tool_calls'] > 0
            assert execution['usage_complete'], 'Usage accounting incomplete'
        report['passed'] = True
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        target = ROOT / 'artifacts/llm-verification.json'
        if target.exists():
            previous = json.loads(target.read_text())
            suffix = previous['finished_at'].replace(':', '-').replace('+', '_')
            (ROOT / ('artifacts/llm-verification-' + suffix + '.json')).write_text(
                json.dumps(previous, ensure_ascii=False, indent=2))
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print('Saved artifacts/llm-verification.json', flush=True)


if __name__ == '__main__':
    main()
