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

from ebpf_ml_mao.loader import load_jsonl
from ebpf_ml_mao.normalizer import normalize_event
from ebpf_ml_mao.pipeline import run_phase1


class Phase1PipelineTest(unittest.TestCase):
    def test_normalizer_populates_required_fields(self) -> None:
        raw = load_jsonl("samples/benign.jsonl")[0]
        event = normalize_event(raw)
        self.assertEqual(event.source, "tetragon")
        self.assertEqual(event.workload, "checkout")
        self.assertGreater(event.cpu_usage, 0)

    def test_pipeline_generates_anomalous_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = run_phase1(
                "samples/benign.jsonl",
                "samples/anomalous.jsonl",
                temp_dir,
            )
            self.assertEqual(report.verdict, "anomalous")
            self.assertGreater(report.score, 0.45)
            self.assertEqual(len(report.agent_results), 4)

            report_json = json.loads(
                Path(temp_dir, "report.json").read_text(encoding="utf-8")
            )
            report_md = Path(temp_dir, "report.md").read_text(encoding="utf-8")
            self.assertEqual(report_json["verdict"], "anomalous")
            self.assertIn("# MVP Analysis Report", report_md)


if __name__ == "__main__":
    unittest.main()
