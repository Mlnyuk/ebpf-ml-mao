"""Read-only adapters. Frozen replay NEVER falls back to Kubernetes/network."""
import copy
import json
import time
from urllib.parse import quote, urlencode
from .common import compact, now, redact
from .context import present_evidence
from .evidence_ledger import digest, scope_of
from .replay import query_key

KINDS=('get_workload_status','get_k8s_events','get_logs','metrics_cpu','metrics_memory','get_ebpf_summary')


def source_key(e):
    if e.get('source_key'):return e['source_key']
    if e['tool']=='get_metrics':return 'metrics_memory' if 'working_set_bytes' in e.get('series',{}) else 'metrics_cpu'
    return e['tool']


def dependency_uids(evidence):
    """Only explicit captured EndpointSlice targetRefs, never IP/name guessing."""
    uids=set()
    for e in evidence:
        data=e.get('data',{});mapping=data.get('expected_destination_source',{})
        for endpoint in mapping.get('endpoints',[]):
            ref=endpoint.get('targetRef',{})
            if ref.get('kind')=='Pod' and ref.get('uid'):uids.add(ref['uid'])
    return uids


class FrozenSources:
    frozen=True
    def __init__(self, case):
        if set(case)!={'case_id','incident','evidence'}:raise ValueError('public case fields only; private truth is not accepted')
        self.incident=copy.deepcopy(case['incident']);self.records={};self.locations={};self.reads=[]
        self.dependency_uids=dependency_uids(case['evidence'])
        for i,e in enumerate(case['evidence']):
            key=source_key(e)
            if key in self.records:raise ValueError('ambiguous source key')
            self.records[key]=copy.deepcopy(e);self.locations[key]=f'agent-cases/{case["case_id"]}.json#/evidence/{i}'

    def descriptors(self):
        out=[]
        for key,e in sorted(self.records.items()):
            scope=scope_of(e,self.incident)
            identity_matches=all(e.get('target',{}).get(k)==self.incident.get(k) for k in ('namespace','pod_uid','container_id'))
            group='target' if identity_matches else ('dependency' if e.get('target',{}).get('pod_uid') in self.dependency_uids else 'other')
            out.append({'source':key,'tool':e['tool'],'group':group,'scope':scope,
                'contains_historical_context':bool(e.get('historical_context')),
                'target':{k:e.get('target',{}).get(k) for k in ('namespace','pod','pod_uid','container_id')},
                'estimated_bytes':len(compact(present_evidence(redact(e),self.incident,'compact-v4')).encode())+700,
                'availability':e.get('availability','unknown'),'immutable':True})
        return out

    def version(self,key):return digest(self.records[key])

    def normalize_window(self,key,window):return window

    def read(self,key,window_seconds=None,refresh=False):
        if key not in self.records:raise ValueError('source not in authorized catalog')
        self.reads.append((key,window_seconds));e=copy.deepcopy(self.records[key])
        if window_seconds is not None:
            raise ValueError('frozen source has an exact captured interval; request original window (null), no live fallback')
        return e,self.locations[key]

    def expand(self, group, cursor=0):return {'next_cursor':None}


