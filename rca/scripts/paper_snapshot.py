#!/usr/bin/env python3
"""Archive already-frozen sources without changing an experiment or its results."""
import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.capture import write_new
from research.evidence import digest
from rca.common import now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True)
    args = parser.parse_args()
    study = args.study.resolve()
    files = {}
    for name in ('freeze.json', 'capture-freeze.json', 'analysis-freeze.json'):
        manifest = study / name
        for relative, expected in json.loads(manifest.read_text())['sha256'].items():
            path = (ROOT / relative).resolve()
            if not path.is_relative_to(ROOT):
                raise ValueError('archive path outside project')
            data = path.read_bytes()
            if digest(data) != expected:
                raise ValueError('frozen source changed: ' + relative)
            files[relative] = data
        files[str(manifest.relative_to(ROOT))] = manifest.read_bytes()
    archive = study / 'frozen-sources.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as target:
        for relative, data in sorted(files.items()):
            info = zipfile.ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            target.writestr(info, data)
    with zipfile.ZipFile(archive) as source:
        for relative, data in files.items():
            if source.read(relative) != data:
                raise ValueError('archive roundtrip failed')
    write_new(study / 'source-archive.json', {
        'created_at': now(), 'archive': archive.name,
        'sha256': digest(archive.read_bytes()), 'files': len(files),
        'scope': 'Exact frozen sources only; no credentials, no mutable results. Packaging performed after run start; does not change prior freezes.',
        'packager_sha256': digest(Path(__file__).read_bytes()),
    })
    print(json.dumps({'archive': str(archive), 'files': len(files), 'verified': True}))


if __name__ == '__main__':
    main()
