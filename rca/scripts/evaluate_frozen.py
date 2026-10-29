#!/usr/bin/env python3
"""Plan a paired real-model evaluation; paid calls require --execute --key-file.

Never starts the cluster agent, injects faults, or queries live telemetry.
Default arms isolate encoding using the SAME v3 prompt/model/budgets.
"""
import argparse
import base64
import contextlib
import hashlib
import json
import random
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rca.agent import Agent, Provider
from rca.common import Settings, compact
from rca.replay import FrozenTelemetry
from rca.store import Store


class CallBudget:
    def __init__(self, maximum, maximum_usd=1.0, path=None):
        self.maximum = maximum
        self.attempts = 0
        self.maximum_usd = maximum_usd
        self.accounted_usd = 0.0
        self.path = path
        if path and path.exists():
            state = json.loads(path.read_text())
            if state['maximum'] != maximum or state['maximum_usd'] != maximum_usd:
                raise ValueError('Shared study budget limits cannot be changed implicitly')
            self.attempts = state['attempts']
            self.accounted_usd = state['accounted_usd']

    def save(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({'maximum': self.maximum, 'maximum_usd': self.maximum_usd,
                'attempts': self.attempts, 'accounted_usd': self.accounted_usd}, indent=2))

    def reserve(self, estimated_ceiling=0.0):
        if self.attempts >= self.maximum:
            raise ValueError('global evaluation API-call budget exhausted')
        if self.accounted_usd + estimated_ceiling > self.maximum_usd:
            raise ValueError('evaluation conservative cost budget exhausted')
        self.attempts += 1
        self.accounted_usd += estimated_ceiling
        self.save()

    def settle(self, reserved, usage):
        cost = usage.get('cost')
        if type(cost) in (int, float) and 0 <= cost <= reserved:
            self.accounted_usd -= reserved - cost
        # Missing/invalid cost or lost response retains the entire reservation.
        elif type(cost) in (int, float) and cost > reserved:
            self.accounted_usd += cost - reserved
            self.save()
            raise ValueError('provider charge exceeded conservative reservation; stop evaluation')
        self.save()


class BudgetProvider(Provider):
    def __init__(self, settings, budget):
        super().__init__(settings)
        self.budget = budget

    def complete(self, messages, tools, timeout):
        body = self.payload(messages, tools)
        # Conservative byte-based reservation, NOT a tokenizer measurement.
        # Request-side routing caps provider token prices; unknown costs keep
        # reservations. This is an operational guard, not a provider dollar SLA.
        reserve = ((2 * len(compact(body).encode()) + 8192) * self.settings.input_price +
                   2 * self.settings.max_output * self.settings.output_price) / 1e6
        self.budget.reserve(reserve)
        answer = super().complete(messages, tools, timeout)
        self.budget.settle(reserve, answer.get('usage', {}))
        return answer


