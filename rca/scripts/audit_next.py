#!/usr/bin/env python3
"""Post-execution integrity/accounting audit; never grades or reruns a model."""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.capture import write_new
from research.evidence import digest
from research_v4.protocol import check
from research_v4.analyze import write_csv
from research.spec import FINAL_TOOL
from rca.common import now


def audit(study,out):
    check(study)
    capture=json.loads((study/'capture-completion.json').read_text())
    dataset=json.loads((study/'dataset.json').read_text())
    truth=json.loads((study/'private/truth.json').read_text())['cases']
    completion=json.loads((study/'runs-main/completion.json').read_text())
    schedule=json.loads((study/'runs-main/schedule.json').read_text())['items']
    files=list((study/'runs-main').glob('*.json'))
    runs=[json.loads(f.read_text()) for f in files if f.name not in ('completion.json','schedule.json')]
    observed=[{k:r[k] for k in ('case_id','arm','repeat')} for r in runs]
    if len({(x['case_id'],x['arm'],x['repeat']) for x in observed})!=len(observed):raise ValueError('duplicate registered run')
    if any(x not in schedule for x in observed):raise ValueError('unscheduled result')
    if completion['complete'] and len(runs)!=len(schedule):raise ValueError('false completion')
    for cid,h in dataset['case_sha256'].items():
        if digest((study/'agent-cases'/(cid+'.json')).read_bytes())!=h:raise ValueError('case changed')
    parents={t['independent_incident_id']:t for t in truth if t['view']=='original'}
    if len({t['target']['pod_uid'] for t in parents.values()})!=len(parents):raise ValueError('reused Pod UID across occurrences')
    calls=[]
    for category,paths in [('primary',study.glob('runs-main/*.jsonl')),('native_k8sgpt',study.glob('private/*/k8sgpt-api.jsonl'))]:
        for path in paths:
            pending=None;sequence=0
            for line in path.read_text().splitlines():
                e=json.loads(line)
                if e['type']=='request':
                    sequence+=1
                    body=e['payload'] if category=='primary' else e['forwarded_request']
                    text=json.dumps(body)
                    if any(marker in text for marker in ['assigned_cause','assigned_scenario','independent_incident_id','ground_truth_for_evaluation_only']):raise ValueError('truth marker in paid request')
                    if body['model']!='z-ai/glm-5.3-flash' or body['provider']['only']!=['z-ai/fp8'] or body['provider']['allow_fallbacks'] is not False:raise ValueError('model/provider drift')
                    if category=='primary':
                        finals=[t for t in body['tools'] if t['function']['name']=='submit_rca']
                        if finals!=[FINAL_TOOL]:raise ValueError('output contract drift')
                        if e['phase']=='repair' and any(t['function']['name']=='inspect' for t in body['tools']):raise ValueError('repair can acquire new evidence')
                    pending={'category':category,'record':str(path.relative_to(study)),'call':sequence,'phase':e.get('phase','native_explain'),
                        'request_bytes':len(json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()),'response_received':False,
                        'input_tokens':None,'output_tokens':None,'cached_input_tokens':None,'reasoning_tokens_subset':None,'cost_usd':None}
                    calls.append(pending)
                elif e['type']=='response':
                    if pending is None or pending['response_received']:raise ValueError('unpaired response')
                    u=e['response'].get('usage',{})
                    pending.update(response_received=True,input_tokens=u.get('prompt_tokens'),output_tokens=u.get('completion_tokens'),
                        cached_input_tokens=u.get('prompt_tokens_details',{}).get('cached_tokens'),
                        reasoning_tokens_subset=u.get('completion_tokens_details',{}).get('reasoning_tokens'),cost_usd=u.get('cost'))
    out.mkdir(parents=True,exist_ok=False)
    write_csv(out/'all-api-calls.csv',calls)
    accounts=[]
    for category in ['primary','native_k8sgpt']:
        selected=[c for c in calls if c['category']==category]
        accounts.append({'category':category,'request_records':len(selected),'responses':sum(c['response_received'] for c in selected),
            'input_tokens':sum(c['input_tokens'] or 0 for c in selected),'output_tokens':sum(c['output_tokens'] or 0 for c in selected),
            'cached_input_tokens_known_subset':sum(c['cached_input_tokens'] or 0 for c in selected),
            'repair_tokens_subset':sum((c['input_tokens'] or 0)+(c['output_tokens'] or 0) for c in selected if c['phase']=='repair'),
            'known_cost_usd':sum(c['cost_usd'] for c in selected if type(c['cost_usd']) in (int,float)),
            'unknown_cost_records':sum(type(c['cost_usd']) not in (int,float) for c in selected)})
    write_csv(out/'accounting.csv',accounts)
    result={'at':now(),'posthoc_audit_code_sha256':digest(Path(__file__).read_bytes()),'frozen_protocol_and_code_match':True,
        'old_clock_v3_hashes_match':True,'dataset_hashes_match':True,'shared_primary_output_contract_verified':True,
        'private_truth_marker_scan_passed':True,'truth_isolation_limit':'logical separation; substring check is not an OS security proof',
        'capture_complete':capture['complete'],'independent_occurrences':len(parents),'distinct_pod_uids':len(parents),
        'occurrence_scenarios':dict(Counter(t['assigned_cause'] for t in parents.values())),
        'successful_injection_effect_checks':sum(t['injection_effect_observed'] for t in parents.values()),
        'physical_clusters':1,'independence_limit':'Fresh occurrence and Pod identity, not independently provisioned clusters or guaranteed statistical independence',
        'planned_runs':len(schedule),'recorded_runs':len(runs),'suite_complete':completion['complete'],
        'outcomes':dict(Counter(r['result']['state'] for r in runs)),'accounting':accounts,
        'global_budget':json.loads((study/'budget.json').read_text()),'human_diagnostic_quality':'NOT_EVALUATED','online_overhead':'NOT_MEASURED'}
    write_new(out/'integrity-and-accounting.json',result)
    scope={'allowed_claims':['Measured usage and format outcomes on the registered pilot','Traceability to preserved exported events','Conditional paired token/cost differences across the specified evidence breadth'],
        'not_established':['General diagnostic superiority','Quality-preserving token reduction before independent ratings','Low end-to-end online overhead','Statistically independent clusters','Zero kernel/export loss'],
        'comparison_limits':[
            'Primary method latency is frozen-evidence controller/LLM time and excludes source capture/preprocessing. Native K8sGPT latency includes live Kubernetes/CLI work.',
            'K8sGPT native prompt/output/language defaults differ from our Korean structured contract; this is a native-scope exploratory comparison, not a controlled prompt/output ablation.',
            'K8sGPT --no-cache disables application result reuse. Provider prefix caching is not controlled; actual returned cache usage is recorded separately.',
            'Three neighboring workloads are controlled lab services with actual generated telemetry, not a production-scale diversity claim.',
            'The 1 and 4 requests/second offered loads are bounded low-rate conditions, not capacity/overhead stress tests.',
            'One model run per fresh episode/method/breadth prioritizes new collection; model-run variability within a factorial cell is not separately estimated.',
            'A native finding is not necessarily a correct diagnosis; scope gaps, detection absence and human judgments must remain separate.'
        ]}
    write_new(out/'claim-scope.json',scope)
    print(json.dumps(result,ensure_ascii=False))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();audit(a.study.resolve(),a.output.resolve())

if __name__=='__main__':main()
