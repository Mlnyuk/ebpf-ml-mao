"""Bounded read-only Kubernetes access for the operator terminal."""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from datetime import datetime, timezone
import ipaddress
import json
import re
import subprocess
import time


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if re.search(r'(?i)^(password|secret|token|api[_-]?key|authorization)$', k)
                else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r'\bsk-(?:or-v1-)?[A-Za-z0-9_-]{20,}\b', '[REDACTED]', value)
        value = re.sub(r'(?i)(bearer\s+)[\w.\-/+=]+', r'\1[REDACTED]', value)
        value = re.sub(r'(?i)((?:password|token|api[_-]?key|secret)\s*[=:]\s*)[^\s,;]+', r'\1[REDACTED]', value)
    return value


def ready(obj):
    return next((c.get('status', 'Unknown') for c in obj.get('status', {}).get('conditions', [])
                 if c.get('type') == 'Ready'), 'Unknown')


def pod_record(p):
    statuses = p.get('status', {}).get('containerStatuses', [])
    containers = [{'name': c['name'], 'id': c.get('containerID', ''), 'ready': c.get('ready', False),
                   'restarts': c.get('restartCount', 0), 'state': c.get('state', {})} for c in statuses]
    reasons = [v.get('reason') for c in statuses for k, v in c.get('state', {}).items()
               if k in ('waiting', 'terminated') and v.get('reason')]
    return {'name': p['metadata']['name'], 'namespace': p['metadata']['namespace'],
            'uid': p['metadata']['uid'], 'node': p.get('spec', {}).get('nodeName', '?'),
            'ready': ready(p), 'phase': ','.join(reasons) or p.get('status', {}).get('phase', 'Unknown'),
            'restarts': sum(c['restarts'] for c in containers), 'containers': containers,
            'app': p['metadata'].get('labels', {}).get('app', ''),
            'collector_namespace': next((e.get('value') for c in p.get('spec', {}).get('containers', [])
                                         if c['name'] == 'summary' for e in c.get('env', [])
                                         if e.get('name') == 'TARGET_NAMESPACE'), None),
            'created': p['metadata'].get('creationTimestamp')}


class ReadError(Exception):
    pass


class KubeSource:
    """No shell strings, arbitrary commands, writes, Secret reads or AI clients."""
    def __init__(self, namespaces=('rca-lab', 'rca-system'), context=None, runner=None):
        if not namespaces or any(not re.fullmatch(r'[a-z0-9][a-z0-9-]*', n) for n in namespaces):
            raise ValueError('잘못된 namespace')
        self.namespaces = tuple(dict.fromkeys(namespaces)); self.context = context
        self.runner = runner or subprocess.run

    def _call(self, args, raw=False):
        cmd = ['kubectl', '--request-timeout=6s']
        if self.context:
            cmd += ['--context', self.context]
        cmd += args
        try:
            r = self.runner(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=9, check=False)
        except subprocess.TimeoutExpired:
            raise ReadError('조회 시간 초과') from None
        except OSError:
            raise ReadError('kubectl 실행 불가') from None
        if r.returncode:
            # stderr can contain auth-plugin details; never echo it to the screen/export.
            raise ReadError('조회 실패: 연결·권한·대상 상태 확인 필요')
        if len(r.stdout.encode('utf-8')) > 4_000_000:
            raise ReadError('조회 결과 크기 상한 초과')
        if raw:
            return r.stdout
        try:
            return json.loads(r.stdout)
        except ValueError:
            raise ReadError('조회 결과 JSON 오류') from None

    def refresh(self):
        queries = {'nodes': ['get', 'nodes', '-o', 'json'],
                   'system': ['get', 'deployment/rca-agent', 'daemonset/rca-ebpf-summary', '-n', 'rca-system', '-o', 'json']}
        queries.update({'pods:' + n: ['get', 'pods', '-n', n, '-o', 'json'] for n in self.namespaces})
        result = {'mode': 'live', 'observed_at': stamp(), 'nodes': [], 'pods': [], 'system': [], 'sources': {}}
        def read(item):
            key, args = item
            try:
                return key, self._call(args), None
            except ReadError as e:
                return key, None, str(e)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for key, data, error in pool.map(read, queries.items()):
                result['sources'][key] = {'state': 'failed' if error else 'available', 'error': error, 'at': stamp()}
                if error:
                    continue
                if key == 'nodes':
                    result['nodes'] = [{'name': n['metadata']['name'], 'ready': ready(n),
                                        'cpu': n.get('status', {}).get('allocatable', {}).get('cpu', '?'),
                                        'memory': n.get('status', {}).get('allocatable', {}).get('memory', '?'),
                                        'unschedulable': n.get('spec', {}).get('unschedulable', False)} for n in data['items']]
                elif key == 'system':
                    for o in data.get('items', [data]):
                        result['system'].append({'name': o['metadata']['name'], 'kind': o['kind'],
                            'desired': o.get('spec', {}).get('replicas', 1) if o['kind'] == 'Deployment' else o.get('status', {}).get('desiredNumberScheduled', 0),
                            'ready': o.get('status', {}).get('readyReplicas', 0) if o['kind'] == 'Deployment' else o.get('status', {}).get('numberReady', 0)})
                else:
                    result['pods'] += [pod_record(p) for p in data['items']]
        result['nodes'].sort(key=lambda n: (n['ready'] == 'True', n['name']))
        result['pods'].sort(key=lambda p: (p['namespace'], p['name']))
        return result

    def _target(self, pod, container):
        if pod['namespace'] not in self.namespaces:
            raise ReadError('허용되지 않은 namespace')
        for value in (pod['name'], container['name']):
            if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', value):
                raise ReadError('잘못된 조회 대상')
        current = pod_record(self._call(['get', 'pod', pod['name'], '-n', pod['namespace'], '-o', 'json']))
        c = next((c for c in current['containers'] if c['name'] == container['name']), {})
        if current['uid'] != pod['uid'] or not container['id'] or c.get('id') != container['id']:
            raise ReadError('Pod/컨테이너 실행이 바뀌었습니다. 목록을 갱신하세요.')

    def inspect(self, kind, pod, container, inventory):
        self._target(pod, container)
        if kind == 'logs':
            text = self._call(['logs', pod['name'], '-n', pod['namespace'], '-c', container['name'],
                               '--tail=40', '--since=5m', '--limit-bytes=16000', '--timestamps=true'], raw=True)
            value = {'availability': 'observed_zero' if not text.strip() else 'available',
                     'lines': text.splitlines(), 'scope': '최근 5분 / 최대 40줄·16000 bytes. 전체 요청 수가 아님.'}
        elif kind == 'events':
            if not re.fullmatch(r'[a-zA-Z0-9-]+', pod['uid']):
                raise ReadError('잘못된 Pod UID')
            events = self._call(['get', 'events', '-n', pod['namespace'], '--field-selector',
                                 'involvedObject.uid=' + pod['uid'], '-o', 'json'])['items']
            events.sort(key=lambda e: e.get('lastTimestamp') or e.get('eventTime') or '', reverse=True)
            value = {'availability': 'available' if events else 'observed_zero', 'events': [
                {'time': e.get('lastTimestamp') or e.get('eventTime'), 'type': e.get('type'),
                 'reason': e.get('reason'), 'message': e.get('message'), 'count': e.get('count')}
                for e in events[:30]], 'scope': '같은 Pod UID의 보존된 이벤트. 과거 시각은 현재 장애 원인이 아님.'}
        elif kind == 'ebpf':
            collector = next((p for p in inventory['pods'] if p['namespace'] == 'rca-system' and
                              p['app'] == 'rca-ebpf-summary' and p['node'] == pod['node'] and p['ready'] == 'True'), None)
            if not collector:
                raise ReadError('해당 노드의 실행 중인 요약기를 찾지 못했습니다.')
            # Existing collector's read-only local snapshot. Never starts a collector or policy.
            if collector.get('collector_namespace') != pod['namespace']:
                value = {'availability': 'not_collected', 'scope':
                         '선택한 namespace가 요약기의 명시된 수집 범위와 다르거나 범위를 확인하지 못했습니다.'}
            else:
                snapshot = self._call(['exec', '-n', 'rca-system', collector['name'], '-c', 'summary', '--',
                                       'cat', '/state/latest.json'])
                value = summarize(snapshot, pod, container)
        else:
            raise ReadError('지원하지 않는 읽기 작업')
        self._target(pod, container)  # Do not attribute a restart's data to the previous execution.
        return redact({'mode': 'live', 'read_at': stamp(), 'pod_uid': pod['uid'],
                       'container_id': container['id'], 'container': container['name'], **value})


