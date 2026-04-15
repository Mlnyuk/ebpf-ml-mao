from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ebpf_ml_mao.pipeline import run_phase5, train_baseline_model_from_raw
from ebpf_ml_mao.registry import activate_model, list_models, load_registry, resolve_model_path
from ebpf_ml_mao.scoring import describe_model_file, migrate_model_file


class Step7RegistryTest(unittest.TestCase):
    def test_registry_list_reflects_saved_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir, "registry.json")
            train_baseline_model_from_raw(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                Path(temp_dir, "baseline-v2.json"),
                model_type="baseline",
                registry_path=registry_path,
                tags=["baseline"],
                activate=True,
            )
            train_baseline_model_from_raw(
                "samples/step2/baseline_tetragon.jsonl",
                "samples/step2/baseline_prometheus.json",
                Path(temp_dir, "zscore-v2.json"),
                model_type="zscore",
                registry_path=registry_path,
                tags=["candidate"],
            )
            models = list_models(registry_path)
            self.assertEqual(len(models), 2)
            self.assertEqual(models[0]["model_type"], "baseline")
            self.assertEqual(models[1]["model_type"], "zscore")

    def test_registry_activation_and_phase5_default_model(self) -> None:
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
            registry = load_registry(registry_path)
            zscore_id = next(item["id"] for item in registry["models"] if item["path"] == str(zscore_path))
            activate_model(zscore_id, registry_path)
            resolved = resolve_model_path(registry_path=registry_path)
            self.assertEqual(resolved, str(zscore_path))

            batch = run_phase5(
                None,
                "samples/step6/input_tetragon.jsonl",
                "samples/step6/input_prometheus.json",
                temp_dir,
                registry_path=registry_path,
            )
            self.assertEqual(len(batch.reports), 3)
            self.assertTrue(Path(temp_dir, "report-index.json").exists())

    def test_migrate_v1_to_v2_produces_valid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            legacy_path = Path(temp_dir, "legacy-v1.json")
            migrated_path = Path(temp_dir, "legacy-v2.json")
            legacy_path.write_text(
                json.dumps(
                    {
                        "feature_keys": ["event_count"],
                        "threshold": 0.45,
                        "baseline": {"event_count": 2.0},
                    }
                ),
                encoding="utf-8",
            )
            model = migrate_model_file(legacy_path, migrated_path)
            self.assertEqual(model.schema_version, "v2")
            self.assertEqual(model.model_type, "baseline")
            description = describe_model_file(migrated_path)
            self.assertEqual(description["registry_entry"]["payload_keys"], ["baseline"])


if __name__ == "__main__":
    unittest.main()
