"""Unpack immutable historical test data without editing research artifacts."""
import atexit
import functools
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path


@functools.lru_cache(maxsize=1)
def legacy_root():
    directory=tempfile.TemporaryDirectory(prefix='rca-historical-tests-')
    atexit.register(directory.cleanup)
    root=Path(directory.name)
    with zipfile.ZipFile(Path(__file__).with_name('fixtures')/'legacy-v4-checkpoint.zip') as z:
        manifest=json.loads(z.read('manifest.json'))
        for name,expected in manifest['sha256'].items():
            destination=(root/name).resolve()
            if not destination.is_relative_to(root):raise ValueError('invalid fixture path')
            data=z.read(name)
            if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('historical fixture changed')
            destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
    return root
