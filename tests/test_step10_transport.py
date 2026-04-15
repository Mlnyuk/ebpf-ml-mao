from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ebpf_ml_mao.transport import post_report


class Step10TransportTest(unittest.TestCase):
    def test_post_report_raises_when_server_unreachable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir, "report.json")
            report_path.write_text(json.dumps({"score": 1.0}), encoding="utf-8")
            with self.assertRaises(ValueError):
                post_report(
                    "http://127.0.0.1:9",
                    node_name="node-a",
                    report_path=report_path,
                    retries=1,
                    timeout=0.1,
                )
