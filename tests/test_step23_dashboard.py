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

from ebpf_ml_mao.api import load_workflow_summary, serve_api, store_ingest_payload


def _report(workload: str, score: float, verdict: str, exec_count: float, ws: float) -> dict:
    return {
        "node_name": "worker-1",
        "phase": "phase3",
        "received_at": int(ws),
        "report": {
            "score": score,
            "verdict": verdict,
            "confidence": 0.9,
            "feature_window": {
                "window_start": ws,
                "window_end": ws + 30,
                "workload": workload,
                "values": {
                    "exec_count": exec_count,
                    "file_event_count": 5.0,
                    "network_event_count": 0.0,
                },
            },
        },
    }


class Step23DashboardTest(unittest.TestCase):
    def _free_port(self) -> int:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def test_index_captures_score_workload_features(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ingest = Path(temp_dir) / "ingest"
            store_ingest_payload(ingest, _report("fault-target", 0.88, "anomalous", 12.0, 1000))
            index = json.loads((ingest / "index.json").read_text(encoding="utf-8"))
            item = next(iter(index["items"].values()))
            self.assertEqual(item["workload"], "fault-target")
            self.assertEqual(item["score"], 0.88)
            self.assertEqual(item["window_start"], 1000.0)
            self.assertEqual(item["features"]["exec_count"], 12.0)

    def test_workflow_per_workload_aggregation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ingest = Path(temp_dir) / "ingest"
            store_ingest_payload(ingest, _report("fault-target", 0.01, "normal", 0.0, 1000))
            store_ingest_payload(ingest, _report("fault-target", 0.88, "anomalous", 12.0, 1040))
            store_ingest_payload(ingest, _report("coredns", 0.03, "normal", 0.0, 1000))
            workflow = load_workflow_summary(ingest)

            workloads = workflow["workloads"]
            self.assertIn("fault-target", workloads)
            self.assertIn("coredns", workloads)

            ft = workloads["fault-target"]
            self.assertEqual(ft["sample_count"], 2)
            self.assertEqual(ft["anomalous_count"], 1)
            self.assertEqual(ft["latest_verdict"], "anomalous")
            self.assertEqual(ft["latest_score"], 0.88)
            self.assertEqual(ft["top_feature"]["name"], "exec_count")
            self.assertEqual(len(ft["recent_scores"]), 2)

            self.assertEqual(workloads["coredns"]["latest_verdict"], "normal")

    def test_latest_score_follows_window_time_not_insertion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ingest = Path(temp_dir) / "ingest"
            # Insert the later window first to prove ordering is by time, not insertion.
            store_ingest_payload(ingest, _report("fault-target", 0.90, "anomalous", 13.0, 2000))
            store_ingest_payload(ingest, _report("fault-target", 0.10, "normal", 0.0, 1000))
            ft = load_workflow_summary(ingest)["workloads"]["fault-target"]
            self.assertEqual(ft["latest_score"], 0.90)
            self.assertEqual(ft["latest_verdict"], "anomalous")

    def test_scores_endpoint_returns_workloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            ingest = tmp / "ingest"
            registry_path = tmp / "registry.json"
            registry_path.write_text(json.dumps({"models": [], "active_model_id": None}), encoding="utf-8")
            store_ingest_payload(ingest, _report("fault-target", 0.88, "anomalous", 12.0, 1000))

            port = self._free_port()
            thread = threading.Thread(
                target=serve_api,
                kwargs={"host": "127.0.0.1", "port": port, "registry_path": registry_path, "ingest_dir": ingest},
                daemon=True,
            )
            thread.start()
            time.sleep(0.2)

            with request.urlopen(f"http://127.0.0.1:{port}/v1/scores", timeout=2.0) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            self.assertIn("fault-target", payload["workloads"])
            self.assertEqual(payload["workloads"]["fault-target"]["latest_verdict"], "anomalous")

            with request.urlopen(f"http://127.0.0.1:{port}/v1/dashboard", timeout=2.0) as resp:
                dashboard = json.loads(resp.read().decode("utf-8"))
            self.assertIn("workloads", dashboard["workflow"])
            self.assertIn("fault-target", dashboard["workflow"]["workloads"])

    def test_ui_assets_have_workload_view(self) -> None:
        html = Path(ROOT, "app/ebpf_ml_mao/ui/dashboard.html").read_text(encoding="utf-8")
        js = Path(ROOT, "app/ebpf_ml_mao/ui/dashboard.js").read_text(encoding="utf-8")
        css = Path(ROOT, "app/ebpf_ml_mao/ui/dashboard.css").read_text(encoding="utf-8")
        self.assertIn("workload-grid", html)
        self.assertIn("renderWorkloads", js)
        self.assertIn("sparkline", js)
        self.assertIn("workload-card", css)


if __name__ == "__main__":
    unittest.main()
