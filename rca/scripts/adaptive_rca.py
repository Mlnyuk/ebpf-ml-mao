#!/usr/bin/env python3
"""Offline policy preview or exact saved-response replay. No paid execution flag.

Live use is through rca.agent.Agent with an explicitly configured NEW budget.
Replayed provider usage belongs to the historical run, not this local execution.
"""
import argparse
import copy
import csv
import hashlib
import json
import os
import sys
import time
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rca.agent import Provider
from rca.common import Settings,compact,redact
from rca.investigation import Investigation,Limits
from rca.investigation_sources import FrozenSources


class ReplayProvider:
    offline=True
    measurement='saved_response_replay_not_new_model_execution'
    def __init__(self, responses=()):
        s=Settings();s.routing={'only':['z-ai/fp8'],'allow_fallbacks':False};s.max_output=2048
        self.encoder=Provider(s);self.responses=iter(responses);self.historical_usage=[]
    def payload(self,messages,tools):return self.encoder.payload(messages,tools)
    def complete(self,messages,tools,timeout):
        value=copy.deepcopy(next(self.responses));self.historical_usage.append(value.pop('usage',{}))
        return value


def read_cases(args):
    if args.case:return [(args.case.name,json.loads(args.case.read_text()))]
    # Reuse the preserved published bundle, including public cases only.
    with zipfile.ZipFile(args.bundle) as z:
        names=sorted(n for n in z.namelist() if '/agent-cases/' in n and n.endswith('.json'))
        return [(n,json.loads(z.read(n))) for n in names]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--case',type=Path);source.add_argument('--bundle',type=Path)
    p.add_argument('--policy',choices=['batch','filtered-batch','selective','adaptive'],default='adaptive')
    p.add_argument('--compare',action='store_true',help='compare first-request policy routing only; no model outputs')
    p.add_argument('--responses',type=Path,help='saved JSONL responses, exact replay; never a new model run')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.responses and (a.compare or a.bundle):p.error('response replay requires one --case and one policy')
    a.output.mkdir(parents=True,exist_ok=False)
    cases=read_cases(a);results=[]
    freeze={'mode':'offline_only','source_files':{str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted((ROOT/'rca').glob('*.py'))},
        'cases':{c['case_id']:hashlib.sha256(compact(c).encode()).hexdigest() for _,c in cases},
        'limits':vars(Limits()),'paid_api_calls':0,'new_model_quality':'NOT_EVALUATED',
        'comparison_scope':'Shared current output contract/prompt, four routing policies. Historical engines/results are preserved separately; this is not a new model comparison.'}
    (a.output/'freeze.json').write_text(json.dumps(freeze,indent=2))
    responses=[]
    if a.responses:
        records=[json.loads(l) for l in a.responses.read_text().splitlines()]
        responses=[r['response'] for r in records if r.get('type')=='response']
    for source_name,case in cases:
        for policy in ('batch','filtered-batch','selective','adaptive') if a.compare else (a.policy,):
            stem=hashlib.sha256(compact([case['case_id'],policy]).encode()).hexdigest()[:16]
            provider=ReplayProvider(responses);adapter=FrozenSources(case);events=[]
            with (a.output/(stem+'.jsonl')).open('x') as trace:
                def record(e):
                    events.append(e);trace.write(compact(redact(e))+'\n');trace.flush();os.fsync(trace.fileno())
                engine=Investigation(adapter,provider,policy,record=record)
                if a.responses:
                    result=engine.run();result['historical_response_usage']=provider.historical_usage
                    result['paid_api_calls_this_replay']=0
                else:
                    start=time.perf_counter();routing=engine.prepare()
                    payload=provider.payload(engine.messages(),engine.tools(policy in ('batch','filtered-batch')))
                    record({'type':'first_request_preview','payload':payload,'sent':False})
                    result={'case_id':case['case_id'],'policy':policy,**routing,'initial_sources':len(engine.ledger.entries),
                        'first_request_bytes':len(compact(payload).encode()),'would_exceed_request_limit':len(compact(payload).encode())>engine.limits.request_bytes,'local_prepare_seconds':time.perf_counter()-start,
                        'paid_api_calls':0,'billed_tokens':None,'diagnostic_quality':'NOT_EVALUATED','scope':'routing preview only'}
                (a.output/(stem+'.json')).write_text(json.dumps(redact(result),ensure_ascii=False,indent=2))
                results.append(result)
    if a.compare:
        with (a.output/'routing.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    (a.output/'completion.json').write_text(json.dumps({'complete':True,'records':len(results),'paid_calls':0,'new_quality':'NOT_EVALUATED'},indent=2))
    print(json.dumps({'output':str(a.output),'records':len(results),'paid_calls':0}))


if __name__=='__main__':main()
