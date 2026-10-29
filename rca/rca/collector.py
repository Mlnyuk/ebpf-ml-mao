"""Read existing Tetragon exports; aggregate without loading new eBPF programs."""
import os
import ipaddress
import time
from collections import Counter
from pathlib import Path

from .common import epoch, now, request, secret
import json


def event_identity(event, namespace):
    kind = next((k for k in ('process_exec', 'process_exit', 'process_kprobe', 'process_tracepoint') if k in event), None)
    if not kind:
        return None
    body = event[kind]
    pod = body.get('process', {}).get('pod', {})
    if pod.get('namespace') != namespace or not pod.get('uid') or not pod.get('container', {}).get('id'):
        return None
    label = kind
    if kind == 'process_kprobe':
        label = 'kprobe:' + body.get('function_name', 'unknown')[:80]
    elif kind == 'process_tracepoint':
        label = 'tracepoint:' + body.get('subsys', '') + '/' + body.get('event', '')
    return pod['uid'], pod['container']['id'], label, epoch(event['time'])


def event_counts(event, label):
    """Retain low-cardinality evidence from EXISTING probes, not RCA labels."""
    counts = Counter({label: 1})
    body = event.get('process_kprobe', {})
    if body.get('function_name') == 'tcp_connect':
        for arg in body.get('args', []):
            sock = arg.get('sock_arg', {})
            try:
                address = str(ipaddress.ip_address(sock['daddr']))
                port = sock['dport']
                if type(port) is int and 0 <= port <= 65535:
                    counts['tcp_attempt|' + address + '|' + str(port)] += 1
            except (KeyError, ValueError, TypeError):
                continue
    return counts


def merge_counts(counter, observation, max_destinations=16):
    for label, count in observation.items():
        if label.startswith('tcp_attempt|') and label not in counter and sum(
                key.startswith('tcp_attempt|') for key in counter) >= max_destinations:
            counter['tcp_attempt_overflow'] += count
        else:
            counter[label] += count


def network_summary(counts, limit=8):
    peers = []
    for key, count in counts.items():
        if key.startswith('tcp_attempt|'):
            _, address, port = key.split('|')
            peers.append({'destination_ip': address, 'destination_port': int(port), 'attempts': count})
    peers.sort(key=lambda p: (-p['attempts'], p['destination_ip'], p['destination_port']))
    return {'tcp_connect_attempts': peers[:limit],
            'omitted_destination_attempts': sum(p['attempts'] for p in peers[limit:]) + counts.get('tcp_attempt_overflow', 0),
            'semantics': 'tcp_connect entry probe: attempts only, NOT connection success or failure.',
            'not_measured': ['connect_result', 'connection_latency', 'tcp_retransmissions']}


def main():
    path = Path(os.getenv('TETRAGON_LOG', '/tetragon/tetragon.log'))
    node = os.environ['NODE_NAME']
    namespace = os.getenv('TARGET_NAMESPACE', 'rca-lab')
    endpoint = os.getenv('RCA_URL', 'http://rca-agent.rca-system.svc:8080') + '/internal/windows'
    token_file = os.getenv('AUTH_TOKEN_FILE', '/secrets/auth/token')
    snapshot_file = os.getenv('SNAPSHOT_FILE', '')
    groups, dirty = {}, set()
    handle, inode, partial = None, None, ''
    health = {'parse_errors': 0, 'dropped_windows': 0, 'matched_events': 0,
              'prefiltered_lines': 0, 'started_at': now()}
    last_send = 0
    last_snapshot, retry_delay = 0, 5
    while True:
        try:
            st = path.stat()
            if handle is None or inode != st.st_ino or st.st_size < handle.tell():
                if handle:
                    handle.close()
                handle = path.open()
                inode, partial = st.st_ino, ''
            health['source_readable'] = True
            health['source_mtime'] = st.st_mtime
            for _ in range(2000):
                line = handle.readline(65537)
                if not line:
                    break
                if len(partial) + len(line) > 65536:
                    partial = ''
                    health['parse_errors'] += 1
                    continue
                partial += line
                if not partial.endswith('\n'):
                    continue
                # Exporter emits literal Kubernetes ASCII namespace strings.
                # Cheap coarse rejection before decoding unrelated cluster JSON;
                # exact namespace/UID/container validation still follows.
                if json.dumps(namespace) not in partial:
                    health['prefiltered_lines'] += 1
                    partial = ''
                    continue
                try:
                    event = json.loads(partial)
                    identity = event_identity(event, namespace)
                    if identity:
                        uid, cid, label, timestamp = identity
                        if time.time() - 600 <= timestamp <= time.time() + 5:
                            start = int(timestamp // 10) * 10
                            key = (uid, cid, start)
                            merge_counts(groups.setdefault(key, Counter()), event_counts(event, label))
                            groups[key]['raw_event_bytes'] += len(partial.encode())
                            dirty.add(key)
                            health['matched_events'] += 1
                except (ValueError, KeyError, TypeError):
                    health['parse_errors'] += 1
                partial = ''
        except OSError:
            health['source_readable'] = False
        current = time.time()
        for key in sorted(groups, key=lambda k: k[2]):
            if key[2] < current - 600 or len(groups) > 500:
                groups.pop(key)
                if key in dirty:
                    health['dropped_windows'] += 1
                    dirty.discard(key)
        if snapshot_file and current - last_snapshot >= 5:
            # Bounded local snapshot supports operator capture while RCA/LLM
            # is stopped. Not an unauthenticated network endpoint.
            snapshot = {'node': node, 'health': health, 'captured_at': now(), 'windows': [
                {'pod_uid': uid, 'container_id': cid, 'start': start, 'end': start + 10,
                 'counts': dict(counts)} for (uid, cid, start), counts in sorted(groups.items())]}
            target = Path(snapshot_file)
            try:
                temporary = target.with_suffix('.tmp')
                temporary.write_text(json.dumps(snapshot, separators=(',', ':')))
                temporary.replace(target)
            except OSError:
                health['snapshot_errors'] = health.get('snapshot_errors', 0) + 1
            last_snapshot = current
        if current - last_send >= retry_delay:
            sending = sorted((k for k in dirty if k[2] + 10 <= current), key=lambda k: k[2])[:200]
            pending = [{'pod_uid': uid, 'container_id': cid, 'start': start, 'end': start + 10,
                        'counts': dict(groups[(uid, cid, start)])} for uid, cid, start in sending]
            try:
                request(endpoint, 'POST', {'node': node, 'windows': pending, 'health': health},
                        headers={'Authorization': 'Bearer ' + secret(token_file)}, timeout=5)
                dirty.difference_update(sending)
                retry_delay = 5
            except Exception as e:
                print(json.dumps({'component': 'collector', 'error': type(e).__name__}), flush=True)
                retry_delay = min(60, retry_delay * 2)
            last_send = current
        time.sleep(0.2)


if __name__ == '__main__':
    main()
