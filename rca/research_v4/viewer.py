"""Standalone replay/review artifact and opt-in localhost live-execution server."""
import hashlib
import json
import secrets
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from urllib.parse import unquote,urlsplit
from research.evidence import digest
from rca.context import restore_evidence
from research_v4.engine import citation_registry

TEMPLATE=Path(__file__).with_name('viewer.html')


def build(study,out):
    out.mkdir(parents=True,exist_ok=False)
    cases=[json.loads(p.read_text()) for p in sorted((study/'agent-cases').glob('*.json'))]
    truth={t['case_id']:t for t in json.loads((study/'private/truth.json').read_text())['cases']}
    runs=[]
    for folder in study.glob('runs-*'):
        for p in sorted(folder.glob('*.json')):
            if p.name in ('schedule.json','completion.json'):continue
            r=json.loads(p.read_text());v=r['result'];cid=r['case_id'];c=next(c for c in cases if c['case_id']==cid)
            usage=[a['usage'] for a in v['attempts']];costs=[u.get('cost') for u in usage]
            runs.append({'run_id':r['run_id'],'case_id':cid,'arm':r['arm'],'repeat':r['repeat'],'state':v['state'],
                'total_tokens':sum(u.get('prompt_tokens',0)+u.get('completion_tokens',0) for u in usage),
                'cost_usd':sum(costs) if all(type(x) in (int,float) for x in costs) else None,'seconds':v['duration_seconds'] or 0,
                'answer':v['answer'],'error':v['error'],'retrievals':v['retrievals'],
                'evidence':list(citation_registry([restore_evidence(e,c['incident']) for e in v['shown_evidence']]).values()),
                'trace':[json.loads(line) for line in p.with_suffix('.jsonl').read_text().splitlines()]})
    for c in cases:
        parent=truth[c['case_id']]['independent_incident_id']
        # Server maps this fixed prefix to the selected study, independent of output directory.
        c['source_links']={n:'/source/private/'+parent+'/'+n for n in ['raw-export.json','summary-proof.json','capture.json']}
        c.pop('evidence')
    packet=json.loads((study/'report/independent-review-packet.json').read_text())
    reviewer_truth={t['review_id']:t['truth'] for t in json.loads((study/'private/reviewer-truth.json').read_text())}
    for p in packet['packets']:p['truth']=reviewer_truth[p['review_id']]
    signature=digest((study/'dataset.json').read_bytes())
    owner={'mode':'replay','dataset_hash':signature,'cases':cases,'runs':runs}
    masked={'mode':'review','dataset_hash':signature,'packets':packet['packets'],'rubric':packet['rubric']}
    for filename,data in [('index.html',owner),('review.html',masked)]:
        # JSON script content is escaped against HTML termination/injection.
        payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
        (out/filename).write_text(TEMPLATE.read_text().replace('__DATA__',payload))
    (out/'manifest.json').write_text(json.dumps({'dataset_sha256':signature,'runs':len(runs),'review_packets':len(packet['packets']),
        'reviewer_independence':'not externally verified','mode':'replay by default; live requires explicit server flag',
        'source_links':'Work through the localhost server; standalone HTML supports embedded evidence/requests but not external raw-file links.'},indent=2))


def serve(study,viewer,args):
    if args.enable_live and json.loads((study/'protocol.json').read_text()).get('version')!='paper-next-v1':
        raise ValueError('Live demonstrations require the new study and its separate budget; old artifacts are replay-only')
    csrf=secrets.token_urlsafe(24)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*values):pass
        def valid_host(self):return self.headers.get('Host') in ('127.0.0.1:'+str(server.server_port),'localhost:'+str(server.server_port))
        def send_json(self,code,value):
            data=json.dumps(value,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            if not self.valid_host():return self.send_json(403,{'error':'host not allowed'})
            path=unquote(urlsplit(self.path).path)
            if path=='/api/capabilities':
                budget=json.loads((study/'budget.json').read_text()) if (study/'budget.json').exists() else None
                return self.send_json(200,{'live_enabled':args.enable_live,'csrf':csrf,'budget':budget,'no_automatic_retry':True,'results':'formal registered results never replaced'})
            if path.startswith('/source/'):
                base=study;target=(base/path.removeprefix('/source/')).resolve()
                if not target.is_relative_to(base.resolve()) or target.suffix not in ('.json','.jsonl'):return self.send_json(403,{'error':'path not allowed'})
            else:
                base=viewer;target=(base/('index.html' if path=='/' else path.lstrip('/'))).resolve()
                if not target.is_relative_to(base.resolve()):return self.send_json(403,{'error':'path not allowed'})
            if not target.is_file():return self.send_json(404,{'error':'not found'})
            data=target.read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8' if target.suffix=='.html' else 'application/json');self.send_header('Content-Length',str(len(data)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
        def do_POST(self):
            if not self.valid_host() or self.path!='/api/live' or not args.enable_live:return self.send_json(403,{'error':'live execution disabled'})
            if self.headers.get('X-RCA-CSRF')!=csrf or self.headers.get('Origin') not in ('http://127.0.0.1:'+str(server.server_port),'http://localhost:'+str(server.server_port)):return self.send_json(403,{'error':'origin/token mismatch'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<4096:raise ValueError('request size')
                body=json.loads(self.rfile.read(size))
                if set(body)!={'case_id','arm','confirm_paid'} or body['confirm_paid'] is not True:raise ValueError('explicit paid confirmation required')
                from research_v4.run import live
                result=live(study,args,body['case_id'],body['arm']);return self.send_json(200,result)
            except BlockingIOError:return self.send_json(409,{'error':'another bounded API session owns the budget; no retry started'})
            except Exception as exc:return self.send_json(400,{'error':type(exc).__name__,'detail':str(exc)[:200],'automatic_retry':False})
    if args.enable_live and not (args.cluster_key or args.key_file):raise ValueError('live mode requires explicit key source')
    server=HTTPServer(('127.0.0.1',args.port),Handler)
    print(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port),'live_enabled':args.enable_live}),flush=True)
    try:server.serve_forever()
    finally:server.server_close()
