"""Bounded lab service. Faults affect this container only; no host mutation."""
import json
import os
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlsplit, urlunsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def log(message):
    print(json.dumps({'time': time.time(), 'message': message}), flush=True)


routing_fault = None
routing_fault_until = 0


def fault(mode):
    global routing_fault, routing_fault_until
    time.sleep(1)
    if mode in ('network_port', 'network_peer'):
        routing_fault, routing_fault_until = mode, time.monotonic() + 90
        return
    if mode == 'crash':
        log('RuntimeError: required payment configuration is missing')
        os._exit(42)
    if mode == 'memory':
        blocks = []
        for _ in range(48):
            blocks.append(bytearray(4 * 1024 * 1024))
            log('request buffer bytes=' + str(len(blocks) * 4 * 1024 * 1024))
            time.sleep(0.8)
        log('allocation finished without OOM; verify container limit')
    if mode == 'cpu':
        deadline = time.monotonic() + 45
        log('starting compute request')
        while time.monotonic() < deadline:
            sum(i*i for i in range(10000))
        log('compute request finished')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        status, result = 200, {'ok': True, 'role': os.getenv('ROLE', 'frontend')}
        if self.path == '/work':
            subprocess.run(['/bin/true'], check=True, timeout=2)
            backend = os.getenv('BACKEND_URL')
            if backend:
                try:
                    target = backend
                    if time.monotonic() < routing_fault_until:
                        parts = urlsplit(backend)
                        if routing_fault == 'network_port':
                            target = urlunsplit((parts.scheme, parts.hostname + ':9099', parts.path, '', ''))
                        elif routing_fault == 'network_peer':
                            target = 'http://sample-service:8080'
                    with urllib.request.urlopen(target + '/healthz', timeout=2) as response:
                        result['dependency_status'] = response.status
                        if json.loads(response.read()).get('role') != 'backend':
                            raise ValueError('unexpected dependency')
                except Exception as e:
                    # Opaque-log benchmark: no endpoint or hidden injection
                    # label is exposed here. Both scenarios have the same log.
                    status, result = 503, {'error': 'dependency request failed'}
                    detail = (' target=' + target + ' error_type=' + type(e).__name__
                              if os.getenv('LOG_DETAIL', 'opaque') == 'endpoint' else '')
                    log('dependency request failed' + detail)
            log('request completed status=' + str(status))
        self.send_response(status)
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def do_POST(self):
        # Fault API only accepts loopback calls made through kubectl exec.
        mode = self.path.removeprefix('/fault/')
        if self.client_address[0] != '127.0.0.1' or mode not in ('crash', 'memory', 'cpu', 'network_port', 'network_peer'):
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(202)
        self.end_headers()
        self.wfile.write(b'{"accepted":true}')
        threading.Thread(target=fault, args=(mode,), daemon=True).start()


if __name__ == '__main__':
    log('service started')
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
