#!/usr/bin/env python3
"""Continue the frozen 32-run pilot without repeating its first four runs.

Only the stop policy changes. Default is offline preflight; --execute reads a
key and makes bounded paid calls. Original artifacts and frozen code are kept.
"""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_v4_validation import fixed_run
from scripts.evaluate_frozen import BudgetProvider, CallBudget, evaluation_key
from rca.agent import Agent
from rca.common import Settings, now, redact
from rca.replay import FrozenTelemetry
from rca.store import Store

VALIDATION_ERRORS = {
    'invalid RCA output fields', 'invalid RCA status/confidence', 'invalid RCA text',
    'invalid root cause', 'invalid missing evidence', 'invalid citations',
    'unknown or invalid evidence citation', 'invalid citation claim_type',
    'invalid root_cause_status',
    'undetermined cause requires null root_cause and non-high confidence',
    'root cause requires text and available cited evidence',
    'completed RCA requires available cited evidence',
    'fixed arm failed to submit one complete RCA',
}


def failure_kind(execution, answers, provider_failed=False):
    error = execution.get('error')
    if provider_failed:
        return 'transport_or_provider_budget'
    if not error:
        return None
    # Output exhaustion is also a budget stop. Never infer a transport failure
    # is merely a schema error from its text. Unknown failures stop safely.
    if 'budget' in error or 'limit reached' in error or 'allowance' in error:
        return 'budget'
    if answers and all(c.get('finish_reason') != 'length'
                       for a in answers for c in a.get('choices', [])):
        if error in VALIDATION_ERRORS:
            return 'model_output_validation'
        if any(error.startswith(prefix) for prefix in (
                'Expecting value:', 'Expecting property name enclosed in double quotes:',
                "Expecting ',' delimiter:", "Expecting ':' delimiter:",
                'Unterminated string starting at:', 'Extra data:', 'Invalid control character at:')):
            return 'model_output_validation'
    return 'unknown_execution_error'


class AuditProvider(BudgetProvider):
    """Observe public replies without changing requests or retaining reasoning."""
    def __init__(self, settings, budget):
        super().__init__(settings, budget)
        self.answers = []
        self.failed = False

    def complete(self, messages, tools, timeout):
        try:
            answer = super().complete(messages, tools, timeout)
        except Exception:
            self.failed = True
            raise
        public = {k: answer[k] for k in ('id', 'model', 'provider', 'usage') if k in answer}
        public['choices'] = [
            {'finish_reason': choice.get('finish_reason'), 'message': {
                k: v for k, v in choice.get('message', {}).items()
                if k in ('role', 'content', 'tool_calls')}} for choice in answer.get('choices', [])]
        self.answers.append(redact(public))
        return answer


def validate_prefix(previous, fixture_raw, freeze, budget):
    plan = previous['plan']
    if plan['code_freeze'] != freeze or hashlib.sha256(fixture_raw).hexdigest() != plan['fixture_sha256']:
        raise ValueError('Original frozen code or dataset identity differs')
    runs, schedule = previous['runs'], plan['schedule']
    if previous['complete'] or len(runs) != 4 or len(schedule) != 32:
        raise ValueError('Continuation is only authorized for the original four-run prefix')
    if len({(r['case'], r['arm'], r['repeat']) for r in schedule}) != 32:
        raise ValueError('Duplicate scheduled investigation')
    for run, scheduled in zip(runs, schedule):
        if {k: run[k] for k in ('case', 'arm', 'repeat')} != scheduled:
            raise ValueError('Previous results are not the exact scheduled prefix')
    if budget['maximum'] != 100 or budget['maximum_usd'] != 1.0:
        raise ValueError('Shared limits must remain unchanged')
    if (budget['attempts'] != previous['api_attempts'] or
            budget['accounted_usd'] != previous['conservative_accounted_usd']):
        raise ValueError('Shared budget differs from original checkpoint; refuse restart/reset')
    fixture = json.loads(fixture_raw)
    if not fixture.get('complete') or len(fixture['cases']) != 8:
        raise ValueError('Incomplete fixture')
    for case in fixture['cases']:
        FrozenTelemetry(case['incident']['data'], case['evidence'])
    return schedule[len(runs):]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    keys = parser.add_mutually_exclusive_group()
    keys.add_argument('--cluster-key', action='store_true')
    keys.add_argument('--key-file', type=Path)
    args = parser.parse_args()
    study = args.study.resolve()
    previous_path = study / 'evaluation/results.json'
    previous = json.loads(previous_path.read_text())
    freeze = json.loads((study / 'freeze.json').read_text())
    for name, digest in freeze['code_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen source changed: ' + name)
    raw = (study / 'network-fixture.json').read_bytes()
    budget_path = study / 'budget.json'
    initial_budget = json.loads(budget_path.read_text())
    schedule = validate_prefix(previous, raw, freeze, initial_budget)
    fixture = json.loads(raw)
    amendment = {
        'original_results_sha256': hashlib.sha256(previous_path.read_bytes()).hexdigest(),
        'fixture_sha256': hashlib.sha256(raw).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'prior_runs_preserved': 4, 'remaining_runs': len(schedule), 'schedule': schedule,
        'initial_shared_budget': initial_budget,
        'change': 'Continue after recognized model-output validation failures only; retain them as failures.',
        'stop': 'Transport/provider, any budget, unknown execution errors. No reruns or extra retry policy.',
        'unchanged': 'Dataset, original schedule, RCA code, prompt, schemas, model, provider, and all budgets.',
        'instrumentation': 'Public response audit excludes private reasoning; does not alter payloads.',
        'authorization': 'User authorized remaining 28 investigations after disclosure of first fixed-arm failure.',
    }
    print(json.dumps(amendment, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        print('PLAN ONLY: no credentials, model calls, or cluster changes.')
        return
    if not args.cluster_key and (not args.key_file or not args.key_file.is_file()):
        parser.error('execution requires a key source')
    output = study / 'continuation-evaluation'
    output.mkdir(exist_ok=False)
    save(output / 'amendment.json', amendment)
    settings = Settings()
    settings.llm_enabled = True
    settings.max_daily = 32
    settings.provider, settings.api_url = 'openrouter', 'https://openrouter.ai/api/v1/chat/completions'
    settings.routing = {'only': ['z-ai/fp8'], 'allow_fallbacks': False,
                        'max_price': {'prompt': settings.input_price, 'completion': settings.output_price}}
    budget = CallBudget(100, 1.0, budget_path)
    report = {'plan': previous['plan'], 'amendment': amendment, 'complete': False,
              'started_at': now(), 'runs': [], 'stop_reason': None}
    try:
        with evaluation_key(args) as key, tempfile.TemporaryDirectory(prefix='rca-v4-continue-') as directory:
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
                    report.update(api_attempts=budget.attempts, conservative_accounted_usd=budget.accounted_usd)
                    save(output / 'results.json', report)
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
        report.update(finished_at=now(), api_attempts=budget.attempts, conservative_accounted_usd=budget.accounted_usd)
        save(output / 'results.json', report)
        combined = {**report, 'original_started_at': previous['started_at'],
                    'runs': previous['runs'] + report['runs'],
                    'request_directories': ['evaluation', 'continuation-evaluation']}
        save(output / 'combined-results.json', combined)


if __name__ == '__main__':
    main()
