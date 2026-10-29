import hmac
import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .agent import Agent
from .common import Kubernetes, Settings, compact, epoch, now, secret
from .store import Store
from .telemetry import Telemetry


class Application:
    def __init__(self, settings=None, kube=None):
        self.settings = settings or Settings()
        self.kube = kube or Kubernetes()
        self.store = Store(self.settings.database)
        self.telemetry = Telemetry(self.kube, self.store, self.settings)
        self.agent = Agent(self.store, self.telemetry, self.settings)
        self.queue = queue.Queue(maxsize=50)
        self.start_time = time.time()
        self.poll_status = {'ok': False}

    def incident(self, body, dedup=None, pod=None, enqueue=True):
        if body.get('namespace', self.settings.namespace) != self.settings.namespace:
            raise ValueError('only the configured lab namespace is allowed')
        pod = pod or self.telemetry.pod(body['pod'])
        if pod.get('spec', {}).get('nodeName') not in ('worker-1', 'worker-3'):
            raise ValueError('incident target must be on worker-1 or worker-3')
        if body.get('pod_uid', pod['metadata']['uid']) != pod['metadata']['uid']:
            raise ValueError('pod UID mismatch')
        name = body.get('container_name', pod['spec']['containers'][0]['name'])
        if name not in [c['name'] for c in pod['spec']['containers']]:
            raise ValueError('unknown container')
        cs = next((c for c in pod.get('status', {}).get('containerStatuses', []) if c['name'] == name), {})
        cid = body.get('container_id') or cs.get('containerID', '')
        allowed_ids = {cs.get('containerID', ''), cs.get('lastState', {}).get('terminated', {}).get('containerID', '')}
        if cid not in allowed_ids:
            raise ValueError('unknown container ID')
        timestamp = body.get('time', now())
        if not time.time() - 86400 <= epoch(timestamp) <= time.time() + 60:
            raise ValueError('incident timestamp outside accepted range')
        incident = {'namespace': self.settings.namespace, 'pod': pod['metadata']['name'],
                    'pod_uid': pod['metadata']['uid'], 'container_name': name, 'container_id': cid,
                    'node': pod['spec']['nodeName'], 'time': timestamp,
                    'symptom': str(body.get('symptom', 'manual investigation'))[:500]}
        iid, created = self.store.add(incident, dedup or compact(incident))
        if created:
            try:
                self.telemetry.capture(iid, pod)
                state = ('paused' if not self.settings.llm_enabled else
                         'awaiting_api_key' if not secret(self.settings.api_key_file) else 'queued')
                self.store.update(iid, state)
                if enqueue and self.settings.llm_enabled:
                    self.queue.put_nowait(iid)
            except Exception as e:
                self.store.update(iid, 'capture_error', {'error': type(e).__name__})
        return self.store.get(iid)

    def poll(self):
        while True:
            try:
                pods = self.kube.get('/api/v1/namespaces/' + self.settings.namespace + '/pods')['items']
                for pod in pods:
                    if pod.get('spec', {}).get('nodeName') not in ('worker-1', 'worker-3'):
                        continue
                    for cs in pod.get('status', {}).get('containerStatuses', []):
                        key = 'seen:' + pod['metadata']['uid'] + ':' + cs['name']
                        previous = self.store.meta(key)
                        current = {'restarts': cs.get('restartCount', 0),
                                   'waiting': cs.get('state', {}).get('waiting', {}).get('reason', '')}
                        old_pod = epoch(pod['metadata']['creationTimestamp']) < self.start_time
                        if previous is None and old_pod:
                            self.store.meta(key, current)
                            continue
                        previous = previous or {'restarts': 0, 'waiting': ''}
                        if current['restarts'] > previous['restarts']:
                            ended = cs.get('lastState', {}).get('terminated', {})
                            self.incident({'pod': pod['metadata']['name'], 'container_name': cs['name'],
                                           'container_id': ended.get('containerID', cs.get('containerID', '')),
                                           'time': ended.get('finishedAt', now()), 'symptom': 'ContainerRestart'},
                                          key + ':restart:' + str(current['restarts']), pod)
                        elif current['waiting'] in ('CrashLoopBackOff', 'ImagePullBackOff') and current['waiting'] != previous['waiting'] and current['restarts'] == 0:
                            self.incident({'pod': pod['metadata']['name'], 'container_name': cs['name'],
                                           'symptom': current['waiting']}, key + ':waiting:' + current['waiting'], pod)
                        self.store.meta(key, current)
                self.poll_status = {'ok': True, 'last_success': now()}
            except Exception as e:
                self.poll_status = {'ok': False, 'error': type(e).__name__, 'time': now()}
            time.sleep(5)

    def worker(self):
        while True:
            iid = self.queue.get()
            try:
                # Allow the final 10s eBPF bucket to arrive, then preserve it beyond retention.
                delay = max(0, min(15, epoch(self.store.get(iid)['data']['time']) + 15 - time.time()))
                time.sleep(delay)
                self.telemetry.freeze_ebpf(iid)
                self.agent.run(iid)
            except Exception as e:
                self.store.update(iid, 'error', {'error': type(e).__name__})
            finally:
                self.queue.task_done()

    def start(self):
        for target in (self.poll, self.worker):
            threading.Thread(target=target, daemon=True).start()

    def preflight(self, iid):
        output = [self.telemetry.call(iid, name, args) for name, args in (
            ('get_workload_status', {}), ('get_k8s_events', {}), ('get_logs', {}),
            ('get_metrics', {'metric': 'memory'}), ('get_metrics', {'metric': 'cpu'}),
            ('get_ebpf_summary', {}))]
        return {'mode': 'telemetry_preflight', 'incident_id': iid, 'evidence': output}


def handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, body):
            data = compact(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            token = secret(app.settings.auth_file)
            return bool(token) and hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/healthz':
                self.respond(200, {'status': 'ok', 'llm_configured': bool(secret(app.settings.api_key_file)),
                                   'llm_enabled': app.settings.llm_enabled,
                                   'model': app.settings.model, 'pod_poll': app.poll_status,
                                   'collectors': app.store.health()})
                return
            if not self.authorized():
                self.respond(401, {'error': 'unauthorized'})
                return
            try:
                parts = path.strip('/').split('/')
                if path == '/incidents':
                    self.respond(200, app.store.list())
                elif len(parts) in (2, 3) and parts[0] == 'incidents':
                    iid = parts[1]
                    self.respond(200, app.store.all_evidence(iid) if parts[-1] == 'evidence' else app.store.get(iid))
                else:
                    self.respond(404, {'error': 'not found'})
            except ValueError as e:
                self.respond(404, {'error': str(e)})

        def do_POST(self):
            if not self.authorized():
                self.respond(401, {'error': 'unauthorized'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1_000_000:
                    raise ValueError('invalid body size')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('body must be an object')
                path = urlparse(self.path).path
                parts = path.strip('/').split('/')
                if path == '/internal/windows':
                    app.store.ingest(body)
                    self.respond(200, {'accepted': True})
                elif path == '/incidents':
                    self.respond(201, app.incident(body))
                elif path == '/preflight':
                    inc = app.incident({**body, 'symptom': 'Telemetry preflight (not an RCA result)'},
                                       dedup='preflight:' + now(), enqueue=False)
                    # Preflight gathers all tools, but never invokes a real or fake LLM.
                    iid = inc['id']
                    app.store.update(iid, 'preflight')
                    self.respond(200, app.preflight(iid))
                elif len(parts) == 3 and parts[0] == 'incidents' and parts[2] == 'preflight':
                    app.store.get(parts[1])
                    self.respond(200, app.preflight(parts[1]))
                elif len(parts) == 3 and parts[0] == 'incidents' and parts[2] == 'run':
                    if not app.settings.llm_enabled:
                        raise ValueError('LLM calls are disabled; explicitly enable before running')
                    app.store.get(parts[1])
                    app.queue.put_nowait(parts[1])
                    self.respond(202, {'queued': parts[1]})
                elif path == '/alertmanager':
                    incidents = []
                    for alert in body.get('alerts', [])[:10]:
                        labels = alert.get('labels', {})
                        if alert.get('status') != 'firing' or labels.get('namespace') != app.settings.namespace or not labels.get('pod'):
                            continue
                        inc = app.incident({'namespace': labels['namespace'], 'pod': labels['pod'],
                                           'time': alert.get('startsAt', now()), 'symptom': labels.get('alertname', 'Alert')},
                                          'alert:' + compact([alert.get('fingerprint'), labels, alert.get('startsAt')]))
                        incidents.append(inc['id'])
                    self.respond(202, {'incidents': incidents})
                else:
                    self.respond(404, {'error': 'not found'})
            except (ValueError, KeyError, TypeError) as e:
                self.respond(400, {'error': str(e)[:200]})
            except queue.Full:
                self.respond(429, {'error': 'investigation queue full'})
            except Exception as e:
                self.respond(502, {'error': type(e).__name__})
    return Handler


def main():
    app = Application()
    app.start()
    print(compact({'component': 'rca-agent', 'model': app.settings.model, 'llm_configured': bool(secret(app.settings.api_key_file))}), flush=True)
    ThreadingHTTPServer(('0.0.0.0', 8080), handler(app)).serve_forever()


if __name__ == '__main__':
    main()
