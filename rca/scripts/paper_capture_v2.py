#!/usr/bin/env python3
"""Rotation-aware capture adapter. Preserves the failed first capture batch."""
import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.capture import capture, write_new
from research.evidence import digest
from scripts.paper_study import initialize, freeze, check
from scripts.capture_network_study import snapshot_pod
from scripts.rcactl import kubectl
from rca.common import now

REMOTE_SCAN = '''import pathlib,json,base64
uid=UID
records=[]; files=[]; total=0
paths=sorted(pathlib.Path('/tetragon').glob('tetragon*.log'))
for p in paths:
 if not p.is_file(): continue
 st=p.stat(); scanned=0
 if total+st.st_size>80000000: raise RuntimeError('bounded export scan would omit a retained file')
 with p.open('rb') as f:
  while f.tell()<st.st_size:
   offset=f.tell(); line=f.readline(65537); scanned+=len(line)
   if uid.encode() in line:
    if len(line)>65536 or not line.endswith(b'\\n'): raise RuntimeError('incomplete/oversize matching event')
    records.append({'path':str(p),'inode':st.st_ino,'offset':offset,'base64':base64.b64encode(line).decode()})
   if len(records)>10000: raise RuntimeError('capture record limit')
 after=p.stat()
 if st.st_ino!=after.st_ino or after.st_size<st.st_size: raise RuntimeError('export rotated during scan')
 files.append({'path':str(p),'inode':st.st_ino,'size_before':st.st_size,'size_after':after.st_size,'start_offset':0,'stable_inode':True,'scan_bytes':scanned})
 total+=scanned
if list(pathlib.Path('/tetragon').glob('tetragon*.gz')): raise RuntimeError('compressed retained export present; unsupported, do not silently omit')
if not paths: raise RuntimeError('no readable export files')
print(json.dumps({'records':records,'files':files,'scope':'all retained uncompressed current and rotated exports; kernel loss/older deleted exports remain unknown'}))
'''


def exported_lines(uid):
    return json.loads(kubectl('-n','rca-system','exec',snapshot_pod(),'--','python','-c',REMOTE_SCAN.replace('UID',repr(uid)),capture=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['init','capture'])
    parser.add_argument('--study',type=Path,default=ROOT/'artifacts/paper-v1-capture-v2-20261029')
    args=parser.parse_args(); study=args.study.resolve()
    if args.action=='init':
        initialize(study)
        write_new(study/'capture-amendment.json',{'recorded_at':now(),'version':'rotation-aware-v2',
            'previous_batch':'artifacts/paper-v1-20261029','reason':'captured export omitted retained rotated files; no model evaluation performed on failed batch',
            'changes':'Read all retained tetragon*.log files. Fail on rotation during scan, compressed retained logs, or byte/event bounds rather than silently omit.',
            'unchanged':'RCA controller, prompts, model/provider, four primary arms, three ablations, repeats, budgets, rubric, six captures/three dependent views.',
            'previous_cases_usage':'instrumentation development only; not pooled with fresh captures',
            'code_sha256':digest(Path(__file__).read_bytes())})
        freeze(study)
        write_new(study/'capture-freeze.json',{'frozen_at':now(),'sha256':{
            str(Path(__file__).resolve().relative_to(ROOT)):digest(Path(__file__).read_bytes()),
            str((study/'capture-amendment.json').relative_to(ROOT)):digest((study/'capture-amendment.json').read_bytes())}})
    else:
        check(study)
        for name,expected in json.loads((study/'capture-freeze.json').read_text())['sha256'].items():
            if digest((ROOT/name).read_bytes())!=expected: raise ValueError('capture adapter changed after freeze')
        with patch('research.capture.exported_lines',exported_lines):
            capture(study,json.loads((study/'protocol.json').read_text()))


if __name__=='__main__': main()
