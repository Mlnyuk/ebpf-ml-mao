#!/usr/bin/env python3
"""Create an additive reproducibility archive, with hashes and credential scan."""
import argparse
import base64
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research_v4.protocol import check
from rca.common import now

PATTERNS=[rb'sk-or-v1-[A-Za-z0-9_-]{20,}',rb'sk-[A-Za-z0-9_-]{32,}',
          rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
          rb'Bearer\s+eyJ[A-Za-z0-9_.-]{80,}']


def check_bytes(data,name):
    if any(re.search(pattern,data) for pattern in PATTERNS):raise ValueError('Potential credential in '+name)
    # Exported Tetragon records are base64 inside JSON; scan the decoded records too.
    for match in re.finditer(rb'"base64"\s*:\s*"([A-Za-z0-9+/=]+)"',data):
        decoded=base64.b64decode(match.group(1),validate=True)
        if any(re.search(pattern,decoded) for pattern in PATTERNS):raise ValueError('Potential encoded credential in '+name)


def package(study,out):
    check(study)
    if not json.loads((study/'runs-main/completion.json').read_text())['complete']:raise ValueError('suite incomplete')
    files={}
    for folder in ('rca','research','research_v4','scripts','tests','deploy'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.html','.cjs','.yaml','.yml','.json','.md'):
                files[p.relative_to(ROOT).as_posix()]=p
    for name in ('README.md','Dockerfile'):
        files[name]=ROOT/name
    for p in study.rglob('*'):
        if p.is_file() and p.name!='.api.lock':files[p.relative_to(ROOT).as_posix()]=p
    for p in (ROOT/'vendor/k8sgpt-v0.4.41').rglob('*'):
        if p.is_file() and p.name not in ('k8sgpt','k8sgpt_Linux_x86_64.tar.gz'):
            files[p.relative_to(ROOT).as_posix()]=p
    hashes={}
    for name,p in sorted(files.items()):
        data=p.read_bytes();check_bytes(data,name);hashes['rca/'+name]=hashlib.sha256(data).hexdigest()
    manifest={'created_at':now(),'study':'paper-next-v1','files':hashes,
        'credential_scan':'Known API/private-key patterns scanned in plain files and base64 exported records; not a universal secret detector',
        'exclusions':['Previous study data: separately preserved original archive','K8sGPT binary and release tarball: download pinned v0.4.41 assets and verify frozen hashes','Runtime lock file'],
        'old_data_preserved':True,'human_quality':'NOT_EVALUATED','online_overhead':'NOT_MEASURED'}
    with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in sorted(files.items()):z.write(p,'rca/'+name)
        z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(out) as z:
        if z.testzip() is not None:raise ValueError('archive checksum failure')
        for name,h in hashes.items():
            if hashlib.sha256(z.read(name)).hexdigest()!=h:raise ValueError('archive source mismatch')
    sha=hashlib.sha256(out.read_bytes()).hexdigest()
    with out.with_suffix(out.suffix+'.sha256').open('x') as f:f.write(sha+'  '+out.name+'\n')
    with out.with_suffix(out.suffix+'.manifest.json').open('x') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
    print(json.dumps({'archive':str(out),'files':len(files),'bytes':out.stat().st_size,'sha256':sha,'verified':True}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();package(a.study.resolve(),a.output.resolve())
