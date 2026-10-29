#!/usr/bin/env python3
"""Bounded offline summary replay; never changes collectors or calls an API."""
import argparse
import base64
import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.capture import write_new
from research.evidence import digest,summarize
from research_v4.analyze import write_csv
from research_v4.protocol import check
from rca.common import now


def benchmark(study,out):
    check(study)
    truth=json.loads((study/'private/truth.json').read_text())['cases']
    parents=sorted({t['independent_incident_id'] for t in truth if t['view']=='original'})
    out.mkdir(parents=True,exist_ok=False)
    plan={'registered_at':now(),'version':'offline-summary-next-v1','status':'posthoc_exploratory_component_measurement',
        'script_sha256':digest(Path(__file__).read_bytes()),'summary_source_sha256':digest((ROOT/'research/evidence.py').read_bytes()),
        'occurrences':parents,'warmup_per_occurrence':1,'timing_repeats':3,'traced_memory_repeats':1,
        'timing':'perf_counter and process_time around summarize only; decoded input is resident before timing',
        'memory':'separate tracemalloc pass around summarize; peak tracked Python allocations, not process RSS or node memory',
        'excluded':['export acquisition','base64 decoding','raw file I/O','long-running collector','kernel policy','service impact','cold imports'],
        'environment':{'python':sys.version,'platform':platform.platform(),'host':'shared execution host; no exclusive CPU allocation'},
        'stop_rule':'fail on mismatch; no replacing a failed sample','online_overhead':'NOT_MEASURED'}
    write_new(out/'protocol.json',plan)
    samples=[]
    for parent in parents:
        raw=json.loads((study/'private'/parent/'raw-export.json').read_text())
        proof=json.loads((study/'private'/parent/'summary-proof.json').read_text())
        case=json.loads((study/'agent-cases'/(parent+'-small.json')).read_text())
        expected=next(e for e in case['evidence'] if e['tool']=='get_ebpf_summary')
        lines=[base64.b64decode(x['base64']).decode() for x in raw['records']]
        incident=case['incident'];interval=proof['interval']
        if summarize(lines,incident,*interval)!=(expected,proof):raise ValueError('warmup mismatch')
        for repeat in range(3):
            wall=time.perf_counter();cpu=time.process_time()
            result=summarize(lines,incident,*interval)
            cpu=time.process_time()-cpu;wall=time.perf_counter()-wall
            if result!=(expected,proof):raise ValueError('timed replay mismatch')
            row={'occurrence':parent,'repeat':repeat,'raw_lines':len(lines),'raw_bytes':sum(len(x.encode()) for x in lines),
                'selected_attempts':len(proof['events']),'wall_seconds':wall,'cpu_seconds':cpu}
            samples.append(row);write_new(out/(parent+'-timing-'+str(repeat)+'.json'),row)
        tracemalloc.start()
        result=summarize(lines,incident,*interval)
        current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        if result!=(expected,proof):raise ValueError('allocation replay mismatch')
        write_new(out/(parent+'-allocations.json'),{'occurrence':parent,'retained_traced_bytes':current,'peak_traced_bytes':peak,
            'scope':'Python tracked allocations only; includes produced evidence/proof; excludes resident input and interpreter'})
    write_csv(out/'timing-samples.csv',samples)
    grouped=[]
    for parent in parents:
        rs=[r for r in samples if r['occurrence']==parent]
        mem=json.loads((out/(parent+'-allocations.json')).read_text())
        grouped.append({'occurrence':parent,'raw_lines':rs[0]['raw_lines'],'raw_bytes':rs[0]['raw_bytes'],
            'selected_attempts':rs[0]['selected_attempts'],'median_wall_seconds':statistics.median(r['wall_seconds'] for r in rs),
            'median_cpu_seconds':statistics.median(r['cpu_seconds'] for r in rs),'peak_traced_bytes':mem['peak_traced_bytes']})
    write_csv(out/'occurrences.csv',grouped)
    summary={'finished_at':now(),'complete':True,'occurrences':len(parents),'timing_samples':len(samples),
        'median_of_occurrence_median_wall_seconds':statistics.median(r['median_wall_seconds'] for r in grouped),
        'median_of_occurrence_median_cpu_seconds':statistics.median(r['median_cpu_seconds'] for r in grouped),
        'maximum_peak_traced_bytes':max(r['peak_traced_bytes'] for r in grouped),
        'online_overhead':'NOT_MEASURED','inference':'Offline resident-input component replay only; cannot establish low service/cluster overhead.'}
    write_new(out/'summary.json',summary);print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();benchmark(a.study.resolve(),a.output.resolve())
