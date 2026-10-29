#!/usr/bin/env python3
"""Supplementary read-only checks and post-capture environment metadata.

Does not change the frozen experiment or any old result. Writes new audit files.
"""
import argparse
import json
import platform
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.capture import write_new
from research.evidence import digest
from scripts.paper_study import check
from scripts.rcactl import kubectl
from rca.common import now


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,default=ROOT/'artifacts/paper-v1-20261029')
    parser.add_argument('--environment',action='store_true')
    parser.add_argument('--preflight',action='store_true')
    args=parser.parse_args(); study=args.study.resolve()
    check(study)
    if args.environment:
        result={'observed_at':now(),'timing':'during/after capture; not an assertion that every resource was unchanged beforehand',
                'python':sys.version,'platform':platform.platform(), 'objects':{}}
        queries={
            'nodes':['get','nodes','-o','json'],
            'agent':['-n','rca-system','get','deployment','rca-agent','-o','json'],
            'summary_daemonset':['-n','rca-system','get','daemonset','rca-ebpf-summary','-o','json'],
            'services':['-n','rca-lab','get','services','-o','json'],
            'tetragon_pods':['-n','kube-system','get','pods','-l','app.kubernetes.io/name=tetragon','-o','json'],
            'tracing_policies':['get','tracingpolicies','-o','json'],
        }
        for name,query in queries.items():
            try: result['objects'][name]=json.loads(kubectl(*query,capture=True))
            except Exception as exc: result['objects'][name]={'status':'not_obtained','error':type(exc).__name__}
        write_new(study/'private/environment-observation.json',result)
        return
    dataset=json.loads((study/'dataset.json').read_text()); truth=json.loads((study/'private/truth.json').read_text())
    if len(dataset['case_ids'])!=9: raise ValueError('expected six captures plus three dependent views')
    for cid,hash_value in dataset['case_sha256'].items():
        case=json.loads((study/'agent-cases'/(cid+'.json')).read_text())
        if digest((study/'agent-cases'/(cid+'.json')).read_bytes())!=hash_value: raise ValueError('dataset changed')
        if set(case)!={'case_id','incident','evidence'}: raise ValueError('public/truth mixing')
    originals=[t for t in truth['cases'] if t['view']=='original']
    uids=[t['target']['pod_uid'] for t in originals]
    if len(set(uids))!=6: raise ValueError('capture units are not distinct Pods')
    runs=[]
    for folder in study.glob('runs-*'):
        schedule=json.loads((folder/'schedule.json').read_text())['items']
        for path in folder.glob('*.json'):
            if path.name in ('schedule.json','completion.json'): continue
            r=json.loads(path.read_text()); runs.append(r)
            if {k:r[k] for k in ('case_id','arm','repeat')} not in schedule: raise ValueError('unscheduled run')
            for line in (folder/(r['run_id']+'.jsonl')).read_text().splitlines():
                entry=json.loads(line)
                if entry['type']=='request':
                    text=json.dumps(entry['payload'])
                    if any(k in text for k in ('assigned_fault','assigned_cause','independent_incident_id','ground_truth_for_evaluation_only')):
                        raise ValueError('ground truth leaked into request')
                    if entry['payload']['model']!='z-ai/glm-5.3-flash' or entry['payload']['provider']['only']!=['z-ai/fp8']:
                        raise ValueError('model/provider mismatch')
                    if not r['arm'].startswith('selective') and entry['phase'] not in ('final','repair'):
                        raise ValueError('batch arm received extra selection phase')
    if len({(r['case_id'],r['arm'],r['repeat']) for r in runs})!=len(runs): raise ValueError('duplicate investigation')
    result={'observed_at':now(),'legacy_hashes_match':True,'frozen_code_matches':True,
            'new_independent_pod_count':len(set(uids)),'dependent_views':3,'recorded_investigations':len(runs),
            'unique_case_arm_repeat':True,'truth_marker_scan_passed':True,
            'complete_suites':{p.parent.name:json.loads(p.read_text())['complete'] for p in study.glob('runs-*/completion.json')},
            'independent_human_review':'NOT_PERFORMED',
            'limitations':['Truth separation is logical, not an OS sandbox against malicious evaluation code.',
                           'Clock synchronization is not assumed; clock-aware studies additionally record source offset intervals in private/*/clocks.json and clock-source-preflight.json.',
                           'Raw export completeness, kernel event loss and upstream duplicate delivery remain unmeasured.',
                           'Six original cases have fixed capture order; shared-cluster temporal confounding is possible.',
                           'Historical contamination is a declared dependent robustness view, not an independently observed historical incident.']}
    if args.preflight:
        files=[p for p in (study/'private').rglob('*') if p.is_file()]
        files += [study/'dataset.json'] + list((study/'agent-cases').glob('*.json'))
        write_new(study/'dataset-source-sha256.json',{'frozen_at':now(),'sha256':{
            str(p.relative_to(study)):digest(p.read_bytes()) for p in sorted(files)}})
    else:
        for name,expected in json.loads((study/'dataset-source-sha256.json').read_text())['sha256'].items():
            if digest((study/name).read_bytes())!=expected: raise ValueError('source artifact changed: '+name)
        result['dataset_source_hashes_match']=True
    write_new(study/('preflight-audit.json' if args.preflight else 'integrity-audit.json'),result)
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
