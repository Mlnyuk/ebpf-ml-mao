#!/usr/bin/env python3
"""Offline provenance and budget audit of the continuation; no model calls."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--phase', choices=['continuation-evaluation', 'final-evaluation'], default='continuation-evaluation')
    args = parser.parse_args()
    study = args.study
    continuation = study / args.phase
    original_path = study / 'evaluation/results.json'
    original = json.loads(original_path.read_text())
    report = json.loads((continuation / 'combined-results.json').read_text())
    amendment = report['amendment']
    assert report['runs'][:4] == original['runs']
    if args.phase == 'final-evaluation':
        prior_path = study / 'continuation-evaluation/combined-results.json'
        prior = json.loads(prior_path.read_text())
        assert hashlib.sha256(prior_path.read_bytes()).hexdigest() == amendment['prior_results_sha256']
        assert report['runs'][:25] == prior['runs']
        first_amendment = prior['amendment']
        runner = 'scripts/finish_v4_validation.py'
        prior_count = 25
    else:
        first_amendment = amendment
        runner = 'scripts/continue_v4_validation.py'
        prior_count = 4
    assert hashlib.sha256(original_path.read_bytes()).hexdigest() == first_amendment['original_results_sha256']
    assert hashlib.sha256((ROOT / 'scripts/continue_v4_validation.py').read_bytes()).hexdigest() == first_amendment['runner_sha256']
    assert hashlib.sha256((study / 'network-fixture.json').read_bytes()).hexdigest() == report['plan']['fixture_sha256']
    assert hashlib.sha256((ROOT / runner).read_bytes()).hexdigest() == amendment['runner_sha256']
    freeze = json.loads((study / 'freeze.json').read_text())
    for name, digest in freeze['code_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    runs = report['runs']
    executed = [{k: r[k] for k in ('case', 'arm', 'repeat')} for r in runs]
    assert executed == report['plan']['schedule'][:len(runs)]
    assert len({(r['case'], r['arm'], r['repeat']) for r in runs}) == len(runs)
    request_count = 0
    errors = []
    for run in runs:
        execution = run['incident']['result']['execution']
        paths = [study / directory / (execution['run_id'] + '-requests.json')
                 for directory in report['request_directories']]
        paths = [p for p in paths if p.exists()]
        assert len(paths) == 1
        requests = json.loads(paths[0].read_text())
        request_count += len(requests)
        for payload in requests:
            assert payload['model'] == 'z-ai/glm-5.3-flash'
            assert payload['provider']['only'] == ['z-ai/fp8']
            assert payload['provider']['allow_fallbacks'] is False
            text = json.dumps(payload, ensure_ascii=False)
            assert 'ground_truth_for_evaluation_only' not in text
            assert 'label_for_evaluation_only' not in text
            if run['arm'].endswith('-no-ebpf'):
                assert all(t['function']['name'] != 'get_ebpf_summary' for t in payload['tools'])
        if execution['error']:
            errors.append({'case': run['case'], 'arm': run['arm'], 'error': execution['error']})
    budget = json.loads((study / 'budget.json').read_text())
    assert budget['maximum'] == 100 and budget['maximum_usd'] == 1.0
    assert budget['attempts'] == report['api_attempts']
    assert budget['attempts'] <= 100 and budget['accounted_usd'] <= 1
    assert request_count == budget['attempts']
    if report['complete']:
        assert len(runs) == 32
    result = {'complete': report['complete'], 'runs': len(runs), 'new_runs': len(runs) - prior_count,
              'prior_runs_preserved': prior_count,
              'original_four_runs_unchanged': True, 'original_code_hashes_match': True,
              'fixture_hash_matches': True, 'schedule_prefix_matches': True, 'no_duplicate_runs': True,
              'request_artifacts': request_count, 'shared_budget': budget, 'execution_errors': errors,
              'note': 'Provenance checks do not establish semantic correctness or ON/OFF overhead.'}
    (continuation / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
