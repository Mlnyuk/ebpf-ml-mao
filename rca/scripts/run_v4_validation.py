#!/usr/bin/env python3
"""Randomized four-arm frozen evaluation. Paid calls require --execute.

No cluster writes; only --cluster-key reads a Secret. One shared serial budget.
"""
import argparse
import hashlib
import json
import random
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_frozen import BudgetProvider, CallBudget, evaluation_key
from scripts.evaluate_fixed import prepare
from rca.agent import Agent, FINAL_TOOL_V4, validate_result
from rca.common import Settings, compact, now
from rca.replay import FrozenTelemetry
from rca.store import Store

ARMS = ['compact', 'compact-v4', 'compact-v4-no-ebpf', 'fixed-compact-v4']


def fixed_run(case, settings, provider, output):
    evidence, messages = prepare(case, 'compact-v4')
    payload = provider.payload(messages, [FINAL_TOOL_V4])
    run_id = str(uuid.uuid4())
    started = time.monotonic()
    usage, trace, error = {}, [], None
    (output / (run_id + '-requests.json')).write_text(json.dumps([payload], ensure_ascii=False, indent=2))
    try:
        if len(compact(payload)) > min(settings.max_context_chars, settings.max_input_chars_total):
            raise ValueError('fixed request exceeds character allowance')
        answer = provider.complete(messages, [FINAL_TOOL_V4], 60)
        usage = answer.get('usage', {})
        trace = [{'usage': usage, 'routed_provider': answer.get('provider'),
                  'request_id': answer.get('id'), 'request_bytes': len(compact(payload).encode())}]
        choice = answer['choices'][0]
        calls = choice['message'].get('tool_calls', [])
        if choice.get('finish_reason') == 'length' or len(calls) != 1 or calls[0]['function']['name'] != 'submit_rca':
            raise ValueError('fixed arm failed to submit one complete RCA')
        result = validate_result(json.loads(calls[0]['function']['arguments']), evidence, v4=True)
    except Exception as exc:
        error = str(exc)[:200] if isinstance(exc, ValueError) else type(exc).__name__
        result = {'status': 'inconclusive', 'failure_mechanism': '', 'root_cause': None,
                  'root_cause_status': 'undetermined', 'confidence': 'low', 'evidence': [],
                  'missing_evidence': [error], 'recommended_action': 'Inspect the recorded execution error.'}
    known = all(k in usage for k in ('prompt_tokens', 'completion_tokens'))
    result['execution'] = {'run_id': run_id, 'model': settings.model, 'prompt_version': 'rca-v4',
        'context_mode': 'compact-v4', 'allow_ebpf': True, 'llm_responses': len(trace),
        'tool_calls': 6, 'tool_calls_meaning': 'prefetched, not model selected',
        'input_tokens': usage.get('prompt_tokens', 0), 'output_tokens': usage.get('completion_tokens', 0),
        'cached_input_tokens': usage.get('prompt_tokens_details', {}).get('cached_tokens', 0),
        'provider_reported_cost_usd': usage.get('cost'), 'usage_complete': known and not error,
        'duration_seconds': round(time.monotonic() - started, 3), 'trace': trace, 'error': error}
    return {'state': 'error' if error else result['status'], 'data': case['incident']['data'], 'result': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--budget-file', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    keys = parser.add_mutually_exclusive_group()
    keys.add_argument('--cluster-key', action='store_true')
    keys.add_argument('--key-file', type=Path)
    args = parser.parse_args()
    frozen = json.loads(args.freeze.read_text())
    for name, digest in frozen['code_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen source changed: ' + name)
    raw = args.fixture.read_bytes()
    fixture = json.loads(raw)
    if not fixture.get('complete') or len(fixture['cases']) != 8:
        raise ValueError('Protocol requires eight completed fresh incidents')
    for case in fixture['cases']:
        FrozenTelemetry(case['incident']['data'], case['evidence'])
    rng = random.Random(2816)
    schedule = []
    for index in range(len(fixture['cases'])):
        arms = list(ARMS)
        rng.shuffle(arms)
        schedule.extend({'case': index, 'arm': arm, 'repeat': 0} for arm in arms)
    plan = {'fixture_sha256': hashlib.sha256(raw).hexdigest(), 'code_freeze': frozen,
            'schedule': schedule, 'seed': 2816, 'max_api_attempts': 100, 'conservative_guard_usd': 1.0}
    print(json.dumps(plan, indent=2), flush=True)
    if not args.execute:
        print('PLAN ONLY; no keys, model calls or cluster writes.')
        return
    if not args.cluster_key and (not args.key_file or not args.key_file.is_file()):
        parser.error('execution requires a key source')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    settings = Settings()
    settings.llm_enabled = True
    settings.max_daily = len(schedule)
    settings.provider, settings.api_url = 'openrouter', 'https://openrouter.ai/api/v1/chat/completions'
    settings.routing = {'only': ['z-ai/fp8'], 'allow_fallbacks': False,
                        'max_price': {'prompt': settings.input_price, 'completion': settings.output_price}}
    budget = CallBudget(100, 1.0, args.budget_file)
    report = {'plan': plan, 'complete': False, 'started_at': now(), 'runs': []}
    try:
        with evaluation_key(args) as key, tempfile.TemporaryDirectory(prefix='rca-v4-validate-') as directory:
            settings.api_key_file = key
            store = Store(str(Path(directory) / 'eval.sqlite3'))
            try:
                for item in schedule:
                    case = fixture['cases'][item['case']]
                    settings.allow_ebpf = not item['arm'].endswith('-no-ebpf')
                    settings.context_mode = item['arm'].removeprefix('fixed-').removesuffix('-no-ebpf')
                    provider = BudgetProvider(settings, budget)
                    if item['arm'].startswith('fixed-'):
                        incident = fixed_run(case, settings, provider, args.output_dir)
                    else:
                        iid, _ = store.add(case['incident']['data'], json.dumps(item, sort_keys=True))
                        incident = Agent(store, FrozenTelemetry(case['incident']['data'], case['evidence']), settings, provider).run(iid)
                        execution = incident['result']['execution']
                        (args.output_dir / (execution['run_id'] + '-requests.json')).write_text(
                            json.dumps(store.meta('requests:' + execution['run_id']), ensure_ascii=False, indent=2))
                    report['runs'].append({**item, 'label_for_evaluation_only': case['mode'],
                                          'logging': case['logging'], 'incident': incident})
                    execution = incident['result']['execution']
                    report.update(api_attempts=budget.attempts, conservative_accounted_usd=budget.accounted_usd)
                    (args.output_dir / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
                    print(json.dumps({**item, 'state': incident['state'], 'api_attempts': budget.attempts,
                                      'cost_usd': budget.accounted_usd, 'error': execution['error']}), flush=True)
                    if execution['error']:
                        raise RuntimeError('Stop on execution error; partial report preserved.')
                report['complete'] = True
            finally:
                store.db.close()
    finally:
        report.update(finished_at=now(), api_attempts=budget.attempts, conservative_accounted_usd=budget.accounted_usd)
        (args.output_dir / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
