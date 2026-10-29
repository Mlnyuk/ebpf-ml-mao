#!/usr/bin/env python3
"""Descriptive four-arm statistics and arm-masked human review packet; offline."""
import argparse
import csv
import hashlib
import json
import random
import statistics
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=Path('artifacts/v4-validation'))
    parser.add_argument('--results', type=Path, help='Combined checkpoint; default preserves original behavior')
    parser.add_argument('--reviews', type=Path)
    parser.add_argument('--output-dir', type=Path, help='Keep original partial summaries unchanged')
    args = parser.parse_args()
    root = args.study
    results_path = args.results or root / 'evaluation/results.json'
    output = args.output_dir or root
    output.mkdir(parents=True, exist_ok=True)
    report = json.loads(results_path.read_text())
    fixture = json.loads((root / 'network-fixture.json').read_text())
    reviews_path = args.reviews or root / 'assistant-review.json'
    review_document = json.loads(reviews_path.read_text()) if reviews_path.exists() else {}
    reviews = review_document.get('reviews', [])
    decisions = {(r['case'], r['arm']): r for r in reviews}
    rows, packets, mapping = [], [], []
    for run in report['runs']:
        result = run['incident']['result']
        e = result['execution']
        decision = decisions.get((run['case'], run['arm']), {})
        row = {k: run[k] for k in ('case', 'arm', 'logging', 'label_for_evaluation_only')}
        row.update({k: e.get(k) for k in ('input_tokens', 'output_tokens', 'cached_input_tokens',
                   'provider_reported_cost_usd', 'llm_responses', 'tool_calls', 'duration_seconds', 'error')})
        # Agent usage_complete also depends on output validity. A rejected RCA
        # can still have valid billed usage; keep returned-charge accounting
        # separate instead of silently dropping the failed run's cost.
        costs = [step.get('usage', {}).get('cost') for step in e.get('trace', [])]
        row['returned_response_cost_usd'] = (sum(costs) if costs and all(
            type(cost) in (int, float) and cost >= 0 for cost in costs) else None)
        row.update(total_tokens=e.get('input_tokens', 0) + e.get('output_tokens', 0),
                   status=result['status'], endpoint_correct=decision.get('endpoint_correct'),
                   claim_issue=(bool(decision['issues']) if 'issues' in decision and
                                decision.get('semantic_answer_assessable', True) else None),
                   abstention=decision.get('abstention'))
        rows.append(row)
        candidates = [root / directory / (e['run_id'] + '-requests.json')
                      for directory in report.get('request_directories', ['evaluation'])]
        found = [p for p in candidates if p.exists()]
        if len(found) != 1:
            raise ValueError('Expected exactly one original request artifact per run: ' + e['run_id'])
        request_file = found[0]
        requests = json.loads(request_file.read_text())
        evidence = json.loads(requests[-1]['messages'][1]['content'])['evidence'] if requests else []
        review_id = hashlib.sha256(('v4-review:' + e['run_id']).encode()).hexdigest()[:12]
        answer = {k: v for k, v in result.items() if k not in ('execution', 'root_cause_status')}
        answer['evidence'] = [{k:v for k,v in citation.items() if k != 'claim_type'} for citation in answer['evidence']]
        packets.append({'review_id': review_id, 'incident': run['incident']['data'],
                        'ground_truth_for_reviewer_only': fixture['cases'][run['case']]['ground_truth_for_evaluation_only'],
                        'shown_evidence': evidence, 'answer': answer,
                        'accepted_model_answer': not bool(e.get('error')),
                        'error_fallback_is_not_model_abstention': bool(e.get('error')),
                        'review': {'endpoint_correct': None, 'unsupported_claims': [], 'appropriate_abstention': None, 'reviewer': None}})
        mapping.append({'review_id': review_id, 'case': run['case'], 'arm': run['arm'], 'run_id': e['run_id']})
    groups = {}
    for condition in ('all', 'opaque', 'endpoint'):
        groups[condition] = {}
        for arm in sorted({r['arm'] for r in rows}):
            selected = [r for r in rows if r['arm'] == arm and (condition == 'all' or r['logging'] == condition)]
            if not selected:
                continue
            item = {'n': len(selected), 'reviewed': sum(r['endpoint_correct'] is not None for r in selected),
                    'semantic_answers_reviewed': sum(r['claim_issue'] is not None for r in selected),
                    'endpoint_correct_preliminary': sum(r['endpoint_correct'] is True for r in selected),
                    'runs_with_claim_issue_preliminary': sum(r['claim_issue'] is True for r in selected),
                    'abstentions_preliminary': sum(r['abstention'] is True for r in selected),
                    'execution_errors': sum(bool(r['error']) for r in selected)}
            for key in ('total_tokens', 'input_tokens', 'output_tokens', 'cached_input_tokens',
                   'provider_reported_cost_usd', 'returned_response_cost_usd', 'llm_responses', 'tool_calls', 'duration_seconds'):
                values = [r[key] for r in selected if r[key] is not None]
                item[key] = {'n_observed': len(values), 'sum': sum(values), 'mean': statistics.mean(values), 'median': statistics.median(values)} if values else None
            groups[condition][arm] = item
    pairs = []
    for condition in ('all', 'opaque', 'endpoint'):
        for left, right in [('compact', 'compact-v4'), ('compact-v4-no-ebpf', 'compact-v4'), ('compact-v4', 'fixed-compact-v4')]:
            matched = []
            for index, case in enumerate(fixture['cases']):
                if condition != 'all' and case['logging'] != condition:
                    continue
                by_arm = {r['arm']: r for r in rows if r['case'] == index}
                if left in by_arm and right in by_arm:
                    a, b = by_arm[left], by_arm[right]
                    matched.append({'case': index, 'left_tokens': a['total_tokens'], 'right_tokens': b['total_tokens'],
                                    'both_execution_successful': not a['error'] and not b['error']})
            if matched:
                total_left = sum(r['left_tokens'] for r in matched)
                pairs.append({'condition': condition, 'left': left, 'right': right, 'pairs': matched,
                              'aggregate_token_reduction_pct': 100 * (1 - sum(r['right_tokens'] for r in matched) / total_left) if total_left else None})
    summary = {'complete': report['complete'], 'groups': groups, 'paired_comparisons': pairs,
               'review_scope': {k:v for k,v in review_document.items() if k != 'reviews'},
               'shared_budget': json.loads((root / 'budget.json').read_text()),
               'input_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                               [root / 'network-fixture.json', results_path, root / 'protocol.json', root / 'freeze.json'] +
                               ([reviews_path] if reviews_path.exists() else [])},
               'limitations': [
                   'Eight fresh instances of two known fault types, two log conditions, two load conditions; descriptive pilot only.',
                   'One model execution per arm/instance; no population accuracy or statistical superiority claim.',
                   'v3/v4 differ in prompt, encoding, schema and schema pruning; bundle comparison, not encoding-only effect.',
                   'Assistant preliminary audit is not independent or blinded; arm-masked human packet provided.',
                   'Masking arm labels cannot hide all arm clues, e.g. evidence absence or formatting.',
                   'Frozen replay latency excludes real telemetry query delays and incident detection.',
                   'Resource snapshots do not measure causal ON/OFF overhead.',
                   'Token sums include all returned requests; missing responses can leave usage incomplete.',
                   'Costs are provider-reported usage, not payment fees; budget reserves unknown charges.',
                   'Execution-error fallbacks are not semantic answers or appropriate model abstentions.',
                   'All-scheduled-arm token comparisons include failed outputs; cheaper is not automatically better.']}
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    with (output / 'runs.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    random.Random(2816).shuffle(packets)
    (output / 'review-packet.json').write_text(json.dumps({'arm_masked_not_guaranteed_blind': True, 'packets': packets}, ensure_ascii=False, indent=2))
    (output / 'review-mapping-private.json').write_text(json.dumps(mapping, indent=2))
    print(json.dumps({'complete': summary['complete'], 'groups': groups, 'budget': summary['shared_budget']}, indent=2))


if __name__ == '__main__':
    main()
