from __future__ import annotations

import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ebpf_ml_mao.api import serve_api
from ebpf_ml_mao.transport import post_report


class Step13APITest(unittest.TestCase):
    def _free_port(self) -> int:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def test_dashboard_and_alerts_include_queue_snapshot(self) -> None:
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
            queue_dir = tmp / "queue"

            port = self._free_port()
            thread = threading.Thread(
                target=serve_api,
                kwargs={
                    "host": "127.0.0.1",
                    "port": port,
                    "registry_path": registry_path,
                    "ingest_dir": ingest_dir,
                    "postprocess_queue_dir": queue_dir,
                    "queue_alert_threshold": 0,
                    "shared_token": "",
                },
                daemon=True,
            )
            thread.start()
            time.sleep(0.2)

            report_path = tmp / "report.json"
            report_path.write_text(json.dumps({"verdict": "anomalous"}), encoding="utf-8")
            response = post_report(f"http://127.0.0.1:{port}", node_name="node-a", report_path=report_path)
            self.assertEqual(response["status"], "stored")
            self.assertEqual(response["queue"]["status"], "queued")

            with request.urlopen(f"http://127.0.0.1:{port}/v1/dashboard", timeout=2.0) as dashboard_response:
                dashboard = json.loads(dashboard_response.read().decode("utf-8"))
            self.assertEqual(dashboard["queue"]["count"], 1)
            self.assertEqual(dashboard["workflow"]["latest_verdict"], "anomalous")
            self.assertEqual(dashboard["summary"]["state"], "warning")
            self.assertTrue(any(alert["name"] == "queue_backlog" for alert in dashboard["alerts"]))

            with request.urlopen(f"http://127.0.0.1:{port}/v1/alerts", timeout=2.0) as alerts_response:
                alerts = json.loads(alerts_response.read().decode("utf-8"))
            self.assertEqual(alerts["status"], "warning")
            self.assertGreaterEqual(len(alerts["alerts"]), 1)

    def test_readyz_fails_without_active_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            registry_path = tmp / "registry.json"
            registry_path.write_text(json.dumps({"models": [], "active_model_id": None}), encoding="utf-8")
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

            with self.assertRaises(error.HTTPError) as context:
                request.urlopen(f"http://127.0.0.1:{port}/readyz", timeout=2.0)
            self.assertEqual(context.exception.code, 503)
