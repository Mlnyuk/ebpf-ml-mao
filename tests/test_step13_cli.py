from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class Step13BuildArtifactsTest(unittest.TestCase):
    def test_step13_manifest_paths_exist(self) -> None:
        self.assertTrue(Path(ROOT, "deploy/yaml/step13/kustomization.yaml").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step13/patch-analyzer-deployment.yaml").exists())

    def test_step13_docs_exist(self) -> None:
        self.assertTrue(Path(ROOT, "docs/steps/step13/README.md").exists())
        self.assertTrue(Path(ROOT, "docs/steps/step13/agent-notes.md").exists())
