from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ebpf_ml_mao.pipeline import train_baseline_model_from_raw
from ebpf_ml_mao.registry import (
    backup_registry,
    list_models,
    load_registry,
    prune_registry,
    registry_status,
    resolve_model_path,
    tag_model,
)


class Step8RegistryOpsTest(unittest.TestCase):
    def test_tag_model_merges_tags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir, "registry.json")
            model_path = Path(temp_dir, "baseline-v2.json")
            train_baseline_model_from_raw(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                model_path,
                model_type="baseline",
                registry_path=registry_path,
                tags=["baseline"],
                activate=True,
            )
            model_id = list_models(registry_path)[0]["id"]
            entry = tag_model(model_id, ["prod", "baseline"], registry_path)
            self.assertEqual(entry["tags"], ["baseline", "prod"])

    def test_prune_missing_only_removes_missing_entries_and_rehomes_active(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir, "registry.json")
            baseline_path = Path(temp_dir, "baseline-v2.json")
            zscore_path = Path(temp_dir, "zscore-v2.json")
            train_baseline_model_from_raw(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                baseline_path,
                model_type="baseline",
                registry_path=registry_path,
                activate=True,
            )
            train_baseline_model_from_raw(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                zscore_path,
                model_type="zscore",
                registry_path=registry_path,
            )
            baseline_path.unlink()
            result = prune_registry(registry_path=registry_path, missing_only=True)
            self.assertEqual(result["removed_count"], 1)
            registry = load_registry(registry_path)
            self.assertEqual(len(registry["models"]), 1)
            self.assertEqual(registry["active_model_id"], registry["models"][0]["id"])
            self.assertTrue(result["backup_path"])

    def test_prune_specific_model_can_delete_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir, "registry.json")
            model_path = Path(temp_dir, "baseline-v2.json")
            train_baseline_model_from_raw(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                model_path,
                model_type="baseline",
                registry_path=registry_path,
                activate=True,
            )
            model_id = list_models(registry_path)[0]["id"]
            result = prune_registry(
                registry_path=registry_path,
                model_id=model_id,
                delete_artifact=True,
            )
            self.assertEqual(result["removed_count"], 1)
            self.assertFalse(model_path.exists())
            self.assertIsNone(load_registry(registry_path)["active_model_id"])

    def test_resolve_model_path_rejects_conflicting_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir, "registry.json")
            model_path = Path(temp_dir, "baseline-v2.json")
            train_baseline_model_from_raw(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                model_path,
                model_type="baseline",
                registry_path=registry_path,
                activate=True,
            )
            model_id = list_models(registry_path)[0]["id"]
            with self.assertRaises(ValueError):
                resolve_model_path(
                    model_path=model_path,
                    model_id=model_id,
                    registry_path=registry_path,
                )

    def test_load_registry_rejects_corrupt_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir, "registry.json")
            registry_path.write_text("{not-json}", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_registry(registry_path)

    def test_backup_and_status_report_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir, "registry.json")
            model_path = Path(temp_dir, "baseline-v2.json")
            train_baseline_model_from_raw(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                model_path,
                model_type="baseline",
                registry_path=registry_path,
                tags=["baseline"],
                activate=True,
            )
            backup_path = backup_registry(registry_path)
            self.assertTrue(Path(backup_path).exists())
            status = registry_status(registry_path)
            self.assertEqual(status["model_count"], 1)
            self.assertEqual(status["missing_artifact_count"], 0)
            self.assertEqual(status["tagged_model_count"], 1)
            self.assertEqual(resolve_model_path(registry_path=registry_path), str(model_path))


if __name__ == "__main__":
    unittest.main()
