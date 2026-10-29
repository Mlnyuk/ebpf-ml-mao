"""Common adaptive controller for live telemetry and immutable replay.

No fault rules, model calls for routing, or automatic transport retries.
"""
import copy
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from .common import compact, redact
from .evidence_ledger import Ledger, digest
from .investigation_contract import SYSTEM, ContractError, TEXT, STRINGS, obj, final_tool, validate_answer, validate_schema

QUERY=obj({'source':TEXT,'question':{'type':'string','maxLength':240},
    'window_seconds':{'type':['integer','null'],'minimum':30,'maximum':300},
    'refresh':{'type':'boolean'},'representation':{'type':'string','enum':['compact','raw']}},['source','question'])
SHORT_NOTES={'type':'array','items':{'type':'string','maxLength':240},'maxItems':4}
INSPECT=obj({'state':obj({'observed_evidence_ids':{'type':'array','items':{'type':'string','maxLength':100},'maxItems':12},'hypotheses':SHORT_NOTES,'open_questions':SHORT_NOTES}),
    'queries':{'type':'array','items':QUERY,'maxItems':8},
    'catalog':obj({'group':{'type':'string','enum':['all','target','dependency','other']},
                   'cursor':{'type':'integer','minimum':0,'maximum':100000},
                   'discover':{'type':'boolean'}},['group','cursor'])},['state','queries'])


@dataclass
class Limits:
    calls:int=4
    tools:int=24
    seconds:float=240
    request_bytes:int=65000
    total_bytes:int=180000
    eager_bytes:int=32000
    catalog_bytes:int=5000
    catalog_page:int=12
    repairs:int=1
    workers:int=4


