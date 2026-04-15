from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ebpf_ml_mao.transport import build_report_payload, drain_spool, prune_spool, spool_report, spool_status


class Step12TransportTest(unittest.TestCase):
    def test_spool_ttl_prunes_expired_and_quarantines_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            spool = Path(temp_dir, "spool")
            payload = {"node_name": "node-a", "report": {"verdict": "normal"}}
            expired = spool_report(spool, payload, ttl_seconds=0)
            time.sleep(1)
            corrupt = spool / "bad.json"
            corrupt.parent.mkdir(parents=True, exist_ok=True)
            corrupt.write_text("{bad-json}", encoding="utf-8")
            result = prune_spool(spool, ttl_seconds=0)
            self.assertEqual(result["removed"], 1)
            self.assertEqual(len(result["quarantined"]), 1)
            self.assertFalse(expired.exists())

    def test_spool_status_counts_expired(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            spool = Path(temp_dir, "spool")
            spool_report(spool, {"node_name": "node-a", "report": {}}, ttl_seconds=0)
            time.sleep(1)
            status = spool_status(spool, ttl_seconds=0)
            self.assertEqual(status["count"], 1)
            self.assertEqual(status["expired_count"], 1)
