"""Recompute frozen outcomes from public response traces; no semantic grading."""
import csv
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

from research.evidence import digest
from research.capture import write_new
from research.spec import ARMS, SCHEMA
from rca.common import now


def write_csv(path, rows):
    with path.open('x', newline='') as f:
        if rows:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def bad_strings(value, path='$'):
    """Describe output-contract violations, never repair or regrade old answers."""
    if isinstance(value,dict):
        result=[]
        for k,v in value.items():result+=bad_strings(v,path+'.'+k)
        return result
    if isinstance(value,list):
        result=[]
        for i,v in enumerate(value):result+=bad_strings(v,f'{path}[{i}]')
        return result
    if value is None:return [{'path':path,'type':'null'}]
    if isinstance(value,str) and len(value)>2000:return [{'path':path,'type':'string_length','length':len(value)}]
    return []


def type_violations(value, schema=SCHEMA, path='$'):
    expected={'object':dict,'array':list,'string':str}[schema['type']]
    if not isinstance(value,expected):return [{'path':path,'expected':schema['type'],'actual':type(value).__name__}]
    if isinstance(value,dict):return [v for k,s in schema['properties'].items() if k in value for v in type_violations(value[k],s,path+'.'+k)]
    if isinstance(value,list):return [v for i,x in enumerate(value) for v in type_violations(x,schema['items'],path+f'[{i}]')]
    return []


def nested_ids(value):
    if isinstance(value,dict):return ({value['evidence_id']} if isinstance(value.get('evidence_id'),str) else set()).union(*(nested_ids(v) for v in value.values()))
    if isinstance(value,list):return set().union(*(nested_ids(v) for v in value))
    return set()


def read_runs(study):
    truth={t['case_id']:t for t in json.loads((study/'private/truth.json').read_text())['cases']}
    rows=[];failures=[];queries=[];sources={}
    for path in sorted(study.glob('runs-*/*.json')):
        if path.name in ('completion.json','schedule.json'):continue
        run=json.loads(path.read_text());r=run['result'];t=truth[run['case_id']]
        trace_path=path.with_suffix('.jsonl');raw=trace_path.read_bytes()
        events=[json.loads(x) for x in raw.decode().splitlines()]
        response=[x for x in events if x['type']=='response'];requests=[x for x in events if x['type']=='request']
        if len(response)!=len(r['attempts']):raise ValueError('trace/terminal attempt mismatch')
        for x,a in zip(response,r['attempts']):
            if x['response'].get('usage',{})!=a['usage']:raise ValueError('trace/terminal usage mismatch')
        usage=[x['response'].get('usage',{}) for x in response]
        costs=[u.get('cost') for u in usage]
        known_cost=sum(c for c in costs if type(c) in (float,int))
        inp=sum(u.get('prompt_tokens',0) for u in usage);out=sum(u.get('completion_tokens',0) for u in usage)
        repairs=[x for x in response if x['phase']=='repair']
        repair_tokens=sum(x['response'].get('usage',{}).get('prompt_tokens',0)+x['response'].get('usage',{}).get('completion_tokens',0) for x in repairs)
        q=r['retrievals'];cited={eid for claim in (r.get('answer') or {}).get('claims',[]) for eid in claim['evidence_ids']}
        uncited=[e['evidence_id'] for e in r['shown_evidence'] if e['evidence_id'] not in cited]
        row={'run_id':run['run_id'],'case_id':run['case_id'],'parent_incident':t['independent_incident_id'],
            'group':'primary' if run['arm'] in ARMS else 'ablation','arm':run['arm'],'view':t['view'],
            'assigned_cause':t['assigned_cause'],'repeat':run['repeat'],'state':r['state'],'format_outcome':r['format_outcome'],
            'prompt_tokens':inp,'output_tokens':out,'total_tokens':inp+out,'known_cost_usd':known_cost,
            'missing_cost_responses':sum(type(c) not in (float,int) for c in costs),'unreturned_requests':len(requests)-len(response),
            'seconds':r['duration_seconds'],'requests':len(requests),'repair_calls':len(repairs),'repair_tokens_subset':repair_tokens,
            'retrieval_requests':len(q),'duplicate_requests':sum(x['duplicate'] for x in q),
            'executed_duplicate_requests':sum(x['duplicate'] and x['executed'] for x in q),
            'shown_evidence_count':len(r['shown_evidence']),'uncited_evidence_count':len(uncited),
            'catalog_source_count':len(r['source_states']),'all_catalog_sources_retrieved':all(v!='not_retrieved' for v in r['source_states'].values()),
            'new_evidence_bytes':sum(x['byte_attribution']['new_evidence_bytes'] for x in requests),
            'repeated_evidence_bytes':sum(x['byte_attribution']['repeated_evidence_bytes'] for x in requests),
            'diagnostic_quality':'NOT_EVALUATED_BY_HUMANS','error':r['error']}
        rows.append(row)
        queries.append({'run_id':run['run_id'],'retrievals':q,'source_states':r['source_states'],
            'uncited_evidence_ids':uncited,'interpretation':'Uncited evidence can support exclusion/context. This proxy does not prove an unnecessary query.'})
        if r['error']:
            attempts=[]
            for x in response:
                choices=x['response'].get('choices',[]);m=choices[0].get('message',{}) if choices else {}
                calls=m.get('tool_calls',[]);value=None
                try:value=json.loads(calls[0]['function']['arguments'] if calls else m.get('content',''))
                except (ValueError,KeyError,IndexError,TypeError):pass
                top_ids={e['evidence_id'] for e in r['shown_evidence']};visible=nested_ids(r['shown_evidence'])
                unknown=[i for c in (value or {}).get('claims',[]) for i in c.get('evidence_ids',[]) if i not in top_ids] if isinstance(value,dict) else []
                attempts.append({'call':x['call'],'phase':x['phase'],'finish_reason':choices[0].get('finish_reason') if choices else None,
                    'null_or_overlong_fields':bad_strings(value),'schema_type_violations':type_violations(value),
                    'citations_rejected_by_old_top_level_registry':unknown,
                    'rejected_but_present_in_nested_visible_evidence':[i for i in unknown if i in visible],
                    'usage':x['response'].get('usage',{})})
            failures.append({'run_id':run['run_id'],'case_id':run['case_id'],'arm':run['arm'],'view':t['view'],
                'error':r['error'],'validation_errors':[x for x in events if x['type']=='validation_error'],
                'attempts':attempts,'source_trace':str(trace_path),'replacement_or_rerun':False})
        sources[str(path)]=digest(path.read_bytes());sources[str(trace_path)]=digest(raw)
    return rows,failures,queries,sources


