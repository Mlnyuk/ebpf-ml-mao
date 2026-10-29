#!/usr/bin/env python3
"""Prepare supplementary data dictionary, truth table and honest delivery status."""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rca.common import now
from rca.context import present_evidence,restore_evidence
from research.capture import write_new
from research.evidence import digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True)
    parser.add_argument('--evidence-only',action='store_true')
    args=parser.parse_args(); study=args.study.resolve()
    dataset=json.loads((study/'dataset.json').read_text()); truth=json.loads((study/'private/truth.json').read_text())
    checked=0
    for cid in dataset['case_ids']:
        case=json.loads((study/'agent-cases'/(cid+'.json')).read_text())
        for e in case['evidence']:
            compact=present_evidence(e,case['incident'],'compact-v4')
            if restore_evidence(compact,case['incident'])!=e:raise ValueError('lossless evidence roundtrip failed')
            checked+=1
    if args.evidence_only:
        write_new(study/'encoding-validation.json',{'checked_at':now(),'cases':len(dataset['case_ids']),
                   'evidence_snapshots':checked,'exact_roundtrip':True,'note':'Not a token/quality improvement measurement.'})
        return
    rows=[]
    for t in truth['cases']:
        rows.append({'case_id':t['case_id'],'independent_incident_id':t['independent_incident_id'],
            'view':t['view'],'assigned_cause':t['assigned_cause'],'injection_effect_observed':t['injection_effect_observed'],
            'pod_uid':t['target']['pod_uid'],'container_id':t['target']['container_id'],
            'expected_service':t['expected_destination']['service'],'expected_vip':t['expected_destination']['expected_ip'],
            'expected_port':t['expected_destination']['expected_port'],
            'assigned_wrong_port':9099 if t['assigned_cause']=='network_port' else None,
            'assigned_wrong_service':'rca-lab/sample-service' if t['assigned_cause']=='network_peer' else None,
            'source':'private capture assignment and frozen lab fault code, not inferred from model output'})
    with (study/'private/ground-truth-table.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    completions={p.parent.name:json.loads(p.read_text()) for p in study.glob('runs-*/completion.json')}
    status={'created_at':now(),'implementation':'research-only; operational Agent unchanged and not enabled',
            'experiment_completion':completions,
            'independent_review':{'status':'NOT_PERFORMED','requires':'two actual independent human reviewers; empty score files are not results'},
            'online_overhead':{'status':'NOT_MEASURED','details':'overhead.json separates unsafe/unperformed components from measured offline replay'},
            'artifacts':{'protocol':'protocol.json','data_spec':'data-specification.json','version_settings':'version-comparison.json',
                'truth':'private/ground-truth-table.csv','raw_events':'private/<case>/raw-export.json',
                'source_proofs':'private/<case>/summary-proof.json','model_records':'runs-all/*.jsonl',
                'format_and_usage':'report/runs.csv','per_condition':'report/conditions.csv','per_incident':'report/incident-means.csv',
                'paired_ablation_deltas':'report/paired-deltas.csv','independent_review_packet':'report/independent-review-packet.json',
                'independent_scores':'report/independent-ratings-template.json (UNRATED)',
                'failure_analysis':'report/failure-analysis.json','overhead':'overhead.json',
                'figure':'report/tokens.svg','claim_scope_report':'report/report.html','integrity':'integrity-audit.json'},
            'limitations':['Pilot only; six independent captures, three dependent views, two LLM repeats per case/arm.',
                           'No statistical superiority or general accuracy claim.',
                           'Unfavorable results and failed capture batch retained; no success-seeking repeats.',
                           'Exact tokens by semantic prompt component cannot be recovered from aggregate provider usage; byte attribution is a proxy.',
                           'Public response text/tool arguments are retained; private chain-of-thought and credentials are excluded.']}
    write_new(study/'delivery-status.json',status)
    files=[p for p in study.rglob('*') if p.is_file() and p.name!='bundle-sha256.json']
    write_new(study/'bundle-sha256.json',{'created_at':now(),'sha256':{str(p.relative_to(study)):digest(p.read_bytes()) for p in sorted(files)}})
    print(json.dumps(status,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
