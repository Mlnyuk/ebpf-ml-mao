#!/usr/bin/env python3
"""Update only lab frontend code to support controlled log detail; Agent stays off."""
import hashlib
import json
from rcactl import ROOT, kubectl


def main():
    agent = json.loads(kubectl('-n', 'rca-system', 'get', 'deployment', 'rca-agent', '-o', 'json', capture=True))
    if agent['spec'].get('replicas', 1) != 0:
        raise SystemExit('Agent must remain stopped')
    data = {p.name: p.read_text() for p in sorted((ROOT / 'rca').glob('*.py'))}
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    name = 'rca-lab-validation-' + digest[:12]
    existing = kubectl('-n', 'rca-lab', 'get', 'configmap', name, '--ignore-not-found', '-o', 'json', capture=True)
    if not existing.strip():
        kubectl('create', '-f', '-', data=json.dumps({'apiVersion': 'v1', 'kind': 'ConfigMap',
            'metadata': {'namespace': 'rca-lab', 'name': name}, 'immutable': True, 'data': data}))
    elif json.loads(existing)['data'] != data:
        raise ValueError('Versioned ConfigMap mismatch')
    frontend = json.loads(kubectl('-n', 'rca-lab', 'get', 'deployment', 'sample-service', '-o', 'json', capture=True))
    vi = next(i for i,v in enumerate(frontend['spec']['template']['spec']['volumes']) if v['name'] == 'code')
    patch = [{'op': 'test', 'path': '/metadata/resourceVersion', 'value': frontend['metadata']['resourceVersion']},
             {'op': 'replace', 'path': f'/spec/template/spec/volumes/{vi}/configMap/name', 'value': name}]
    kubectl('-n', 'rca-lab', 'patch', 'deployment', 'sample-service', '--type=json', '-p', json.dumps(patch))
    kubectl('-n', 'rca-lab', 'rollout', 'status', 'deployment/sample-service', '--timeout=120s')
    print('Frontend-only code ready. No Agent/collector/GPU changes.')


if __name__ == '__main__':
    main()
