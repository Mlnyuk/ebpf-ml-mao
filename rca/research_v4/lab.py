"""Versioned lab-only faults and real surrounding traffic; no host mutations."""
import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, urlunsplit

MODES={'normal','application_error','route_error','mixed_route_error','auxiliary_error'}
mode='normal';expires=0


def log(message):
    print(json.dumps({'time':time.time(),'message':message}),flush=True)


def route(url,port):
    p=urlsplit(url)
    return urlunsplit((p.scheme,p.hostname+':'+str(port),p.path,'',''))


def work(active,detail,backend,aux,fetch):
    """Injected labels stay in private control, never in workload logs/responses."""
    target=route(backend,9099) if active in ('route_error','mixed_route_error') else backend
    status=200
    try:
        fetch(target+'/healthz')
        if active=='application_error':
            raise ArithmeticError('calculation rejected')
    except Exception as exc:
        status=503
        extra=(' component=application error_type=ArithmeticError' if isinstance(exc,ArithmeticError) else ' component=dependency target='+target+' error_type='+type(exc).__name__)
        log('request processing failed'+(extra if detail=='endpoint' else ''))
    if active in ('mixed_route_error','auxiliary_error'):
        auxiliary=route(aux,9099) if active=='auxiliary_error' else aux
        try:fetch(auxiliary+'/healthz')
        except Exception as exc:log('noncritical auxiliary warning'+(' target='+auxiliary+' error_type='+type(exc).__name__ if detail=='endpoint' else ''))
    log('request completed status='+str(status))
    return status


def fetch(url):
    with urllib.request.urlopen(url,timeout=1.5) as r:r.read();return r.status


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        status=200
        if self.path.startswith('/work'):
            active=mode if time.monotonic()<expires else 'normal'
            status=work(active,os.getenv('LOG_DETAIL','opaque'),os.environ['BACKEND_URL'],os.getenv('AUX_URL','http://sample-service:8080'),fetch)
            if os.getenv('BACKGROUND_LOAD'):
                log('route='+self.path+' tenant='+os.getenv('CONTEXT_LABEL','context')+' response_bytes='+str(len(self.path)*17))
        self.send_response(status);self.end_headers();self.wfile.write(json.dumps({'ok':status==200}).encode())
    def do_POST(self):
        global mode,expires
        candidate=self.path.removeprefix('/fault/')
        if self.client_address[0]!='127.0.0.1' or candidate not in MODES:
            self.send_response(403);self.end_headers();return
        mode=candidate;expires=time.monotonic()+120
        self.send_response(202);self.end_headers();self.wfile.write(b'{"accepted":true}')


def background():
    time.sleep(2);n=0
    while True:
        n+=1
        try:fetch('http://127.0.0.1:8080/work?resource='+str(n%19)+'&request='+str(n))
        except Exception:pass
        time.sleep(0.7)


if __name__=='__main__':
    if os.getenv('BACKGROUND_LOAD'):threading.Thread(target=background,daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
