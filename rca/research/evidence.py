"""Deterministic exported-event provenance, NOT an RCA decision engine."""
import hashlib
import json
from collections import Counter
from rca.common import compact, epoch
from rca.collector import event_identity


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else compact(value).encode()).hexdigest()


def summarize(raw_lines, incident, start, end, readable=True):
    if end <= start:
        raise ValueError('invalid half-open interval')
    peers, refs, rejected = Counter(), [], Counter()
    for line in raw_lines:
        try:
            event = json.loads(line)
            identity = event_identity(event, incident['namespace'])
            if not identity:
                rejected['namespace_or_identity'] += 1
                continue
            uid, cid, label, timestamp = identity
            if uid != incident['pod_uid'] or cid != incident['container_id']:
                rejected['different_container'] += 1
                continue
            if not start <= timestamp < end:
                rejected['outside_interval'] += 1
                continue
            if label != 'kprobe:tcp_connect':
                continue
            import ipaddress
            destinations = set()
            for arg in event['process_kprobe'].get('args', []):
                sock = arg.get('sock_arg', {})
                try:
                    ip = str(ipaddress.ip_address(sock['daddr']))
                    port = sock['dport']
                    if type(port) is int and 0 <= port <= 65535:
                        destinations.add((ip, port))
                except (KeyError, TypeError, ValueError):
                    pass
            if len(destinations) != 1:
                rejected['ambiguous_or_missing_socket'] += 1
                continue
            peer = next(iter(destinations))
            peers[peer] += 1  # exactly one connection attempt per exported event
            refs.append({'raw_sha256': digest(line.encode()), 'time': event['time'],
                         'pod_uid': uid, 'container_id': cid, 'destination': list(peer)})
        except (ValueError, KeyError, TypeError):
            rejected['malformed'] += 1
    state = 'collection_failed' if not readable else ('observed_nonzero' if refs else 'observed_zero')
    proof = {'interval': [start, end], 'boundary': '[start,end)', 'events': refs,
             'rejected': dict(rejected), 'raw_lines_sha256': digest(''.join(raw_lines).encode())}
    evidence = {'tool': 'get_ebpf_summary', 'availability': 'available' if readable else 'unavailable',
                'observation_state': state, 'source': 'Exact-window Tetragon exported-event replay',
                'target': dict(incident), 'interval_epoch': [start, end],
                'network': {'tcp_connect_attempts': [{'destination_ip': ip, 'destination_port': port, 'attempts': count}
                            for (ip, port), count in sorted(peers.items())] if readable else [],
                            'semantics': 'connection attempts only; NOT success/failure',
                            'not_measured': ['connect_result', 'connection_latency', 'tcp_retransmissions']},
                'provenance_sha256': digest(proof),
                'limitations': ['Zero means zero matching valid events in the captured export, NOT zero kernel activity.',
                                'Export/kernel loss and upstream duplicate delivery are not quantified.',
                                'Raw read completeness and parse exclusions are recorded in the private audit.']}
    evidence['evidence_id'] = 'ev-' + digest(evidence)[:20]
    return evidence, proof


def verify_chain(evidence, proof, raw_lines, incident):
    rebuilt, rebuilt_proof = summarize(raw_lines, incident, *proof['interval'],
                                      readable=evidence['observation_state'] != 'collection_failed')
    if rebuilt != evidence or rebuilt_proof != proof:
        raise ValueError('Raw/summary/identity/time/provenance mismatch')
    return True


def mismatch_baseline(case):
    """Offline comparator ONLY; never used by the LLM/controller."""
    status = next((e for e in case['evidence'] if e['tool'] == 'get_workload_status'), {})
    summary = next((e for e in case['evidence'] if e['tool'] == 'get_ebpf_summary'), {})
    contract = status.get('data', {}).get('declared_dependency')
    try:
        contract = json.loads(contract) if isinstance(contract, str) else contract
        expected = (contract['expected_ip'], contract['expected_port'])
    except (KeyError, TypeError, ValueError):
        return {'status': 'unassessable', 'reason': 'no declared expected destination'}
    if summary.get('observation_state') not in ('observed_nonzero', 'observed_zero'):
        return {'status': 'unassessable', 'reason': 'collection unavailable/not retrieved'}
    attempts = summary['network']['tcp_connect_attempts']
    if not attempts:
        return {'status': 'unassessable', 'reason': 'zero observed attempts is not health'}
    mismatches = [p for p in attempts if (p['destination_ip'], p['destination_port']) != expected]
    return {'status': 'destination_mismatch' if mismatches else 'no_destination_mismatch_observed',
            'mismatches': mismatches, 'evidence_ids': [status['evidence_id'], summary['evidence_id']],
            'scope': 'Literal declared IP/port comparison only; not general RCA, DNS analysis, or reachability proof.'}