@contextlib.contextmanager
def evaluation_key(args):
    if not args.cluster_key:
        yield str(args.key_file.resolve())
        return
    with tempfile.TemporaryDirectory(prefix='rca-eval-key-') as directory:
        value = json.loads(subprocess.run(['kubectl', '--request-timeout=20s', '-n', 'rca-system',
            'get', 'secret', 'rca-llm', '-o', 'json'], check=True, capture_output=True, text=True).stdout)
        key = base64.b64decode(value['data']['api-key']).decode().strip()
        if not key.startswith('sk-or-'):
            raise ValueError('Cluster key is not an OpenRouter key; refusing to send it')
        target = Path(directory) / 'key'
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(key)
        yield str(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=ROOT / 'artifacts/llm-verification.json')
    parser.add_argument('--arms', nargs='+', choices=['legacy', 'full', 'compact', 'compact-no-ebpf',
                        'full-v4', 'compact-v4', 'compact-v4-no-ebpf'], default=['full', 'compact'])
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--max-api-calls', type=int, default=36)
    parser.add_argument('--max-usd', type=float, default=1.0)
    parser.add_argument('--budget-file', type=Path)
    parser.add_argument('--provider', default='z-ai/fp8')
    parser.add_argument('--execute', action='store_true')
    keys = parser.add_mutually_exclusive_group()
    keys.add_argument('--key-file', type=Path)
    keys.add_argument('--cluster-key', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10 or not 1 <= args.max_api_calls <= 100 or len(set(args.arms)) != len(args.arms):
        parser.error('repeats 1..10, API calls 1..100, unique arms required')
    if not 0 < args.max_usd <= 1:
        parser.error('max-usd must be greater than 0 and at most 1 for this evaluation runner')
    raw = args.fixture.read_bytes()
    fixture = json.loads(raw)
    cases = fixture['cases']
    # Validate all fixtures before reading credentials or calling any provider.
    for case in cases:
        FrozenTelemetry(case['incident']['data'], case['evidence'])
    rng = random.Random(args.seed)
    schedule = []
    for repeat in range(args.repeats):
        for index in range(len(cases)):
            arms = list(args.arms)
            rng.shuffle(arms)
            schedule.extend({'repeat': repeat, 'case': index, 'arm': arm} for arm in arms)
    settings = Settings()
    # This runner only supports the explicitly approved OpenRouter destination.
    settings.provider = 'openrouter'
    settings.api_url = 'https://openrouter.ai/api/v1/chat/completions'
    settings.routing = {'only': [args.provider], 'allow_fallbacks': False,
                        'max_price': {'prompt': settings.input_price, 'completion': settings.output_price}}
    plan = {'fixture_sha256': hashlib.sha256(raw).hexdigest(), 'model': settings.model,
            'code_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted((ROOT / 'rca').glob('*.py')) + [Path(__file__).resolve()]},
            'seed': args.seed, 'schedule': schedule, 'max_api_calls': args.max_api_calls,
            'provider_routing': settings.routing, 'max_usd_conservative_guard': args.max_usd,
            'max_requests_per_investigation': settings.max_requests,
            'max_output_tokens_per_request': settings.max_output,
            'max_input_chars_total_per_investigation': settings.max_input_chars_total,
            'paid_execution_requested': args.execute,
            'limits': ['API-call cap is enforced before requests; it is NOT a dollar cap.',
                       'Stops on first execution error. No retry or live telemetry fallback.',
                       'One repeat is a smoke test, not statistical proof.',
                       'All labels are evaluation-only; they are never included in model input.']}
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        print('PLAN ONLY: no credentials read, no API calls, no cluster changes.')
        return
    if not args.cluster_key and (not args.key_file or not args.key_file.is_file()):
        parser.error('--execute requires --cluster-key or an existing --key-file')
    output = args.output_dir or ROOT / 'artifacts' / ('paired-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    output.mkdir(parents=True, exist_ok=False)
    settings.llm_enabled = True
    settings.max_daily = len(schedule)
    budget = CallBudget(args.max_api_calls, args.max_usd, args.budget_file)
    report = {'plan': plan, 'started_at': datetime.now(timezone.utc).isoformat(), 'runs': [],
              'semantic_accuracy': 'requires_blinded_manual_review', 'complete': False}
    # Persistent artifacts never contain credentials or model private reasoning.
    # Keep an independent DB: evaluation cannot modify production incidents.
    try:
        with evaluation_key(args) as key_path, tempfile.TemporaryDirectory(prefix='rca-paired-') as directory:
            settings.api_key_file = key_path
            store = Store(str(Path(directory) / 'eval.sqlite3'))
            try:
                for item in schedule:
                    case = cases[item['case']]
                    settings.context_mode = item['arm'].removesuffix('-no-ebpf')
                    settings.allow_ebpf = not item['arm'].endswith('-no-ebpf')
                    iid, _ = store.add(case['incident']['data'], json.dumps(item, sort_keys=True))
                    started = time.monotonic()
                    result = Agent(store, FrozenTelemetry(case['incident']['data'], case['evidence']), settings,
                                   BudgetProvider(settings, budget)).run(iid)
                    execution = (result.get('result') or {}).get('execution', {})
                    report['runs'].append({**item, 'label_for_evaluation_only': case['mode'],
                                           'incident': result, 'wall_seconds': round(time.monotonic() - started, 3)})
                    report['api_attempts'] = budget.attempts
                    if execution.get('run_id'):
                        request_file = output / (execution['run_id'] + '-requests.json')
                        request_file.write_text(json.dumps(store.meta('requests:' + execution['run_id']), ensure_ascii=False, indent=2))
                    (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
                    print(json.dumps({'case': item['case'], 'arm': item['arm'], 'state': result['state'],
                                      'api_attempts': budget.attempts, 'error': execution.get('error')}, ensure_ascii=False), flush=True)
                    if not execution or execution.get('error'):
                        raise RuntimeError('Evaluation stopped on first unsuccessful execution; inspect saved result.')
                report['complete'] = True
            finally:
                store.db.close()
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        report['api_attempts'] = budget.attempts
        report['conservative_accounted_usd'] = budget.accounted_usd
        (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print('Saved ' + str(output / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
