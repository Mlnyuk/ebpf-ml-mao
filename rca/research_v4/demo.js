/* Offline investigation console. Observations are derived from saved records. */
window.RCABooth = function(D) {
  'use strict';
  if(window.RCABoothCleanup)window.RCABoothCleanup();
  const $=(tag,text,parent,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;if(parent)parent.append(e);return e;};
  const button=(text,parent,fn,cls='')=>{const e=$('button',text,parent,cls);e.type='button';e.onclick=fn;return e;};
  const mono=(text,parent,cls='')=>$('span',text,parent,'mono '+cls);
  const cfg=D.demo,run=D.runs?.find(r=>r.run_id===cfg?.primary_run_id),baseline=D.runs?.find(r=>r.run_id===cfg?.baseline_run_id);
  const incident=D.cases?.find(c=>c.case_id===run?.case_id)?.incident,evidence=run?.evidence||[],byID=new Map(evidence.map(e=>[e.evidence_id,e]));
  const log=byID.get(cfg?.log_evidence_id),net=evidence.find(e=>e.tool==='get_ebpf_summary'),settings=evidence.find(e=>e.tool==='get_workload_status');
  let dep={};try{dep=JSON.parse(settings?.data?.declared_dependency||'{}');}catch{}
  const attempts=net?.network?.tcp_connect_attempts||[],claim=run?.answer?.claims?.[cfg?.claim_index],line=log?.lines?.[cfg?.log_line_index];
  const key=e=>e.source_key||(e.tool==='get_metrics'?('metrics_'+('working_set_bytes' in (e.series||{})?'memory':'cpu')):e.tool);
  const titles={get_workload_status:'서비스 설정',get_k8s_events:'Kubernetes 이벤트',get_logs:'애플리케이션 로그',metrics_cpu:'CPU 표본',metrics_memory:'메모리 표본',get_ebpf_summary:'eBPF 연결 시도'};
  const symbols={get_workload_status:'◇',get_k8s_events:'▤',get_logs:'≡',metrics_cpu:'⌁',metrics_memory:'▥',get_ebpf_summary:'⇢'};
  const time=t=>String(t||'').slice(11,23),shortTime=t=>String(t||'').slice(11,19);
  function raw(label,value,parent){const d=$('details',undefined,parent,'raw');$('summary',label,d);$('pre',typeof value==='string'?value:JSON.stringify(value,null,2),d);return d;}
  function icon(name,parent){
    const paths={grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',trace:'M5 4v16 M5 7h12 M5 17h12 M17 4v6 M17 14v6',compare:'M4 5h6v14H4z M14 5h6v14h-6z',file:'M6 3h8l4 4v14H6z M14 3v5h5 M9 12h6 M9 16h6'};
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');
    const p=document.createElementNS(svg.namespaceURI,'path');p.setAttribute('d',paths[name]);svg.append(p);parent.append(svg);
  }
  document.body.classList.add('booth-mode');document.title='RCA Console · 저장 기록 재생';
  const root=$('div',undefined,document.body);root.id='booth';
  if(!run||!incident||!line||!claim||!dep.expected_port||!attempts.length||claim.evidence_ids.some(id=>!byID.has(id))){
    const stage=$('section',undefined,root,'missing');stage.id='demo-stage';$('h1','시연에 필요한 저장 기록이 부족합니다.',stage);$('p','실제 사건·로그·인용 증거를 찾지 못했습니다. 예시 데이터로 대체하지 않습니다.',stage);$('a','기존 재생 화면',stage).href='?demo=0';return;
  }
  const rows=log.lines.map((raw,index)=>{const pos=raw.indexOf(' ');let message=raw;try{message=JSON.parse(raw.slice(pos+1)).message||raw;}catch{}const status=/status=(\d+)/.exec(message)?.[1];return {raw,index,message,status,stamp:raw.slice(0,pos)};});
  const failures=rows.filter(r=>r.status&&Number(r.status)>=400),totalAttempts=attempts.reduce((n,a)=>n+a.attempts,0);
  const appName=incident.pod.replace(/-[a-z0-9]+-[a-z0-9]+$/,'');
  let mode=0,query='',activeSource='get_logs',inspector=null,returnFocus=null;
  const rail=$('nav',undefined,root,'rail');rail.setAttribute('aria-label','콘솔 탐색');
  const logo=$('div','R',rail,'logo');logo.title='RCA Console';
  const navs=[];[['grid','사건 개요',0],['trace','AI의 조사 보기',1],['compare','실행 비교',2]].forEach(([i,label,m])=>{
    const b=button('',rail,()=>render(m),'rail-button');icon(i,b);b.setAttribute('aria-label',label);b.title=label;navs.push(b);
  });
  const archive=button('',rail,()=>inspect('사건 및 저장 실행',{incident,case_id:run.case_id,run_id:run.run_id,baseline_run_id:baseline?.run_id,selection_reason:cfg.selection_reason,scope:cfg.scope}),'rail-button archive-button');icon('file',archive);archive.title='사건 원본';archive.setAttribute('aria-label','사건 원본');
  const shell=$('div',undefined,root,'console-shell');
  const top=$('header',undefined,shell,'console-top');const brand=$('div',undefined,top,'brand');$('strong','RCA',brand);$('span','CONSOLE',brand);
  const crumbs=$('div',undefined,top,'breadcrumbs');$('span','Investigations',crumbs);$('span','/',crumbs);$('span','Kubernetes',crumbs);
  const topRight=$('div',undefined,top,'top-right');$('span','저장된 조사 기록 재생',topRight,'replay-badge');mono('OFFLINE',topRight,'offline');
  const reset=button('↺  처음으로',topRight,()=>{query='';activeSource='get_logs';closeInspector();render(0);},'quiet');reset.id='demo-reset';
  const body=$('main',undefined,shell,'console-body');body.id='demo-stage';
  const heading=$('div',undefined,body,'incident-heading');const naming=$('div',undefined,heading);
  const meta=$('div',undefined,naming,'incident-path');mono(incident.namespace,meta);$('span',' / ',meta);mono(appName,meta);
  const h1=$('h1','요청 실패 · 목적지 조사',naming);h1.tabIndex=-1;
  const timebox=$('div',undefined,heading,'timebox');mono(incident.time.slice(0,10)+'  UTC',timebox);mono(shortTime(incident.window_start)+' — '+shortTime(incident.time),timebox);
  const guide=$('div',undefined,body,'guide');const guideText=$('span',undefined,guide);const guideAction=$('div',undefined,guide);
  const stats=$('div',undefined,body,'stats');
  const layout=$('div',undefined,body,'workspace');const sidebar=$('aside',undefined,layout,'source-sidebar');
  const center=$('div',undefined,layout,'center-panels');const right=$('aside',undefined,layout,'right-panels');
  const statusbar=$('footer',undefined,shell,'booth-footer');
  $('span','●',statusbar,'status-dot');$('span','저장 파일에서 읽는 중',statusbar);$('span','새 API 호출 0',statusbar,'footer-item');
  mono('1 개요   2 조사   3 비교   / 검색   R 초기화',statusbar,'shortcuts');
  raw('기록 정보',{incident,run_id:run.run_id,baseline_run_id:baseline?.run_id||null,scope:cfg.scope},statusbar);
  function panel(title,parent,tag=''){const p=$('section',undefined,parent,'panel');const head=$('div',undefined,p,'panel-head');$('h2',title,head);if(tag)mono(tag,head,'panel-tag');return p;}
  function metric(label,value,unit,accent=''){const box=$('div',undefined,stats,'stat '+accent);$('span',label,box,'stat-label');const n=$('div',undefined,box,'stat-number');$('strong',String(value),n);$('span',unit,n);}
  function fact(e){
    if(!e)return '대응하는 저장 증거 없음';if(e.availability!=='available')return '자료 미확보 · 정상 여부 미확인';
    if(e.tool==='get_workload_status')return dep.expected_ip+':'+dep.expected_port+' 선언';
    if(e.tool==='get_k8s_events')return (e.events?.length||0)+'개 이벤트 · 요청 결과와 별개';
    if(e.tool==='get_logs')return failures.length+'줄의 오류 응답 로그';
    if(e.tool==='get_ebpf_summary')return totalAttempts+'회 연결 시도 · 결과 미측정';
    const s=e.series?.usage_cores||e.series?.working_set_bytes;return s?(s.samples??s.points?.length??0)+'개 표본 · 표본 사이 상태 미확인':'저장된 자원 표본';
  }
  function inspect(title,value,needle=''){
    closeInspector();returnFocus=document.activeElement;
    inspector=$('div',undefined,root,'inspector-shade');const box=$('section',undefined,inspector,'inspector');box.setAttribute('role','dialog');box.setAttribute('aria-modal','true');box.setAttribute('aria-label',title);
    const head=$('div',undefined,box,'inspector-head');$('div',title,head);const close=button('닫기  Esc',head,closeInspector,'quiet');close.id='inspector-close';
    $('p','저장된 원문 · 읽기 전용',box,'inspector-note');const pre=$('pre',undefined,box);pre.id='inspector-json';
    const text=typeof value==='string'?value:JSON.stringify(value,null,2);text.split('\n').forEach((s,i)=>{const line=$('span',s+'\n',pre,'code-line');line.dataset.line=i+1;if(needle&&s.includes(needle))line.classList.add('code-match');});
    if(needle){const match=pre.querySelector('.code-match');if(match)pre.scrollTop=match.offsetTop-pre.offsetTop-100;}
    inspector.addEventListener('click',e=>{if(e.target===inspector)closeInspector();});close.focus();
  }
  function closeInspector(){if(inspector){inspector.remove();inspector=null;if(returnFocus?.isConnected)returnFocus.focus();returnFocus=null;}}
  function proof(e,parent){
    const d=raw('인용 원문',e,parent);d.dataset.evidence=e.evidence_id;const pre=d.querySelector('pre');
    const needle=e.tool==='get_ebpf_summary'?'"destination_port"':'"declared_dependency"';const lines=pre.textContent.split('\n'),index=lines.findIndex(s=>s.includes(needle));
    pre.replaceChildren();lines.forEach((s,i)=>$('span',s+(i<lines.length-1?'\n':''),pre,i===index?'code-match':''));
    d.addEventListener('toggle',()=>{if(d.open)pre.scrollTop=Math.max(0,(index-2)*18);});
  }
  function sourceList(){
    sidebar.replaceChildren();const listHead=$('div',undefined,sidebar,'sidebar-label');$('span','사건',listHead);mono(String(D.cases.length),listHead);
    const incidentButton=button('',sidebar,()=>render(0),'incident-row');$('span','HTTP 503',incidentButton,'error-tag');$('strong',appName,incidentButton);mono(shortTime(incident.time)+' UTC',incidentButton);
    const count=$('div',undefined,sidebar,'sidebar-label');$('span','수집 자료',count);mono(String(evidence.length),count);
    evidence.forEach(e=>{const k=key(e),b=button('',sidebar,()=>{activeSource=k;if(k==='get_logs'){render(mode);document.getElementById('log-search').focus();}else inspect(titles[k]||e.tool,e,k==='get_ebpf_summary'?'"destination_port"':'');},'source-row'+(activeSource===k?' selected':''));
      $('span',symbols[k]||'◇',b,'source-symbol');$('span',titles[k]||e.tool,b);$('span',e.availability==='available'?'●':'○',b,'source-health');b.title='저장된 자료 열기';});
    const context=$('div',undefined,sidebar,'target-context');$('div','조사 대상',context,'sidebar-label');[['Node',incident.node],['Container',incident.container_name],['Namespace',incident.namespace]].forEach(([k,v])=>{const r=$('div',undefined,context);$('span',k,r);mono(v,r);});
    raw('용어 안내',{Kubernetes:'앱을 실행하고 관리하는 시스템',eBPF:'운영체제에서 연결 시도 같은 동작을 관찰하는 기술',포트:'같은 주소에서 서비스가 사용하는 통신 번호'},sidebar).classList.add('glossary');
  }
  function histogram(parent){
    const bins=new Map();for(const r of failures){const t=Math.floor(Date.parse(r.stamp)/1000);if(Number.isFinite(t))bins.set(t,(bins.get(t)||0)+1);}
    if(!bins.size)return;
    const first=Math.min(...bins.keys()),last=Math.max(...bins.keys()),count=last-first+1,max=Math.max(...bins.values());
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 600 64');svg.setAttribute('preserveAspectRatio','none');svg.setAttribute('role','img');svg.setAttribute('aria-label','저장된 오류 응답 로그의 초별 줄 수');svg.dataset.total=failures.length;svg.id='log-histogram';parent.append(svg);
    for(let i=0;i<count;i++){const val=bins.get(first+i)||0;const rect=document.createElementNS(svg.namespaceURI,'rect');rect.setAttribute('x',i*600/count+1);rect.setAttribute('y',62-val/max*52);rect.setAttribute('width',Math.max(2,600/count-3));rect.setAttribute('height',val/max*52);rect.setAttribute('rx','1');rect.setAttribute('fill','#d78953');const title=document.createElementNS(svg.namespaceURI,'title');title.textContent=new Date((first+i)*1000).toISOString().slice(11,19)+' · '+val+'줄';rect.append(title);svg.append(rect);}
    const axis=$('div',undefined,parent,'chart-axis');mono(new Date(first*1000).toISOString().slice(11,19),axis);$('span','오류 응답 로그 / 1초 구간 · 최대 '+max+'줄',axis);mono(new Date(last*1000).toISOString().slice(11,19),axis);
  }
  function logPanel(){
    const p=panel('애플리케이션 로그',center,'CONTAINER LOGS');p.classList.add('logs-panel');
    const chart=$('div',undefined,p,'log-chart');histogram(chart);
    const toolbar=$('div',undefined,p,'log-toolbar');const input=$('input',undefined,toolbar);input.id='log-search';input.type='search';input.placeholder='로그 검색   /';input.setAttribute('aria-label','저장된 로그 검색');input.value=query;
    const count=mono('',toolbar);button('원문',toolbar,()=>inspect('애플리케이션 로그 원문',log),'text-button');
    const table=$('div',undefined,p,'log-table');table.setAttribute('role','table');table.setAttribute('aria-label','실제 애플리케이션 로그');
    function fill(){table.replaceChildren();const filtered=rows.filter(r=>r.raw.toLowerCase().includes(query.toLowerCase()));count.textContent=filtered.length+' / '+rows.length+'줄';
      for(const r of filtered){const tr=button('',table,()=>inspect('로그 한 줄 원문',r.raw),'log-row');tr.setAttribute('role','row');mono(time(r.stamp),tr,'log-time');$('span',r.status||'APP',tr,r.status?'log-code':'log-kind');$('span',r.message,tr,'log-message');}
      if(!filtered.length)$('div','일치하는 저장 로그가 없습니다.',table,'empty-logs');}
    input.oninput=()=>{query=input.value;fill();};fill();
    $('div','이 로그에는 연결 목적지가 없습니다. 캡처된 일부 로그이며 전체 요청 수는 아닙니다.',p,'panel-note');
  }
  function networkPanel(){
    const p=panel('연결 목적지',center,'DECLARED / OBSERVED');p.classList.add('network-panel');
    if(mode===0){const empty=$('div',undefined,p,'network-empty');$('span','⇢',empty,'empty-route');$('strong','로그에 없는 목적지',empty);$('p','조사 기록을 재생하면 eBPF가 관찰한 연결 시도와 설정을 함께 볼 수 있습니다.',empty);mono('connection attempts · outcome not measured',empty);return;}
    const route=$('div',undefined,p,'route-grid');const origin=$('div',undefined,route,'origin');$('span','출발 컨테이너',origin,'route-label');$('strong',appName,origin);mono(incident.container_name+' @ '+incident.node,origin);
    const ends=$('div',undefined,route,'route-ends');
    const exp=$('article',undefined,ends,'endpoint expected');exp.id='demo-expected';const er=$('div',undefined,exp,'endpoint-main');$('span','선언된 목적지',er,'endpoint-label');mono(dep.expected_ip,er);mono(String(dep.expected_port),er,'port-value');if(mode===2)proof(settings,exp);
    const obs=$('article',undefined,ends,'endpoint observed');obs.id='demo-observed';attempts.forEach(a=>{const or=$('div',undefined,obs,'endpoint-main');$('span','연결 시도',or,'endpoint-label');mono(a.destination_ip,or);mono(String(a.destination_port),or,'port-value');mono(a.attempts+'회',or,'attempt-count');});
    if(mode===2)proof(net,obs);
    $('div','eBPF는 연결 시도만 관찰했습니다. 연결 성공·실패는 미측정입니다.',p,'scope-note');
    if(mode===1)button('인용된 원문과 비교 보기  ↗',p,()=>render(2),'network-link');
  }
  function timeline(){
    const p=panel('AI 조사 기록',right,'SAVED TRACE');p.classList.add('trace-panel');
    const sub=$('div',undefined,p,'trace-subhead');$('span',mode?'조회 완료 · 저장 순서':'저장된 조회 순서',sub);mono(run.retrievals.length+' sources',sub);
    const list=$('ol',undefined,p);list.id='demo-timeline';
    run.retrievals.forEach((r,i)=>{const e=evidence.find(e=>key(e)===r.source),li=$('li',undefined,list,mode?'read':'');li.dataset.source=r.source;
      li.title=mode?fact(e):'저장된 조회 순서';$('span',String(i+1).padStart(2,'0'),li,'trace-index');const text=$('div',undefined,li);$('strong',titles[r.source]||r.source,text);$('span',mode?fact(e):'재생 전',text,'trace-fact');
      const open=button(mode?'↗':'·',li,()=>inspect(titles[r.source]||r.source,e||r),'trace-open');open.setAttribute('aria-label',(titles[r.source]||r.source)+' 원문');});
    const bottom=$('div',undefined,p,'trace-footer');$('span','1회 묶음 선택 · 단계별 새 호출 아님',bottom);button('호출 원문',bottom,()=>inspect('실제 조회 및 공개 응답',{retrievals:run.retrievals,trace:run.trace}),'text-button');
  }
  function verdict(){
    const p=panel('AI 판단',right,mode?'RECORDED':'WAITING');p.classList.add('verdict-panel');
    if(!mode){$('div','실패 로그 → 추가 증거 → 원인 추정',p,'verdict-wait');$('p','AI가 실제로 조회한 자료와 판단을 저장 순서대로 확인합니다.',p,'muted');return;}
    $('span','포트 불일치',p,'finding-tag');$('blockquote',claim.text,p,'claim-quote');
    const citations=$('div',undefined,p,'citations');claim.evidence_ids.forEach(id=>{const e=byID.get(id);button((e.tool==='get_ebpf_summary'?'[2] 연결 시도':'[1] 서비스 설정')+' ↗',citations,()=>inspect('판단에 인용된 '+titles[key(e)],e,e.tool==='get_ebpf_summary'?'"destination_port"':'"declared_dependency"'),'citation');});
    $('p','저장된 AI의 추정입니다. 잘못된 설정의 출처와 연결 결과는 미확인입니다.',p,'muted');
    if(mode===1){const b=button('판단 근거 열기  →',p,()=>render(2),'primary');b.id='demo-evidence';}
    else button('AI 답변 전체',p,()=>inspect('저장된 AI 답변',run.answer),'text-button');
  }
  function comparison(){
    const p=panel(baseline?'같은 사건 · 실행 비교':'로그 / eBPF 정보 비교',right,'eBPF ±');p.id='demo-comparison';p.classList.add('comparison-panel');
    if(!baseline){$('p','같은 사건의 eBPF 제외 실행이 없어 자료의 정보 차이만 보여줍니다.',p,'muted');$('p',line,p);$('blockquote',claim.text,p);return;}
    const a=$('div',undefined,p,'comparison-row');$('span','eBPF 제외',a,'compare-label');$('strong',baseline.answer?.status==='inconclusive'?'AI는 원인을 보류':'저장된 판단',a);$('p',baseline.answer?.unknowns?.find(s=>s.includes('목적지'))||baseline.answer?.unknowns?.[0]||'저장된 설명 없음',a);
    button('답변 원문 ↗',a,()=>inspect('eBPF 제외 · 저장된 AI 답변',baseline.answer),'text-button');
    const b=$('div',undefined,p,'comparison-row with-ebpf');$('span','eBPF 포함',b,'compare-label');$('strong','실제 시도 포트까지 특정',b);$('p',claim.text,b);button('답변 원문 ↗',b,()=>inspect('eBPF 포함 · 저장된 AI 답변',run.answer),'text-button');
    $('div','동일 사건·선택 조회·반복 번호. 한 사례의 기록 비교입니다.',p,'panel-note');
  }
  function render(next){
    mode=next;closeInspector();root.dataset.mode=mode;root.querySelectorAll('details').forEach(d=>d.open=false);
    navs.forEach((b,i)=>{b.classList.toggle('active',mode===i);if(mode===i)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
    guideText.textContent=['실패 로그만으로는 어디에 연결하려 했는지 알 수 없습니다.','설정과 실제 연결 시도를 대조해 조사 범위를 좁혔습니다.','AI가 인용한 원문과 eBPF 포함·제외 실행을 비교합니다.'][mode];guideAction.replaceChildren();
    if(!mode){const b=button('▶  AI의 조사 보기',guideAction,()=>render(1),'primary');b.id='demo-investigate';}
    else button(mode===1?'실행 비교  →':'↺  처음으로',guideAction,()=>mode===1?render(2):reset.click(),'quiet');
    stats.replaceChildren();metric('관측된 오류 응답 로그',failures.length,'줄','amber');metric('eBPF 연결 시도',mode?totalAttempts:'—',mode?'회':'재생 대기');metric('판단에 인용된 증거',mode?claim.evidence_ids.length:'—','개');
    metric('저장된 실행 비용',run.cost_usd===null?'미확정':'$'+run.cost_usd.toFixed(6),'새 과금 없음');
    sourceList();center.replaceChildren();right.replaceChildren();logPanel();networkPanel();
    if(mode===2){verdict();comparison();}else{timeline();verdict();}
    h1.focus({preventScroll:true});window.scrollTo(0,0);
  }
  function onKey(e){
    if(!root.isConnected)return;
    if(inspector){if(e.key==='Escape'){e.preventDefault();closeInspector();}else if(e.key==='Tab'){e.preventDefault();inspector.querySelector('button').focus();}return;}
    if(/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)){if(e.key==='Escape')e.target.blur();return;}
    if(e.ctrlKey||e.metaKey||e.altKey)return;
    if(['1','2','3'].includes(e.key)){e.preventDefault();render(Number(e.key)-1);}
    if(e.key==='/'){e.preventDefault();document.getElementById('log-search')?.focus();}
    if(e.key.toLowerCase()==='r'){e.preventDefault();reset.click();}
  }
  window.addEventListener('keydown',onKey);window.RCABoothCleanup=()=>window.removeEventListener('keydown',onKey);
  render(0);
};
