#!/usr/bin/env python3
"""Resolve a final atomic claim to shown evidence and exact exported-event locators."""
import argparse
import base64
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.evidence import digest, verify_chain
from rca.context import restore_evidence


def trace(study, run_id, claim_index):
    paths=list(study.glob('runs-*/'+run_id+'.json'))
    if len(paths)!=1: raise ValueError('run must resolve uniquely')
    run=json.loads(paths[0].read_text()); result=run['result']
    if not result.get('answer'): raise ValueError('no accepted model answer; inspect raw invalid responses instead')
    claims=result['answer']['claims']
    if type(claim_index) is not int or not 0<=claim_index<len(claims): raise ValueError('invalid claim index')
    case=json.loads((study/'agent-cases'/(run['case_id']+'.json')).read_text())
    by_id={e['evidence_id']:restore_evidence(e,case['incident']) for e in result['shown_evidence']}
    resolved=[]
    for eid in claims[claim_index]['evidence_ids']:
        if eid not in by_id: raise ValueError('citation not shown')
        evidence=by_id[eid]
        item={'evidence_id':eid,'shown_snapshot':evidence,'snapshot_sha256':digest(evidence)}
        proof_digest=evidence.get('provenance_sha256')
        if proof_digest:
            proofs=[p for p in (study/'private').glob('*/summary-proof.json') if digest(json.loads(p.read_text()))==proof_digest]
            if len(proofs)!=1:raise ValueError('missing or ambiguous summary proof')
            proof_path=proofs[0]; proof=json.loads(proof_path.read_text())
            raw=json.loads((proof_path.parent/'raw-export.json').read_text())
            records={}
            for record in raw['records']:
                line=base64.b64decode(record['base64']).decode()
                records.setdefault(digest(line.encode()),[]).append({k:v for k,v in record.items() if k!='base64'})
            # Dependent views may cite an unchanged parent summary. Its target
            # stays that parent's incident identity, never silently rewritten.
            verify_chain(evidence,proof,[base64.b64decode(r['base64']).decode() for r in raw['records']],evidence['target'])
            item.update(proof=str(proof_path.relative_to(study)),verified=True,
                raw_event_locators=[{**event,'locators':records.get(event['raw_sha256'],[])} for event in proof['events']])
        else:
            item['raw_kernel_trace']='not applicable/unavailable for this evidence; no fabricated raw provenance'
        resolved.append(item)
    return {'run_id':run_id,'claim_index':claim_index,'claim':claims[claim_index],'sources':resolved,
            'warning':'Verified traceability does not validate causal truth or connection outcomes.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,required=True);p.add_argument('--run-id',required=True);p.add_argument('--claim',type=int,required=True)
    a=p.parse_args(); print(json.dumps(trace(a.study,a.run_id,a.claim),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
