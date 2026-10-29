import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from scripts.paper_capture_v2 import REMOTE_SCAN


class RotationTests(unittest.TestCase):
    def test_current_and_rotated_lines_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'tetragon.log').write_text('{"uid":"wanted","n":2}\n')
            (p/'tetragon-2026-10-29.log').write_text('{"uid":"wanted","n":1}\n')
            (p/'other.log').write_text('{"uid":"wanted","n":9}\n')
            code=REMOTE_SCAN.replace("'/tetragon'",repr(tmp)).replace('UID',repr('wanted'))
            result=json.loads(subprocess.run([sys.executable,'-c',code],check=True,capture_output=True,text=True).stdout)
            self.assertEqual(len(result['records']),2)
            self.assertEqual(len(result['files']),2)

    def test_compressed_archive_is_not_silently_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'tetragon.log').write_text('{}\n'); (p/'tetragon-old.log.gz').write_bytes(b'not used')
            code=REMOTE_SCAN.replace("'/tetragon'",repr(tmp)).replace('UID',repr('wanted'))
            result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('compressed retained export',result.stderr)


if __name__=='__main__': unittest.main()
