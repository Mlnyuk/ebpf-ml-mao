#!/usr/bin/env python3
"""Explicit paper-study actions. No automatic deployment, retry or scheduling."""
import argparse
import fcntl
import hashlib
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.spec import protocol, ARMS, ABLATIONS, SCHEMA
from research.evidence import digest, verify_chain
from research.capture import write_new, capture
from research.engine import run_case
from rca.common import Settings, now, request
from scripts.evaluate_frozen import CallBudget, BudgetProvider, evaluation_key


def check(study):
    for manifest in ('legacy-sha256.json', 'freeze.json'):
        data = json.loads((study / manifest).read_text())
        for name, expected in data['sha256'].items():
            if digest((ROOT / name).read_bytes()) != expected:
                raise ValueError('Frozen file changed: ' + name)


def initialize(study):
    study.mkdir(parents=True, exist_ok=False)
    (study / 'private').mkdir(mode=0o700)
    legacy = [p for p in (ROOT / 'artifacts').rglob('*') if p.is_file() and study not in p.parents]
    write_new(study / 'legacy-sha256.json', {'captured_at': now(), 'sha256': {str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(legacy)}})
    write_new(study / 'protocol.json', protocol())
    url = 'https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints'
    metadata = request(url, timeout=25)
    write_new(study / 'endpoint-metadata.json', {'observed_at': now(), 'url': url, 'response': metadata})
    endpoint = [e for e in metadata['data']['endpoints'] if e['tag'] == 'z-ai/fp8']
    write_new(study / 'endpoint-support.json', {'observed_at': now(), 'endpoint': endpoint,
        'structured_outputs_advertised': bool(endpoint) and all('structured_outputs' in e.get('supported_parameters', []) for e in endpoint),
        'enforcement_verified': False, 'actual_probe': 'not_performed',
        'interpretation': 'response_format alone does not establish JSON Schema enforcement. Use common client-validated tool contract; no silent provider switch.',
        'documentation': 'https://github.com/OpenRouterTeam/docs/blob/main/guides/features/structured-outputs.mdx'})


def freeze(study):
    paths = list((ROOT / 'research').glob('*.py')) + [Path(__file__).resolve()]
    paths += list((ROOT / 'rca').glob('*.py')) + [ROOT / 'scripts/evaluate_frozen.py', ROOT / 'scripts/capture_network_study.py', ROOT / 'scripts/rcactl.py']
    paths += [study / 'protocol.json', study / 'endpoint-metadata.json', study / 'endpoint-support.json']
    paths += list((ROOT / 'tests').glob('test_paper*.py'))
    write_new(study / 'freeze.json', {'frozen_at': now(), 'sha256': {str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(set(paths))}})