def summarize(snapshot, pod, container, wall_time=None):
    """Same tcp_attempt counters as the existing collector; no RCA classification."""
    current = time.time() if wall_time is None else wall_time
    captured = datetime.fromisoformat(snapshot['captured_at'].replace('Z', '+00:00')).timestamp()
    if snapshot['node'] != pod['node']:
        raise ReadError('요약기 노드 매핑 불일치')
    age = current - captured
    if age > 30 or age < -15:
        return {'availability': 'expired', 'captured_at': snapshot['captured_at'], 'age_seconds': round(age),
                'scope': '스냅샷 기간 만료 또는 시계 차이. 현재 상태를 판단할 수 없음.'}
    if not snapshot.get('health', {}).get('source_readable'):
        return {'availability': 'collection_failed', 'captured_at': snapshot['captured_at'],
                'scope': '원본 수집 파일을 읽지 못함. 정상 근거로 사용하지 않음.'}
    canonical = lambda s: s.removeprefix('containerd://').removeprefix('docker://')
    windows = [w for w in snapshot.get('windows', []) if w['pod_uid'] == pod['uid'] and
               canonical(w['container_id']) == canonical(container['id']) and
               captured - 300 <= w['start'] < w['end'] <= captured]
    counts = Counter()
    for window in windows:
        counts.update(window['counts'])
    peers = []
    for key, count in counts.items():
        if key.startswith('tcp_attempt|'):
            _, address, port = key.split('|')
            peers.append({'destination_ip': str(ipaddress.ip_address(address)), 'destination_port': int(port), 'attempts': count})
    peers.sort(key=lambda p: (-p['attempts'], p['destination_ip'], p['destination_port']))
    return {'availability': 'available' if peers else 'observed_zero', 'captured_at': snapshot['captured_at'],
            'clock': 'collector node clock', 'age_seconds': round(age), 'window_count': len(windows),
            'tcp_connect_attempts': peers[:8],
            'omitted_destination_attempts': sum(p['attempts'] for p in peers[8:]) + counts.get('tcp_attempt_overflow', 0),
            'health': snapshot['health'],
            'scope': '최근 5분의 완료된 10초 집계. 연결 시도 목적지·포트·횟수만 관측. 성공·실패·지연은 미측정.',
            'zero_meaning': '일치하는 저장 관측 0건. 네트워크 정상 또는 원본 수집 완전성을 뜻하지 않음.',
            'selected_windows': windows}
