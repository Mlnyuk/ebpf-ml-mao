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

from ebpf_ml_mao.api import rebuild_ingest_index, serve_api
from ebpf_ml_mao.transport import post_report


class Step12APITest(unittest.TestCase):
    def test_corrupt_ingest_index_is_rebuilt_on_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            registry_path = tmp / "registry.json"
            registry_path.write_text(json.dumps({"models": [], "active_model_id": None}), encoding="utf-8")
            ingest_dir = tmp / "ingest"
            ingest_dir.mkdir(parents=True, exist_ok=True)
            (ingest_dir / "index.json").write_text("{bad-json}", encoding="utf-8")
            node_dir = ingest_dir / "node-a"
            node_dir.mkdir()
            (node_dir / "sample.json").write_text(json.dumps({"node_name": "node-a", "report_name": "sample.json", "phase": "phase3", "report": {"verdict": "normal"}}), encoding="utf-8")

            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()
            thread = threading.Thread(target=serve_api, kwargs={"host": "127.0.0.1", "port": port, "registry_path": registry_path, "ingest_dir": ingest_dir, "shared_token": ""}, daemon=True)
            thread.start()
            time.sleep(0.2)

            with request.urlopen(f"http://127.0.0.1:{port}/v1/status", timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["ingest"]["unique_count"], 1)
            self.assertTrue(any(p.name.startswith("index-corrupt-") for p in ingest_dir.iterdir()))
