from __future__ import annotations

import argparse
import json

from .api import load_ingest_index, serve_api
from .pipeline import (
    run_phase1,
    run_phase2,
    run_phase3,
    run_phase4,
    run_phase5,
    train_baseline_model_from_raw,
)
from .registry import activate_model, backup_registry, load_registry, prune_registry, registry_status, tag_model
from .scoring import describe_model_file, migrate_model_file
from .transport import drain_spool, post_report, ship_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the eBPF ML MAO MVP pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_model = subparsers.add_parser("train-model", help="Train and save a model")
    train_model.add_argument("--baseline-tetragon", required=True)
    train_model.add_argument("--baseline-prometheus", required=True)
    train_model.add_argument("--model-path", required=True)
    train_model.add_argument("--threshold", type=float, default=0.45)
    train_model.add_argument("--model-type", choices=["baseline", "zscore"], default="baseline")
    train_model.add_argument("--registry-path")
    train_model.add_argument("--tag", dest="tags", action="append", default=[])
    train_model.add_argument("--activate", action="store_true")

    phase1 = subparsers.add_parser("phase1")
    phase1.add_argument("--baseline", required=True)
    phase1.add_argument("--input", required=True)
    phase1.add_argument("--output-dir", required=True)

    phase2 = subparsers.add_parser("phase2")
    phase2.add_argument("--baseline-tetragon", required=True)
    phase2.add_argument("--baseline-prometheus", required=True)
    phase2.add_argument("--input-tetragon", required=True)
    phase2.add_argument("--input-prometheus", required=True)
    phase2.add_argument("--output-dir", required=True)

    phase3 = subparsers.add_parser("phase3")
    phase3.add_argument("--baseline-tetragon", required=True)
    phase3.add_argument("--baseline-prometheus", required=True)
    phase3.add_argument("--tetragon-log", required=True)
    phase3.add_argument("--prometheus-url", required=True)
    phase3.add_argument("--output-dir", required=True)
    phase3.add_argument("--tetragon-tail-lines", type=int, default=100)
    phase3.add_argument("--scrape-timeout", type=float, default=5.0)

    phase4 = subparsers.add_parser("phase4")
    phase4.add_argument("--baseline-tetragon", required=True)
    phase4.add_argument("--baseline-prometheus", required=True)
    phase4.add_argument("--input-tetragon", required=True)
    phase4.add_argument("--input-prometheus", required=True)
    phase4.add_argument("--output-dir", required=True)

    phase5 = subparsers.add_parser("phase5")
    phase5.add_argument("--model-path")
    phase5.add_argument("--model-id")
    phase5.add_argument("--registry-path")
    phase5.add_argument("--input-tetragon", required=True)
    phase5.add_argument("--input-prometheus", required=True)
    phase5.add_argument("--output-dir", required=True)

    show_model = subparsers.add_parser("show-model")
    show_model.add_argument("--model-path", required=True)

    migrate_model = subparsers.add_parser("migrate-model")
    migrate_model.add_argument("--source-path", required=True)
    migrate_model.add_argument("--output-path", required=True)
    migrate_model.add_argument("--target-schema-version", default="v2")

    api = subparsers.add_parser("api", help="Run analyzer API server")
    api.add_argument("--host", default="0.0.0.0")
    api.add_argument("--port", type=int, default=8080)
    api.add_argument("--registry-path", required=True)
    api.add_argument("--ingest-dir", required=True)
    api.add_argument("--shared-token", default="")

    push = subparsers.add_parser("push-report", help="Send a report to analyzer API")
    push.add_argument("--api-url", required=True)
    push.add_argument("--node-name", required=True)
    push.add_argument("--report-path", required=True)
    push.add_argument("--shared-token", default="")
    push.add_argument("--timeout", type=float, default=5.0)
    push.add_argument("--retries", type=int, default=3)

    ship = subparsers.add_parser("ship-report", help="Send a report or spool it on failure")
    ship.add_argument("--api-url", required=True)
    ship.add_argument("--node-name", required=True)
    ship.add_argument("--report-path", required=True)
    ship.add_argument("--spool-dir", required=True)
    ship.add_argument("--shared-token", default="")
    ship.add_argument("--timeout", type=float, default=5.0)
    ship.add_argument("--retries", type=int, default=3)

    drain = subparsers.add_parser("drain-spool", help="Replay spooled reports to analyzer API")
    drain.add_argument("--api-url", required=True)
    drain.add_argument("--spool-dir", required=True)
    drain.add_argument("--shared-token", default="")
    drain.add_argument("--timeout", type=float, default=5.0)
    drain.add_argument("--retries", type=int, default=3)

    ingest = subparsers.add_parser("ingest-status", help="Show analyzer ingest index summary")
    ingest.add_argument("--ingest-dir", required=True)

    registry = subparsers.add_parser("registry")
    registry_subparsers = registry.add_subparsers(dest="registry_command", required=True)
    registry_list = registry_subparsers.add_parser("list")
    registry_list.add_argument("--registry-path", required=True)
    registry_status_parser = registry_subparsers.add_parser("status")
    registry_status_parser.add_argument("--registry-path", required=True)
    registry_activate = registry_subparsers.add_parser("activate")
    registry_activate.add_argument("--registry-path", required=True)
    registry_activate.add_argument("--model-id", required=True)
    registry_tag = registry_subparsers.add_parser("tag")
    registry_tag.add_argument("--registry-path", required=True)
    registry_tag.add_argument("--model-id", required=True)
    registry_tag.add_argument("--tag", dest="tags", action="append", required=True)
    registry_backup = registry_subparsers.add_parser("backup")
    registry_backup.add_argument("--registry-path", required=True)
    registry_backup.add_argument("--backup-path")
    registry_prune = registry_subparsers.add_parser("prune")
    registry_prune.add_argument("--registry-path", required=True)
    registry_prune.add_argument("--model-id")
    registry_prune.add_argument("--missing-only", action="store_true")
    registry_prune.add_argument("--delete-artifact", action="store_true")
    registry_prune.add_argument("--no-backup", action="store_true")
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
        migrated = migrate_model_file(args.source_path, args.output_path, target_schema_version=args.target_schema_version)
        print(json.dumps(migrated.to_dict(), indent=2))
        return 0
    if args.command == "api":
        serve_api(args.host, args.port, registry_path=args.registry_path, ingest_dir=args.ingest_dir, shared_token=args.shared_token)
        return 0
    if args.command == "push-report":
        payload = post_report(args.api_url, node_name=args.node_name, report_path=args.report_path, shared_token=args.shared_token, timeout=args.timeout, retries=args.retries)
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "ship-report":
        payload = ship_report(args.api_url, node_name=args.node_name, report_path=args.report_path, spool_dir=args.spool_dir, shared_token=args.shared_token, timeout=args.timeout, retries=args.retries)
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "drain-spool":
        payload = drain_spool(args.api_url, spool_dir=args.spool_dir, shared_token=args.shared_token, timeout=args.timeout, retries=args.retries)
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "ingest-status":
        print(json.dumps(load_ingest_index(args.ingest_dir), indent=2))
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
            payload = prune_registry(registry_path=args.registry_path, model_id=args.model_id, missing_only=args.missing_only, delete_artifact=args.delete_artifact, create_backup=not args.no_backup)
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "phase1":
        report = run_phase1(args.baseline, args.input, args.output_dir)
    elif args.command == "phase2":
        report = run_phase2(args.baseline_tetragon, args.baseline_prometheus, args.input_tetragon, args.input_prometheus, args.output_dir)
    elif args.command == "phase3":
        report = run_phase3(args.baseline_tetragon, args.baseline_prometheus, args.tetragon_log, args.prometheus_url, args.output_dir, tetragon_tail_lines=args.tetragon_tail_lines, scrape_timeout=args.scrape_timeout)
    elif args.command == "phase4":
        report = run_phase4(args.baseline_tetragon, args.baseline_prometheus, args.input_tetragon, args.input_prometheus, args.output_dir)
    else:
        report = run_phase5(args.model_path, args.input_tetragon, args.input_prometheus, args.output_dir, registry_path=args.registry_path, model_id=args.model_id)
    print(json.dumps(report.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
