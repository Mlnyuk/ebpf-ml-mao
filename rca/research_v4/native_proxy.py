"""Transparent prompt bridge to the same bounded external provider for K8sGPT."""
import contextlib
import fcntl
import json
import os
import threading
from http.server import BaseHTTPRequestHandler,HTTPServer
from types import SimpleNamespace
from scripts.evaluate_frozen import BudgetProvider,evaluation_key
from research_v4.run import provider_settings,budget_for
from rca.common import redact


@contextlib.contextmanager
def bridge(study,record_path):
    spec=json.loads((study/'protocol.json').read_text())
    state={'calls':0,'failed':False,'known_cost_usd':0.0}
    class NativeProvider(BudgetProvider):
        def payload(self,messages,tools):
            body=super().payload(messages,tools)
            body.pop('tools',None);body.pop('tool_choice',None)
            return body
    with (study/'.api.lock').open('a') as lock,record_path.open('x') as stream:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        def record(item):
            stream.write(json.dumps(item,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())
        with evaluation_key(SimpleNamespace(cluster_key=True,key_file=None)) as key:
            settings=provider_settings(spec);settings.api_key_file=key
            provider=NativeProvider(settings,budget_for(study,spec))
            class Handler(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_POST(self):
                    try:
                        if state['failed']:raise ValueError('previous provider failure; no automatic retry')
                        if self.path!='/v1/chat/completions':raise ValueError('unsupported endpoint')
                        size=int(self.headers.get('Content-Length','0'))
                        if not 0<size<=200000:raise ValueError('request size bound')
                        body=json.loads(self.rfile.read(size));messages=body['messages']
                        if body.get('model')!=spec['model']:raise ValueError('model mismatch')
                        state['calls']+=1
                        record({'type':'request','native_request':body,'forwarded_request':provider.payload(messages,[]),
                            'note':'Native prompt unchanged. Common pinned provider, output cap and low reasoning are applied; no output schema rewrite.'})
                        answer=provider.complete(messages,[],60)
                        public={k:v for k,v in answer.items() if k in ('id','object','created','model','provider','usage')}
                        public['choices']=[{'index':c.get('index',0),'finish_reason':c.get('finish_reason'),
                            'message':{k:v for k,v in c.get('message',{}).items() if k in ('role','content','tool_calls')}} for c in answer.get('choices',[])]
                        record({'type':'response','response':redact(public)})
                        cost=answer.get('usage',{}).get('cost')
                        if isinstance(cost,(int,float)):state['known_cost_usd']+=cost
                        result=json.dumps(public).encode();self.send_response(200)
                    except Exception as exc:
                        state['failed']=True;record({'type':'error','error':type(exc).__name__})
                        result=json.dumps({'error':{'message':type(exc).__name__}}).encode();self.send_response(502)
                    self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(result)));self.end_headers()
                    try:self.wfile.write(result)
                    except (BrokenPipeError,ConnectionResetError):pass
            server=HTTPServer(('127.0.0.1',0),Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:yield 'http://127.0.0.1:'+str(server.server_port)+'/v1',state
            finally:server.shutdown();server.server_close();thread.join(timeout=5)
