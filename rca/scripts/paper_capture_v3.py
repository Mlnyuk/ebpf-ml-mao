#!/usr/bin/env python3
"""Clock-aware capture with immutable prior failure batches and carried budget."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.paper_capture_v2 import exported_lines
from scripts.paper_study import initialize,freeze,check
from research.clock_capture import capture
from research.capture import write_new
from research.evidence import digest
from rca.common import now

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['init','capture'])
    p.add_argument('--study',type=Path,default=ROOT/'artifacts/paper-clock-v3-20261029');a=p.parse_args();study=a.study.resolve()
    if a.action=='init':
        initialize(study)
        prior=ROOT/'artifacts/paper-v1-capture-v2-20261029/budget.json'
        budget=json.loads(prior.read_text())
        write_new(study/'budget.json',budget)
        write_new(study/'initial-budget.json',{'source':str(prior.relative_to(ROOT)),'source_sha256':digest(prior.read_bytes()),'state':budget,
                                            'policy':'Carry all prior attempts and conservative unknown-charge reservations; do not reset $2/760 global guard.'})
        write_new(study/'capture-amendment.json',{'recorded_at':now(),'version':'clock-aware-v3',
            'prior_batches':['paper-v1-20261029: rotation omission','paper-v1-capture-v2-20261029: mixed node clock domain'],
            'changes':'Both eBPF/log reference-window bounds use worker-1 wall clock, checked against its monotonic duration. Prometheus query end is translated with bracketed measured offsets; raw timestamps and uncertainty retained. No node clock changes.',
            'unchanged':'LLM engine, seven arms, two repeats, output contract, repair policy, rubric. Prior incomplete studies never pooled into primary results.',
            'budget':'Initial budget carries previous study consumption; see initial-budget.json.'})
        freeze(study)
        paths=[Path(__file__).resolve(),ROOT/'scripts/paper_capture_v2.py',study/'capture-amendment.json',study/'initial-budget.json']
        write_new(study/'capture-freeze.json',{'frozen_at':now(),'sha256':{str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in paths}})
    else:
        check(study)
        for name,expected in json.loads((study/'capture-freeze.json').read_text())['sha256'].items():
            if digest((ROOT/name).read_bytes())!=expected:raise ValueError('capture amendment changed')
        capture(study,json.loads((study/'protocol.json').read_text()),exported_lines)

if __name__=='__main__':main()
