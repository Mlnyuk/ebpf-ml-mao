/* Existing saved records only. No fetch, API capability probe, timer or diagnosis. */
window.RCABooth = function(D) {
  'use strict';
  const node=(tag,text,parent,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;if(parent)parent.append(e);return e;};
  const raw=(label,value,parent)=>{const d=node('details',undefined,parent);node('summary',label,d);node('pre',typeof value==='string'?value:JSON.stringify(value,null,2),d);return d;};
  const b=(label,parent,action,secondary=false)=>{const e=node('button',label,parent,secondary?'secondary':'');e.type='button';e.onclick=action;return e;};
  const message=line=>{try{return JSON.parse(line.slice(line.indexOf(' ')+1)).message||line;}catch{return line;}};
  const key=e=>e.source_key||(e.tool==='get_metrics'?('metrics_'+('working_set_bytes' in (e.series||{})?'memory':'cpu')):e.tool);
  const title={get_workload_status:'서비스 설정 확인',get_k8s_events:'실행 상태 기록 확인',get_logs:'로그 확인',metrics_cpu:'CPU 사용 기록 확인',metrics_memory:'메모리 사용 기록 확인',get_ebpf_summary:'연결 시도 기록 확인'};
  const safeDeclaration=e=>{try{return JSON.parse(e?.data?.declared_dependency||'{}');}catch{return {};}};
  document.body.classList.add('booth-mode');document.title='어디로 연결을 시도했을까? · RCA 저장 기록 시연';
  const root=node('div',undefined,document.body);root.id='booth';
  const top=node('div',undefined,root,'booth-top');node('div','장애의 원인을 찾는 AI',top,'booth-brand');
  const actions=node('div',undefined,top,'booth-top-actions');node('span','저장된 조사 기록 재생',actions,'booth-badge');
  const reset=b('처음으로',actions,()=>show(0),true);reset.id='demo-reset';
  const progress=node('ol',undefined,root,'booth-progress');progress.setAttribute('aria-label','시연 순서');
  const tabs=['1  장애 상황','2  AI의 조사','3  판단 근거'].map(t=>node('li',t,progress));
  const stage=node('section',undefined,root);stage.id='demo-stage';stage.setAttribute('aria-live','polite');
  const config=D.demo;
  const run=D.runs?.find(r=>r.run_id===config?.primary_run_id);
  const baseline=D.runs?.find(r=>r.run_id===config?.baseline_run_id);
  const incident=D.cases?.find(c=>c.case_id===run?.case_id)?.incident;
  const evidence=run?.evidence||[];
  const byID=new Map(evidence.map(e=>[e.evidence_id,e]));
  const log=byID.get(config?.log_evidence_id);
  const net=evidence.find(e=>e.tool==='get_ebpf_summary');
  const settings=evidence.find(e=>e.tool==='get_workload_status');
  const declaration=safeDeclaration(settings);
  const attempts=net?.network?.tcp_connect_attempts||[];
  const claim=run?.answer?.claims?.[config?.claim_index];
  const line=log?.lines?.[config?.log_line_index];
  // An arbitrary ?demo=1 must report missing exhibit data, not invent a case.
  if(!run||!incident||!line||!claim||!declaration.expected_port||!attempts.length||claim.evidence_ids.some(id=>!byID.has(id))){
    reset.disabled=true;node('h1','시연에 필요한 저장 기록이 부족합니다.',stage);
    node('p','대표 사건, 실제 로그, 연결 시도, 또는 인용 증거를 찾지 못했습니다. 예시 데이터로 대체하지 않았습니다.',stage,'lead');
    node('a','기존 재생 화면 열기',stage).href='?demo=0';return;
  }
  const footer=node('footer',undefined,root,'booth-footer');
  node('p','인터넷·API 키 없이 재생합니다. 새 AI 분석이나 클러스터 조작은 실행하지 않습니다.',footer);
  const audit=raw('사건·실행 기록과 선정 기준',{
    incident,case_id:run.case_id,primary_run_id:run.run_id,baseline_run_id:baseline?.run_id||null,
    selection_reason:config.selection_reason,scope:config.scope,
    evidence_note:'AI에 실제 제공된 증거 원문입니다. eBPF 자료는 연결 시도 요약이며 커널 원시 이벤트 전체는 포함하지 않습니다.'
  },footer);
  const link=node('a','전체 조사 기록 보기',footer);link.href='?demo=0';
  function heading(text){const h=node('h1',text,stage);h.tabIndex=-1;return h;}
  function proof(e,parent){
    if(!e){node('p','해당 조회의 증거 원문이 없습니다.',parent);return;}
    const d=raw('인용된 증거 원문 펼치기',e,parent);d.dataset.evidence=e.evidence_id;
    const pre=d.querySelector('pre'),needle=e.tool==='get_ebpf_summary'?'"destination_port"':'"declared_dependency"';
    const lines=pre.textContent.split('\n'),index=lines.findIndex(line=>line.includes(needle));
    if(index>=0){
      pre.replaceChildren();lines.forEach((line,i)=>{node(i===index?'mark':'span',line+(i<lines.length-1?'\n':''),pre);});
      d.addEventListener('toggle',()=>{if(d.open)pre.scrollTop=Math.max(0,(index-3)*(parseFloat(getComputedStyle(pre).lineHeight)||19.5));});
    }
  }
  function fact(e){
    if(!e)return '조회에 대응하는 저장 증거가 없습니다.';
    if(e.availability!=='available')return '자료를 확보하지 못했습니다. 정상이라는 뜻은 아닙니다.';
    if(e.tool==='get_workload_status'){const dep=safeDeclaration(e);return dep.expected_port?`설정에 적힌 목적지는 ${dep.expected_ip}:${dep.expected_port}입니다.`:'저장된 서비스 실행 상태를 확인했습니다.';}
    if(e.tool==='get_logs')return `“${message(e.lines.find(l=>l.includes('status=503'))||e.lines[0]||'')}”가 남았습니다.`;
    if(e.tool==='get_k8s_events')return `실행 관련 이벤트 ${e.events?.length??0}건이 저장돼 있습니다. 요청 성공 여부는 별도입니다.`;
    if(e.tool==='get_ebpf_summary')return (e.network?.tcp_connect_attempts||[]).map(a=>`${a.destination_ip}:${a.destination_port}로 ${a.attempts}회 연결을 시도했습니다.`).join(' ');
    if(e.tool==='get_metrics'){
      const s=e.series?.usage_cores||e.series?.working_set_bytes;
      if(!s)return '저장된 자원 표본을 확인했습니다. 표본 사이 상태는 알 수 없습니다.';
      return `${e.series.usage_cores?'CPU':'메모리'} 표본 ${s.samples??s.points?.length??0}개를 확인했습니다. 표본 사이 변화는 알 수 없습니다.`;
    }
    return '저장된 관측 자료를 확인했습니다.';
  }
  function show(step){
    root.querySelectorAll('details').forEach(d=>d.open=false);stage.replaceChildren();
    tabs.forEach((t,i)=>{if(i===step)t.setAttribute('aria-current','step');else t.removeAttribute('aria-current');});
    if(step===0){
      heading('서비스 요청이 실패했습니다. 어디서 문제가 생겼을까요?');
      node('p','앱의 기록에는 실패만 남았습니다. 어느 주소로 연결하려 했는지는 보이지 않습니다.',stage,'lead');
      const card=node('div',undefined,stage,'booth-card log-card');
      node('div','실제 애플리케이션 로그 · message 원문',card,'eyebrow');node('code',message(line),card,'log-line');
      node('p','503: 서비스 요청을 처리하지 못했다는 응답입니다.',card);
      raw('시간이 포함된 로그 한 줄 원문',line,card);
      node('p','Kubernetes는 앱을 실행·관리하는 시스템입니다. eBPF는 운영체제 안에서 연결 시도 같은 동작을 관찰합니다.',stage,'note');
      const a=node('div',undefined,stage,'booth-actions');b('AI의 조사 보기',a,()=>show(1)).id='demo-investigate';
      node('span','저장된 AI가 무엇을 조회했는지 살펴봅니다.',a,'note');
    }else if(step===1){
      heading('AI는 어떤 자료를 확인했을까요?');
      node('p','아래는 실제 저장된 조회 순서입니다. 각 설명은 그 자료에서 확인한 사실입니다.',stage,'lead');
      const list=node('ol',undefined,stage,'timeline');list.id='demo-timeline';
      run.retrievals.forEach((r,i)=>{
        const e=evidence.find(e=>key(e)===r.source),li=node('li',undefined,list,r.source==='get_ebpf_summary'?'network-step':'');li.dataset.source=r.source;
        node('div',String(i+1).padStart(2,'0'),li,'number');node('h3',title[r.source]||'자료 조회',li);
        node('p',r.executed===false?'이미 읽은 자료를 재사용했습니다.':fact(e),li);
      });
      const batches=[];
      for(const event of run.trace||[])if(event.type==='response')for(const call of event.response?.choices?.[0]?.message?.tool_calls||[]){
        if(call.function?.name==='inspect')try{batches.push(JSON.parse(call.function.arguments).sources||[]);}catch{/* raw trace remains available */}
      }
      if(batches.length===1)node('p',`AI가 한 번의 요청에서 ${batches[0].length}개 자료를 함께 선택했습니다. 단계마다 AI를 새로 호출한 것은 아닙니다.`,stage,'note');
      const finding=node('div',undefined,stage,'finding');node('div','저장된 AI의 추정 원인 · 답변 첫 문장 발췌',finding,'eyebrow');
      const cause=run.answer.confirmed_cause||run.answer.hypotheses?.[0]||'원인을 특정하지 못했습니다.';
      const stop=cause.indexOf('. ');node('p',stop<0?cause:cause.slice(0,stop+1),finding);
      const a=node('div',undefined,stage,'booth-actions');b('판단 근거 열기',a,()=>show(2)).id='demo-evidence';
      raw('실제 도구 선택 응답·조회 순서', {retrievals:run.retrievals,selection_responses:(run.trace||[]).filter(t=>t.type==='response')},stage);
    }else{
      heading('설정과 실제 연결 시도를 비교해 보세요');
      const finding=node('div',undefined,stage,'finding');node('div','저장된 AI의 판단 · 인용된 주장 원문',finding,'eyebrow');node('p',claim.text,finding);
      const ports=node('div',undefined,stage,'ports');
      const expected=node('article',undefined,ports,'booth-card port-card');expected.id='demo-expected';
      node('div','설정에 적힌 포트',expected,'eyebrow');node('div',String(declaration.expected_port),expected,'port-value');
      node('div',declaration.expected_ip,expected,'address');node('p','Pod에 선언된 의존성 · 서비스 주소 스냅샷',expected,'note');proof(settings,expected);
      const observed=node('article',undefined,ports,'booth-card port-card observed');observed.id='demo-observed';
      node('div','실제로 연결을 시도한 포트',observed,'eyebrow');
      attempts.forEach(a=>{node('div',String(a.destination_port),observed,'port-value');node('div',`${a.destination_ip} · ${a.attempts}회 시도`,observed,'address');});
      node('p','eBPF 연결 시도 요약에서 발췌',observed,'note');proof(net,observed);
      node('div','연결을 시도한 목적지는 확인했습니다. 연결 성공·실패와 잘못된 설정의 출처는 이 기록만으로 확정할 수 없습니다.',stage,'scope-note');
      node('h2',baseline?'같은 사건, eBPF 자료를 주었을 때와 빼었을 때':'로그와 eBPF가 각각 알려준 정보',stage,'comparison-title');
      const comparison=node('div',undefined,stage,'comparison');comparison.id='demo-comparison';
      if(baseline){
        const a=node('article',undefined,comparison);node('h3','eBPF 제외 · '+(baseline.answer?.status==='inconclusive'?'AI는 원인을 보류':'저장된 AI 판단'),a);
        const uncertain=baseline.answer?.unknowns?.find(s=>s.includes('목적지'))||baseline.answer?.unknowns?.[0]||baseline.answer?.confirmed_cause||'저장된 설명 없음';
        node('blockquote',uncertain,a);node('p','앱 로그·설정·이벤트·자원 기록은 제공했습니다.',a,'note');raw('저장된 AI 답변 전체',baseline.answer,a);
        const z=node('article',undefined,comparison);node('h3','eBPF 포함 · 저장된 AI 판단',z);node('blockquote',claim.text,z);
        node('p','같은 사건·같은 선택 조회 방식·같은 반복 번호의 기록입니다.',z,'note');raw('저장된 AI 답변 전체',run.answer,z);
      }else{
        const a=node('article',undefined,comparison);node('h3','로그에 남은 정보',a);node('blockquote',message(line),a);
        const z=node('article',undefined,comparison);node('h3','eBPF가 추가한 정보',z);node('blockquote',fact(net),z);
        node('p','같은 사건의 eBPF 제외 실행이 없어 AI 결과 비교는 제공하지 않습니다.',stage,'note');
      }
      node('p','이 한 사례의 저장 답변 비교입니다. 전체 진단 정확도가 검증됐다는 의미는 아닙니다.',stage,'note');
    }
    stage.querySelector('h1')?.focus({preventScroll:true});window.scrollTo(0,0);
  }
  show(0);
};