class LiveSources:
    """Incident target plus explicitly requested namespace-scoped exploration.

    Captured incident records are immutable. Live windows use TTL+version keys;
    refresh is explicit and target/time/arguments remain checked by Telemetry.
    """
    frozen=False
    def __init__(self, iid, telemetry, allow_ebpf=True, ttl=15, clock=time.monotonic):
        self.iid,self.telemetry=iid,telemetry;self.incident=telemetry.store.get(iid)['data']
        if self.incident['namespace']!=telemetry.settings.namespace:raise ValueError('namespace outside allowed scope')
        self.ttl,self.clock=ttl,clock;self.targets={};self.sources={};self.allow_ebpf=allow_ebpf
        self._register('target',self.incident,'target')

    def _register(self,prefix,target,group):
        for kind in KINDS:
            if kind=='get_ebpf_summary' and (not self.allow_ebpf or group!='target'):continue
            name='get_metrics' if kind.startswith('metrics_') else kind
            args={'metric':kind.split('_')[1],'window_seconds':300} if name=='get_metrics' else ({'window_seconds':300} if name=='get_ebpf_summary' else {})
            key=prefix+'.'+kind
            self.sources[key]={'tool':name,'args':args,'target':copy.deepcopy(target),'group':group}

    def set_deadline(self,deadline):
        if hasattr(self.telemetry,'for_deadline'):
            self.telemetry=self.telemetry.for_deadline(deadline)

    def _captured(self,s):
        return self.telemetry.store.cached(self.iid,s['tool'],s['args']) if s['group']=='target' else None

    @staticmethod
    def _immutable(s,cached):
        if s['tool']=='get_ebpf_summary':return True  # versioned captured export, not a live probe call
        return bool(cached) and s['tool']!='get_metrics' and (
            cached.get('availability')=='available' or cached.get('observation_state')=='period_expired')

    def descriptors(self):
        out=[]
        for key,s in sorted(self.sources.items()):
            cached=self._captured(s);immutable=self._immutable(s,cached)
            estimate=len(compact(present_evidence(cached,self.incident,'compact-v4')).encode())+700 if cached else {
                'get_logs':7000,'get_k8s_events':8500,'get_workload_status':5000,'get_metrics':3500,'get_ebpf_summary':5000}[s['tool']]
            out.append({'source':key,'tool':s['tool'],'group':s['group'],'scope':scope_of({'target':s['target']},self.incident),
                'target':{k:s['target'].get(k) for k in ('namespace','pod','pod_uid','container_id')},
                'estimated_bytes':estimate,'availability':cached.get('availability') if cached else 'not_retrieved','immutable':immutable})
        return out

    def version(self,key):
        s=self.sources[key];cached=self._captured(s)
        if s['tool']=='get_ebpf_summary':return digest(self.telemetry.store.meta('ebpf:'+self.iid) or {})
        if self._immutable(s,cached):return cached['evidence_id']
        return int(self.clock()//self.ttl)

    def normalize_window(self,key,window):
        return self.sources[key]['args'].get('window_seconds') if window is None else window

    def read(self,key,window_seconds=None,refresh=False):
        s=self.sources[key];args=dict(s['args'])
        if window_seconds is not None:
            if 'window_seconds' not in args:raise ValueError('tool has immutable captured interval')
            args['window_seconds']=window_seconds
        query_key(s['tool'],args)  # same allowlist/default/type/range validation
        if s['group']=='target':
            # Cached snapshot tools remain frozen; mutable windows can refresh.
            dynamic=s['tool']=='get_ebpf_summary' or not self._immutable(s,self._captured(s))
            e=self.telemetry.call(self.iid,s['tool'],args,refresh=dynamic)
        else:
            e=self.telemetry.read_scoped(self.iid,s['target'],s['tool'],args)
        # Original captured status sometimes lacks target. Its incident binding
        # is the Store's foreign key; never infer an arbitrary record's identity.
        if 'target' not in e:e={**e,'target':copy.deepcopy(s['target']),
            'identity_binding':{'source':'Store incident foreign key','incident_id':self.iid,'original_record_sha256':digest(e)}}
        return e,'store:evidence/'+e['evidence_id']

    def expand(self,group,cursor=0):
        if group=='target':return {'next_cursor':None}
        if type(cursor) is not int or cursor<0:raise ValueError('invalid catalog cursor')
        ns=self.incident['namespace'];query={'limit':100}
        # Opaque continuation tokens are held by adapter, never arbitrary URLs.
        token=self.targets.get(('cursor',cursor))
        if cursor and token is None:raise ValueError('unknown discovery cursor')
        if token:query['continue']=token
        result=self.telemetry._get('/api/v1/namespaces/'+quote(ns,safe='')+'/pods?'+urlencode(query))
        for p in result.get('items',[]):
            if p.get('metadata',{}).get('namespace',ns)!=ns:continue
            for cs in p.get('status',{}).get('containerStatuses',[]):
                if not cs.get('containerID'):continue
                target={**self.incident,'pod':p['metadata']['name'],'pod_uid':p['metadata']['uid'],
                    'container_name':cs['name'],'container_id':cs['containerID'],'node':p.get('spec',{}).get('nodeName')}
                if target['pod_uid']==self.incident['pod_uid'] and target['container_id']==self.incident['container_id']:continue
                self._register('scope-'+digest([target['pod_uid'],target['container_id']])[:12],target,'other')
        continuation=result.get('metadata',{}).get('continue')
        if continuation:self.targets[('cursor',cursor+1)]=continuation
        return {'next_cursor':cursor+1 if continuation else None,
                'dependency_mapping':'Not inferred from pod names. Namespace exploration stays available; service endpoint mapping not captured by this adapter.'}