def probe(study, args):
    class ProbeProvider(BudgetProvider):
        def payload(self, messages, tools):
            body = super().payload(messages, tools)
            body.pop('tools'); body.pop('tool_choice')
            body['response_format'] = {'type':'json_schema','json_schema':{'name':'support_probe','strict':True,
                'schema': {'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}}}
            return body
    settings = Settings()
    settings.llm_enabled = True
    settings.provider = 'openrouter'
    settings.api_url = 'https://openrouter.ai/api/v1/chat/completions'
    settings.max_output = 128
    settings.routing = {'only':['z-ai/fp8'],'allow_fallbacks':False}
    budget = CallBudget(1, 0.02, study / 'capability-budget.json')
    result = {'started_at': now(), 'endpoint': 'z-ai/fp8', 'enforcement_verified': False}
    with evaluation_key(args) as key:
        settings.api_key_file = key
        provider = ProbeProvider(settings, budget)
        messages = [{'role':'user','content':'Return JSON with boolean ok=true.'}]
        result['request'] = provider.payload(messages, [])
        try:
            answer = provider.complete(messages, [], 30)
            result['response'] = {k:answer[k] for k in ('id','provider','model','usage') if k in answer}
            result['content'] = answer['choices'][0]['message'].get('content')
            value = json.loads(result['content'])
            result['schema_conforming_sample'] = isinstance(value, dict) and set(value)=={'ok'} and type(value['ok']) is bool
            result['interpretation'] = 'One conforming sample is not proof of constrained decoding or universal schema enforcement.'
        except Exception as exc:
            result['error'] = str(exc)[:150] if isinstance(exc, ValueError) or type(exc).__name__ == 'RemoteError' else type(exc).__name__
        write_new(study / 'capability-probe.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def execute(study, args):
    check(study)
    spec = json.loads((study / 'protocol.json').read_text())
    dataset = json.loads((study / 'dataset.json').read_text())
    if not dataset['complete']:
        raise ValueError('dataset capture incomplete')
    cases = {}
    for cid, expected in dataset['case_sha256'].items():
        path = study / 'agent-cases' / (cid + '.json')
        if digest(path.read_bytes()) != expected:
            raise ValueError('public case changed after capture')
        cases[cid] = json.loads(path.read_text())
    arms = {**ARMS, **ABLATIONS} if args.suite == 'all' else ARMS if args.suite == 'primary' else ABLATIONS
    rng, schedule = random.Random(spec['seed']), []
    for repeat in range(spec['llm_repeats_per_case_arm']):
        items = [{'case_id':cid,'arm':arm,'repeat':repeat} for cid in dataset['case_ids'] for arm in arms]
        rng.shuffle(items)
        schedule += items
    run_dir = study / ('runs-' + args.suite)
    run_dir.mkdir(exist_ok=False)  # Never silently repeat partial/failed suite.
    write_new(run_dir / 'schedule.json', {'items':schedule,'dataset_sha256':digest((study/'dataset.json').read_bytes()),
                                        'freeze_sha256':digest((study/'freeze.json').read_bytes())})
    limits = spec['limits']
    settings = Settings()
    settings.llm_enabled = True
    settings.model, settings.provider = spec['model'], 'openrouter'
    settings.api_url = 'https://openrouter.ai/api/v1/chat/completions'
    settings.max_output = limits['output_tokens']
    settings.routing = {'only':[spec['provider_tag']], 'allow_fallbacks':False,
                        'max_price':{'prompt':settings.input_price,'completion':settings.output_price}}
    budget = CallBudget(limits['global_api_calls'], limits['global_usd_guard'], study / 'budget.json')
    report = {'complete':False,'started_at':now(),'runs':[],'stop_reason':None}
    try:
        with evaluation_key(args) as key:
            settings.api_key_file = key
            for index, item in enumerate(schedule):
                check(study)
                run_id = digest(item)[:20]
                record_path = run_dir / (run_id + '.jsonl')
                with record_path.open('x') as stream:
                    def record(value):
                        stream.write(json.dumps(value,ensure_ascii=False)+'\n'); stream.flush(); os.fsync(stream.fileno())
                    record({'type':'start','at':now(),'run_id':run_id,**item,'config':arms[item['arm']]})
                    outcome = run_case(cases[item['case_id']], arms[item['arm']], BudgetProvider(settings,budget), limits, record)
                    record({'type':'end','at':now(),'result':outcome})
                write_new(run_dir/(run_id+'.json'), {**item,'run_id':run_id,'result':outcome})
                report['runs'].append(run_id)
                print(json.dumps({'done':index+1,'planned':len(schedule),**item,'state':outcome['state'],
                                  'calls':budget.attempts,'accounted_usd':budget.accounted_usd,'error':outcome['error']}),flush=True)
                if outcome.get('global_stop'):
                    report['stop_reason'] = outcome['error']; break
            else:
                report['complete'] = True
    finally:
        report.update(finished_at=now(),api_attempts=budget.attempts,conservative_accounted_usd=budget.accounted_usd)
        write_new(run_dir/'completion.json',report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['init','freeze','check','capture','probe','run','report','overhead'])
    parser.add_argument('--study',type=Path,default=ROOT/'artifacts/paper-v1-20261029')
    parser.add_argument('--suite',choices=['primary','ablations','all'],default='all')
    keys = parser.add_mutually_exclusive_group()
    keys.add_argument('--cluster-key',action='store_true')
    keys.add_argument('--key-file',type=Path)
    args = parser.parse_args()
    study = args.study.resolve()
    if args.action == 'init': initialize(study)
    elif args.action == 'freeze': freeze(study)
    elif args.action == 'check': check(study); print('Frozen and legacy hashes match.')
    elif args.action == 'capture': check(study); capture(study,json.loads((study/'protocol.json').read_text()))
    elif args.action in ('run','probe'):
        if not args.cluster_key and not args.key_file:
            parser.error('explicit key source required for paid calls')
        with (study/'.execution.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            (execute(study,args) if args.action=='run' else probe(study,args))
    elif args.action == 'report':
        from research.reporting import report
        report(study)
    elif args.action == 'overhead':
        from research.reporting import overhead
        overhead(study)


if __name__ == '__main__': main()
