from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Step18ArtifactsTest(unittest.TestCase):
    def test_step18_scripts_exist_and_are_strict_bash(self) -> None:
        for script_name in [
            "analyzer_storage_check.sh",
            "analyzer_prune.sh",
            "step16_preflight.sh",
        ]:
            with self.subTest(script=script_name):
                path = Path(ROOT, "scripts", script_name)
                self.assertTrue(path.exists())
                self.assertIn("set -euo pipefail", path.read_text(encoding="utf-8"))

    def test_prune_script_has_dry_run_and_age_controls(self) -> None:
        content = Path(ROOT, "scripts/analyzer_prune.sh").read_text(encoding="utf-8")
        self.assertIn("DRY_RUN", content)
        self.assertIn("OLDER_THAN_DAYS", content)
        self.assertIn("MAX_FILES_PER_DIR", content)
        self.assertIn("PRINT_DELETED", content)
        self.assertIn("PRUNE_ALL", content)
        delete_index = content.find("-delete")
        self.assertNotEqual(delete_index, -1)
        guard_index = content.find("dry_run")
        self.assertNotEqual(guard_index, -1)
        self.assertLess(guard_index, delete_index)
        self.assertNotRegex(content, re.compile(r"\brm\s+-rf\b"))

    def test_preflight_mentions_strict(self) -> None:
        content = Path(ROOT, "scripts/step16_preflight.sh").read_text(encoding="utf-8")
        self.assertIn("STRICT", content)

    def test_step18_deploy_and_docs_exist(self) -> None:
        self.assertTrue(Path(ROOT, "deploy/yaml/step18/kustomization.yaml").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step18/patch-analyzer-hpa-single-writer.yaml").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step18/patch-analyzer-pvc-storage.yaml").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step18/analyzer-prune-cronjob.yaml").exists())
        self.assertTrue(Path(ROOT, "docs/steps/step18/README.md").exists())

    def test_step18_kustomization_includes_retention_and_pvc_patch(self) -> None:
        content = Path(ROOT, "deploy/yaml/step18/kustomization.yaml").read_text(encoding="utf-8")
        self.assertIn("analyzer-prune-cronjob.yaml", content)
        self.assertIn("patch-analyzer-pvc-storage.yaml", content)
        self.assertIn("step18-target-filter", content)
        pvc_patch = Path(ROOT, "deploy/yaml/step18/patch-analyzer-pvc-storage.yaml").read_text(encoding="utf-8")
        self.assertIn("8Gi", pvc_patch)
        cronjob = Path(ROOT, "deploy/yaml/step18/analyzer-prune-cronjob.yaml").read_text(encoding="utf-8")
        self.assertIn("CronJob", cronjob)
        self.assertIn("MAX_FILES_PER_DIR", cronjob)
        config_patch = Path(ROOT, "deploy/yaml/step18/patch-configmap-image.yaml").read_text(encoding="utf-8")
        self.assertIn("DEPLOYMENT_IMAGE", config_patch)
        self.assertIn("ANALYZER_TARGET_NAMESPACE", config_patch)
        self.assertIn("ANALYZER_TARGET_WORKLOAD", config_patch)

    def test_step18_readme_mentions_required_topics(self) -> None:
        content = Path(ROOT, "docs/steps/step18/README.md").read_text(encoding="utf-8")
        for term in ["storage check", "prune", "preflight", "HPA", "single-writer", "CronJob", "8Gi"]:
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_project_readme_mentions_step18(self) -> None:
        content = Path(ROOT, "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/steps/step18/README.md", content)
