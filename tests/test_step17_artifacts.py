from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Step17ArtifactsTest(unittest.TestCase):
    def test_step17_artifacts_exist(self) -> None:
        self.assertTrue(Path(ROOT, "scripts/step16_collect_results.sh").exists())
        self.assertTrue(Path(ROOT, "scripts/step16_generate_report.py").exists())
        self.assertTrue(Path(ROOT, "docs/steps/step17/README.md").exists())

    def test_collect_script_is_strict_bash(self) -> None:
        content = Path(ROOT, "scripts/step16_collect_results.sh").read_text(encoding="utf-8")
        self.assertIn("set -euo pipefail", content)
        self.assertIn("tetragon-tail.jsonl", content)
        self.assertIn("tetragon-fault-target.jsonl", content)
        self.assertIn("TETRAGON_LOG_PATH", content)

    def test_generator_targets_step16_results(self) -> None:
        content = Path(ROOT, "scripts/step16_generate_report.py").read_text(encoding="utf-8")
        self.assertIn("results/step16", content)
        self.assertIn("experiment-report.md", content)
        self.assertIn("process_exec", content)
        self.assertIn("tcp_connect", content)
        self.assertIn("tetragon_fault_target_lines", content)

    def test_step17_readme_mentions_commands_and_scenarios(self) -> None:
        content = Path(ROOT, "docs/steps/step17/README.md").read_text(encoding="utf-8")
        self.assertIn("bash scripts/step16_collect_results.sh", content)
        self.assertIn("python3 scripts/step16_generate_report.py", content)
        for scenario in [
            "exec-storm",
            "network-burst",
            "cpu-stress",
            "memory-pressure",
        ]:
            with self.subTest(scenario=scenario):
                self.assertIn(scenario, content)
