from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class Step15ArtifactsTest(unittest.TestCase):
    def test_step15_docs_and_ui_assets_exist(self) -> None:
        self.assertTrue(Path(ROOT, "docs/steps/step15/README.md").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step15/kustomization.yaml").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step15/ui-service.yaml").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step15/patch-serviceaccounts.yaml").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step15/ghcr-pull-secret.example.yaml").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step15/generated/live.py").exists())
        self.assertTrue(Path(ROOT, "app/ebpf_ml_mao/ui/dashboard.html").exists())
        self.assertTrue(Path(ROOT, "app/ebpf_ml_mao/ui/dashboard.css").exists())
        self.assertTrue(Path(ROOT, "app/ebpf_ml_mao/ui/dashboard.js").exists())
