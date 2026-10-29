#!/usr/bin/env python3
"""Exploratory bounded-all, one-request comparator; default is plan only.

Not the raw-log dump strawman: six bounded summaries, same frozen telemetry,
same model/system prompt, no labels. Added after primary experiment began.
Run sequentially with other runners sharing the budget file (no file lock).
"""
import argparse
import hashlib
import json
import random
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_frozen import BudgetProvider, CallBudget, evaluation_key
from rca.agent import SYSTEM, SYSTEM_V4, V4_MODES, FINAL_TOOL, validate_result
from rca.common import Settings, compact, now
from rca.context import ledger_messages, present_evidence
from rca.replay import FrozenTelemetry

QUERIES = [('get_workload_status', {}), ('get_k8s_events', {}), ('get_logs', {}),
           ('get_metrics', {'metric': 'memory', 'window_seconds': 300}),
           ('get_metrics', {'metric': 'cpu', 'window_seconds': 300}),
           ('get_ebpf_summary', {'window_seconds': 300})]


def prepare(case, mode):
    incident = case['incident']['data']
    telemetry = FrozenTelemetry(incident, case['evidence'])
    evidence = [present_evidence(telemetry.call('fixed', name, args), incident, mode)
                for name, args in QUERIES]
    for i, item in enumerate(evidence):
        if len(compact(item)) > 9000:
            evidence[i] = {k: item[k] for k in ('evidence_id', 'tool', 'availability')}
            evidence[i].update(availability='unavailable', error='tool response exceeded context allowance', truncated=True)
    return evidence, ledger_messages(SYSTEM_V4 if mode in V4_MODES else SYSTEM, incident, evidence, [], 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--budget-file', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    keys = parser.add_mutually_exclusive_group()
    keys.add_argument('--cluster-key', action='store_true')
    keys.add_argument('--key-file', type=Path)
    args = parser.parse_args()
    raw = args.fixture.read_bytes()
    fixture = json.loads(raw)
    rng = random.Random(7)
    schedule = []
    for index, case in enumerate(fixture['cases']):
        modes = ['full', 'compact']
        rng.shuffle(modes)
        for mode in modes:
            prepare(case, mode)
            schedule.append({'case': index, 'mode': mode})
    report = {'kind': 'exploratory_fixed_bounded_all_one_request', 'complete': False,
              'started_at': now(), 'fixture_sha256': hashlib.sha256(raw).hexdigest(),
              'code_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted((ROOT / 'rca').glob('*.py')) + [Path(__file__).resolve(), ROOT / 'scripts/evaluate_frozen.py']},
              'schedule': schedule, 'queries': QUERIES, 'runs': [],
              'limits': ['Added after primary evaluation began; exploratory, not preregistered.',
                         'Six bounded summaries, not all raw telemetry.',
                         'Same SYSTEM but no retrieval tools and only one model request.',
                         'No automatic correctness score; human review required.']}
    print(json.dumps({k: v for k, v in report.items() if k != 'code_sha256'}, indent=2), flush=True)
    if not args.execute:
        print('PLAN ONLY: no credential reads or API calls.')
        return
    if not args.cluster_key and (not args.key_file or not args.key_file.is_file()):
        parser.error('execution requires a key source')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    settings = Settings()
    settings.llm_enabled = True
    settings.provider = 'openrouter'
    settings.api_url = 'https://openrouter.ai/api/v1/chat/completions'
    settings.routing = {'only': ['z-ai/fp8'], 'allow_fallbacks': False,
                        'max_price': {'prompt': settings.input_price, 'completion': settings.output_price}}
    budget = CallBudget(100, 1.0, args.budget_file)
    provider = BudgetProvider(settings, budget)
    try:
        with evaluation_key(args) as key:
            settings.api_key_file = key
            for item in schedule:
                case = fixture['cases'][item['case']]
                evidence, messages = prepare(case, item['mode'])
                payload = provider.payload(messages, [FINAL_TOOL])
                if len(compact(payload)) > settings.max_context_chars:
                    raise ValueError('fixed-all request exceeds same character allowance')
                run_id = str(uuid.uuid4())
                (args.output_dir / (run_id + '-requests.json')).write_text(json.dumps([payload], ensure_ascii=False, indent=2))
                started = time.monotonic()
                answer = provider.complete(messages, [FINAL_TOOL], 60)
                choice = answer['choices'][0]
                if choice.get('finish_reason') == 'length':
                    raise ValueError('fixed-all output limit reached')
                message = choice['message']
                calls = message.get('tool_calls', [])
                if len(calls) != 1 or calls[0]['function']['name'] != 'submit_rca':
                    raise ValueError('fixed-all did not submit exactly one RCA')
                result = validate_result(json.loads(calls[0]['function']['arguments']), evidence)
                usage = answer.get('usage', {})
                result['execution'] = {'run_id': run_id, 'model': answer.get('model'),
                    'prompt_version': 'rca-v3', 'context_mode': item['mode'], 'allow_ebpf': True,
                    'duration_seconds': round(time.monotonic() - started, 3),
                    'llm_responses': 1, 'tool_calls': 6, 'tool_calls_meaning': 'prefetched, not model selected',
                    'input_tokens': usage.get('prompt_tokens'), 'output_tokens': usage.get('completion_tokens'),
                    'cached_input_tokens': usage.get('prompt_tokens_details', {}).get('cached_tokens', 0),
                    'provider_reported_cost_usd': usage.get('cost'), 'usage_complete': True,
                    'trace': [{'usage': usage, 'routed_provider': answer.get('provider'), 'request_id': answer.get('id'),
                               'request_bytes': len(compact(payload).encode())}], 'error': None}
                run = {'case': item['case'], 'arm': 'fixed-' + item['mode'], 'repeat': 0,
                       'label_for_evaluation_only': case['mode'],
                       'incident': {'state': result['status'], 'data': case['incident']['data'], 'result': result}}
                report['runs'].append(run)
                (args.output_dir / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
                print(json.dumps({'case': item['case'], 'arm': run['arm'], 'api_attempts': budget.attempts}), flush=True)
            report['complete'] = True
    except Exception as error:
        # Do not persist provider bodies/credentials or retry failed requests.
        report['error_type'] = type(error).__name__
        raise
    finally:
        report.update(finished_at=now(), api_attempts=budget.attempts,
                      conservative_accounted_usd=budget.accounted_usd)
        (args.output_dir / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
