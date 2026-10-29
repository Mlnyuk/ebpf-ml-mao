"""Tables and owner/reviewer datasets; quality remains ungraded until humans act."""
import base64
import json
from pathlib import Path
from research.capture import write_new
from research.evidence import digest,verify_chain
from research.spec import RUBRIC
from research_v4.analyze import read_runs,aggregate,write_csv
from research_v4.baseline import compare
from research_v4.protocol import check
from rca.common import now
from rca.context import restore_evidence


def report(study):
    check(study);out=study/'report';out.mkdir(exist_ok=False)
    truth={t['case_id']:t for t in json.loads((study/'private/truth.json').read_text())['cases']}
    rows,failures,queries,sources=read_runs(study)
    for r in rows:
        t=truth[r['case_id']];r.update(group='primary',breadth=t['breadth'],logging=t['trial']['logging'],load_interval=t['trial']['load_interval_seconds'])
    methods=aggregate(rows,['view','breadth','arm'])
    factors=aggregate(rows,['view','breadth','assigned_cause','logging','load_interval','arm'])
    incidents=aggregate(rows,['view','breadth','case_id','parent_incident','assigned_cause','arm'])
    for name,data in [('runs.csv',rows),('methods.csv',methods),('factors.csv',factors),('incidents.csv',incidents)]:write_csv(out/name,data)
    write_new(out/'failure-analysis.json',failures);write_new(out/'retrieval-analysis.json',queries)
    cases={cid:json.loads((study/'agent-cases'/(cid+'.json')).read_text()) for cid in truth}
    baseline=[{'case_id':cid,'breadth':truth[cid]['breadth'],'view':truth[cid]['view'],**compare(c)} for cid,c in cases.items()]
    write_new(out/'destination-baseline.json',baseline)
    audits=[]
    for cid in sorted({t['independent_incident_id'] for t in truth.values()}):
        proof=json.loads((study/'private'/cid/'summary-proof.json').read_text())
        raw=json.loads((study/'private'/cid/'raw-export.json').read_text())
        c=cases[cid+'-small'];e=next(e for e in c['evidence'] if e['tool']=='get_ebpf_summary')
        verify_chain(e,proof,[base64.b64decode(x['base64']).decode() for x in raw['records']],c['incident'])
        audits.append({'incident':cid,'raw_replay_verified':True,'attempts':len(proof['events'])})
    write_new(out/'evidence-audit.json',audits)
    pairs=[]
    for cid in cases:
        same=[r for r in rows if r['case_id']==cid];a=next((r for r in same if r['arm']=='batch'),None);b=next((r for r in same if r['arm']=='selective'),None)
        if a and b:pairs.append({'case_id':cid,'parent':a['parent_incident'],'view':a['view'],'breadth':a['breadth'],
            'delta_tokens_selective_minus_batch':b['total_tokens']-a['total_tokens'],'delta_cost_selective_minus_batch':b['known_cost_usd']-a['known_cost_usd'],
            'delta_seconds_selective_minus_batch':b['seconds']-a['seconds'],'batch_state':a['state'],'selective_state':b['state'],'quality_delta':None})
    write_csv(out/'paired-deltas.csv',pairs)
    native_rows=[]
    for cid in sorted({t['independent_incident_id'] for t in truth.values()}):
        t=next(t for t in truth.values() if t['independent_incident_id']==cid and t['view']=='original')
        native=json.loads((study/'private'/cid/'k8sgpt-native.json').read_text())
        explain_path=study/'private'/cid/'k8sgpt-explain.json'
        explanation=json.loads(explain_path.read_text()) if explain_path.exists() else {'status':'NOT_EXECUTED'}
        name=t['target']['pod'];prefix='rca-lab/'+name
        detected=[r for r in (native.get('parsed') or {}).get('results',[]) if r.get('name')==prefix or r.get('name','').startswith(prefix+'/')]
        signal=t['assigned_cause'] in ('application_error','route_error','mixed_route_error') or (t['assigned_cause']=='auxiliary_error' and t['trial']['logging']=='endpoint')
        coverage=('execution_failed' if native['status']!='executed' else 'in_scope_finding_present' if detected else 'in_scope_not_detected' if signal else 'no_expected_keyword_signal')
        native_rows.append({'independent_incident_id':cid,'scenario':t['assigned_cause'],'logging':t['trial']['logging'],
            'load_interval':t['trial']['load_interval_seconds'],'version':'v0.4.41','native_scan_status':native['status'],
            'target_findings':len(detected),'syntactic_signal_expected':signal,'coverage_state':coverage,
            'native_explain_status':explanation['status'],'explain_requests':explanation.get('requests',0),
            'known_explain_cost_usd':explanation.get('known_cost_usd',0),'explain_seconds':explanation.get('seconds'),
            'unsupported_components':'kernel TCP-attempt destinations; runtime Prometheus metric correlation',
            'diagnosis_correctness':'NOT_HUMAN_EVALUATED','misdiagnosis':'NOT_HUMAN_EVALUATED','appropriate_abstention':'NOT_HUMAN_EVALUATED'})
    write_csv(out/'k8sgpt-native.csv',native_rows)
    write_new(out/'k8sgpt-scope.json',{'version':'v0.4.41','default_scan':'core analyzers plus Log, no explain; unfiltered global findings preserved',
        'explain':'Pod,Service,Deployment,ReplicaSet,Log over the whole lab namespace; no cache, same external model/provider; native prompt/output retained',
        'scope_not_accuracy':'Coverage states describe native target finding presence. A keyword finding is not a correct cause, and absence is not calibrated abstention.',
        'out_of_scope':['Kernel-level TCP-attempt evidence','Application runtime metric correlation through built-in Prometheus integration'],
        'in_scope_not_detected':'Expected error/exception/fail log signal or supported resource state, but no matching target finding; never combined with out-of-scope denominator',
        'misdiagnosis_and_appropriate_abstention':'Require actual human review of native explanation; left ungraded',
        'unsupported_case_comparison':'Our methods do not get native output. K8sGPT does not get private truth or our preprocessed evidence.',
        'positive_control':'development/k8sgpt-positive-control.json','primary_sources':'development/preflight.json'})
    packets=[];mapping=[]
    for folder in study.glob('runs-*'):
        for file in sorted(folder.glob('*.json')):
            if file.name in ('schedule.json','completion.json'):continue
            r=json.loads(file.read_text());cid=r['case_id'];rid=digest('review:'+r['run_id'])[:16]
            packet={'review_id':rid,'incident':cases[cid]['incident'],'shown_evidence':[restore_evidence(e,cases[cid]['incident']) for e in r['result']['shown_evidence']],
                'answer':r['result']['answer'],'accepted_output':r['result']['state']=='accepted','error_is_not_abstention':r['result']['state']!='accepted',
                'scores':{k:None for k in RUBRIC if k!='output_format'},'claim_ratings':[],'reviewer':None,'rationale':None}
            packets.append(packet);mapping.append({'review_id':rid,'run_id':r['run_id'],'arm':r['arm'],'case_id':cid,'repeat':r['repeat']})
    import random
    random.Random(2910294).shuffle(packets)
    write_new(out/'independent-review-packet.json',{'status':'unrated','not_guaranteed_blind':True,'rubric':RUBRIC,'packets':packets})
    write_new(study/'private/review-mapping.json',mapping)
    write_new(study/'private/reviewer-truth.json',[{'review_id':m['review_id'],'truth':truth[m['case_id']]} for m in mapping])
    summary={'at':now(),'independent_captures':20,'llm_repeats':1,'runs':len(rows),'methods':methods,'quality':'NOT_EVALUATED_BY_HUMANS',
        'tokens':sum(r['total_tokens'] for r in rows),'known_cost_usd':sum(r['known_cost_usd'] for r in rows),'failures':len(failures),
        'native_explain_requests':sum(r['explain_requests'] for r in native_rows),'native_explain_known_cost_usd':sum(r['known_explain_cost_usd'] for r in native_rows),
        'baseline_scope':'destination allowlist only, not general RCA','native_comparison_scope':'K8sGPT live Kubernetes analyzer access differs from frozen Agent inputs; not pooled'}
    write_new(out/'summary.json',summary)
    lines=['# paper-next-v1 — 새 독립 사건 평가','',f"새 독립 수집 20건, 각 사건의 작은/주변 포함 증거는 종속 비교 조건이다. LLM 반복은 사건·방식·증거 조건당 1회. 기록된 조사 {len(rows)}건, 최종 실패 {len(failures)}건.",
        '', '**진단 품질은 독립 사람 채점 전 미평가다. 아래 수치는 실패를 포함한 실제 사용량이며, 정확도 유지나 우월성을 입증하지 않는다.**','',
        '| 조건 | 증거 규모 | 방식 | 조사 | 평균 토큰 | 총 비용 USD | 평균 초 | 수정 호출 | 실패 |','|---|---|---|---:|---:|---:|---:|---:|---:|']
    for g in methods:lines.append(f"| {g['view']} | {g['breadth']} | {g['arm']} | {g['investigations']} | {g['mean_tokens']:.1f} | {g['known_cost_usd']:.6f} | {g['mean_seconds']:.1f} | {g['repair_calls']} | {g['failures']} |")
    lines+=['','단순 목적지 기준선은 정상 목적지에서 발생하는 애플리케이션 오류나 비핵심 보조 통신의 서비스 영향까지 판단하지 않는다. 이는 해당 기준선의 정의된 범위이며 일반 RCA 정확도와 같은 지표로 합산하지 않는다.',
        '', 'K8sGPT 원본은 private/<occurrence>/k8sgpt-native.json에 보존한다. analyzer 범위 밖과 범위 내 미감지를 구분해야 하며 사람 채점 없이 오진/적절한 보류를 자동 확정하지 않는다.',
        '', '공유 클러스터 온라인 Tetragon·정책·추가 요약기·서비스 영향의 인과적 오버헤드는 미측정이다.','']
    (out/'SUMMARY.md').write_text('\n'.join(lines))
    return summary
