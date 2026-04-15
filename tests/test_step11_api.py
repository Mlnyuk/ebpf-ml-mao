from __future__ import annotations

import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ebpf_ml_mao.api import serve_api
from ebpf_ml_mao.transport import post_report


class Step11APITest(unittest.TestCase):
    def test_api_deduplicates_report_and_tracks_ingest_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
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
                    "shared_token": "secret-token",
                },
                daemon=True,
            )
            thread.start()
            time.sleep(0.2)

            report_path = tmp / "report.json"
            report_path.write_text(json.dumps({"score": 0.5, "verdict": "normal"}), encoding="utf-8")
            first = post_report(f"http://127.0.0.1:{port}", node_name="node-a", report_path=report_path, shared_token="secret-token")
            second = post_report(f"http://127.0.0.1:{port}", node_name="node-a", report_path=report_path, shared_token="secret-token")
            self.assertEqual(first["status"], "stored")
            self.assertEqual(second["status"], "duplicate")

            with request.urlopen(f"http://127.0.0.1:{port}/v1/ingest", timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["received_count"], 2)
            self.assertEqual(payload["unique_count"], 1)
            self.assertEqual(payload["duplicates_count"], 1)
