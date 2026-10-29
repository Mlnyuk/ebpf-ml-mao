#!/usr/bin/env python3
"""Operator CLI; uses the current kubectl context. No API key in argv or shell history."""
import getpass
import hashlib
import json
import pathlib
import secrets
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]


def kubectl(*args, data=None, capture=False):
    return subprocess.run(['kubectl', '--request-timeout=30s', *args], input=data, text=True,
                          check=True, stdout=subprocess.PIPE if capture else None).stdout


def apply(value):
    kubectl('apply', '-f', '-', data=json.dumps(value))


def code_version(namespace, kind, name):
    checksum = hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT / 'rca').glob('*.py')))).hexdigest()
    kubectl('-n', namespace, 'patch', kind, name, '--type=merge', '-p',
            json.dumps({'spec': {'template': {'metadata': {'annotations': {'rca/code-sha256': checksum}}}}}))


def deploy():
    kubectl('apply', '-f', str(ROOT / 'deploy' / 'namespaces.yaml'))
    for namespace in ('rca-system', 'rca-lab'):
        apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'rca-code', 'namespace': namespace},
               'data': {p.name: p.read_text() for p in (ROOT / 'rca').glob('*.py')}})
    found = kubectl('-n', 'rca-system', 'get', 'secret', 'rca-auth', '--ignore-not-found', '-o', 'name', capture=True)
    if not found.strip():
        # create, not apply: do not store secret in last-applied-configuration annotations.
        kubectl('create', '-f', '-', data=json.dumps({'apiVersion': 'v1', 'kind': 'Secret',
                'metadata': {'name': 'rca-auth', 'namespace': 'rca-system'},
                'stringData': {'token': secrets.token_urlsafe(32)}}))
    auth = json.loads(kubectl('-n', 'rca-system', 'get', 'secret', 'rca-auth', '-o', 'json', capture=True))
    webhook_exists = kubectl('-n', 'rca-lab', 'get', 'secret', 'rca-webhook-auth', '--ignore-not-found', '-o', 'name', capture=True)
    kubectl('replace' if webhook_exists.strip() else 'create', '-f', '-', data=json.dumps({
        'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'rca-webhook-auth', 'namespace': 'rca-lab'},
        'data': {'token': auth['data']['token']}}))
    kubectl('apply', '-f', str(ROOT / 'deploy' / 'system.yaml'))
    code_version('rca-system', 'deployment', 'rca-agent')
    code_version('rca-system', 'daemonset', 'rca-ebpf-summary')
    kubectl('-n', 'rca-system', 'rollout', 'status', 'deployment/rca-agent', '--timeout=180s')
    kubectl('-n', 'rca-system', 'rollout', 'status', 'daemonset/rca-ebpf-summary', '--timeout=180s')
    kubectl('apply', '-f', str(ROOT / 'deploy' / 'lab.yaml'))
    for name in ('sample-service', 'sample-backend'):
        code_version('rca-lab', 'deployment', name)
        kubectl('-n', 'rca-lab', 'rollout', 'status', 'deployment/' + name, '--timeout=180s')
    monitor()


def monitor():
    name = 'my-monitoring-kube-prometh-prometheus'
    desired = {'name': 'rca-cadvisor-scrape', 'key': 'scrape-configs.yaml'}
    prom = json.loads(kubectl('-n', 'monitoring', 'get', 'prometheus', name, '-o', 'json', capture=True))
    existing = prom['spec'].get('additionalScrapeConfigs')
    if existing and existing != desired:
        raise SystemExit('Existing additionalScrapeConfigs found; merge manually rather than overwrite.')
    kubectl('apply', '-f', str(ROOT / 'deploy' / 'monitoring.yaml'))
    kubectl('-n', 'monitoring', 'patch', 'prometheus', name, '--type=merge', '-p',
            json.dumps({'spec': {'additionalScrapeConfigs': desired}}))


def install_key():
    key = getpass.getpass('OpenRouter API key (hidden): ').strip()
    if not key:
        raise SystemExit('Empty key; nothing changed')
    found = kubectl('-n', 'rca-system', 'get', 'secret', 'rca-llm', '--ignore-not-found', '-o', 'name', capture=True)
    value = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'rca-llm', 'namespace': 'rca-system'},
             'stringData': {'api-key': key}}
    kubectl('replace' if found.strip() else 'create', '-f', '-', data=json.dumps(value))
    print('Key stored. Mounted Secret refresh can take about a minute; check health. No paid call was made by this command.')


def pod():
    data = json.loads(kubectl('-n', 'rca-lab', 'get', 'pods', '-l', 'app=sample-service', '-o', 'json', capture=True))
    return next(p['metadata']['name'] for p in data['items'] if not p['metadata'].get('deletionTimestamp'))


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else 'health'
    if command == 'deploy':
        deploy()
    elif command == 'monitor':
        monitor()
    elif command == 'set-key':
        install_key()
    elif command == 'fault':
        mode = sys.argv[2]
        if mode not in ('crash', 'memory', 'cpu', 'network_port', 'network_peer'):
            raise SystemExit('Fault must be crash, memory, cpu, network_port, or network_peer')
        target = json.loads(kubectl('-n', 'rca-lab', 'get', 'pod', pod(), '-o', 'json', capture=True))
        requested = datetime.now(timezone.utc).isoformat()
        kubectl('-n', 'rca-lab', 'exec', 'deployment/sample-service', '--', 'python', '-c',
                'import urllib.request; print(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8080/fault/' + mode + '",data=b"{}"),timeout=5).read().decode())')
        (ROOT / 'artifacts').mkdir(exist_ok=True)
        with (ROOT / 'artifacts' / 'experiments.jsonl').open('a') as stream:
            stream.write(json.dumps({'requested_at': requested, 'mode': mode, 'pod_uid': target['metadata']['uid'],
                                    'pod': target['metadata']['name'], 'node': target['spec']['nodeName']}) + '\n')
        print('Fault requested. Restart incidents are automatic; CPU alerts are handled by the lab PrometheusRule if installed.')
    elif command == 'traffic':
        kubectl('-n', 'rca-lab', 'exec', 'deployment/sample-backend', '--', 'python', '-c',
                'import urllib.request,time\nfor _ in range(30):\n try:\n  print(urllib.request.urlopen("http://sample-service:8080/work",timeout=3).status,flush=True)\n except Exception as e:\n  print(type(e).__name__,flush=True)\n time.sleep(1)')
    else:
        args = sys.argv[1:] or ['health']
        if command in ('preflight', 'incident') and len(args) == 1:
            args.append(pod())
        kubectl('-n', 'rca-system', 'exec', 'deployment/rca-agent', '--', 'python', '-m', 'rca.cli', *args)


if __name__ == '__main__':
    main()
