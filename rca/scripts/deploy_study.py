#!/usr/bin/env python3
"""Update ONLY RCA collectors and the scoped lab frontend; keep Agent stopped."""
import json
from rcactl import ROOT, apply, code_version, kubectl


def main():
    deployment = json.loads(kubectl('-n', 'rca-system', 'get', 'deployment', 'rca-agent', '-o', 'json', capture=True))
    if deployment['spec'].get('replicas', 1) != 0:
        raise SystemExit('Agent must remain stopped for the isolated study')
    for namespace in ('rca-system', 'rca-lab'):
        apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'rca-code', 'namespace': namespace},
               'data': {p.name: p.read_text() for p in (ROOT / 'rca').glob('*.py')}})
    documents = (ROOT / 'deploy/system.yaml').read_text().split('---')
    daemonset = next(doc for doc in documents if 'kind: DaemonSet' in doc)
    kubectl('apply', '-f', '-', data=daemonset)
    code_version('rca-system', 'daemonset', 'rca-ebpf-summary')
    kubectl('-n', 'rca-system', 'rollout', 'status', 'daemonset/rca-ebpf-summary', '--timeout=180s')
    service = json.loads(kubectl('-n', 'rca-lab', 'get', 'service', 'sample-backend', '-o', 'json', capture=True))
    contract = {'service': 'rca-lab/sample-backend', 'expected_ip': service['spec']['clusterIP'], 'expected_port': 8080}
    kubectl('-n', 'rca-lab', 'patch', 'deployment', 'sample-service', '--type=merge', '-p', json.dumps({
        'spec': {'template': {'metadata': {'annotations': {'rca.lab/dependency-contract': json.dumps(contract)}}}}}))
    code_version('rca-lab', 'deployment', 'sample-service')
    kubectl('-n', 'rca-lab', 'rollout', 'status', 'deployment/sample-service', '--timeout=180s')
    print('Collector/lab updated. No new eBPF program, GPU change, or Agent activation.')


if __name__ == '__main__':
    main()