class Investigation:
    def __init__(self, sources, provider, policy='adaptive', limits=None, record=None, budget=None, clock=time.monotonic):
        if policy not in ('batch','filtered-batch','selective','adaptive'):raise ValueError('unknown investigation policy')
        self.sources,self.provider,self.policy=sources,provider,policy
        self.limits=limits or Limits();self.record=record or (lambda event:None);self.budget=budget;self.clock=clock
        self.ledger=Ledger(sources.incident);self.cache={};self.retrievals=[];self.started=clock();self.tool_count=0
        if hasattr(sources,'set_deadline'):sources.set_deadline(self.started+self.limits.seconds)
        self.catalog_filter={'group':'all','cursor':0};self.discovery=None
        self.attempts=[];self.errors=[];self.requests=0;self.bytes=0;self.repair_count=0

    def emit(self,event):self.record(redact(copy.deepcopy(event)))

    def catalog(self):
        ds=self.sources.descriptors();group=self.catalog_filter['group'];cursor=self.catalog_filter['cursor']
        ds=[d for d in ds if group=='all' or d['group']==group]
        # Incident's own sources first; identities/order do not encode diagnosis.
        ds.sort(key=lambda d:(d['group']!='target',d['source']))
        page=[];size=0
        for d in ds[cursor:cursor+self.limits.catalog_page]:
            row={k:d[k] for k in ('source','tool','group','scope','target','estimated_bytes','availability','immutable')}
            row['retrieval_state']=self.ledger.query_states.get(d['source'],'not_retrieved')
            n=len(compact(row).encode())
            if size+n>self.limits.catalog_bytes:break
            size+=n;page.append(row)
        next_cursor=cursor+len(page) if cursor+len(page)<len(ds) else None
        return {'entries':page,'group':group,'next_cursor':next_cursor,'total_in_group':len(ds),
                'discovery':self.discovery,'note':'Not listed does not mean unavailable; use inspect.catalog to browse/expand.'}

    def prepare(self):
        ds=self.sources.descriptors()
        selected=[d for d in ds if d['group'] in ('target','dependency') and d['scope'] not in ('unverified_identity','unverified_time')]
        # Include the real model/tool envelope and bounded catalog, not only
        # telemetry text. This is a UTF-8 estimate, not a tokenizer measurement.
        scaffold=self.provider.payload(self.messages(),self.tools(False))
        envelope=len(compact(scaffold).encode())
        projected=sum(d['estimated_bytes'] for d in selected)+envelope
        full_projection=sum(d['estimated_bytes'] for d in ds)+envelope
        certain=bool(selected) and bool(self.sources.incident.get('pod_uid')) and bool(self.sources.incident.get('container_id')) and all(
            d['scope'] in ('current_incident','historical_context','other_target') and not d.get('contains_historical_context') for d in selected)
        self.route='batch' if self.policy=='batch' else 'filtered-batch' if self.policy=='filtered-batch' else 'selective'
        if self.policy=='adaptive' and certain and projected<=min(self.limits.eager_bytes,self.limits.request_bytes):self.route='eager'
        self.routing={'policy':self.policy,'route':self.route,'estimated_input_bytes':projected,
            'unfiltered_estimated_bytes':full_projection,'eager_limit_bytes':self.limits.eager_bytes,'scope_certain':certain}
        self.emit({'type':'routing',**self.routing})
        if self.route in ('batch','filtered-batch','eager'):
            chosen=ds if self.route=='batch' else selected
            self.retrieve([{'source':d['source'],'question':'Initial bounded target/time evidence bundle'} for d in chosen])
        return self.routing

    def retrieve(self, queries):
        descriptors={d['source']:d for d in self.sources.descriptors()}
        jobs=[];pending={};completed=[]
        for q in queries:
            validate_schema(q,QUERY,'$.queries')
            if not q['question'].strip():raise ContractError('format','$.queries.question','state the distinguishing question')
            key=q['source'];window=q.get('window_seconds');refresh=q.get('refresh',False)
            if key not in descriptors:raise ValueError('source outside authorized catalog')
            window=self.sources.normalize_window(key,window)
            q={**q,'window_seconds':window}
            if self.sources.frozen and (window is not None or refresh):
                raise ValueError('immutable replay cannot refresh/change a captured interval; no live fallback')
            version=self.sources.version(key)
            signature=(key,window,compact(version))
            if refresh and descriptors[key]['immutable']:raise ValueError('captured snapshot cannot be refreshed')
            cached=self.cache.get(signature) if not refresh else None
            meta={'source':key,'question':q['question'],'signature':list(signature),'representation':q.get('representation','compact')}
            if cached:
                self.ledger.add(*cached,representation=q.get('representation','compact'))
                self.retrievals.append({**meta,'executed':False,'cache_hit':True});continue
            if signature in pending:
                self.retrievals.append({**meta,'executed':False,'cache_hit':True,'pending_same_batch':True});continue
            if self.clock()-self.started>=self.limits.seconds:raise ValueError('time budget exhausted')
            pending[signature]=True;jobs.append((q,signature,meta))
        if self.tool_count+len(jobs)>self.limits.tools:raise ValueError('tool budget exhausted')
        def read(job):
            q,signature,meta=job
            try:
                e,location=self.sources.read(q['source'],q.get('window_seconds'),q.get('refresh',False))
                return job,(e,location),None
            except Exception as exc:
                # Only class/name in public failure; backend exception may contain credentials.
                e={'evidence_id':'ev-query-failed-'+digest([signature,len(self.retrievals)])[:20],
                   'tool':descriptors[q['source']]['tool'],'target':descriptors[q['source']]['target'],
                   'availability':'unavailable','observation_state':'query_failed','error':type(exc).__name__}
                return job,(e,'query:'+q['source']),type(exc).__name__
        # Futures are joined; no detached worker can keep mutating after return.
        self.tool_count+=len(jobs)
        with ThreadPoolExecutor(max_workers=max(1,min(self.limits.workers,len(jobs) or 1))) as pool:
            completed=list(pool.map(read,jobs))
        for (q,signature,meta),pair,error in completed:
            self.emit({'type':'evidence_received','source':q['source'],'location':pair[1],'evidence':pair[0]})
            self.ledger.add(*pair,representation=q.get('representation','compact'))
            # Negative cache retains failure as failure, never as zero/healthy.
            # Repeat only for an explicit live refresh or a changed version/TTL.
            self.cache[signature]=pair
            self.ledger.query_states[q['source']]=self.ledger.registry[pair[0]['evidence_id']]['state']
            event={**meta,'executed':True,'cache_hit':False,'evidence_id':pair[0]['evidence_id'],'error':error}
            self.retrievals.append(event);self.emit({'type':'retrieval',**event})

    def messages(self,final_only=False,repair=None):
        payload=self.ledger.payload()
        payload['catalog']=self.catalog();payload['remaining']={'calls':self.limits.calls-self.requests,'tools':self.limits.tools-self.tool_count}
        payload['instruction']='Submit supported findings or explicitly stop inconclusive; no more retrieval.' if final_only else 'Submit if supported; otherwise inspect only a question that can still be answered.'
        if repair is not None:payload['output_correction']=repair
        return [{'role':'system','content':SYSTEM},{'role':'user','content':compact(payload)}]

    def tools(self,final_only):
        tools=[final_tool()]
        if not final_only:tools.insert(0,{'type':'function','function':{'name':'inspect',
            'description':'Resolve stated questions with independent read-only queries, or page/expand the authorized catalog. No arbitrary URLs or commands.',
            'parameters':INSPECT}})
        return tools

    def run(self):
        result={'state':'error','answer':None,'error':None,'termination_reason':None,
                'validation':{'format':'not_checked','citation_scope':'not_checked','semantic':'NOT_VERIFIED'},'measurement':getattr(self.provider,'measurement','offline_test') if getattr(self.provider,'offline',False) else 'external_api'}
        repair=None;last_candidate=None
        try:
            if not getattr(self.provider,'offline',False) and self.budget is None:raise ValueError('paid execution disabled: new budget required')
            self.prepare()
            while self.requests<self.limits.calls:
                remaining=self.limits.seconds-(self.clock()-self.started)
                if remaining<=0:raise ValueError('time budget exhausted')
                forced=self.requests==self.limits.calls-1 or self.tool_count>=self.limits.tools
                final_only=forced or repair is not None or self.policy in ('batch','filtered-batch')
                messages=self.messages(forced,repair);tools=self.tools(final_only)
                payload=self.provider.payload(messages,tools)
                n=len(compact(payload).encode())
                if n>self.limits.request_bytes or self.bytes+n>self.limits.total_bytes:raise ValueError('input budget exhausted; ledger not truncated')
                reservation=self.budget.reserve(payload) if self.budget else None
                self.requests+=1;self.bytes+=n
                self.emit({'type':'request','call':self.requests,'phase':'repair' if repair else 'investigate','payload':payload})
                try:
                    response=self.provider.complete(messages,tools,min(60,remaining))
                except Exception:
                    if self.budget:self.budget.abort()
                    raise
                if not isinstance(response,dict):
                    self.emit({'type':'response','call':self.requests,'response':response})
                    if self.budget:self.budget.abort()
                    raise ValueError('provider returned a non-object response')
                usage=response.get('usage',{}) if isinstance(response.get('usage',{}),dict) else {}
                public={k:response[k] for k in ('id','model','provider','usage') if k in response}
                choices=response.get('choices')
                protocol_ok=isinstance(choices,list) and bool(choices) and all(isinstance(c,dict) and isinstance(c.get('message'),dict) for c in choices)
                public['choices']=[{'finish_reason':c.get('finish_reason'),'message':{k:v for k,v in c['message'].items() if k in ('role','content','tool_calls')}} for c in choices] if protocol_ok else []
                if not protocol_ok:public['protocol_error']='missing choices/message object; not a model answer validation error'
                self.emit({'type':'response','call':self.requests,'response':public})
                self.attempts.append({'call':self.requests,'usage':usage,'phase':'repair' if repair else 'investigate','request_bytes':n})
                settled=self.budget.settle(reservation,usage) if self.budget else True
                if not protocol_ok:raise ValueError('provider_protocol_error: malformed response; no model correction requested')
                if self.clock()-self.started>self.limits.seconds:raise ValueError('time budget exhausted after provider response')
                try:
                    choice=response['choices'][0]
                    if choice.get('finish_reason')=='length':raise ContractError('format','$','truncated response, cannot reconstruct missing content')
                    msg=choice['message'];calls=msg.get('tool_calls',[])
                    if len(calls)==1:
                        name=calls[0]['function']['name'];raw=calls[0]['function'].get('arguments','')
                    elif not calls:name='submit_rca';raw=msg.get('content','')
                    else:raise ContractError('format','$','one inspect batch or one submit_rca call required')
                    last_candidate=raw
                    if isinstance(raw,str) and raw.strip().startswith('```json\n') and raw.strip().endswith('```'):
                        normalized=raw.strip()[8:-3].strip();self.emit({'type':'normalization','before':raw,'after':normalized});raw=normalized
                    value=json.loads(raw) if isinstance(raw,str) else raw
                    if name=='inspect' and not final_only:
                        validate_schema(value,INSPECT)
                        for eid in value['state']['observed_evidence_ids']:
                            if eid not in self.ledger.registry:raise ContractError('citation_scope','$.state.observed_evidence_ids','unshown ID '+eid)
                        if not value['queries'] and 'catalog' not in value:raise ContractError('format','$.queries','empty investigation action')
                        self.ledger.interpretation=copy.deepcopy(value['state'])
                        self.emit({'type':'investigator_state','unverified_interpretation':value['state']})
                        if 'catalog' in value:
                            c=value['catalog'];self.catalog_filter={k:c[k] for k in ('group','cursor')}
                            if c.get('discover'):
                                try:self.discovery=self.sources.expand(c['group'],c['cursor'])
                                except Exception as exc:self.discovery={'state':'query_failed','error':type(exc).__name__}
                        self.retrieve(value['queries'])
                        if not settled:raise ValueError('unknown or over-ceiling API cost; no further requests')
                        continue
                    if name!='submit_rca':raise ContractError('format','$','tool not allowed now: '+name)
                    answer=validate_answer(value,self.ledger,forced)
                    result.update(state='accepted',answer=answer,termination_reason=answer['termination_reason'],
                        validation={'format':'passed','citation_scope':'passed','semantic':'NOT_VERIFIED'})
                    break
                except (ContractError,json.JSONDecodeError,KeyError,IndexError,TypeError) as exc:
                    layer=exc.layer if isinstance(exc,ContractError) else 'format'
                    self.emit({'type':'validation_error','call':self.requests,'layer':layer,'error':str(exc)[:500]})
                    if self.repair_count>=self.limits.repairs or not settled:raise ValueError('output invalid; repair unavailable')
                    self.repair_count+=1
                    # Preserve the original candidate in the correction request,
                    # unlike v4 which only supplied an error and regenerated it.
                    repair={'layer':layer,'error':str(exc)[:500],'original_candidate':last_candidate,
                            'instruction':'Correct the identified field/consistency error. Retain supported claims, hypotheses, counterevidence and uncertainty; no new evidence or invented facts.'}
            if result['state']!='accepted':raise ValueError('call budget exhausted')
        except Exception as exc:
            detail=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
            result.update(error=detail[:500],termination_reason='budget_exhausted' if 'budget' in detail else 'execution_error')
            self.emit({'type':'execution_error','error':result['error'],'termination_reason':result['termination_reason']})
        costs=[a['usage'].get('cost') for a in self.attempts]
        known=[c for c in costs if type(c) in (int,float) and math.isfinite(c) and c>=0]
        result.update(routing=getattr(self,'routing',None),requests=self.requests,repairs=self.repair_count,
            tool_calls=self.tool_count,retrievals=self.retrievals,attempts=self.attempts,ledger=self.ledger.payload(),
            claims_trace=[{'claim':i,'evidence':[self.ledger.registry[eid] for eid in c['evidence_ids']]} for i,c in enumerate((result['answer'] or {}).get('claims',[]))],
            duration_seconds=self.clock()-self.started,request_bytes=self.bytes,
            known_cost_usd=sum(known),total_cost_usd=sum(known) if len(known)==self.requests else None,
            input_tokens=sum(a['usage'].get('prompt_tokens',0) for a in self.attempts),
            output_tokens=sum(a['usage'].get('completion_tokens',0) for a in self.attempts))
        return result
