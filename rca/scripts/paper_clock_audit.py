#!/usr/bin/env python3
"""Post-capture clock-offset bounds; no retrospective timestamp correction."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.rcactl import kubectl
from research.capture import write_new
from rca.common import now


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,required=True);a=p.parse_args()
    samples=[]
    for deployment,node in [('sample-service','worker-1'),('sample-backend','worker-3')]:
        for repeat in range(3):
            before=time.time()
            remote=float(kubectl('-n','rca-lab','exec','deployment/'+deployment,'--','python','-c','import time; print(time.time())',capture=True).strip())
            after=time.time()
            samples.append({'node':node,'repeat':repeat,'local_before':before,'local_after':after,'remote_epoch':remote,
                            'offset_interval_seconds':[remote-after,remote-before],
                            'offset_midpoint_seconds':remote-(before+after)/2,'round_trip_seconds':after-before})
    write_new(a.study/'clock-audit.json',{'measured_at':now(),'phase':'POST_CAPTURE diagnostic, not capture-time synchronization proof',
        'samples':samples,'warning':'Do not retrospectively shift frozen events using this later measurement. Exact numerical window replay is not proof of cross-node wall-clock alignment.'})
    print(json.dumps(samples,indent=2))


if __name__=='__main__':main()
