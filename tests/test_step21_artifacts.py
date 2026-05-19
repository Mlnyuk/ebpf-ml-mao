from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Step21ArtifactsTest(unittest.TestCase):
    def test_step21_overlay_files_exist(self) -> None:
        for rel in (
            "deploy/yaml/step21/kustomization.yaml",
            "deploy/yaml/step21/tetragon-fault-file-coverage-policy.yaml",
            "deploy/yaml/step21/patch-fault-target-deployment.yaml",
            "deploy/yaml/step21/patch-configmap-baseline-paths.yaml",
            "deploy/yaml/step21/patch-collector-baseline-mount.yaml",
            "deploy/yaml/step21/baseline_tetragon.jsonl",
            "deploy/yaml/step21/baseline_prometheus.json",
        ):
            with self.subTest(path=rel):
                self.assertTrue(Path(ROOT, rel).exists(), rel)

    def test_step21_kustomization_chains_step19(self) -> None:
        content = Path(ROOT, "deploy/yaml/step21/kustomization.yaml").read_text(encoding="utf-8")
        self.assertIn("../step19", content)
        self.assertIn("tetragon-fault-file-coverage-policy.yaml", content)
        self.assertIn("patch-fault-target-deployment.yaml", content)
        self.assertIn("patch-configmap-baseline-paths.yaml", content)
        self.assertIn("patch-collector-baseline-mount.yaml", content)
        self.assertIn("ebpf-ml-mao-baseline-data", content)

    def test_step21_configmap_patch_overrides_baseline_paths(self) -> None:
        content = Path(ROOT, "deploy/yaml/step21/patch-configmap-baseline-paths.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("BASELINE_TETRAGON_PATH", content)
        self.assertIn("BASELINE_PROMETHEUS_PATH", content)
        self.assertIn("/etc/ebpf-ml-mao/baseline", content)

    def test_step21_collector_patch_mounts_baseline(self) -> None:
        content = Path(ROOT, "deploy/yaml/step21/patch-collector-baseline-mount.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("ebpf-ml-mao-collector", content)
        self.assertIn("ebpf-ml-mao-baseline-data", content)
        self.assertIn("mountPath: /etc/ebpf-ml-mao/baseline", content)

    def test_step21_file_policy_targets_fault_target(self) -> None:
        content = Path(ROOT, "deploy/yaml/step21/tetragon-fault-file-coverage-policy.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("security_file_open", content)
        self.assertIn("app: fault-target", content)
        self.assertIn("TracingPolicyNamespaced", content)
        self.assertIn("namespace: ebpf-obs-test", content)

    def test_step21_fault_target_patch_uses_python_image(self) -> None:
        content = Path(ROOT, "deploy/yaml/step21/patch-fault-target-deployment.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("python:3.11-alpine", content)
        self.assertIn("python3", content)
        self.assertIn("open(", content)
        self.assertIn("time.sleep", content)

    def test_step21_scripts_exist_and_strict_bash(self) -> None:
        for script in ("step21_collect_baseline.sh", "step21_activate_model.sh"):
            with self.subTest(script=script):
                path = Path(ROOT, "scripts", script)
                self.assertTrue(path.exists(), script)
                self.assertIn("set -euo pipefail", path.read_text(encoding="utf-8"))

    def test_step21_train_script_uses_baseline_scorer(self) -> None:
        content = Path(ROOT, "scripts/step21_train_baseline.py").read_text(encoding="utf-8")
        self.assertIn("BaselineScorer", content)
        self.assertIn("fault-target-baseline.jsonl", content)
        self.assertIn("baseline-v4.json", content)

    def test_step21_docs_describe_overcoming_limit(self) -> None:
        content = Path(ROOT, "docs/steps/step21/README.md").read_text(encoding="utf-8")
        for term in (
            "Baseline Workload Redesign",
            "security_file_open",
            "python:3.11-alpine",
            "baseline-v4-01",
            "step21_collect_baseline.sh",
            "step21_train_baseline.py",
            "step21_activate_model.sh",
            "WARMUP_BASELINE=false",
        ):
            with self.subTest(term=term):
                self.assertIn(term, content)


if __name__ == "__main__":
    unittest.main()
