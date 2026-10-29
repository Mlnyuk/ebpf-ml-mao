"""Identity/time-qualified, lossless ledger, reusing the existing v4 encoder."""
import copy
import hashlib
from .common import compact, epoch, redact
from .context import present_evidence


def digest(value):return hashlib.sha256(compact(value).encode()).hexdigest()


def scope_of(e, incident, historical=False):
    if historical:return 'historical_context'
    target=e.get('target',{})
    if any(target.get(k) is None for k in ('pod_uid','container_id')):return 'unverified_identity'
    if any(target.get(k)!=incident.get(k) for k in ('namespace','pod_uid','container_id')):return 'other_target'
    try:
        start=epoch(incident.get('window_start',incident['time'])) if incident.get('window_start') else epoch(incident['time'])-300
        end=epoch(incident['time'])
        interval=e.get('interval_epoch')
        if interval is None and e.get('window_start') and e.get('window_end'):
            interval=[epoch(e['window_start']),epoch(e['window_end'])]
        if interval and (interval[1]<start or interval[0]>end):return 'historical_context'
        if target.get('time') and not start<=epoch(target['time'])<=end:return 'historical_context'
        # If every timestamped log/event is outside the incident interval, the
        # wrapper's target.time cannot turn those observations into current data.
        stamps=[]
        for line in e.get('lines',[]):
            try:stamps.append(epoch(line.split(' ',1)[0]))
            except (ValueError,AttributeError,IndexError):pass
        for event in e.get('events',[]):
            try:stamps.append(epoch(event['time']))
            except (ValueError,KeyError,TypeError):pass
        if stamps and all(t<start or t>end for t in stamps):return 'historical_context'
    except (ValueError,TypeError,KeyError):return 'unverified_time'
    return 'current_incident'


def state_of(e):
    if e.get('observation_state') in ('collection_failed','collection_missing','query_failed','period_expired','observed_zero','observed_nonzero'):
        return e['observation_state']
    if e.get('availability')!='available':return 'query_failed' if e.get('error') else 'collection_missing'
    for key in ('lines','events'):
        if key in e:return 'observed_nonzero' if e[key] else 'observed_zero'
    if 'series' in e and not any(s.get('points') for s in e['series'].values()):return 'collection_missing'
    return 'available'


def capabilities(e):
    return {
        'get_ebpf_summary':'Exported connection attempts/destinations/counts only; no connect outcome, latency or retransmissions.',
        'get_metrics':'Sampled values only; unsampled periods remain unknown.',
        'get_workload_status':'Resource state/configuration; Ready is not request success; lastState is historical.',
        'get_logs':'Captured application statements within recorded bounds; not complete execution history.',
        'get_k8s_events':'Pod events; cumulative/old reasons may be unrelated to this container.'
    }.get(e.get('tool'),'Scope limited to recorded source and interval.')


class Ledger:
    def __init__(self, incident):
        self.incident=copy.deepcopy(redact(incident));self.entries={};self.registry={};self.originals={}
        self.interpretation=None;self.query_states={};self.errors=[]
        self.target_label='/'.join(str(incident.get(k,'')) for k in ('namespace','pod','container_name'))+'@'+str(incident.get('container_id',''))

    def add(self, evidence, location, representation='compact'):
        original=copy.deepcopy(redact(evidence));eid=original['evidence_id']
        if eid in self.originals and self.originals[eid]!=original:raise ValueError('ambiguous evidence ID')
        self.originals[eid]=original
        payload=present_evidence(original,self.incident,'compact-v4') if representation=='compact' else original
        metadata=self._register(original,location,False,digest(payload))
        self.entries[eid]={'provenance':metadata,'representation':('lossless-compact-v4' if representation=='compact' else 'original-redacted'),'data':payload}
        return self.entries[eid]

    def _register(self,e,location,historical,representation_hash):
        eid=e['evidence_id']
        metadata={'evidence_id':eid,'source_location':location,'source':e.get('source'),
            'target':e.get('target',{}),'scope':scope_of(e,self.incident,historical),'state':state_of(e),
            'availability':e.get('availability','unknown'),
            'observation_interval':e.get('interval_epoch') or [e.get('window_start'),e.get('window_end')],
            'observed_at':e.get('observed_at'),'retrieved_at':e.get('retrieved_at'),'source_sha256':digest(e),
            'identity_binding':e.get('identity_binding'),
            'freshness':'incident-scoped snapshot; not current wall-clock health' if scope_of(e,self.incident,historical)=='current_incident' else 'context or unverified; not direct incident evidence',
            'representation_sha256':representation_hash,'supports_scope':capabilities(e)}
        if eid in self.registry and self.registry[eid]['source_sha256']!=metadata['source_sha256']:raise ValueError('ambiguous evidence ID')
        self.registry[eid]=metadata
        # Preserve the existing nested-ID fix, with an explicit trusted container
        # for historical records, not arbitrary dictionaries embedded in logs.
        for i,child in enumerate(e.get('historical_context',{}).get('evidence',[])):
            self._register(child,location+f'/historical_context/evidence/{i}',True,digest(child))
        return metadata

    def payload(self):
        return {'incident':self.incident,'affected_target_identifier':self.target_label,
            'evidence_ledger':list(self.entries.values()),'source_states':self.query_states,
            'nested_context_scopes':[m for eid,m in self.registry.items() if eid not in self.entries],
            'investigator_state_unverified':self.interpretation,'tool_errors':self.errors}
