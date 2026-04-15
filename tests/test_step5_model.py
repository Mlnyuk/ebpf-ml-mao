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


class Step5ModelTest(unittest.TestCase):
    def test_model_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir, "baseline-model.json")
            model = train_baseline_model_from_raw(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                model_path,
            )
            self.assertTrue(model_path.exists())
            payload = json.loads(model_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["feature_keys"], model.feature_keys)

            scorer = BaselineScorer()
            loaded = scorer.load_model(model_path)
            self.assertEqual(loaded.feature_keys, model.feature_keys)
            self.assertEqual(loaded.threshold, model.threshold)

    def test_phase5_inference_uses_saved_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir, "baseline-model.json")
            train_baseline_model_from_raw(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                model_path,
            )
            batch = run_phase5(
                model_path,
                "samples/step5/input_tetragon.jsonl",
                "samples/step5/input_prometheus.json",
                temp_dir,
            )
            self.assertEqual(len(batch.reports), 3)
            self.assertTrue(Path(temp_dir, "report-index.json").exists())
            self.assertTrue(Path(temp_dir, "reports", "report-02.json").exists())


if __name__ == "__main__":
    unittest.main()
