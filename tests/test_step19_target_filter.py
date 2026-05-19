from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ebpf_ml_mao.models import NormalizedEvent
from ebpf_ml_mao.pipeline import _filter_target_events


class Step19TargetFilterTest(unittest.TestCase):
    def test_target_filter_keeps_fault_target_and_drops_infra_workloads(self) -> None:
        target = NormalizedEvent(
            ts=1.0,
            source="tetragon",
            event_type="process_exec",
            node="node-1",
            workload="fault-target",
            pod="fault-target-abc",
            container="fault-target",
            pid=10,
            cpu_usage=0.0,
            memory_usage=0.0,
            network_connections=0,
            metadata={"namespace": "ebpf-obs-test"},
        )
        infra = NormalizedEvent(
            ts=2.0,
            source="tetragon",
            event_type="network_connection",
            node="node-1",
            workload="instance-manager",
            pod="instance-manager-0",
            container="manager",
            pid=20,
            cpu_usage=0.0,
            memory_usage=0.0,
            network_connections=0,
            metadata={"namespace": "longhorn-system"},
        )

        filtered = _filter_target_events(
            [target, infra],
            namespace="ebpf-obs-test",
            workload="fault-target",
        )

        self.assertEqual(filtered, [target])


if __name__ == "__main__":
    unittest.main()
