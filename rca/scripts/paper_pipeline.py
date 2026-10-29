#!/usr/bin/env python3
"""One explicitly invoked bounded experiment, then offline reports. Never reruns."""
import argparse
import base64
import html
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.capture import write_new
from research.evidence import digest, verify_chain
from rca.common import now
from scripts.paper_study import check


def validate_clocks_and_sources(study):
    check(study)
    for manifest in ['capture-freeze.json','dataset-source-sha256.json']:
        base=ROOT if manifest=='capture-freeze.json' else study
        for name,expected in json.loads((study/manifest).read_text())['sha256'].items():
            if digest((base/name).read_bytes())!=expected:raise ValueError('immutable source changed: '+name)
    truth=json.loads((study/'private/truth.json').read_text())
    checks=[]
    for t in truth['cases']:
        if t['view']!='original':continue
        cid=t['case_id'];case=json.loads((study/'agent-cases'/(cid+'.json')).read_text())
        clocks=json.loads((study/'private'/cid/'clocks.json').read_text())
        start,end=clocks['window_start'],clocks['window_end']
        if start['node']!='worker-1' or end['node']!='worker-1' or start['pod']!=end['pod']:
            raise ValueError('mixed reference-clock domain')
        if case['incident']['reference_clock']!='worker-1':raise ValueError('reference clock not explicit')
        proof=json.loads((study/'private'/cid/'summary-proof.json').read_text())
        if proof['interval']!=[start['remote_epoch'],end['remote_epoch']]:raise ValueError('wrong clock-domain window')
        raw=json.loads((study/'private'/cid/'raw-export.json').read_text())
        summary=next(e for e in case['evidence'] if e['tool']=='get_ebpf_summary')
        verify_chain(summary,proof,[base64.b64decode(r['base64']).decode() for r in raw['records']],case['incident'])
        for e in case['evidence']:
            if e['tool']=='get_metrics' and 'clock_alignment' not in e:raise ValueError('unmapped metric clock')
        checks.append({'case_id':cid,'reference_node':'worker-1','interval_verified':True,'raw_replay_verified':True,
            'observed_attempts':len(proof['events']),
            'prometheus_alignment_uncertainty_seconds':clocks['metric_query_end']['uncertainty_seconds']})
    if len(checks)!=6:raise ValueError('expected six independent captures')
    return checks


