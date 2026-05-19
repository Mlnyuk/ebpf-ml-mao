from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Step20ArtifactsTest(unittest.TestCase):
    def test_step20_scripts_exist_and_strict_bash(self) -> None:
        for script_name in [
            "step16_warmup_baseline.sh",
            "step16_repeat_experiments.sh",
        ]:
            with self.subTest(script=script_name):
                path = Path(ROOT, "scripts", script_name)
                self.assertTrue(path.exists(), f"missing {path}")
                content = path.read_text(encoding="utf-8")
                self.assertIn("set -euo pipefail", content)

    def test_step20_aggregator_script_exists(self) -> None:
        path = Path(ROOT, "scripts/step16_aggregate_repeated.py")
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("aggregated-threshold-analysis.md", content)
        self.assertIn("aggregated-paper-results.md", content)
        self.assertIn("aggregated-detection.csv", content)

    def test_step20_aggregator_prefers_fault_target_verdict(self) -> None:
        content = Path(ROOT, "scripts/step16_aggregate_repeated.py").read_text(encoding="utf-8")
        self.assertIn("fault_target_verdict", content)
        self.assertIn("fault_target_verdict(scores)", content)

    def test_step20_docs_exist(self) -> None:
        path = Path(ROOT, "docs/steps/step20/README.md")
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        for term in [
            "Repeated Experiment Validation",
            "WARMUP_BASELINE",
            "step16_repeat_experiments.sh",
            "step16_aggregate_repeated.py",
            "step16_warmup_baseline.sh",
            "Detection rate",
        ]:
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_warmup_uses_kubectl_exec_on_fault_target(self) -> None:
        content = Path(ROOT, "scripts/step16_warmup_baseline.sh").read_text(encoding="utf-8")
        self.assertIn("app=fault-target", content)
        self.assertIn("kubectl exec", content)
        self.assertIn("WARMUP_DURATION", content)

    def test_repeat_driver_invokes_prune_and_collect(self) -> None:
        content = Path(ROOT, "scripts/step16_repeat_experiments.sh").read_text(encoding="utf-8")
        self.assertIn("analyzer_prune.sh", content)
        self.assertIn("step16_collect_results.sh", content)
        self.assertIn("step16_analyze_thresholds.py", content)
        self.assertIn("WARMUP_BASELINE", content)
        self.assertIn("RESULT_DIR", content)

    def test_collect_script_supports_warmup_baseline(self) -> None:
        content = Path(ROOT, "scripts/step16_collect_results.sh").read_text(encoding="utf-8")
        self.assertIn("WARMUP_BASELINE", content)
        self.assertIn("step16_warmup_baseline.sh", content)

    def test_analyze_thresholds_respects_result_dir_env(self) -> None:
        content = Path(ROOT, "scripts/step16_analyze_thresholds.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("RESULT_DIR"', content)


if __name__ == "__main__":
    unittest.main()
