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

from ebpf_ml_mao.pipeline import run_phase5, train_baseline_model_from_raw
from ebpf_ml_mao.scoring import BaselineScorer
from ebpf_ml_mao.models import FeatureWindow


class Step6ModelsTest(unittest.TestCase):
    def test_versioned_baseline_model_contains_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir, "baseline-v2.json")
            model = train_baseline_model_from_raw(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                model_path,
                model_type="baseline",
            )
            self.assertEqual(model.schema_version, "v2")
            self.assertEqual(model.model_type, "baseline")
            payload = json.loads(model_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "v2")
            self.assertEqual(payload["model_type"], "baseline")

    def test_zscore_model_roundtrip_and_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir, "zscore-v2.json")
            model = train_baseline_model_from_raw(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                model_path,
                model_type="zscore",
                threshold=0.5,
            )
            self.assertEqual(model.model_type, "zscore")
            self.assertTrue(model.std)

            scorer = BaselineScorer()
            loaded = scorer.load_model(model_path)
            self.assertEqual(loaded.schema_version, "v2")
            self.assertEqual(loaded.model_type, "zscore")

            batch = run_phase5(
                model_path,
                "samples/step6/input_tetragon.jsonl",
                "samples/step6/input_prometheus.json",
                temp_dir,
            )
            self.assertEqual(len(batch.reports), 3)
            self.assertTrue(Path(temp_dir, "report-index.json").exists())
            self.assertTrue(any(report.verdict in {"normal", "anomalous"} for report in batch.reports))

    def test_zscore_peak_signal_is_not_diluted_by_many_features(self) -> None:
        baseline = [
            FeatureWindow(
                window_start=1.0,
                window_end=31.0,
                workload="fault-target",
                values={
                    "event_count": 2.0,
                    "tetragon_event_count": 2.0,
                    "prometheus_event_count": 0.0,
                    "exec_count": 2.0,
                    "network_event_count": 0.0,
                    "file_event_count": 0.0,
                    "privilege_event_count": 0.0,
                    "unique_pids": 2.0,
                    "window_duration_seconds": 30.0,
                    "event_rate_per_minute": 4.0,
                    "exec_rate_per_minute": 4.0,
                    "network_event_rate_per_minute": 0.0,
                    "avg_cpu_usage": 0.0,
                    "max_cpu_usage": 0.0,
                    "cpu_pressure_ratio": 0.0,
                    "avg_memory_usage": 0.0,
                    "max_memory_usage": 0.0,
                    "avg_network_connections": 0.0,
                    "max_network_connections": 0.0,
                    "network_connection_pressure": 0.0,
                },
            ),
            FeatureWindow(
                window_start=61.0,
                window_end=91.0,
                workload="fault-target",
                values={
                    "event_count": 3.0,
                    "tetragon_event_count": 3.0,
                    "prometheus_event_count": 0.0,
                    "exec_count": 3.0,
                    "network_event_count": 0.0,
                    "file_event_count": 0.0,
                    "privilege_event_count": 0.0,
                    "unique_pids": 3.0,
                    "window_duration_seconds": 30.0,
                    "event_rate_per_minute": 6.0,
                    "exec_rate_per_minute": 6.0,
                    "network_event_rate_per_minute": 0.0,
                    "avg_cpu_usage": 0.0,
                    "max_cpu_usage": 0.0,
                    "cpu_pressure_ratio": 0.0,
                    "avg_memory_usage": 0.0,
                    "max_memory_usage": 0.0,
                    "avg_network_connections": 0.0,
                    "max_network_connections": 0.0,
                    "network_connection_pressure": 0.0,
                },
            ),
        ]
        scorer = BaselineScorer(model_type="zscore")
        scorer.fit(baseline, threshold=0.45, model_type="zscore")
        fault = FeatureWindow(
            window_start=121.0,
            window_end=151.0,
            workload="fault-target",
            values={**baseline[0].values, "exec_count": 12.0, "exec_rate_per_minute": 24.0},
        )
        score, confidence = scorer.score(fault)
        self.assertGreaterEqual(score, 0.45)
        self.assertGreater(confidence, 0.0)

    def test_zscore_event_count_only_spike_is_capped_below_threshold(self) -> None:
        baseline = [
            FeatureWindow(
                window_start=1.0,
                window_end=31.0,
                workload="fault-target",
                values={
                    "event_count": 2.0,
                    "tetragon_event_count": 2.0,
                    "exec_count": 0.0,
                    "network_event_count": 0.0,
                    "unique_pids": 1.0,
                    "avg_cpu_usage": 0.0,
                    "max_cpu_usage": 0.0,
                    "avg_memory_usage": 0.0,
                    "max_memory_usage": 0.0,
                    "avg_network_connections": 0.0,
                    "max_network_connections": 0.0,
                },
            )
        ]
        scorer = BaselineScorer(model_type="zscore")
        scorer.fit(baseline, threshold=0.45, model_type="zscore")
        noisy_normal = FeatureWindow(
            window_start=61.0,
            window_end=91.0,
            workload="fault-target",
            values={**baseline[0].values, "event_count": 100.0, "tetragon_event_count": 100.0},
        )
        score, _ = scorer.score(noisy_normal)
        self.assertLess(score, 0.45)

    def test_unknown_schema_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir, "bad-model.json")
            model_path.write_text(
                json.dumps(
                    {
                        "schema_version": "v9",
                        "model_type": "baseline",
                        "feature_keys": ["event_count"],
                        "threshold": 0.45,
                        "baseline": {"event_count": 1.0},
                    }
                ),
                encoding="utf-8",
            )
            scorer = BaselineScorer()
            with self.assertRaises(ValueError):
                scorer.load_model(model_path)


if __name__ == "__main__":
    unittest.main()
