"""Non-evaluation smoke checks with explicit cleanup and no external LLM calls."""
import json
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from research.capture import stopped,OperatorKube,kubectl,write_new
from research_v4.k8sgpt import native_scan,BIN
from rca.common import now


def native_positive_control(study):
    stopped();cid='native-control-'+uuid.uuid4().hex[:8];name='paper-'+cid
    target=study/'development';kube=OperatorKube()
    frontend=kube.get('/apis/apps/v1/namespaces/rca-lab/deployments/sample-service')
    image=frontend['spec']['template']['spec']['containers'][0]['image']
    obj={'apiVersion':'v1','kind':'Pod','metadata':{'namespace':'rca-lab','name':name,'labels':{'research-control':cid}},
         'spec':{'automountServiceAccountToken':False,'restartPolicy':'Never','nodeSelector':{'kubernetes.io/hostname':'worker-1'},
                 'containers':[{'name':'app','image':image,'imagePullPolicy':'IfNotPresent','command':['python','-c','print("RuntimeError: controlled application exit",flush=True); raise SystemExit(7)'],
                     'resources':{'requests':{'cpu':'50m','memory':'32Mi'},'limits':{'cpu':'200m','memory':'64Mi'}},
                     'securityContext':{'runAsUser':10001,'runAsNonRoot':True,'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}}}]}}
    kubectl('create','-f','-',data=json.dumps(obj));created=True
    try:
        deadline=time.monotonic()+60
        while True:
            pod=kube.get('/api/v1/namespaces/rca-lab/pods/'+name)
            if pod['status'].get('phase')=='Failed':break
            if time.monotonic()>deadline:raise RuntimeError('positive control did not terminate in time')
            time.sleep(1)
        write_new(target/'private'/cid/'pod.json',pod)
        native_scan(target,cid)
        scan=json.loads((target/'private'/cid/'k8sgpt-native.json').read_text())
        matched=[r for r in (scan.get('parsed') or {}).get('results',[]) if name in r.get('name','')]
        requests=[]
        class Mock(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(body)
                reply={'id':'transport-test-only','object':'chat.completion','created':int(time.time()),'model':body['model'],
                    'choices':[{'index':0,'message':{'role':'assistant','content':'TRANSPORT TEST ONLY. No diagnostic grading.'},'finish_reason':'stop'}],
                    'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}
                raw=json.dumps(reply).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=HTTPServer(('127.0.0.1',0),Mock);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='k8sgpt-transport-only-') as tmp:
                cfg=Path(tmp)/'config.yaml';cfg.write_text(json.dumps({'ai':{'defaultprovider':'openai','providers':[{'name':'openai','model':'z-ai/glm-5.3-flash','password':'mock-only','baseurl':f'http://127.0.0.1:{server.server_port}/v1','temperature':1,'topP':1}]}}))
                p=subprocess.run([str(BIN),'analyze','--config',str(cfg),'--namespace','rca-lab','--filter','Pod,Log','--selector','research-control='+cid,'--no-cache','--explain','--backend','openai','--output','json'],capture_output=True,text=True,timeout=45)
                write_new(target/'private'/cid/'transport-test.json',{'at':now(),'mock_transport_only':True,'external_llm_calls':0,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'requests':requests})
        finally:server.shutdown();server.server_close();thread.join(timeout=5)
        result={'at':now(),'case_id':cid,'pod':name,'native_positive_control_detected':bool(matched),'matched_findings':matched,
                'external_llm_calls':0,'mock_transport_requests':len(requests),'mock_transport_exit':p.returncode,'diagnostic_evaluation':False}
        write_new(target/'k8sgpt-positive-control.json',result)
        if not matched or not requests or p.returncode:raise ValueError('native positive-control/transport test failed')
    finally:
        if created:kubectl('-n','rca-lab','delete','pod',name,'--wait=true','--timeout=30s')
