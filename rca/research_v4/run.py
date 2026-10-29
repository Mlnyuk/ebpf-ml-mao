"""One preregistered bounded suite; failed outcomes are never replaced."""
import fcntl
import json
import os
import random
from pathlib import Path
from research.capture import write_new
from research.evidence import digest
from research_v4.engine import run_case
from research_v4.protocol import check
from rca.common import Settings,now
from scripts.evaluate_frozen import CallBudget,BudgetProvider,evaluation_key


def provider_settings(spec):
    s=Settings();s.llm_enabled=True;s.model=spec['model'];s.provider='openrouter'
    s.api_url='https://openrouter.ai/api/v1/chat/completions';s.max_output=spec['limits']['output_tokens']
    s.routing={'only':[spec['provider_tag']],'allow_fallbacks':False,'max_price':{'prompt':s.input_price,'completion':s.output_price}}
    return s


def budget_for(study,spec):
    b=spec['global_budget'];return CallBudget(b['api_calls'],b['usd_guard'],study/'budget.json')


def validate_case(study,cid,dataset):
    if cid not in dataset['case_ids']:raise ValueError('unknown registered case')
    path=study/'agent-cases'/(cid+'.json');data=path.read_bytes()
    if digest(data)!=dataset['case_sha256'][cid]:raise ValueError('case changed')
    return json.loads(data)


def one(study,folder,item,settings,budget,spec,dataset):
    case=validate_case(study,item['case_id'],dataset)
    rid=digest(item)[:20]
    with (folder/(rid+'.jsonl')).open('x') as stream:
        def record(value):
            stream.write(json.dumps(value,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())
        record({'type':'start','run_id':rid,'at':now(),**item})
        outcome=run_case(case,spec['arms'][item['arm']],BudgetProvider(settings,budget),spec['limits'],record)
        record({'type':'end','at':now(),'result':outcome})
    run={'run_id':rid,**item,'result':outcome};write_new(folder/(rid+'.json'),run)
    return run


def execute(study,args):
    check(study);spec=json.loads((study/'protocol.json').read_text());dataset=json.loads((study/'dataset.json').read_text())
    if not dataset['complete']:raise ValueError('capture incomplete')
    schedule=[{'case_id':c,'arm':a,'repeat':0} for c in dataset['case_ids'] for a in spec['arms']]
    random.Random(spec['seed']).shuffle(schedule)
    if len(schedule)!=spec['planned_primary_llm_runs']+spec['planned_robustness_llm_runs']:raise ValueError('schedule mismatch')
    folder=study/'runs-main';folder.mkdir(exist_ok=False)
    write_new(folder/'schedule.json',{'items':schedule,'dataset_sha256':digest((study/'dataset.json').read_bytes()),'freeze_sha256':digest((study/'freeze.json').read_bytes())})
    completion={'complete':False,'started_at':now(),'runs':[],'stop_reason':None}
    with (study/'.api.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        budget=budget_for(study,spec);settings=provider_settings(spec)
        try:
            with evaluation_key(args) as key:
                settings.api_key_file=key
                for item in schedule:
                    check(study)
                    r=one(study,folder,item,settings,budget,spec,dataset);completion['runs'].append(r['run_id'])
                    print(json.dumps({'done':len(completion['runs']),'planned':len(schedule),'arm':r['arm'],'state':r['result']['state'],
                        'api_attempts':budget.attempts,'accounted_usd':budget.accounted_usd}),flush=True)
                    if r['result'].get('global_stop'):
                        completion['stop_reason']=r['result']['error'];break
                else:completion['complete']=True
        except BaseException as e:
            completion['stop_reason']=type(e).__name__;raise
        finally:
            completion.update(finished_at=now(),api_attempts=budget.attempts,accounted_usd=budget.accounted_usd)
            write_new(folder/'completion.json',completion)


def live(study,args,cid,arm):
    """Explicit UI demonstration only; separate unique outputs, same total budget."""
    import uuid
    check(study);spec=json.loads((study/'protocol.json').read_text());dataset=json.loads((study/'dataset.json').read_text())
    if arm not in spec['arms']:raise ValueError('unknown arm')
    with (study/'.api.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        folder=study/'live-exploratory'/uuid.uuid4().hex;folder.mkdir(parents=True,exist_ok=False)
        settings=provider_settings(spec)
        with evaluation_key(args) as key:
            settings.api_key_file=key
            return one(study,folder,{'case_id':cid,'arm':arm,'repeat':0,'mode':'unregistered_explicit_live_demo'},settings,budget_for(study,spec),spec,dataset)
