"""Deploy only named research lab workloads. Never touch global collectors."""
import copy
import json
from pathlib import Path
from research.capture import stopped,write_new,OperatorKube,kubectl
from research.evidence import digest
from rca.common import now

ROOT=Path(__file__).resolve().parents[1]
CONTEXT_NAMES=['paper-context-a','paper-context-b','paper-context-c']


def configure(study):
    stopped()
    frontend=OperatorKube().get('/apis/apps/v1/namespaces/rca-lab/deployments/sample-service')
    write_new(study/'development/frontend-before.json',frontend)
    data={p.name:p.read_text() for p in (ROOT/'rca').glob('*.py')}
    data['lab.py']=(ROOT/'research_v4/lab.py').read_text()
    name='rca-lab-next-'+digest(data)[:12]
    cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':'rca-lab','name':name},'immutable':True,'data':data}
    kubectl('create','-f','-',data=json.dumps(cm))
    template=copy.deepcopy(frontend['spec']['template'])
    next(v for v in template['spec']['volumes'] if v['name']=='code')['configMap']['name']=name
    contract=json.loads(template['metadata']['annotations']['rca.lab/dependency-contract'])
    aux=OperatorKube().get('/api/v1/namespaces/rca-lab/services/sample-service')
    contract['allowed_auxiliary_destinations']=[{'service':'rca-lab/sample-service','expected_ip':aux['spec']['clusterIP'],'expected_port':8080,'critical':False}]
    template['metadata']['annotations']['rca.lab/dependency-contract']=json.dumps(contract)
    template['metadata']['annotations']['research/version']='paper-next-v1'
    template['spec']['terminationGracePeriodSeconds']=3
    kubectl('-n','rca-lab','patch','deployment','sample-service','--type=json','-p',json.dumps([
        {'op':'test','path':'/metadata/resourceVersion','value':frontend['metadata']['resourceVersion']},
        {'op':'replace','path':'/spec/template','value':template}]))
    kubectl('-n','rca-lab','rollout','status','deployment/sample-service','--timeout=120s')
    configure_context(template)
    write_new(study/'development/deployment.json',{'at':now(),'configmap':name,'code_sha256':digest(data),
              'context_deployments':CONTEXT_NAMES,'scope':'lab only; no Agent, Tetragon or policy mutation'})


def configure_context(template=None):
    stopped()
    if template is None:template=OperatorKube().get('/apis/apps/v1/namespaces/rca-lab/deployments/sample-service')['spec']['template']
    if template['metadata']['annotations'].get('research/version')!='paper-next-v1':raise ValueError('wrong lab version')
    for label in CONTEXT_NAMES:
        t=copy.deepcopy(template);t['metadata']={'labels':{'app':label,'research/version':'paper-next-v1'},'annotations':template['metadata']['annotations']}
        c=next(c for c in t['spec']['containers'] if c['name']=='app')
        c['env']+=[{'name':'BACKGROUND_LOAD','value':'true'},{'name':'CONTEXT_LABEL','value':label}]
        c['resources']={'requests':{'cpu':'50m','memory':'32Mi'},'limits':{'cpu':'500m','memory':'96Mi'}}
        obj={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':label,'namespace':'rca-lab','labels':{'research/version':'paper-next-v1'}},
             'spec':{'replicas':1,'selector':{'matchLabels':{'app':label}},'template':t}}
        existing=kubectl('-n','rca-lab','get','deployment',label,'--ignore-not-found','-o','json',capture=True)
        if existing.strip():
            d=json.loads(existing)
            if d['metadata'].get('labels',{}).get('research/version')!='paper-next-v1':raise ValueError('not owned test deployment')
            kubectl('-n','rca-lab','patch','deployment',label,'--type=json','-p',json.dumps([
                {'op':'test','path':'/metadata/resourceVersion','value':d['metadata']['resourceVersion']},
                {'op':'replace','path':'/spec/template','value':t}]))
        else:kubectl('create','-f','-',data=json.dumps(obj))
        kubectl('-n','rca-lab','rollout','status','deployment/'+label,'--timeout=120s')


def reset_frontend(logging):
    d=OperatorKube().get('/apis/apps/v1/namespaces/rca-lab/deployments/sample-service')
    t=copy.deepcopy(d['spec']['template'])
    c=next(c for c in t['spec']['containers'] if c['name']=='app')
    c['env']=[e for e in c['env'] if e['name']!='LOG_DETAIL']+[{'name':'LOG_DETAIL','value':logging}]
    t['metadata']['annotations']['research/capture-restart']=now()
    kubectl('-n','rca-lab','patch','deployment','sample-service','--type=json','-p',json.dumps([
        {'op':'test','path':'/metadata/resourceVersion','value':d['metadata']['resourceVersion']},
        {'op':'replace','path':'/spec/template','value':t}]))
    kubectl('-n','rca-lab','rollout','status','deployment/sample-service','--timeout=120s')


def stop_background():
    for name in CONTEXT_NAMES:
        kubectl('-n','rca-lab','scale','deployment/'+name,'--replicas=0')
