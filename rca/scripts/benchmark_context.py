#!/usr/bin/env python3
"""Offline paired payload benchmark. NO model, network, key, or cluster access.

Uses the same six queries in the same order for every case and every arm.
The fixed query plan is a measurement fixture, NOT an agent/RCA rule.
Reports UTF-8 bytes and characters, never invented token counts or accuracy.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rca.agent import Provider, SYSTEM_V2, build_messages, request_tools
from rca.common import Settings, compact
from rca.context import present_evidence, restore_evidence
from rca.replay import FrozenTelemetry
from rca.telemetry import TOOLS


PLAN = [
    [('get_workload_status', {}), ('get_k8s_events', {})],
    [('get_logs', {}), ('get_metrics', {'metric': 'memory', 'window_seconds': 300})],
    [('get_metrics', {'metric': 'cpu', 'window_seconds': 300}), ('get_ebpf_summary', {'window_seconds': 300})],
    [],
]


def measure(case, mode):
    incident = case['incident']['data']
    frozen = FrozenTelemetry(incident, case['evidence'])
    transcript = [{'role': 'system', 'content': SYSTEM_V2}, {'role': 'user', 'content': compact(incident)}]
    evidence, payloads, source_sizes, view_sizes = [], [], [], []
    settings = Settings()
    for index, batch in enumerate(PLAN):
        messages = build_messages(mode, incident, transcript, evidence, [], 8 - len(evidence))
        payload = Provider(settings).payload(messages, request_tools(mode, TOOLS, evidence))
        payloads.append({'step': index + 1, 'chars': len(compact(payload)), 'bytes': len(compact(payload).encode())})
        if not batch:
            break
        transcript.append({'role': 'assistant', 'content': '', 'tool_calls': [
            {'id': f'fixture-{index}-{n}', 'type': 'function',
             'function': {'name': name, 'arguments': compact(args)}} for n, (name, args) in enumerate(batch)]})
        for n, (name, args) in enumerate(batch):
            source = frozen.call('offline', name, args)
            view = present_evidence(source, incident, 'full' if mode == 'legacy' else mode)
            if restore_evidence(view, incident) != source:
                raise AssertionError('Lossless roundtrip failed: ' + name)
            source_sizes.append(len(compact(source).encode()))
            view_sizes.append(len(compact(view).encode()))
            evidence.append(view)
            transcript.append({'role': 'tool', 'tool_call_id': f'fixture-{index}-{n}', 'content': compact(view)})
    return {'mode': mode, 'requests': payloads, 'request_bytes_total': sum(p['bytes'] for p in payloads),
            'request_chars_total': sum(p['chars'] for p in payloads),
            'evidence_bytes': sum(view_sizes), 'original_evidence_bytes': sum(source_sizes),
            'roundtrip_exact': True, 'all_six_sources_available': all(e['availability'] == 'available' for e in evidence)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=ROOT / 'artifacts/llm-verification.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/context-benchmark.json')
    parser.add_argument('--arms', nargs='+', choices=['legacy', 'full', 'compact', 'full-v4', 'compact-v4'],
                        default=['legacy', 'full', 'compact'])
    args = parser.parse_args()
    raw = args.fixture.read_bytes()
    fixture = json.loads(raw)
    cases = fixture['cases']
    report = {'kind': 'offline_paired_request_size', 'created_at': datetime.now(timezone.utc).isoformat(),
              'code_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted((ROOT / 'rca').glob('*.py')) + [Path(__file__).resolve()]},
              'fixture_sha256': hashlib.sha256(raw).hexdigest(), 'query_plan': PLAN,
              'network_calls': 0, 'llm_calls': 0, 'billed_tokens': 0,
              'semantic_accuracy': 'not_measured', 'model_token_savings': 'not_measured',
              'limitations': ['Fixed query plan, not model-selected behavior.',
                             'Payload bytes are not tokenizer counts, billed tokens or money.',
                             'Lossless machine decoding does not prove model comprehension.',
                             'No evidence yet of improved RCA accuracy or eBPF marginal value.'], 'cases': []}
    for case in cases:
        arms = {mode: measure(case, mode) for mode in args.arms}
        report['cases'].append({'label_for_evaluation_only': case['mode'], 'arms': arms})
    totals = {mode: sum(c['arms'][mode]['request_bytes_total'] for c in report['cases'])
              for mode in args.arms}
    report['total_request_bytes'] = totals
    report['comparisons'] = [{'baseline': a, 'candidate': b,
                            'request_byte_reduction_percent': round(100 * (1 - totals[b] / totals[a]), 2)}
                           for a, b in [('legacy', 'compact'), ('full', 'compact'),
                                        ('full-v4', 'compact-v4'), ('compact', 'compact-v4')]
                           if a in totals and b in totals]
    report['all_roundtrips_exact'] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit('Output exists; use --output with a new path to preserve previous results.')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in ('cases', 'query_plan')}, indent=2))
    print('Saved ' + str(args.output))


if __name__ == '__main__':
    main()
