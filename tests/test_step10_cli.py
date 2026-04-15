from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class Step10BuildArtifactsTest(unittest.TestCase):
    def test_dockerfile_exists(self) -> None:
        self.assertTrue(Path(ROOT, "Dockerfile").exists())

    def test_step10_manifest_paths_exist(self) -> None:
        self.assertTrue(Path(ROOT, "deploy/yaml/step10/kustomization.yaml").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step10/networkpolicy.yaml").exists())
