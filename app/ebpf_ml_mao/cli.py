from __future__ import annotations

import argparse
import json

from .pipeline import (
    run_phase1,
    run_phase2,
    run_phase3,
    run_phase4,
    run_phase5,
    train_baseline_model_from_raw,
)
from .registry import (
    activate_model,
    backup_registry,
    load_registry,
    prune_registry,
    registry_status,
    tag_model,
)
from .scoring import describe_model_file, migrate_model_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the eBPF ML MAO MVP pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_model = subparsers.add_parser("train-model", help="Train and save a model")
    train_model.add_argument("--baseline-tetragon", required=True, help="Path to benign Tetragon JSONL")
    train_model.add_argument("--baseline-prometheus", required=True, help="Path to benign Prometheus snapshot JSON")
    train_model.add_argument("--model-path", required=True, help="Path to write the trained model JSON")
    train_model.add_argument("--threshold", type=float, default=0.45, help="Anomaly threshold stored in the model")
    train_model.add_argument("--model-type", choices=["baseline", "zscore"], default="baseline", help="Model type to train")
    train_model.add_argument("--registry-path", help="Optional model registry JSON path")
    train_model.add_argument("--tag", dest="tags", action="append", default=[], help="Tag to store with the registered model")
    train_model.add_argument("--activate", action="store_true", help="Mark this model as the active registry entry")

    phase1 = subparsers.add_parser("phase1", help="Run the flat JSONL Phase 1 pipeline")
    phase1.add_argument("--baseline", required=True, help="Path to benign baseline JSONL")
    phase1.add_argument("--input", required=True, help="Path to target JSONL")
    phase1.add_argument("--output-dir", required=True, help="Directory for generated reports")

    phase2 = subparsers.add_parser("phase2", help="Run the raw adapter-based Phase 2 pipeline")
    phase2.add_argument("--baseline-tetragon", required=True, help="Path to benign Tetragon JSONL")
    phase2.add_argument("--baseline-prometheus", required=True, help="Path to benign Prometheus snapshot JSON")
    phase2.add_argument("--input-tetragon", required=True, help="Path to target Tetragon JSONL")
    phase2.add_argument("--input-prometheus", required=True, help="Path to target Prometheus snapshot JSON")
    phase2.add_argument("--output-dir", required=True, help="Directory for generated reports")

    phase3 = subparsers.add_parser("phase3", help="Run the live ingestion Phase 3 pipeline")
    phase3.add_argument("--baseline-tetragon", required=True, help="Path to benign Tetragon JSONL")
    phase3.add_argument("--baseline-prometheus", required=True, help="Path to benign Prometheus snapshot JSON")
    phase3.add_argument("--tetragon-log", required=True, help="Path to the live Tetragon JSONL log")
    phase3.add_argument("--prometheus-url", required=True, help="Prometheus scrape URL")
    phase3.add_argument("--output-dir", required=True, help="Directory for generated reports")
    phase3.add_argument("--tetragon-tail-lines", type=int, default=100, help="How many log lines to tail from the Tetragon file")
    phase3.add_argument("--scrape-timeout", type=float, default=5.0, help="Prometheus scrape timeout in seconds")

    phase4 = subparsers.add_parser("phase4", help="Run the multi-window Phase 4 pipeline")
    phase4.add_argument("--baseline-tetragon", required=True, help="Path to benign Tetragon JSONL")
    phase4.add_argument("--baseline-prometheus", required=True, help="Path to benign Prometheus snapshot JSON")
    phase4.add_argument("--input-tetragon", required=True, help="Path to target Tetragon JSONL")
    phase4.add_argument("--input-prometheus", required=True, help="Path to target Prometheus snapshot JSON")
    phase4.add_argument("--output-dir", required=True, help="Directory for generated reports")

    phase5 = subparsers.add_parser("phase5", help="Run inference from a saved model")
    phase5.add_argument("--model-path", help="Path to the trained model JSON")
    phase5.add_argument("--model-id", help="Model id stored in the registry")
    phase5.add_argument("--registry-path", help="Registry JSON used for default or id-based resolution")
    phase5.add_argument("--input-tetragon", required=True, help="Path to target Tetragon JSONL")
    phase5.add_argument("--input-prometheus", required=True, help="Path to target Prometheus snapshot JSON")
    phase5.add_argument("--output-dir", required=True, help="Directory for generated reports")

    show_model = subparsers.add_parser("show-model", help="Show normalized metadata for a saved model")
    show_model.add_argument("--model-path", required=True, help="Path to the model JSON")

    migrate_model = subparsers.add_parser("migrate-model", help="Migrate a saved model to the latest schema")
    migrate_model.add_argument("--source-path", required=True, help="Path to the source model JSON")
    migrate_model.add_argument("--output-path", required=True, help="Path to write the migrated model JSON")
    migrate_model.add_argument("--target-schema-version", default="v2", help="Target schema version")

    registry = subparsers.add_parser("registry", help="Interact with the local model registry")
    registry_subparsers = registry.add_subparsers(dest="registry_command", required=True)

    registry_list = registry_subparsers.add_parser("list", help="List registered model artifacts")
    registry_list.add_argument("--registry-path", required=True, help="Registry JSON path")

    registry_status_parser = registry_subparsers.add_parser("status", help="Show registry summary")
    registry_status_parser.add_argument("--registry-path", required=True, help="Registry JSON path")

    registry_activate = registry_subparsers.add_parser("activate", help="Set the active registry model")
    registry_activate.add_argument("--registry-path", required=True, help="Registry JSON path")
    registry_activate.add_argument("--model-id", required=True, help="Model id to activate")

    registry_tag = registry_subparsers.add_parser("tag", help="Append tags to a registry model")
    registry_tag.add_argument("--registry-path", required=True, help="Registry JSON path")
    registry_tag.add_argument("--model-id", required=True, help="Model id to tag")
    registry_tag.add_argument("--tag", dest="tags", action="append", required=True, help="Tag to append")

    registry_backup = registry_subparsers.add_parser("backup", help="Create a backup copy of the registry")
    registry_backup.add_argument("--registry-path", required=True, help="Registry JSON path")
    registry_backup.add_argument("--backup-path", help="Optional explicit backup output path")

    registry_prune = registry_subparsers.add_parser("prune", help="Prune registry entries")
    registry_prune.add_argument("--registry-path", required=True, help="Registry JSON path")
    registry_prune.add_argument("--model-id", help="Specific model id to remove")
    registry_prune.add_argument("--missing-only", action="store_true", help="Remove only entries whose artifacts are missing")
    registry_prune.add_argument("--delete-artifact", action="store_true", help="Delete the artifact file when pruning a specific model")
    registry_prune.add_argument("--no-backup", action="store_true", help="Skip registry backup before pruning")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "train-model":
        model = train_baseline_model_from_raw(
            args.baseline_tetragon,
            args.baseline_prometheus,
            args.model_path,
            threshold=args.threshold,
            model_type=args.model_type,
            registry_path=args.registry_path,
            tags=args.tags,
            activate=args.activate,
        )
        print(json.dumps(model.to_dict(), indent=2))
        return 0
    if args.command == "show-model":
        print(json.dumps(describe_model_file(args.model_path), indent=2))
        return 0
    if args.command == "migrate-model":
        migrated = migrate_model_file(
            args.source_path,
            args.output_path,
            target_schema_version=args.target_schema_version,
        )
        print(json.dumps(migrated.to_dict(), indent=2))
        return 0
    if args.command == "registry":
        if args.registry_command == "list":
            payload = load_registry(args.registry_path)
        elif args.registry_command == "status":
            payload = registry_status(args.registry_path)
        elif args.registry_command == "activate":
            payload = activate_model(args.model_id, args.registry_path)
        elif args.registry_command == "tag":
            payload = tag_model(args.model_id, args.tags, args.registry_path)
        elif args.registry_command == "backup":
            payload = {"backup_path": backup_registry(args.registry_path, args.backup_path)}
        else:
            payload = prune_registry(
                registry_path=args.registry_path,
                model_id=args.model_id,
                missing_only=args.missing_only,
                delete_artifact=args.delete_artifact,
                create_backup=not args.no_backup,
            )
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "phase1":
        report = run_phase1(args.baseline, args.input, args.output_dir)
    elif args.command == "phase2":
        report = run_phase2(
            args.baseline_tetragon,
            args.baseline_prometheus,
            args.input_tetragon,
            args.input_prometheus,
            args.output_dir,
        )
    elif args.command == "phase3":
        report = run_phase3(
            args.baseline_tetragon,
            args.baseline_prometheus,
            args.tetragon_log,
            args.prometheus_url,
            args.output_dir,
            tetragon_tail_lines=args.tetragon_tail_lines,
            scrape_timeout=args.scrape_timeout,
        )
    elif args.command == "phase4":
        report = run_phase4(
            args.baseline_tetragon,
            args.baseline_prometheus,
            args.input_tetragon,
            args.input_prometheus,
            args.output_dir,
        )
    else:
        report = run_phase5(
            args.model_path,
            args.input_tetragon,
            args.input_prometheus,
            args.output_dir,
            registry_path=args.registry_path,
            model_id=args.model_id,
        )
    print(json.dumps(report.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
