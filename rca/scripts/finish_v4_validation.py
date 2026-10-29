#!/usr/bin/env python3
"""User-authorized remaining seven investigations; preserve all 25 prior runs."""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.continue_v4_validation import AuditProvider, failure_kind, save
from scripts.run_v4_validation import fixed_run
from scripts.evaluate_frozen import CallBudget, evaluation_key
from rca.agent import Agent
from rca.common import Settings, now
from rca.replay import FrozenTelemetry
from rca.store import Store


def preflight(study):
    prior_path = study / 'continuation-evaluation/combined-results.json'
    previous = json.loads(prior_path.read_text())
    original = json.loads((study / 'evaluation/results.json').read_text())
    first_continuation = json.loads((study / 'continuation-evaluation/results.json').read_text())
    if previous['runs'] != original['runs'] + first_continuation['runs']:
        raise ValueError('Combined history differs from original records')
    if previous['complete'] or len(previous['runs']) != 25 or previous['stop_reason'] != 'budget':
        raise ValueError('Only the disclosed 25-run checkpoint is authorized')
    if previous['runs'][-1]['incident']['result']['execution']['error'] != 'model did not submit a valid RCA within budget':
        raise ValueError('Unexpected stopping error')
    frozen = json.loads((study / 'freeze.json').read_text())
    if previous['plan']['code_freeze'] != frozen:
        raise ValueError('Code freeze identity changed')
    for name, digest in frozen['code_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen source changed: ' + name)
    amendment = previous['amendment']
    if hashlib.sha256((ROOT / 'scripts/continue_v4_validation.py').read_bytes()).hexdigest() != amendment['runner_sha256']:
        raise ValueError('Previous continuation runner changed')
    if hashlib.sha256((study / 'evaluation/results.json').read_bytes()).hexdigest() != amendment['original_results_sha256']:
        raise ValueError('Original four-run report changed')
    raw = (study / 'network-fixture.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != previous['plan']['fixture_sha256']:
        raise ValueError('Fixture changed')
    schedule = previous['plan']['schedule']
    prefix = [{k: r[k] for k in ('case', 'arm', 'repeat')} for r in previous['runs']]
    if len(schedule) != 32 or prefix != schedule[:25] or len({(r['case'], r['arm'], r['repeat']) for r in schedule}) != 32:
        raise ValueError('Invalid original schedule/prefix')
    budget = json.loads((study / 'budget.json').read_text())
    if budget != {'maximum': 100, 'maximum_usd': 1.0, 'attempts': previous['api_attempts'],
                  'accounted_usd': previous['conservative_accounted_usd']}:
        raise ValueError('Budget changed since checkpoint; refuse reset/restart')
    fixture = json.loads(raw)
    if not fixture.get('complete') or len(fixture['cases']) != 8:
        raise ValueError('Incomplete dataset')
    for case in fixture['cases']:
        FrozenTelemetry(case['incident']['data'], case['evidence'])
    return previous, fixture, budget, schedule[25:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    keys = parser.add_mutually_exclusive_group()
    keys.add_argument('--cluster-key', action='store_true')
    keys.add_argument('--key-file', type=Path)
    args = parser.parse_args()
    study = args.study.resolve()
    previous, fixture, initial_budget, schedule = preflight(study)
    amendment = {
        'authorization': 'User authorized remaining seven after disclosure of per-incident six-call failure; no failed run is repeated.',
        'prior_results_sha256': hashlib.sha256((study / 'continuation-evaluation/combined-results.json').read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'prior_runs_preserved': 25, 'remaining_runs': 7, 'schedule': schedule,
        'initial_shared_budget': initial_budget,
        'policy': 'Same frozen RCA/model/provider/data/budgets. Validation failures count and continue; transport, budget, unknown errors stop.',
    }
    print(json.dumps(amendment, indent=2), flush=True)
    if not args.execute:
        print('PLAN ONLY: no credentials, model calls or cluster changes.')
        return
    if not args.cluster_key and (not args.key_file or not args.key_file.is_file()):
        parser.error('execution requires a key source')
    output = study / 'final-evaluation'
    output.mkdir(exist_ok=False)
    save(output / 'amendment.json', amendment)
    settings = Settings()
    settings.llm_enabled, settings.max_daily = True, 32
    settings.provider, settings.api_url = 'openrouter', 'https://openrouter.ai/api/v1/chat/completions'
    settings.routing = {'only': ['z-ai/fp8'], 'allow_fallbacks': False,
                        'max_price': {'prompt': settings.input_price, 'completion': settings.output_price}}
    budget = CallBudget(100, 1.0, study / 'budget.json')
    report = {'plan': previous['plan'], 'amendment': amendment, 'complete': False,
              'started_at': now(), 'runs': [], 'stop_reason': None}
    def checkpoint():
        report.update(api_attempts=budget.attempts, conservative_accounted_usd=budget.accounted_usd)
        save(output / 'results.json', report)
        save(output / 'combined-results.json', {
            **report, 'original_started_at': previous['original_started_at'],
            'runs': previous['runs'] + report['runs'],
            'request_directories': ['evaluation', 'continuation-evaluation', 'final-evaluation']})
    try:
        with evaluation_key(args) as key, tempfile.TemporaryDirectory(prefix='rca-v4-finish-') as directory:
            settings.api_key_file = key
            store = Store(str(Path(directory) / 'eval.sqlite3'))
            try:
                for item in schedule:
                    case = fixture['cases'][item['case']]
                    settings.allow_ebpf = not item['arm'].endswith('-no-ebpf')
                    settings.context_mode = item['arm'].removeprefix('fixed-').removesuffix('-no-ebpf')
                    provider = AuditProvider(settings, budget)
                    if item['arm'].startswith('fixed-'):
                        incident = fixed_run(case, settings, provider, output)
                    else:
                        iid, _ = store.add(case['incident']['data'], json.dumps(item, sort_keys=True))
                        incident = Agent(store, FrozenTelemetry(case['incident']['data'], case['evidence']), settings, provider).run(iid)
                        execution = incident['result']['execution']
                        save(output / (execution['run_id'] + '-requests.json'), store.meta('requests:' + execution['run_id']))
                    execution = incident['result']['execution']
                    save(output / (execution['run_id'] + '-responses.json'), provider.answers)
                    kind = failure_kind(execution, provider.answers, provider.failed)
                    report['runs'].append({**item, 'label_for_evaluation_only': case['mode'],
                                          'logging': case['logging'], 'incident': incident, 'failure_kind': kind})
                    checkpoint()
                    print(json.dumps({**item, 'state': incident['state'], 'api_attempts': budget.attempts,
                                      'cost_usd': budget.accounted_usd, 'error': execution['error'], 'failure_kind': kind}), flush=True)
                    if kind not in (None, 'model_output_validation'):
                        report['stop_reason'] = kind
                        break
                else:
                    report['complete'] = True
            finally:
                store.db.close()
    finally:
        report['finished_at'] = now()
        checkpoint()


if __name__ == '__main__':
    main()
