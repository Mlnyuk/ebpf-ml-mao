from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Step19ArtifactsTest(unittest.TestCase):
    def test_step19_deploy_and_docs_exist(self) -> None:
        self.assertTrue(Path(ROOT, "deploy/yaml/step19/kustomization.yaml").exists())
        self.assertTrue(Path(ROOT, "deploy/yaml/step19/patch-configmap-target-filter.yaml").exists())
        self.assertTrue(Path(ROOT, "docs/steps/step19/README.md").exists())

    def test_step19_kustomization_layers_on_step18(self) -> None:
        content = Path(ROOT, "deploy/yaml/step19/kustomization.yaml").read_text(encoding="utf-8")
        self.assertIn("../step18", content)
        self.assertIn("patch-configmap-target-filter.yaml", content)

    def test_step19_configmap_patch_sets_target_filter(self) -> None:
        content = Path(
            ROOT, "deploy/yaml/step19/patch-configmap-target-filter.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("ebpf-ml-mao-runtime", content)
        self.assertIn("ANALYZER_TARGET_NAMESPACE: ebpf-obs-test", content)
        self.assertIn("ANALYZER_TARGET_WORKLOAD: fault-target", content)
        self.assertIn('DEPLOYMENT_STEP: "step19"', content)

    def test_step19_readme_mentions_required_topics(self) -> None:
        content = Path(ROOT, "docs/steps/step19/README.md").read_text(encoding="utf-8")
        for term in [
            "target filter",
            "ANALYZER_TARGET_NAMESPACE",
            "ANALYZER_TARGET_WORKLOAD",
            "fault-target",
            "step16_collect_results.sh",
            "fault-target-ingest-scores.jsonl",
        ]:
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_step16_extract_fault_target_scores_script_exists(self) -> None:
        path = Path(ROOT, "scripts/step16_extract_fault_target_scores.py")
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("fault-target", content)
        self.assertIn("feature_window", content)

    def test_project_readme_mentions_step19(self) -> None:
        content = Path(ROOT, "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/steps/step19/README.md", content)


if __name__ == "__main__":
    unittest.main()
