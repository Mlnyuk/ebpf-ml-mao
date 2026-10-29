"""Offline evidence audit, unfilled independent review packets, tables and SVG."""
import base64
import csv
import html
import json
import random
import statistics
import subprocess
import sys
from pathlib import Path
from rca.common import now
from rca.context import restore_evidence
from research.capture import write_new
from research.evidence import digest, verify_chain, mismatch_baseline
from research.spec import RUBRIC


def report(study):
    out = study / 'report'
    out.mkdir(exist_ok=False)
    dataset = json.loads((study/'dataset.json').read_text())
    truth = json.loads((study/'private/truth.json').read_text())
    truths = {t['case_id']:t for t in truth['cases']}
    cases = {cid:json.loads((study/'agent-cases'/(cid+'.json')).read_text()) for cid in dataset['case_ids']}
    audits = []
    for cid, case in cases.items():
        if truths[cid]['view'] != 'original':
            audits.append({'case_id':cid,'status':'derived_view','parent':truths[cid]['parent_case_id']}); continue
        raw = json.loads((study/'private'/cid/'raw-export.json').read_text())
        lines = [base64.b64decode(r['base64']).decode() for r in raw['records']]
        proof = json.loads((study/'private'/cid/'summary-proof.json').read_text())
        e = next(e for e in case['evidence'] if e['tool']=='get_ebpf_summary')
        verify_chain(e,proof,lines,case['incident'])
        audits.append({'case_id':cid,'status':'verified_exact_export_replay','raw_events':len(lines),
                       'included_attempts':len(proof['events']),'excluded':proof['rejected'],
                       'source_files':raw['files'],'kernel_export_loss':'not_measured'})
    write_new(out/'evidence-audit.json',audits)
    write_new(out/'mismatch-baseline.json',{'version':'literal-v1','scope':'offline comparison only; not Agent logic',
               'runs':[{'case_id':cid,**mismatch_baseline(c)} for cid,c in cases.items()]})
    rows, packets, mapping, failures = [], [], [], []
    for directory in sorted(study.glob('runs-*')):
        for path in sorted(directory.glob('*.json')):
            if path.name in ('schedule.json','completion.json'): continue
            run = json.loads(path.read_text()); result=run['result']; cid=run['case_id']
            attempts=result['attempts']; costs=[a['usage'].get('cost') for a in attempts]
            row={'run_id':run['run_id'],'case_id':cid,'independent_incident_id':truths[cid]['independent_incident_id'],
                 'condition':truths[cid]['view'],'assigned_cause':truths[cid]['assigned_cause'],'arm':run['arm'],'repeat':run['repeat'],
                 'state':result['state'],'format_outcome':result['format_outcome'],'error':result['error'],
                 'calls':result['calls'],'repairs':result['repairs'],'seconds':result['duration_seconds'],
                 'prompt_tokens':sum(a['usage'].get('prompt_tokens',0) for a in attempts),
                 'completion_tokens':sum(a['usage'].get('completion_tokens',0) for a in attempts),
                 'cached_tokens':sum(a['usage'].get('prompt_tokens_details',{}).get('cached_tokens',0) for a in attempts),
                 'repair_tokens_subset':sum(a['usage'].get('prompt_tokens',0)+a['usage'].get('completion_tokens',0) for a in attempts if a['phase']=='repair'),
                 'returned_cost_usd':sum(costs) if costs and all(type(c) in (float,int) and c>=0 for c in costs) else None,
                 'usage_complete_for_attempts':len(attempts)==result['calls'] and all('prompt_tokens' in a['usage'] and 'completion_tokens' in a['usage'] for a in attempts),
                 'new_evidence_bytes':sum(a['byte_attribution']['new_evidence_bytes'] for a in attempts),
                 'repeated_evidence_bytes':sum(a['byte_attribution']['repeated_evidence_bytes'] for a in attempts),
                 'other_request_bytes':sum(a['byte_attribution']['other_request_bytes'] for a in attempts),
                 'independent_semantic_score':None}
            row['total_tokens']=row['prompt_tokens']+row['completion_tokens']
            rows.append(row)
            review_id=digest('review:'+run['run_id'])[:16]
            packets.append({'review_id':review_id,'incident':cases[cid]['incident'],
                'shown_evidence':[restore_evidence(e,cases[cid]['incident']) for e in result['shown_evidence']],
                'answer':result['answer'],'accepted_output':result['state']=='accepted',
                'error_is_not_abstention':result['state']!='accepted',
                'scores':{k:None for k in RUBRIC if k!='output_format'},'claim_ratings':[],
                'reviewer':None,'rationale':None})
            mapping.append({'review_id':review_id,'run_id':run['run_id'],'arm':run['arm'],'case_id':cid,'repeat':run['repeat']})
            if result['error'] or result['repairs']:
                failures.append({'run_id':run['run_id'],'error':result['error'],'repairs':result['repairs'],
                    'invalid_outputs':[a for a in attempts if a.get('kind')=='invalid'], 'raw_record':str((directory/(run['run_id']+'.jsonl')).relative_to(study))})
    random.Random(291026).shuffle(packets)
    write_new(out/'independent-review-packet.json',{'status':'unrated','not_guaranteed_blind':True,'rubric':RUBRIC,'packets':packets})
    write_new(study/'private/review-mapping.json',mapping)
    write_new(study/'private/reviewer-truth.json',[{'review_id':m['review_id'],'truth':truths[m['case_id']]} for m in mapping])
    write_new(out/'independent-ratings-template.json',{'status':'NOT_PERFORMED','reviewers_required':2,'ratings':[],
        'entry_fields':['review_id','reviewer_id','independent_of_implementation','timestamp','scores','claim_ratings','rationale'],
        'adjudication':[],'instructions':'Preserve separate original ratings. No assistant ratings count as independent review.'})
    write_new(out/'failure-analysis.json',failures)
    groups=[]
    for arm in sorted({r['arm'] for r in rows}):
        for condition in sorted({r['condition'] for r in rows}):
            selected=[r for r in rows if r['arm']==arm and r['condition']==condition]
            if not selected: continue
            groups.append({'arm':arm,'condition':condition,'investigations':len(selected),
                'unique_parent_incidents':len({r['independent_incident_id'] for r in selected}),
                'output_errors':sum(r['state']!='accepted' for r in selected),
                'total_tokens':sum(r['total_tokens'] for r in selected),
                'mean_tokens':statistics.mean(r['total_tokens'] for r in selected),
                'returned_cost_usd':sum(r['returned_cost_usd'] or 0 for r in selected),
                'missing_cost_runs':sum(r['returned_cost_usd'] is None for r in selected),
                'independent_quality_status':'NOT_PERFORMED','quality_score':None})
    incident_means=[]
    for arm in sorted({r['arm'] for r in rows}):
        for cid in dataset['case_ids']:
            subset=[r for r in rows if r['arm']==arm and r['case_id']==cid]
            if subset:
                incident_means.append({'arm':arm,'case_id':cid,'parent':truths[cid]['independent_incident_id'],
                    'view':truths[cid]['view'],'repeats_observed':len(subset),
                    'mean_total_tokens':statistics.mean(r['total_tokens'] for r in subset),
                    'errors':sum(r['state']!='accepted' for r in subset),'quality':None})
    pairs=[]
    for other in ['batch-ebpf','selective-no-ebpf','selective-ebpf-no-compression','selective-ebpf-no-dedup','selective-ebpf-no-stop-guidance']:
        for cid in dataset['case_ids']:
            a=next((r for r in incident_means if r['arm']=='selective-ebpf' and r['case_id']==cid),None)
            b=next((r for r in incident_means if r['arm']==other and r['case_id']==cid),None)
            if a and b:
                pairs.append({'case_id':cid,'view':a['view'],'reference':'selective-ebpf','comparison':other,
                    'delta_mean_tokens_comparison_minus_reference':b['mean_total_tokens']-a['mean_total_tokens'],
                    'both_repeat_counts_complete':a['repeats_observed']==b['repeats_observed']==2,
                    'quality_delta':None,'quality_status':'pending independent review'})
    for name,data in [('runs.csv',rows),('conditions.csv',groups),('incident-means.csv',incident_means),('paired-deltas.csv',pairs)]:
        with (out/name).open('x',newline='') as stream:
            if data:
                writer=csv.DictWriter(stream,fieldnames=list(data[0])); writer.writeheader(); writer.writerows(data)
    write_new(out/'summary.json',{'generated_at':now(),'independent_captures':6,'dependent_views':3,'llm_runs':len(rows),
        'groups':groups,'paired_deltas':pairs,'independent_review':'NOT_PERFORMED',
        'legacy_usage':'development/regression only; never pooled',
        'claims_allowed':['Observed usage, failure rates, byte attribution, exact exported-event reconstruction'],
        'claims_not_allowed':['Independent diagnostic accuracy before human ratings','Low online overhead','Statistical superiority from this pilot','Byte shares as exact token shares'],
        'expected_destination_caveat':'This lab supplies a declared dependency contract; general service dependency discovery is not evaluated.'})
    original=[g for g in groups if g['condition']=='original']
    maximum=max([g['mean_tokens'] for g in original]+[1])
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="420"><rect width="900" height="420" fill="white"/><text x="20" y="25">Pilot mean total tokens — original incidents; failures included</text>']
    for i,g in enumerate(original):
        y=55+i*45; width=400*g['mean_tokens']/maximum
        svg.append(f'<text x="10" y="{y+18}" font-size="12">{html.escape(g["arm"])}</text><rect x="310" y="{y}" width="{width:.2f}" height="25" fill="#4466aa"/><text x="{320+width:.2f}" y="{y+18}">{g["mean_tokens"]:.0f}</text>')
    svg.append('</svg>'); (out/'tokens.svg').write_text(''.join(svg))
    body='<html><meta charset="utf-8"><title>RCA paper pilot</title><h1>Paper pilot: measured usage, quality pending</h1><p>Independent review: NOT PERFORMED. Online causal overhead: NOT MEASURED. Old 8 cases/32 investigations are development only.</p><img src="tokens.svg"><h2>Condition tables</h2><pre>'+html.escape(json.dumps(groups,ensure_ascii=False,indent=2))+'</pre><p>See runs.csv, paired-deltas.csv, evidence-audit.json and failure-analysis.json. Do not equate successful format validation with accurate diagnosis.</p></html>'
    (out/'report.html').write_text(body)
    print(json.dumps({'runs':len(rows),'groups':groups,'independent_review':'NOT_PERFORMED'},ensure_ascii=False))


