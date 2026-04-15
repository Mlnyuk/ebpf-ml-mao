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

from ebpf_ml_mao.transport import enqueue_postprocess, prune_queue, queue_status


class Step13TransportTest(unittest.TestCase):
    def test_queue_status_counts_pending_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            queue = Path(temp_dir, "queue")
            enqueue_postprocess(queue, {"digest": "abc"}, ttl_seconds=60)
            status = queue_status(queue, ttl_seconds=60)
            self.assertEqual(status["count"], 1)
            self.assertEqual(status["pending_count"], 1)
            self.assertEqual(status["failed_count"], 0)
            self.assertIsNotNone(status["oldest_age_seconds"])

    def test_queue_prune_removes_expired_and_quarantines_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            queue = Path(temp_dir, "queue")
            expired = enqueue_postprocess(queue, {"digest": "abc"}, ttl_seconds=0)
            time.sleep(1)
            corrupt = queue / "bad.json"
            corrupt.parent.mkdir(parents=True, exist_ok=True)
            corrupt.write_text("{bad-json}", encoding="utf-8")
            result = prune_queue(queue, ttl_seconds=0)
            self.assertEqual(result["removed"], 1)
            self.assertEqual(len(result["quarantined"]), 1)
            self.assertFalse(expired.exists())
