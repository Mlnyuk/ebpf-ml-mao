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

from ebpf_ml_mao.adapters import adapt_prometheus_snapshot, adapt_tetragon_event
from ebpf_ml_mao.features import extract_features
from ebpf_ml_mao.pipeline import run_phase2


class Step2AdaptersTest(unittest.TestCase):
    def test_tetragon_adapter_extracts_nested_fields(self) -> None:
        raw = {
            "time": "2026-04-13T00:00:05Z",
            "type": "PROCESS_EXEC",
            "process": {
                "pid": 401,
                "binary": "/usr/bin/python3",
                "node_name": "worker-1",
                "pod": {
                    "namespace": "shop",
                    "name": "checkout-6c8b5",
                    "workload": "checkout",
                    "container": {"name": "app"},
                },
            },
        }
        event = adapt_tetragon_event(raw)
        self.assertEqual(event.source, "tetragon")
        self.assertEqual(event.pid, 401)
        self.assertEqual(event.event_type, "process_exec")
        self.assertEqual(event.workload, "checkout")
        self.assertEqual(event.container, "app")

    def test_tetragon_adapter_accepts_process_exec_payload_shape(self) -> None:
        raw = {
            "time": "2026-04-13T00:00:06Z",
            "process_exec": {
                "process": {
                    "pid": 402,
                    "binary": "/bin/sh",
                    "node_name": "worker-2",
                    "pod": {
                        "namespace": "ebpf-obs-test",
                        "name": "fault-target-69df4f49c4-jjrs6",
                        "labels": {"app": "fault-target"},
                        "container": {"name": "fault-target"},
                    },
                }
            },
        }
        event = adapt_tetragon_event(raw)
        self.assertEqual(event.event_type, "process_exec")
        self.assertEqual(event.workload, "fault-target")
        self.assertEqual(event.pod, "fault-target-69df4f49c4-jjrs6")

    def test_tetragon_adapter_classifies_tcp_connect_kprobe(self) -> None:
        raw = {
            "time": "2026-04-13T00:00:07Z",
            "process_kprobe": {
                "function_name": "tcp_connect",
                "policy_name": "step16-fault-network-coverage",
                "process": {
                    "pid": 403,
                    "binary": "/bin/wget",
                    "node_name": "worker-2",
                    "pod": {
                        "namespace": "ebpf-obs-test",
                        "name": "fault-target-69df4f49c4-jjrs6",
                        "container": {"name": "fault-target"},
                    },
                },
            },
        }
        event = adapt_tetragon_event(raw)
        self.assertEqual(event.event_type, "network_connection")
        self.assertEqual(event.metadata["function_name"], "tcp_connect")
        self.assertEqual(event.workload, "fault-target")

    def test_prometheus_adapter_aggregates_metric_series(self) -> None:
        snapshot = json.loads(Path("samples/step2/input_prometheus.json").read_text())
        events = adapt_prometheus_snapshot(snapshot)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.source, "prometheus")
        self.assertEqual(event.cpu_usage, 86.0)
        self.assertEqual(event.network_connections, 26)

    def test_feature_extraction_includes_rates_and_source_counts(self) -> None:
        raw_events = [
            {
                "time": "2026-04-13T00:00:00Z",
                "process_exec": {
                    "process": {
                        "pid": 501,
                        "binary": "/bin/sh",
                        "node_name": "worker-2",
                        "pod": {
                            "namespace": "ebpf-obs-test",
                            "name": "fault-target-69df4f49c4-jjrs6",
                            "labels": {"app": "fault-target"},
                            "container": {"name": "fault-target"},
                        },
                    }
                },
            },
            {
                "time": "2026-04-13T00:00:10Z",
                "process_kprobe": {
                    "function_name": "tcp_connect",
                    "process": {
                        "pid": 502,
                        "binary": "/bin/wget",
                        "node_name": "worker-2",
                        "pod": {
                            "namespace": "ebpf-obs-test",
                            "name": "fault-target-69df4f49c4-jjrs6",
                            "labels": {"app": "fault-target"},
                            "container": {"name": "fault-target"},
                        },
                    },
                },
            },
        ]
        window = extract_features([adapt_tetragon_event(item) for item in raw_events])
        self.assertEqual(window.values["tetragon_event_count"], 2.0)
        self.assertEqual(window.values["exec_count"], 1.0)
        self.assertEqual(window.values["network_event_count"], 1.0)
        self.assertEqual(window.values["event_rate_per_minute"], 12.0)
        self.assertEqual(window.values["exec_rate_per_minute"], 6.0)

    def test_phase2_pipeline_generates_anomalous_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = run_phase2(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                "samples/step2/input_tetragon.jsonl",
                "samples/step2/input_prometheus.json",
                temp_dir,
            )
            self.assertEqual(report.verdict, "anomalous")
            self.assertGreater(report.score, 0.45)
            report_json = json.loads(
                Path(temp_dir, "report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report_json["verdict"], "anomalous")


if __name__ == "__main__":
    unittest.main()