def aggregate(rows, keys):
    grouped=defaultdict(list)
    for r in rows:grouped[tuple(r[k] for k in keys)].append(r)
    out=[]
    for values,rs in sorted(grouped.items()):
        row=dict(zip(keys,values));row.update(investigations=len(rs),unique_parent_incidents=len({r['parent_incident'] for r in rs}),
            failures=sum(r['state']!='accepted' for r in rs),total_tokens=sum(r['total_tokens'] for r in rs),
            mean_tokens=st.mean(r['total_tokens'] for r in rs),median_tokens=st.median(r['total_tokens'] for r in rs),
            known_cost_usd=sum(r['known_cost_usd'] for r in rs),mean_seconds=st.mean(r['seconds'] for r in rs),
            median_seconds=st.median(r['seconds'] for r in rs),requests=sum(r['requests'] for r in rs),
            repair_calls=sum(r['repair_calls'] for r in rs),repair_tokens_subset=sum(r['repair_tokens_subset'] for r in rs),
            duplicate_requests=sum(r['duplicate_requests'] for r in rs),
            executed_duplicate_requests=sum(r['executed_duplicate_requests'] for r in rs),
            all_catalog_sources_retrieved=sum(r['all_catalog_sources_retrieved'] for r in rs),
            mean_shown_evidence=st.mean(r['shown_evidence_count'] for r in rs),
            uncited_evidence_count=sum(r['uncited_evidence_count'] for r in rs),
            missing_usage_requests=sum(r['unreturned_requests']+r['missing_cost_responses'] for r in rs),
            diagnostic_quality='NOT_EVALUATED_BY_HUMANS')
        out.append(row)
    return out


