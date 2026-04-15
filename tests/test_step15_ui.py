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


class Step15UITest(unittest.TestCase):
    def _free_port(self) -> int:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def test_ui_routes_return_dashboard_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            model_path = tmp / "model.json"
            model_path.write_text("{}", encoding="utf-8")
            registry_path = tmp / "registry.json"
            registry_path.write_text(json.dumps({
                "models": [{"id": "baseline-v2-01", "path": str(model_path), "model_type": "baseline", "schema_version": "v2", "threshold": 0.45, "feature_count": 3, "tags": []}],
                "active_model_id": "baseline-v2-01",
            }), encoding="utf-8")
            ingest_dir = tmp / "ingest"
            port = self._free_port()
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

            with request.urlopen(f"http://127.0.0.1:{port}/ui", timeout=2.0) as response:
                html = response.read().decode("utf-8")
                content_type = response.headers.get_content_type()
            self.assertEqual(content_type, "text/html")
            self.assertIn("Operations Console", html)
            self.assertIn("/assets/dashboard.js", html)

            with request.urlopen(f"http://127.0.0.1:{port}/assets/dashboard.js", timeout=2.0) as response:
                script = response.read().decode("utf-8")
                content_type = response.headers.get_content_type()
            self.assertEqual(content_type, "text/javascript")
            self.assertIn("loadDashboard", script)
