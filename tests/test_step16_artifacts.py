from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class Step16ArtifactsTest(unittest.TestCase):
    def test_step16_manifests_exist(self) -> None:
        self.assertTrue(Path(ROOT, "deploy/yaml/step16/kustomization.yaml").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step16/fault-workloads.yaml").exists())

    def test_fault_scenario_scripts_exist_and_reference_target(self) -> None:
        script_names = [
            "exec-storm.sh",
            "network-burst.sh",
            "cpu-stress.sh",
            "memory-pressure.sh",
        ]
        for script_name in script_names:
            with self.subTest(script=script_name):
                path = Path(ROOT, "scripts/fault-scenarios", script_name)
                self.assertTrue(path.exists())
                content = path.read_text(encoding="utf-8")
                self.assertIn("set -euo pipefail", content)
                self.assertIn("ebpf-obs-test", content)
                self.assertIn("fault-target", content)

    def test_step16_readme_mentions_scenarios_and_apply_command(self) -> None:
        path = Path(ROOT, "docs/steps/step16/README.md")
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        for scenario in [
            "exec-storm",
            "network-burst",
            "cpu-stress",
            "memory-pressure",
        ]:
            with self.subTest(scenario=scenario):
                self.assertIn(scenario, content)
        self.assertIn("kubectl apply -k deploy/yaml/step16", content)