def analyze(study,out):
    out.mkdir(parents=True,exist_ok=False)
    # All old artifacts, including failures/protocol, are immutable source inputs.
    initial={str(p.relative_to(study)):digest(p.read_bytes()) for p in study.rglob('*') if p.is_file()}
    rows,failures,queries,sources=read_runs(study)
    methods=aggregate(rows,['group','view','arm'])
    incidents=aggregate(rows,['group','view','case_id','parent_incident','assigned_cause','arm'])
    for name,data in [('runs.csv',rows),('methods.csv',methods),('incidents.csv',incidents),
        ('primary.csv',[r for r in methods if r['group']=='primary']),('ablations.csv',[r for r in methods if r['group']=='ablation'])]:write_csv(out/name,data)
    pairs=[]
    for view in {r['view'] for r in rows}:
        for cid in {r['case_id'] for r in rows if r['view']==view}:
            index={r['arm']:r for r in incidents if r['case_id']==cid}
            for a,b,label in [('batch-no-ebpf','batch-ebpf','ebpf_in_batch'),('selective-no-ebpf','selective-ebpf','ebpf_in_selective'),
                 ('batch-no-ebpf','selective-no-ebpf','selection_without_ebpf'),('batch-ebpf','selective-ebpf','selection_with_ebpf')]+[
                 ('selective-ebpf','selective-ebpf-no-'+component,'ablation_'+component) for component in ['compression','dedup','stop-guidance']]:
                if a in index and b in index:
                    x,y=index[a],index[b]
                    pairs.append({'case_id':cid,'view':view,'comparison':label,'reference':a,'comparison_arm':b,
                        'reference_repeats':x['investigations'],'comparison_repeats':y['investigations'],
                        'delta_mean_tokens':y['mean_tokens']-x['mean_tokens'],
                        'delta_mean_seconds':y['mean_seconds']-x['mean_seconds'],
                        'delta_mean_cost_usd':y['known_cost_usd']/y['investigations']-x['known_cost_usd']/x['investigations'],
                        'quality_delta':None})
    write_csv(out/'paired-incident-deltas.csv',pairs)
    write_new(out/'failure-analysis.json',failures);write_new(out/'retrieval-analysis.json',queries)
    write_new(out/'source-integrity.json',{'at':now(),'study':str(study),'sha256':initial,'raw_run_sources':sources})
    summary={'at':now(),'runs':len(rows),'independent_captures':len({r['parent_incident'] for r in rows if r['view']=='original'}),
        'dependent_views':len({r['case_id'] for r in rows if r['view']!='original'}),'llm_repeats_per_case_arm':2,
        'failures':len(failures),'requests':sum(r['requests'] for r in rows),'total_tokens':sum(r['total_tokens'] for r in rows),
        'cost_usd':sum(r['known_cost_usd'] for r in rows),'methods':methods,'quality':'NOT_EVALUATED_BY_HUMANS',
        'unnecessary_queries':'Not established by citation absence; duplicate executions and uncited snapshots reported as separate proxies.'}
    write_new(out/'summary.json',summary)
    lines=['# paper-clock-v3 원자료 재분석','',f"독립 수집 {summary['independent_captures']}건, 종속 변형 {summary['dependent_views']}건, 사건·방식당 LLM 2회. 총 {len(rows)}개 실행이며 최종 실패 {len(failures)}건을 포함한다.",
        '',f"원본 response usage 재계산: {summary['requests']} API 요청, {summary['total_tokens']:,} tokens, ${summary['cost_usd']:.8f}. 기존 중단 배치 비용과 합산하지 않았다.",
        '', '**사람의 진단 품질 채점은 미평가다. 형식 통과율을 정확도로 해석하지 않는다.**','']
    for group,title in [('primary','주 비교군'),('ablation','구성요소 제거 실험')]:
        lines += ['## '+title+' — 독립 수집만','', '| 방식 | 조사 수 | 평균 토큰 | 비용 합계 USD | 평균 초 | 수정 호출 | 최종 실패 |','|---|---:|---:|---:|---:|---:|---:|']
        for g in methods:
            if g['group']==group and g['view']=='original':lines.append(f"| {g['arm']} | {g['investigations']} | {g['mean_tokens']:.1f} | {g['known_cost_usd']:.6f} | {g['mean_seconds']:.1f} | {g['repair_calls']} | {g['failures']} |")
        lines+=['']
    lines+=['## 실패 및 조회 분석','']
    for f in failures:
        fields=sorted({v['path']+':'+v['type'] for a in f['attempts'] for v in a['null_or_overlong_fields']}|{v['path']+':expected '+v['expected']+', got '+v['actual'] for a in f['attempts'] for v in a['schema_type_violations']})
        lines.append(f"- `{f['run_id']}` / {f['arm']} / {f['view']}: `{f['error']}`. 관측된 형식 문제: {', '.join(fields) or 'validation_errors 참조'}.")
        nested=sorted({i for a in f['attempts'] for i in a['rejected_but_present_in_nested_visible_evidence']})
        if nested:lines.append('  실제 제공된 중첩 증거 ID를 최상위 ID만 인정하는 검증기가 거부함: '+', '.join(nested)+'. 이는 과거 사건을 올바르게 해석했다는 판정이 아니며, 기존 실패 결과도 변경하지 않는다.')
    lines+=['',f"중복 조회 요청 {sum(r['duplicate_requests'] for r in rows)}회, 실제 중복 실행 {sum(r['executed_duplicate_requests'] for r in rows)}회. 인용되지 않은 증거 {sum(r['uncited_evidence_count'] for r in rows)}개는 불필요 조회의 확정 판정이 아니다.",
        '재조회 도구는 고정 스냅샷을 반환하므로 실제 중복 실행에서는 새 관측이 추가되지 않는다. 미인용 증거는 대안 배제나 맥락 확인에 쓰였을 수 있어 동일하게 취급하지 않는다.',
        '', '## 해석 범위','', '종속 변형은 methods.csv에서 별도로 집계한다. incidents.csv와 paired-incident-deltas.csv는 동일 사건 반복을 평균한 뒤 비교한다. 여섯 독립 수집에서 통계적 우월성이나 일반 RCA 정확도를 주장하지 않는다.',
        '', '선택 조회와 eBPF에 불리한 차이도 그대로 남긴다. 원자료·프로토콜·실패를 수정하지 않았다. 온라인 오버헤드는 미측정이며 진단 품질과 비용의 결합 평가는 독립 채점 이후에만 가능하다.','']
    original={g['arm']:g for g in methods if g['view']=='original'}
    if {'batch-ebpf','selective-ebpf','selective-ebpf-no-compression','selective-ebpf-no-dedup','selective-ebpf-no-stop-guidance'}<=set(original):
        s=original['selective-ebpf']['mean_tokens'];b=original['batch-ebpf']['mean_tokens'];full=original['selective-ebpf-no-compression']['mean_tokens']
        lines+=['## 후속 연구를 결정한 관측','',
            f'- eBPF 포함 선택 조회는 일괄 대비 평균 토큰 {(s/b-1)*100:.2f}% 증가했다. 작은 증거 집합에서 선택 조회의 비용 우위는 관측되지 않았다.',
            f'- 압축을 제거하면 평균 토큰이 {(full/s-1)*100:.2f}% 증가했다. 압축 버전은 비압축 버전 대비 {(1-s/full)*100:.2f}% 적었지만 진단 품질 유지는 미평가다.',
            f"- 중복 방지 제거는 평균 {original['selective-ebpf-no-dedup']['mean_tokens']:.1f} tokens로 기본 {s:.1f}보다 낮았다. 이 표본에서 중복 방지의 전체 토큰 절감 주장은 지지되지 않는다.",
            f"- 종료 안내 제거는 평균 {original['selective-ebpf-no-stop-guidance']['mean_tokens']:.1f} tokens였다. 단일 요인 제거 결과이며 작은 반복 표본의 변동을 일반적 효과로 해석하지 않는다.",
            '- 다음 버전은 새 독립 발생, 주변 telemetry 증가, 애플리케이션 오류와 비핵심 보조 통신, 중첩 인용 등록 수정에 집중한다. 이전 결과를 성공으로 교체하지 않는다.','']
    (out/'SUMMARY.md').write_text('\n'.join(lines))
    for name,h in initial.items():
        if digest((study/name).read_bytes())!=h:raise ValueError('old study changed during analysis')
    return summary
