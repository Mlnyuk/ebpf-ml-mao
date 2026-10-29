#!/usr/bin/env python3
"""Offline descriptive report and arm-masked review packet. No model calls."""
import argparse
import csv
import hashlib
import json
import random
import statistics
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=Path('artifacts/study-20261015'))
    args = parser.parse_args()
    directory = args.study
    fixture = json.loads((directory / 'network-fixture.json').read_text())
    review_path = directory / 'assistant-review.json'
    reviews = json.loads(review_path.read_text())['reviews'] if review_path.exists() else []
    decisions = {(x['case'], x['arm']): x for x in reviews}
    rows, packets, mapping, inputs = [], [], [], []
    cost_all, all_costs_known = 0.0, True
    for folder in ('development-v3', 'network-heldout-v3', 'network-fixed-v3'):
        path = directory / folder / 'results.json'
        if not path.exists():
            continue
        report = json.loads(path.read_text())
        inputs.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                       'complete': report['complete'], 'runs': len(report['runs'])})
        for run in report['runs']:
            result = run['incident']['result']
            execution = result['execution']
            cost = execution.get('provider_reported_cost_usd')
            if cost is None:
                all_costs_known = False
            else:
                cost_all += cost
            if folder == 'development-v3':
                continue
            row = {'case': run['case'], 'fault': run['label_for_evaluation_only'], 'arm': run['arm'],
                   **{key: execution.get(key) for key in ('input_tokens', 'output_tokens',
                        'cached_input_tokens', 'llm_responses', 'tool_calls', 'duration_seconds',
                        'provider_reported_cost_usd', 'error')},
                   'status': result['status'],
                   'total_tokens': execution['input_tokens'] + execution['output_tokens']}
            decision = decisions.get((run['case'], run['arm']), {})
            row['assistant_review_endpoint_correct'] = decision.get('endpoint_correct')
            row['assistant_review_has_unsupported_claim'] = bool(decision['issues']) if 'issues' in decision else None
            rows.append(row)
            review_id = hashlib.sha256(('review-v1:' + execution['run_id']).encode()).hexdigest()[:12]
            request_path = path.parent / (execution['run_id'] + '-requests.json')
            requests = json.loads(request_path.read_text())
            ledger = json.loads(requests[-1]['messages'][1]['content'])
            packets.append({'review_id': review_id, 'incident': run['incident']['data'],
                            'ground_truth_for_reviewer_only': fixture['cases'][run['case']]['ground_truth_for_evaluation_only'],
                            'shown_evidence': ledger['evidence'],
                            'answer': {k: v for k, v in result.items() if k != 'execution'},
                            'review': {'endpoint_category_correct': None, 'cited_evidence_supports_endpoint': None,
                                       'unsupported_claims': [], 'reviewer': None}})
            mapping.append({'review_id': review_id, 'case': run['case'], 'arm': run['arm'],
                            'run_id': execution['run_id']})
    arms = {}
    for arm in sorted({x['arm'] for x in rows}):
        selected = [x for x in rows if x['arm'] == arm]
        arms[arm] = {'n': len(selected), 'endpoint_correct_assistant_review':
                     sum(x['assistant_review_endpoint_correct'] is True for x in selected),
                     'reviewed': sum(x['assistant_review_endpoint_correct'] is not None for x in selected),
                     'runs_with_claim_issue_assistant_review': sum(x['assistant_review_has_unsupported_claim'] is True for x in selected)}
        for key in ('input_tokens', 'output_tokens', 'total_tokens', 'cached_input_tokens',
                    'llm_responses', 'tool_calls', 'duration_seconds', 'provider_reported_cost_usd'):
            values = [x[key] for x in selected if x[key] is not None]
            arms[arm][key] = {'sum': sum(values), 'mean': statistics.mean(values),
                             'median': statistics.median(values), 'min': min(values), 'max': max(values)}
    pairs = []
    for left, right in [('full', 'compact'), ('compact-no-ebpf', 'compact'),
                        ('fixed-full', 'fixed-compact'), ('compact', 'fixed-compact')]:
        changes = []
        for case in range(len(fixture['cases'])):
            match = {r['arm']: r for r in rows if r['case'] == case}
            if left in match and right in match:
                changes.append({'case': case, 'left': match[left]['total_tokens'],
                                'right': match[right]['total_tokens'],
                                'reduction_pct': 100 * (1 - match[right]['total_tokens'] / match[left]['total_tokens'])})
        if changes:
            pairs.append({'left': left, 'right': right, 'cases': changes,
                          'aggregate_token_reduction_pct': 100 * (1 - sum(x['right'] for x in changes) / sum(x['left'] for x in changes)),
                          'mean_case_reduction_pct': statistics.mean(x['reduction_pct'] for x in changes)})
    resources = []
    for index, case in enumerate(fixture['cases']):
        r = case['resources']
        item = {'case': index, 'fault': case['mode'],
                'raw_event_bytes': case['ebpf_raw_event_bytes'], 'summary_bytes': case['ebpf_summary_bytes'],
                'byte_reduction_pct': 100 * (1 - case['ebpf_summary_bytes'] / case['ebpf_raw_event_bytes']),
                'rss_mib': r['load_after']['rss_bytes'] / 1024**2}
        for phase in ('idle', 'load'):
            before, after = r[phase + '_before'], r[phase + '_after']
            item[phase + '_cpu_millicores'] = 1000 * (after['cpu_seconds'] - before['cpu_seconds']) / (after['monotonic'] - before['monotonic'])
        resources.append(item)
    summary = {'inputs': inputs, 'arms': arms, 'paired_total_token_comparisons': pairs,
               'aggregation_process_measurements': resources,
               'total_provider_reported_cost_including_development_usd': cost_all,
               'all_returned_runs_have_known_cost': all_costs_known,
               'shared_budget': json.loads((directory / 'budget.json').read_text()),
               'limitations': [
                   'Two fault classes, three distinct Pod trials each, one LLM execution per arm/instance; descriptive pilot only.',
                   'Opaque logs and declared expected endpoint intentionally favor value from kernel destination evidence.',
                   'Endpoint mismatch correctness is narrower than complete fault-free causal explanations.',
                   'Assistant review is not independent or blinded. Human review packet provided separately.',
                   'Selectively retrieved evidence/query plans differ across full/compact; their token difference is not encoding-only.',
                   'Fixed-all is an exploratory one-call baseline with six bounded summaries, not a raw-telemetry dump.',
                   'Raw eBPF aggregation is lossy; evidence formatting compression is lossless. Byte reduction is not token measurement.',
                   'Process CPU/RSS describes aggregation only, excludes existing Tetragon/kernel overhead; no app slowdown A/B proof.',
                   'Cost reflects provider usage fields, excludes payment fees and unknown charges from lost responses.',
                   'No population accuracy, statistical significance, causal overhead or confidence calibration claim.']}
    (directory / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    with (directory / 'runs.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    random.Random(9187).shuffle(packets)
    (directory / 'review-packet.json').write_text(json.dumps({'arm_masked_not_guaranteed_blind': True,
        'instructions': 'Judge supported endpoint mismatch separately from every causal/evidence claim. Do not inspect mapping or model identity before review.',
        'packets': packets}, ensure_ascii=False, indent=2))
    (directory / 'review-mapping-private.json').write_text(json.dumps(mapping, indent=2))
    print(json.dumps({'arms': arms, 'total_cost_usd': cost_all}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
