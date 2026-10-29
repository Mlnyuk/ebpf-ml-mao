"""Operational binding of the same controller used by frozen replay."""
import copy
import math
import uuid
from .common import compact, now, redact
from .investigation import Investigation, Limits
from .investigation_sources import LiveSources


def budget_configured(settings):
    return bool(settings.adaptive_budget_id) and type(settings.adaptive_max_calls) is int and settings.adaptive_max_calls>0 and math.isfinite(settings.adaptive_max_usd) and settings.adaptive_max_usd>0


class PaidBudget:
    """New persistent budget only; old experiment budgets are never read.

    Conservative reservation, not a provider dollar SLA. Unknown cost latches
    the budget closed rather than counting it as zero or automatically retrying.
    """
    def __init__(self,store,settings):
        self.store,self.settings=store,settings
        if not budget_configured(settings):
            raise ValueError('new paid budget ID, call cap and dollar cap required')
        if any(not math.isfinite(x) or x<0 for x in (settings.input_price,settings.output_price)):
            raise ValueError('invalid provider price caps')
        self.key='adaptive-budget:'+settings.adaptive_budget_id
        self.caps={'max_calls':settings.adaptive_max_calls,'max_usd':settings.adaptive_max_usd}
        with store.lock:
            existing=store.meta(self.key)
            if existing and any(existing[k]!=v for k,v in self.caps.items()):raise ValueError('existing budget caps cannot be changed')
            if not existing:store.meta(self.key,{**self.caps,'attempts':0,'reserved_usd':0.0,'known_usd':0.0,'blocked':False})

    def reserve(self,payload):
        s=self.settings
        ceiling=((2*len(compact(payload).encode())+8192)*s.input_price+2*s.max_output*s.output_price)/1e6
        with self.store.lock:
            b=self.store.meta(self.key)
            if b['blocked'] or b['attempts']>=b['max_calls'] or b['reserved_usd']+ceiling>b['max_usd']:
                raise ValueError('paid budget exhausted or blocked')
            b['attempts']+=1;b['reserved_usd']+=ceiling;self.store.meta(self.key,b)
        return ceiling

    def settle(self,reserved,usage):
        cost=usage.get('cost');valid=type(cost) in (int,float) and math.isfinite(cost) and cost>=0
        with self.store.lock:
            b=self.store.meta(self.key)
            if valid:b['known_usd']+=cost;b['reserved_usd']+=cost-reserved
            if not valid or cost>reserved:b['blocked']=True
            self.store.meta(self.key,b)
        return valid and cost<=reserved

    def abort(self):
        with self.store.lock:
            b=self.store.meta(self.key);b['blocked']=True;self.store.meta(self.key,b)


def compatible_result(run, incident, run_id, settings):
    a=run['answer'];failed=run['state']!='accepted'
    # Old consumers keep their fields. Rich cause/claim/termination data live in
    # investigation; no model confidence is converted to a probability.
    result={'status':'inconclusive' if failed or a['status']=='inconclusive' else 'completed',
        'failure_mechanism':a['cause_type'] if a else '',
        'root_cause':a['confirmed_cause'] or None if a else None,
        'root_cause_status':'observed' if a and a['confirmed_cause'] else 'undetermined',
        'confidence':'low','evidence':[{'evidence_id':eid,'supports':c['text'],'claim_type':c['kind']}
            for c in (a or {}).get('claims',[]) for eid in c['evidence_ids']],
        'missing_evidence':a['unknowns'] if a else [run['error']],
        'recommended_action':a['recommendation'] if a else 'Inspect the preserved execution error; no automatic retry.',
        'investigation':a,'termination_reason':run['termination_reason']}
    result['execution']={'run_id':run_id,'prompt_version':'adaptive-v1','context_mode':'compact-v4',
        'investigation_policy':settings.investigation_policy,'model':settings.model,'provider':settings.provider,
        'finished_at':now(),'duration_seconds':run['duration_seconds'],'llm_responses':len(run['attempts']),
        'tool_calls':run['tool_calls'],'input_tokens':run['input_tokens'],'output_tokens':run['output_tokens'],
        'provider_reported_cost_usd':run['total_cost_usd'],'known_cost_usd':run['known_cost_usd'],
        'usage_complete':run['total_cost_usd'] is not None,'trace':run['retrievals'],'error':run['error'],
        'validation':run['validation'],'confidence_is_calibrated':False,'confidence_source':'legacy compatibility placeholder; not a model assessment'}
    return result


def run_operational(agent,iid):
    from .agent import Provider
    s=agent.settings;provider=agent.provider;budget=None
    if isinstance(provider,Provider):
        # Preserve the selected model; lock the current provider and disallow
        # hidden fallback/migration. Never use a cluster Secret in prompts.
        if s.provider!='openrouter' or s.api_url!='https://openrouter.ai/api/v1/chat/completions' or s.model!='z-ai/glm-5.3-flash':
            raise ValueError('adaptive-v1 requires the currently pinned model/provider')
        routed=copy.copy(s);routed.routing={'only':['z-ai/fp8'],'allow_fallbacks':False,
            'max_price':{'prompt':s.input_price,'completion':s.output_price}}
        provider=Provider(routed);budget=PaidBudget(agent.store,s)
    elif not getattr(provider,'offline',False):raise ValueError('unbudgeted provider is not an explicit offline test double')
    if not agent.store.claim(iid,s.max_daily):return agent.store.get(iid)
    run_id=str(uuid.uuid4());events=[]
    def record(event):
        events.append(redact(event));agent.store.meta('adaptive-trace:'+run_id,events)
    source=LiveSources(iid,agent.telemetry,s.allow_ebpf)
    limits=Limits(calls=s.max_requests,tools=s.max_tools,seconds=s.max_seconds,
        request_bytes=s.max_context_chars,total_bytes=s.max_input_chars_total,eager_bytes=s.adaptive_eager_bytes)
    run=Investigation(source,provider,s.investigation_policy,limits,record,budget).run()
    agent.store.meta('adaptive-run:'+run_id,run)
    result=compatible_result(run,source.incident,run_id,s)
    agent.store.update(iid,'error' if run['state']!='accepted' else result['status'],result)
    return agent.store.get(iid)
