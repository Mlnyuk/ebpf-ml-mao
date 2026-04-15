from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class Step14ArtifactsTest(unittest.TestCase):
    def test_step14_manifest_and_docs_exist(self) -> None:
        self.assertTrue(Path(ROOT, "deploy/yaml/step14/kustomization.yaml").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step14/patch-analyzer-deployment.yaml").exists())
        self.assertTrue(Path(ROOT, "docs/steps/step14/README.md").exists())
        self.assertTrue(Path(ROOT, "docs/steps/step14/runbook.md").exists())
        self.assertTrue(Path(ROOT, "docs/steps/step14/checklist.md").exists())

    def test_operations_docs_exist(self) -> None:
        self.assertTrue(Path(ROOT, "docs/operations/runbook.md").exists())
        self.assertTrue(Path(ROOT, "docs/operations/rollback.md").exists())
        self.assertTrue(Path(ROOT, "docs/operations/release-checklist.md").exists())
        self.assertTrue(Path(ROOT, "docs/operations/incident-checklist.md").exists())
        self.assertTrue(Path(ROOT, "docs/operations/ci-cd.md").exists())

    def test_ci_workflows_exist(self) -> None:
        self.assertTrue(Path(ROOT, ".github/workflows/ci.yaml").exists())
        self.assertTrue(Path(ROOT, ".github/workflows/release-image.yaml").exists())

    def test_makefile_exists(self) -> None:
        self.assertTrue(Path(ROOT, "Makefile").exists())
