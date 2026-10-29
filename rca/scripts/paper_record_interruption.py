#!/usr/bin/env python3
"""Preserve an interrupted attempt as a failure without inventing a model reply."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.capture import write_new
from rca.common import now

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,required=True);a=p.parse_args()
interrupted=[]
for log in a.study.glob('runs-*/*.jsonl'):
    target=log.with_suffix('.json')
    if target.exists():continue
    records=[json.loads(line) for line in log.read_text().splitlines()]
    start=records[0]; requests=[r for r in records if r['type']=='request']; responses={r['call']:r for r in records if r['type']=='response'}
    if any(r['type']=='end' for r in records):raise ValueError('unexpected completed trace without result; inspect manually')
    shown=json.loads(requests[-1]['payload']['messages'][1]['content'])['evidence'] if requests else []
    result={'state':'interrupted','answer':None,'error':'operator_abort: cross-node clock alignment validation failed',
        'format_outcome':'interrupted_unknown','duration_seconds':None,'calls':len(requests),
        'repairs':sum(r['phase']=='repair' for r in requests),'shown_evidence':shown,'claims_trace':[],
        'attempts':[{'call':r['call'],'phase':r['phase'],'usage':responses.get(r['call'],{}).get('response',{}).get('usage',{}),
                     'byte_attribution':r['byte_attribution'],'response_received':r['call'] in responses} for r in requests],
        'reconstructed_from_durable_trace':True,'unknown_charge_reserved':True}
    write_new(target,{**{k:start[k] for k in ('run_id','case_id','arm','repeat')},'result':result})
    interrupted.append(start['run_id'])
write_new(a.study/'operator-abort.json',{'recorded_at':now(),'reason':'Post-capture worker-1 clock offset ~-4.5s relative to controller; mixed-clock capture window is not a verified physical interval.',
    'action':'Paid suite stopped with SIGINT; existing code, requests, returned outputs, source records and unknown-cost reservations preserved.',
    'interrupted_runs':interrupted,'research_status':'INVALID_FOR_CONFIRMATORY_TEMPORAL_OR_QUALITY_CLAIMS',
    'no_timestamp_rewrite':True,'no_host_clock_changes':True,'reference':'clock-audit.json'})
print(json.dumps({'interrupted_runs_preserved':interrupted}))
