#!/usr/bin/env python3
"""Stage v4 on the STOPPED Agent only. Default: local plan, no cluster calls.

Uses a dedicated immutable code ConfigMap; does not change collectors/lab,
read credentials, enable LLM calls, or scale any deployment.
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.rcactl import kubectl


def build_patch(deployment, name):
    if deployment['spec'].get('replicas', 1) != 0:
        raise ValueError('Agent must be stopped; refusing to scale or replace a running Agent')
    if deployment.get('status', {}).get('replicas', 0) != 0:
        raise ValueError('Agent pods are still terminating; wait before staging')
    spec = deployment['spec']['template']['spec']
    ci = next(i for i, item in enumerate(spec['containers']) if item['name'] == 'agent')
    vi = next(i for i, item in enumerate(spec['volumes']) if item['name'] == 'code')
    if 'configMap' not in spec['volumes'][vi]:
        raise ValueError('Unexpected code volume source')
    env = copy.deepcopy(spec['containers'][ci].get('env', []))
    env = [e for e in env if e['name'] not in ('LLM_ENABLED', 'RCA_CONTEXT_MODE')]
    env += [{'name': 'LLM_ENABLED', 'value': 'false'}, {'name': 'RCA_CONTEXT_MODE', 'value': 'compact-v4'}]
    return [
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': deployment['metadata']['resourceVersion']},
        {'op': 'test', 'path': '/spec/replicas', 'value': 0},
        {'op': 'add', 'path': f'/spec/template/spec/containers/{ci}/env', 'value': env},
        {'op': 'replace', 'path': f'/spec/template/spec/volumes/{vi}/configMap/name', 'value': name},
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error('Output exists; preserve earlier deployment records')
    data = {p.name: p.read_text() for p in sorted((ROOT / 'rca').glob('*.py'))}
    checksum = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    name = 'rca-agent-code-v4-' + checksum[:12]
    plan = {'code_sha256': checksum, 'code_configmap': name, 'llm_enabled': False,
            'context_mode': 'compact-v4', 'replicas_required': 0, 'executed': False}
    if args.execute:
        deployment = json.loads(kubectl('-n', 'rca-system', 'get', 'deployment', 'rca-agent', '-o', 'json', capture=True))
        patch = build_patch(deployment, name)
        existing = kubectl('-n', 'rca-system', 'get', 'configmap', name, '--ignore-not-found', '-o', 'json', capture=True)
        if existing.strip():
            if json.loads(existing).get('data') != data:
                raise ValueError('Existing versioned ConfigMap content differs; refusing overwrite')
        else:
            kubectl('create', '-f', '-', data=json.dumps({'apiVersion': 'v1', 'kind': 'ConfigMap',
                'metadata': {'namespace': 'rca-system', 'name': name}, 'immutable': True, 'data': data}))
        # Resource-version test prevents overriding concurrent operator changes.
        # A rejected patch can leave the harmless versioned ConfigMap unused.
        kubectl('-n', 'rca-system', 'patch', 'deployment', 'rca-agent', '--type=json', '-p', json.dumps(patch))
        after = json.loads(kubectl('-n', 'rca-system', 'get', 'deployment', 'rca-agent', '-o', 'json', capture=True))
        build_patch(after, name)  # recheck the stopped-state preconditions
        spec = after['spec']['template']['spec']
        env = {e['name']: e.get('value') for c in spec['containers'] if c['name'] == 'agent' for e in c.get('env', [])}
        mounted = next(v['configMap']['name'] for v in spec['volumes'] if v['name'] == 'code')
        if env.get('LLM_ENABLED') != 'false' or env.get('RCA_CONTEXT_MODE') != 'compact-v4' or mounted != name:
            raise ValueError('Post-stage verification failed; inspect deployment')
        plan.update(executed=True, verified_replicas=after['spec']['replicas'],
                    previous_code_configmap=next(v['configMap']['name'] for v in deployment['spec']['template']['spec']['volumes'] if v['name'] == 'code'))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(plan, indent=2))
    print(json.dumps(plan, indent=2))


if __name__ == '__main__':
    main()
