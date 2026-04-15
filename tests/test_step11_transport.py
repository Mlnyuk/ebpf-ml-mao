from __future__ import annotations

import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ebpf_ml_mao.api import serve_api
from ebpf_ml_mao.transport import drain_spool, ship_report


class Step11TransportTest(unittest.TestCase):
    def test_ship_report_spools_on_failure_and_drain_replays(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            report_path = tmp / "report.json"
            report_path.write_text(json.dumps({"score": 1.0, "verdict": "anomalous"}), encoding="utf-8")
            spool_dir = tmp / "spool"

            result = ship_report(
                "http://127.0.0.1:9",
                node_name="node-a",
                report_path=report_path,
                spool_dir=spool_dir,
                retries=1,
                timeout=0.1,
            )
            self.assertEqual(result["status"], "spooled")
            self.assertEqual(len(list(spool_dir.glob("*.json"))), 1)

            registry_path = tmp / "registry.json"
            registry_path.write_text(json.dumps({"models": [], "active_model_id": None}), encoding="utf-8")
            ingest_dir = tmp / "ingest"
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()
            thread = threading.Thread(
                target=serve_api,
                kwargs={
                    "host": "127.0.0.1",
                    "port": port,
                    "registry_path": registry_path,
                    "ingest_dir": ingest_dir,
                    "shared_token": "",
                },
                daemon=True,
            )
            thread.start()
            time.sleep(0.2)

            drain = drain_spool(f"http://127.0.0.1:{port}", spool_dir=spool_dir, retries=1)
            self.assertEqual(drain["sent"], 1)
            self.assertEqual(drain["failed"], 0)
            self.assertFalse(list(spool_dir.glob("*.json")))
