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

from ebpf_ml_mao.pipeline import run_phase4


class Step4BatchTest(unittest.TestCase):
    def test_phase4_generates_multiple_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            batch = run_phase4(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                "samples/step4/input_tetragon.jsonl",
                "samples/step4/input_prometheus.json",
                temp_dir,
            )
            self.assertEqual(len(batch.reports), 3)
            workloads = [report.feature_window.workload for report in batch.reports]
            self.assertEqual(workloads, ["checkout", "checkout", "payment"])
            verdicts = [report.verdict for report in batch.reports]
            self.assertEqual(verdicts.count("anomalous"), 2)
            self.assertEqual(verdicts.count("normal"), 1)

            index_json = json.loads(
                Path(temp_dir, "report-index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index_json["report_count"], 3)
            self.assertTrue(Path(temp_dir, "reports", "report-01.json").exists())
            self.assertTrue(Path(temp_dir, "reports", "report-03.md").exists())


if __name__ == "__main__":
    unittest.main()
