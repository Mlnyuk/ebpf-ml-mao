#!/usr/bin/env python3
"""Import actual independent-human ratings; never invent missing scores."""
import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.capture import write_new
from research.evidence import digest
from rca.common import epoch, now

DIMENSIONS={'destination','affected_target','cause_type','time_confusion','container_confusion','abstention'}
ABSTENTIONS={'appropriate','excessive','insufficient','not_applicable','unassessable'}


def validate(ratings, mapping):
    known={m['review_id']:m for m in mapping}; seen=set()
    if not ratings:
        raise ValueError('No ratings supplied: independent review remains NOT_PERFORMED')
    for r in ratings:
        if r.get('review_id') not in known or not isinstance(r.get('reviewer_id'),str) or not r['reviewer_id'].strip():
            raise ValueError('unknown review or missing reviewer')
        if r.get('independent_of_implementation') is not True:
            raise ValueError('non-independent rating must not be presented as independent evaluation')
        key=(r['review_id'],r['reviewer_id'])
        if key in seen: raise ValueError('duplicate reviewer/answer; retain revisions separately, do not silently overwrite')
        seen.add(key); epoch(r['timestamp'])
        scores=r.get('scores',{})
        if not DIMENSIONS <= set(scores) or set(scores)-DIMENSIONS-{'claim_fidelity'}:
            raise ValueError('all separate rating dimensions required; use null for unassessable')
        if scores.get('claim_fidelity') is not None:
            raise ValueError('claim fidelity belongs in claim_ratings, not an aggregate score')
        for d in ('destination','affected_target','cause_type'):
            if scores[d] is not None and (type(scores[d]) is not int or scores[d] not in (0,1,2)): raise ValueError('invalid ordinal rating')
        for d in ('time_confusion','container_confusion'):
            if scores[d] is not None and type(scores[d]) is not bool: raise ValueError('invalid confusion rating')
        if scores['abstention'] not in ABSTENTIONS: raise ValueError('invalid abstention rating')
        if not isinstance(r.get('claim_ratings'),list) or not isinstance(r.get('rationale'),str) or not r['rationale'].strip():
            raise ValueError('claim-level assessment and rationale required')
        for c in r['claim_ratings']:
            if type(c.get('claim_index')) is not int or c['claim_index']<0 or c.get('rating') not in {'supported','contradicted','unsupported','unassessable'} or not c.get('rationale'):
                raise ValueError('invalid atomic claim rating')
    return known


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True)
    parser.add_argument('--ratings',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    document=json.loads(args.ratings.read_text()); ratings=document.get('ratings',[])
    mapping=json.loads((args.study/'private/review-mapping.json').read_text())
    known=validate(ratings,mapping)
    packets=json.loads((args.study/'report/independent-review-packet.json').read_text())['packets']
    packets={p['review_id']:p for p in packets}
    for r in ratings:
        claims=(packets[r['review_id']].get('answer') or {}).get('claims',[])
        if {c['claim_index'] for c in r['claim_ratings']}!=set(range(len(claims))) or len(r['claim_ratings'])!=len(claims):
            raise ValueError('every actual atomic claim must be assessed exactly once')
        if not packets[r['review_id']]['accepted_output'] and any(r['scores'][d] is not None for d in ('destination','affected_target','cause_type')):
            raise ValueError('execution fallback is not a semantic model answer; rate these dimensions null')
    reviewers=sorted({r['reviewer_id'] for r in ratings})
    complete=all(len({r['reviewer_id'] for r in ratings if r['review_id']==m['review_id']})>=2 for m in mapping)
    args.output.mkdir(parents=True,exist_ok=False)
    write_new(args.output/'original-ratings.json',document)
    rows=[{**known[r['review_id']],'reviewer':r['reviewer_id'],**{k:r['scores'][k] for k in sorted(DIMENSIONS)}} for r in ratings]
    with (args.output/'ratings.csv').open('x',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    agreement={}
    for d in sorted(DIMENSIONS):
        pairs=[]
        for m in mapping:
            values=[r for r in rows if r['review_id']==m['review_id'] and r[d] is not None]
            for i,a in enumerate(values):
                for b in values[i+1:]: pairs.append(a[d]==b[d])
        agreement[d]={'pairwise_comparisons':len(pairs),'matches':sum(pairs),'fraction':statistics.mean(pairs) if pairs else None}
    write_new(args.output/'summary.json',{'generated_at':now(),'status':'complete_two_raters' if complete else 'partial',
        'reviewers':reviewers,'ratings':len(ratings),'expected_answers':len(mapping),
        'agreement_descriptive_only':agreement,'adjudication':document.get('adjudication',[]),
        'source_sha256':digest(args.ratings.read_bytes()),
        'limitations':['Reviewer independence is declared by supplied records, not externally verified by this script.',
                       'Missing ratings remain missing; no assistant-generated ratings or automatic conflict adjudication.',
                       'Repeated model runs are not independent fault occurrences.']})


if __name__=='__main__': main()
