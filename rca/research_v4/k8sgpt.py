"""Native K8sGPT comparison; preserve scope gaps rather than call them errors."""
import json
import subprocess
import tempfile
import time
from pathlib import Path
from research.capture import write_new
from research.evidence import digest
from rca.common import now

ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT/'vendor/k8sgpt-v0.4.41/k8sgpt'


def native_scan(study,case_id):
    target=study/'private'/case_id/'k8sgpt-native.json'
    if not BIN.exists():
        write_new(target,{'status':'NOT_EXECUTED','reason':'pinned binary unavailable','at':now()});return
    with tempfile.TemporaryDirectory(prefix='rca-k8sgpt-config-') as directory:
        cfg=Path(directory)/'config.yaml'
        cfg.write_text('ai:\n  defaultprovider: noopai\n  providers:\n    - name: noopai\n      model: unused-no-explain\n      password: unused\n')
        setup=subprocess.run([str(BIN),'filters','add','Log','--config',str(cfg)],capture_output=True,text=True,timeout=20)
        args=[str(BIN),'analyze','--config',str(cfg),'--namespace','rca-lab','--output','json','--no-cache']
        started=time.monotonic()
        try:
            result=subprocess.run(args,capture_output=True,text=True,timeout=90)
            try:output=json.loads(result.stdout)
            except ValueError:output=None
            record={'status':'executed' if result.returncode==0 and output is not None else 'execution_failed',
                'at':now(),'seconds':time.monotonic()-started,'exit_code':result.returncode,
                'stdout':result.stdout,'stderr':result.stderr,'parsed':output}
        except subprocess.TimeoutExpired as exc:
            record={'status':'execution_failed','error':'timeout','seconds':time.monotonic()-started,
                'stdout':(exc.stdout or b'').decode() if isinstance(exc.stdout,bytes) else exc.stdout,
                'stderr':(exc.stderr or b'').decode() if isinstance(exc.stderr,bytes) else exc.stderr}
        record.update(version='v0.4.41',binary_sha256=digest(BIN.read_bytes()),
            command=[str(BIN),'analyze','--config','<ephemeral isolated config>','--namespace','rca-lab','--output','json','--no-cache'],
            cache='disabled; fresh config each occurrence',llm_calls=0,explain=False,
            filters='native defaults plus optional Log analyzer',filter_setup={'exit':setup.returncode,'stdout':setup.stdout,'stderr':setup.stderr},
            access='live Kubernetes namespace via existing kubeconfig; not Agent bounded snapshots',
            quality_classification='UNREVIEWED; no findings is not automatically misdiagnosis or appropriate abstention')
        write_new(target,record)


def native_explain(study,case_id):
    from research_v4.native_proxy import bridge
    spec=json.loads((study/'protocol.json').read_text());base=study/'private'/case_id
    with tempfile.TemporaryDirectory(prefix='rca-k8sgpt-explain-') as directory:
        cfg=Path(directory)/'config.yaml'
        with bridge(study,base/'k8sgpt-api.jsonl') as (url,state):
            cfg.write_text(json.dumps({'ai':{'defaultprovider':'openai','providers':[{'name':'openai','model':spec['model'],'password':'local-proxy-only','baseurl':url,'temperature':1,'topP':1}]}}))
            # The five relevant namespaced analyzers get the full namespace, not
            # our bounded evidence. Full default+Log scan is separately retained.
            args=[str(BIN),'analyze','--config',str(cfg),'--namespace','rca-lab','--filter','Pod,Service,Deployment,ReplicaSet,Log','--output','json','--no-cache','--explain','--backend','openai']
            start=time.monotonic()
            try:
                p=subprocess.run(args,capture_output=True,text=True,timeout=240)
                try:parsed=json.loads(p.stdout)
                except ValueError:parsed=None
                result={'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'parsed':parsed,
                    'status':'executed' if p.returncode==0 and parsed is not None else 'execution_failed'}
            except subprocess.TimeoutExpired:
                result={'status':'execution_failed','error':'native explanation timeout'}
            result.update(at=now(),seconds=time.monotonic()-start,model=spec['model'],provider=spec['provider_tag'],
                cache='disabled; fresh isolated config',scope='full rca-lab namespace; Pod, Service, Deployment, ReplicaSet, Log',
                requests=state['calls'],known_cost_usd=state['known_cost_usd'],provider_failed=state['failed'],
                native_output_contract='unchanged K8sGPT prose; not forced into our output schema',
                comparison_limit='Access and decision pipeline differ from Agent; do not treat native zero findings as appropriate abstention or unrelated global findings as target misdiagnosis.')
            write_new(base/'k8sgpt-explain.json',result)
            if state['failed']:raise RuntimeError('native provider failed; stop new paid work')
