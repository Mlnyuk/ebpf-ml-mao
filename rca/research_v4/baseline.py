"""Offline destination allowlist comparator; not used by the RCA controller."""
import json


def compare(case):
    evidence=case['evidence'];target=case['incident']['pod_uid']
    state=next((e for e in evidence if e['tool']=='get_workload_status' and e.get('target',{}).get('pod_uid')==target),{})
    ebpf=next((e for e in evidence if e['tool']=='get_ebpf_summary' and e.get('target',{}).get('pod_uid')==target),{})
    contract=state.get('data',{}).get('declared_dependency')
    try:
        contract=json.loads(contract) if isinstance(contract,str) else contract
        expected={(contract['expected_ip'],contract['expected_port'])}
        expected.update((d['expected_ip'],d['expected_port']) for d in contract.get('allowed_auxiliary_destinations',[]))
    except (TypeError,KeyError,ValueError):return {'state':'unassessable','reason':'declared dependency contract unavailable'}
    if ebpf.get('observation_state')!='observed_nonzero':return {'state':'unassessable','reason':'no usable nonzero connection-attempt evidence'}
    unexpected=[x for x in ebpf['network']['tcp_connect_attempts'] if (x['destination_ip'],x['destination_port']) not in expected]
    return {'state':'destination_mismatch' if unexpected else 'no_mismatch_observed','unexpected':unexpected,
        'evidence_ids':[state['evidence_id'],ebpf['evidence_id']],
        'scope':'Allowed destination membership only. Does not determine application health, connection outcome, or whether unexpected traffic is critical.',
        'llm_calls':0,'diagnostic_quality':'NOT_HUMAN_EVALUATED'}