def overhead(study):
    # A process-isolated replay microbenchmark, not a fictional online ON/OFF.
    worker='''import json,base64,time,resource,sys
from research.evidence import summarize
from pathlib import Path
p=Path(sys.argv[1]); case=json.loads((p/'agent-cases'/ (sys.argv[2]+'.json')).read_text()); raw=json.loads((p/'private'/sys.argv[2]/'raw-export.json').read_text()); lines=[base64.b64decode(r['base64']).decode() for r in raw['records']]; proof=json.loads((p/'private'/sys.argv[2]/'summary-proof.json').read_text())
start=time.process_time(); wall=time.monotonic()
for _ in range(100): summarize(lines,case['incident'],*proof['interval'])
print(json.dumps({'cpu_seconds_100_replays':time.process_time()-start,'wall_seconds_100_replays':time.monotonic()-wall,'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'raw_events':len(lines)}))
'''
    truth=json.loads((study/'private/truth.json').read_text())
    samples=[]
    for t in truth['cases']:
        if t['view']=='original':
            for repeat in range(3):
                value=json.loads(subprocess.run([sys.executable,'-c',worker,str(study),t['case_id']],check=True,capture_output=True,text=True).stdout)
                samples.append({'case_id':t['case_id'],'repeat':repeat,**value})
    write_new(study/'overhead.json',{'scope':'offline replay microbenchmark on controller host, not online collector incremental cost',
        'tetragon_base':{'status':'NOT_MEASURED','reason':'shared cluster; disabling global Tetragon is outside safe experimental isolation'},
        'observation_policy':{'status':'NOT_MEASURED','reason':'global probe shared with other users/workloads'},
        'online_summary_incremental':{'status':'NOT_MEASURED','reason':'no randomized ON/OFF service experiment'},
        'offline_exact_summary_replay':samples,'rss_caveat':'whole Python process peak including imports/raw records, not pure summary memory',
        'quality':{'independent_review':'NOT_PERFORMED'}})