def offline_script(name,study,*extra):
    result=subprocess.run([sys.executable,str(ROOT/'scripts'/name),'--study',str(study),*extra],capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError(name+' failed: '+result.stderr[-1500:])


def accounting(study):
    requests=responses=0;cost=0.;inputs=outputs=repair_tokens=0;missing_cost=0
    for path in study.glob('runs-*/*.jsonl'):
        for line in path.read_text().splitlines():
            item=json.loads(line)
            if item['type']=='request':requests+=1
            if item['type']=='response':
                responses+=1;usage=item['response'].get('usage',{})
                inputs+=usage.get('prompt_tokens',0);outputs+=usage.get('completion_tokens',0)
                if item['phase']=='repair':repair_tokens+=usage.get('prompt_tokens',0)+usage.get('completion_tokens',0)
                if type(usage.get('cost')) in (int,float) and usage['cost']>=0:cost+=usage['cost']
                else:missing_cost+=1
    initial=json.loads((study/'initial-budget.json').read_text())['state']
    final=json.loads((study/'budget.json').read_text())
    return {'current_study_requests_recorded':requests,'current_study_responses_recorded':responses,
        'known_returned_cost_usd':cost,'missing_response_count':requests-responses,'responses_without_cost':missing_cost,
        'known_input_tokens':inputs,'known_output_tokens':outputs,'known_repair_tokens_subset':repair_tokens,
        'initial_shared_budget':initial,'final_shared_budget':final,
        'scope':'Known response usage only; unknown/in-flight charges retain conservative reservations. Repair tokens are a subset, not extra to input+output. Prior stopped study consumption remains in shared budget.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,required=True)
    p.add_argument('--cluster-key',action='store_true');a=p.parse_args();study=a.study.resolve()
    if not a.cluster_key:p.error('explicit --cluster-key required for this bounded invocation')
    checks=validate_clocks_and_sources(study)
    write_new(study/'clock-source-preflight.json',{'checked_at':now(),'cases':checks})
    supplementary=[Path(__file__).resolve()]+[ROOT/'scripts'/n for n in ['paper_audit.py','paper_score.py','paper_trace.py','paper_delivery.py']]
    write_new(study/'analysis-freeze.json',{'frozen_at':now(),'phase':'supplementary packaging frozen before paid runs; core rubric/controller/reporting were frozen before capture',
        'sha256':{str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in supplementary}})
    previous=ROOT/'artifacts/paper-v1-capture-v2-20261029'
    for name in ['data-specification.json','version-comparison.json']:
        value=json.loads((previous/name).read_text())
        value['clock_capture_v3']={'source':'research/clock_capture.py','same_reference_clock':'worker-1',
            'prometheus_time_mapping':'captured offset intervals, raw source timestamps preserved',
            'prior_partial_study':'not pooled; see previous operator-abort.json'}
        write_new(study/name,value)
    print(json.dumps({'preflight':'passed','independent_captures':6,'dependent_views':3,'planned_runs':126,
                      'shared_budget_carried':json.loads((study/'initial-budget.json').read_text())['state']}),flush=True)
    rc=subprocess.run([sys.executable,str(ROOT/'scripts/paper_study.py'),'run','--study',str(study),'--suite','all','--cluster-key']).returncode
    if rc:
        write_new(study/'pipeline-error.json',{'at':now(),'run_process_exit':rc,'status':'incomplete; no automatic retry'})
        return
    for action in ['overhead','report']:
        result=subprocess.run([sys.executable,str(ROOT/'scripts/paper_study.py'),action,'--study',str(study)],capture_output=True,text=True)
        if result.returncode:raise RuntimeError(action+' failed: '+result.stderr[-1500:])
    offline_script('paper_audit.py',study)
    write_new(study/'paid-accounting.json',accounting(study))
    completion=json.loads((study/'runs-all/completion.json').read_text())
    summary=json.loads((study/'report/summary.json').read_text())
    title='Bounded pilot finished' if completion['complete'] else 'Incomplete pilot — not all planned investigations ran'
    body='<html lang="ko"><meta charset="utf-8"><title>'+title+'</title><h1>'+title+'</h1><p>독립 사람 채점은 미실시입니다. 형식 통과는 진단 정확도가 아닙니다. 온라인 Tetragon 기본 비용·관측 정책 비용·요약기 추가 오버헤드는 미측정이며, 오프라인 재생 CPU/RSS만 별도 측정했습니다.</p><p>원본 6개 독립 사건과 3개 종속 변형을 구분합니다. 같은 사건의 LLM 반복은 독립 장애 수가 아닙니다. 이전 회전 파일 누락 배치와 시계 기준 오류 배치는 보존하되 본 결과와 합치지 않았습니다.</p><p><a href="report/report.html">조건별 표와 토큰 그래프</a> · <a href="report/independent-review-packet.json">미채점 검토 자료</a> · <a href="paid-accounting.json">정확한 반환 usage 및 미확정 비용</a> · <a href="clock-source-preflight.json">시계/원본 검증</a></p><pre>'+html.escape(json.dumps({'completion':completion,'claim_scope':summary['claims_not_allowed']},ensure_ascii=False,indent=2))+'</pre></html>'
    (study/'paper-status.html').write_text(body)
    offline_script('paper_delivery.py',study)
    print(json.dumps({'pipeline_complete':completion['complete'],'recorded_runs':summary['llm_runs'],
                      'independent_review':'NOT_PERFORMED','online_overhead':'NOT_MEASURED',
                      'status_report':str(study/'paper-status.html')}),flush=True)


if __name__=='__main__':main()
