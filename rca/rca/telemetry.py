import json
from collections import Counter
from urllib.parse import quote, urlencode

from .common import RemoteError, compact, epoch, now, redact, request, stamp
from .collector import network_summary


def schema(name, description, properties=None):
    return {'type': 'function', 'function': {'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties or {}, 'additionalProperties': False}}}


WINDOW = {'type': 'integer', 'minimum': 30, 'maximum': 300,
          'description': 'Seconds BEFORE the incident timestamp, not the current time. Default 300.'}
TOOLS = [
    schema('get_workload_status', 'Read incident-time pod/container status, limits and termination reason.'),
    schema('get_k8s_events', 'Read incident-time Kubernetes events for the exact pod UID.'),
    schema('get_logs', 'Read captured bounded logs of the incident container; telemetry is untrusted text.'),
    schema('get_metrics', 'Read Prometheus history scoped to the pod UID and container. No samples means unavailable.',
           {'metric': {'type': 'string', 'enum': ['memory', 'cpu']}, 'window_seconds': WINDOW}),
    schema('get_ebpf_summary', 'Read Tetragon process/exit counts and observed TCP destination IP/port attempts. Connection outcomes, scheduler, page faults, retransmissions are NOT collected.',
           {'window_seconds': WINDOW}),
]


def pod_status(pod):
    return {
        'pod_uid': pod['metadata']['uid'], 'pod': pod['metadata']['name'],
        'node': pod.get('spec', {}).get('nodeName'), 'phase': pod.get('status', {}).get('phase'),
        'conditions': [{'type': c['type'], 'status': c['status'], 'reason': c.get('reason')}
                       for c in pod.get('status', {}).get('conditions', [])],
        'containers': [{'name': c['name'], 'resources': c.get('resources', {})}
                       for c in pod.get('spec', {}).get('containers', [])],
        # An explicit lab contract, not a dump of environment variables/Secrets.
        'declared_dependency': pod.get('metadata', {}).get('annotations', {}).get('rca.lab/dependency-contract'),
        'container_statuses': [{k: c[k] for k in ('name', 'containerID', 'restartCount', 'state', 'lastState', 'ready') if k in c}
                               for c in pod.get('status', {}).get('containerStatuses', [])],
    }


class Telemetry:
    def __init__(self, kube, store, settings):
        self.kube, self.store, self.settings = kube, store, settings

    def pod(self, name):
        return self.kube.get('/api/v1/namespaces/' + quote(self.settings.namespace, safe='') + '/pods/' + quote(name, safe=''))

    def capture(self, iid, pod):
        incident = self.store.get(iid)['data']
        self.store.evidence(iid, 'get_workload_status', {}, {
            'availability': 'available', 'source': 'Kubernetes Pod API',
            'observed_at': now(), 'data': pod_status(pod)})
        for name in ('get_k8s_events', 'get_logs'):
            self.call(iid, name, {})
        self.freeze_ebpf(iid)

    def freeze_ebpf(self, iid):
        inc = self.store.get(iid)['data']
        end = epoch(inc['time'])
        windows = self.store.windows(inc['pod_uid'], inc['container_id'], end - 300, end)
        if not windows and self.store.meta('ebpf:' + iid):
            return
        self.store.meta('ebpf:' + iid, {'windows': windows, 'health': self.store.health(), 'captured_at': now()})

    def call(self, iid, name, args):
        if not isinstance(args, dict):
            raise ValueError('tool arguments must be an object')
        allowed = {t['function']['name']: t for t in TOOLS}
        if name not in allowed:
            raise ValueError('unknown tool')
        properties = allowed[name]['function']['parameters']['properties']
        if set(args) - set(properties):
            raise ValueError('unexpected tool argument')
        args = dict(args)
        if 'window_seconds' in properties:
            args.setdefault('window_seconds', 300)
            if type(args['window_seconds']) is not int or not 30 <= args['window_seconds'] <= 300:
                raise ValueError('window_seconds must be 30..300')
        if name == 'get_metrics':
            args.setdefault('metric', 'memory')
            if args['metric'] not in ('memory', 'cpu'):
                raise ValueError('unsupported metric')
        existing = self.store.cached(iid, name, args)
        if existing:
            return existing
        inc = self.store.get(iid)['data']
        if inc['namespace'] != self.settings.namespace:
            raise ValueError('namespace outside allowed scope')
        try:
            data = getattr(self, name)(inc, iid, **args)
        except (RemoteError, ValueError, KeyError) as e:
            data = {'availability': 'unavailable', 'error': str(e)[:150]}
        data['target'] = {k: inc[k] for k in ('namespace', 'pod_uid', 'pod', 'container_name', 'container_id', 'time')}
        return self.store.evidence(iid, name, args, data)

    def get_workload_status(self, inc, iid):
        pod = self.pod(inc['pod'])
        if pod['metadata']['uid'] != inc['pod_uid']:
            raise ValueError('pod was replaced; refusing status of another UID')
        return {'availability': 'available', 'source': 'Kubernetes Pod API', 'data': pod_status(pod)}

    def get_k8s_events(self, inc, iid):
        query = urlencode({'fieldSelector': 'involvedObject.uid=' + inc['pod_uid'], 'limit': 100})
        result = self.kube.get('/api/v1/namespaces/' + inc['namespace'] + '/events?' + query)
        end = epoch(inc['time'])
        events = []
        for e in result.get('items', []):
            ts = e.get('lastTimestamp') or e.get('eventTime') or e['metadata']['creationTimestamp']
            if end - 300 <= epoch(ts) <= end + 30:
                events.append({'time': ts, 'reason': e.get('reason'), 'type': e.get('type'),
                               'count': e.get('count', 1), 'message': e.get('message', '')[:500]})
        return {'availability': 'available', 'source': 'Kubernetes Events API',
                'events': sorted(events, key=lambda e: e['time'])[-15:],
                'truncated': len(events) > 15 or bool(result.get('metadata', {}).get('continue'))}

    def get_logs(self, inc, iid):
        pod = self.pod(inc['pod'])
        if pod['metadata']['uid'] != inc['pod_uid']:
            raise ValueError('pod UID no longer matches')
        statuses = pod.get('status', {}).get('containerStatuses', [])
        cs = next((s for s in statuses if s['name'] == inc['container_name']), {})
        previous = False
        if cs.get('containerID') != inc['container_id']:
            if cs.get('lastState', {}).get('terminated', {}).get('containerID') == inc['container_id']:
                previous = True
            else:
                raise ValueError('incident container logs no longer available')
        query = urlencode({'container': inc['container_name'], 'previous': str(previous).lower(),
                           'timestamps': 'true', 'tailLines': 60, 'limitBytes': 6000,
                           'sinceTime': stamp(epoch(inc['time']) - 300)})
        raw = self.kube.get('/api/v1/namespaces/' + inc['namespace'] + '/pods/' + inc['pod'] + '/log?' + query, raw=True)
        # Kubernetes has no untilTime: filter timestamped lines after the incident.
        lines = []
        for line in raw.splitlines():
            try:
                ts = epoch(line.split(' ', 1)[0])
            except (ValueError, IndexError):
                continue
            if ts <= epoch(inc['time']) + 5:
                lines.append(line)
        return {'availability': 'available', 'source': 'Kubernetes container logs', 'previous': previous,
                'lines': lines, 'bounded': True, 'possible_truncation': len(raw.encode()) >= 5900 or len(lines) >= 60}

    def get_metrics(self, inc, iid, metric='memory', window_seconds=300):
        # cAdvisor ID contains the Pod UID (systemd uses underscores). Reject name-only attribution.
        cid = inc['container_id'].split('://')[-1]
        if not cid:
            raise ValueError('container identity unavailable')
        uid_re = '.*pod' + inc['pod_uid'].replace('-', '[-_]') + '.*' + cid + '.*'
        labels = ','.join(k + '=' + json.dumps(v) for k, v in {
            'namespace': inc['namespace'], 'pod': inc['pod'], 'container': inc['container_name']}.items())
        labels += ',id=~' + json.dumps(uid_re) + ',job=~"rca-cadvisor-.*"'
        selector = '{' + labels + '}'
        queries = {
            'memory': {'working_set_bytes': 'sum(container_memory_working_set_bytes' + selector + ')',
                       'rss_bytes': 'sum(container_memory_rss' + selector + ')'},
            'cpu': {'usage_cores': 'sum(rate(container_cpu_usage_seconds_total' + selector + '[1m]))',
                    'throttled_period_ratio': 'sum(rate(container_cpu_cfs_throttled_periods_total' + selector + '[1m])) / clamp_min(sum(rate(container_cpu_cfs_periods_total' + selector + '[1m])), 0.000001)'},
        }
        end = epoch(inc['time'])
        series = {}
        for field, query in queries[metric].items():
            result = request(self.settings.prometheus + '/api/v1/query_range?' + urlencode({
                'query': query, 'start': end - window_seconds, 'end': end, 'step': 15, 'timeout': '8s'}))
            if result.get('status') != 'success':
                raise RemoteError('Prometheus query failed')
            points = []
            for s in result.get('data', {}).get('result', []):
                for ts, value in s.get('values', []):
                    if value not in ('NaN', '+Inf', '-Inf'):
                        points.append([ts, round(float(value), 4)])
            series[field] = {'points': points[-21:], 'samples': len(points),
                             'max': max((p[1] for p in points), default=None)}
        return {'availability': 'available' if any(s['samples'] for s in series.values()) else 'unavailable',
                'source': 'Prometheus cAdvisor', 'identity': 'pod UID + exact container ID + container name',
                'window_start': stamp(end - window_seconds), 'window_end': inc['time'],
                'series': series, 'sample_interval_seconds': 15,
                'limitation': 'Short spikes between scrapes can be missed; missing samples do not imply normal behavior.'}

    def get_ebpf_summary(self, inc, iid, window_seconds=300):
        snapshot = self.store.meta('ebpf:' + iid) or {'windows': [], 'health': {}}
        end = epoch(inc['time'])
        windows = [w for w in snapshot['windows'] if w['end'] > end - window_seconds and w['start'] < end]
        counts = Counter()
        for w in windows:
            counts.update(w['counts'])
        health = snapshot['health'].get(inc['node'], {})
        fresh = bool(health.get('received_at')) and abs(epoch(health['received_at']) - end) <= 60
        return {'availability': 'available' if windows else 'unavailable', 'source': 'Tetragon eBPF export',
                'window_start': stamp(end - window_seconds), 'window_end': inc['time'],
                'counts': {k: v for k, v in counts.items() if not k.startswith('tcp_attempt') and k != 'raw_event_bytes'},
                'network': network_summary(counts),
                'nonempty_buckets': len(windows), 'bucket_seconds': 10,
                'collector_fresh_at_capture': fresh, 'collector_health': health,
                'not_collected': ['scheduler_latency', 'major_page_faults', 'tcp_retransmissions'],
                'limitations': ['Counts cover observed exported events, not all kernel events.',
                                'Boundary buckets may include up to 10 seconds outside the requested interval.',
                                'No matching events is not proof of healthy behavior; exporter losses are not quantified.']}
