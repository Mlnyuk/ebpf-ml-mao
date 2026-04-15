from __future__ import annotations

import argparse
import json

from .api import build_dashboard_snapshot, load_ingest_index, load_workflow_summary, rebuild_ingest_index, serve_api
from .pipeline import run_phase1, run_phase2, run_phase3, run_phase4, run_phase5, train_baseline_model_from_raw
from .registry import activate_model, backup_registry, load_registry, prune_registry, registry_status, tag_model
from .scoring import describe_model_file, migrate_model_file
from .transport import (
    drain_spool,
    post_report,
    prune_queue,
    prune_spool,
    queue_status,
    ship_report,
    spool_status,
)


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
    api.add_argument("--collector-spool-dir", default="")
    api.add_argument("--postprocess-queue-dir", default="")
    api.add_argument("--spool-ttl-seconds", type=int, default=3600)
    api.add_argument("--queue-ttl-seconds", type=int, default=86400)
    api.add_argument("--queue-alert-threshold", type=int, default=20)
    api.add_argument("--spool-alert-threshold", type=int, default=10)
    api.add_argument("--duplicate-ratio-threshold", type=float, default=0.25)

    push = subparsers.add_parser("push-report")
    push.add_argument("--api-url", required=True)
    push.add_argument("--node-name", required=True)
    push.add_argument("--report-path", required=True)
    push.add_argument("--shared-token", default="")
    push.add_argument("--timeout", type=float, default=5.0)
    push.add_argument("--retries", type=int, default=3)

    ship = subparsers.add_parser("ship-report")
    ship.add_argument("--api-url", required=True)
    ship.add_argument("--node-name", required=True)
    ship.add_argument("--report-path", required=True)
    ship.add_argument("--spool-dir", required=True)
    ship.add_argument("--shared-token", default="")
    ship.add_argument("--timeout", type=float, default=5.0)
    ship.add_argument("--retries", type=int, default=3)
    ship.add_argument("--spool-ttl-seconds", type=int, default=3600)

    drain = subparsers.add_parser("drain-spool")
    drain.add_argument("--api-url", required=True)
    drain.add_argument("--spool-dir", required=True)
    drain.add_argument("--shared-token", default="")
    drain.add_argument("--timeout", type=float, default=5.0)
    drain.add_argument("--retries", type=int, default=3)
    drain.add_argument("--ttl-seconds", type=int, default=3600)
    drain.add_argument("--quarantine-dir")
    drain.add_argument("--max-items", type=int)

    spool_status_cmd = subparsers.add_parser("spool-status")
    spool_status_cmd.add_argument("--spool-dir", required=True)
    spool_status_cmd.add_argument("--ttl-seconds", type=int, default=3600)

    spool_prune_cmd = subparsers.add_parser("spool-prune")
    spool_prune_cmd.add_argument("--spool-dir", required=True)
    spool_prune_cmd.add_argument("--ttl-seconds", type=int, default=3600)
    spool_prune_cmd.add_argument("--quarantine-dir")

    queue_status_cmd = subparsers.add_parser("queue-status")
    queue_status_cmd.add_argument("--queue-dir", required=True)
    queue_status_cmd.add_argument("--ttl-seconds", type=int, default=86400)
    queue_status_cmd.add_argument("--quarantine-dir")

    queue_prune_cmd = subparsers.add_parser("queue-prune")
    queue_prune_cmd.add_argument("--queue-dir", required=True)
    queue_prune_cmd.add_argument("--ttl-seconds", type=int, default=86400)
    queue_prune_cmd.add_argument("--quarantine-dir")

    ingest = subparsers.add_parser("ingest-status")
    ingest.add_argument("--ingest-dir", required=True)

    workflow = subparsers.add_parser("workflow-status")
    workflow.add_argument("--ingest-dir", required=True)

    dashboard = subparsers.add_parser("dashboard-status")
    dashboard.add_argument("--registry-path", required=True)
    dashboard.add_argument("--ingest-dir", required=True)
    dashboard.add_argument("--collector-spool-dir", default="")
    dashboard.add_argument("--postprocess-queue-dir", default="")
    dashboard.add_argument("--spool-ttl-seconds", type=int, default=3600)
    dashboard.add_argument("--queue-ttl-seconds", type=int, default=86400)
    dashboard.add_argument("--queue-alert-threshold", type=int, default=20)
    dashboard.add_argument("--spool-alert-threshold", type=int, default=10)
    dashboard.add_argument("--duplicate-ratio-threshold", type=float, default=0.25)

    alerts = subparsers.add_parser("alerts-status")
    alerts.add_argument("--registry-path", required=True)
    alerts.add_argument("--ingest-dir", required=True)
    alerts.add_argument("--collector-spool-dir", default="")
    alerts.add_argument("--postprocess-queue-dir", default="")
    alerts.add_argument("--spool-ttl-seconds", type=int, default=3600)
    alerts.add_argument("--queue-ttl-seconds", type=int, default=86400)
    alerts.add_argument("--queue-alert-threshold", type=int, default=20)
    alerts.add_argument("--spool-alert-threshold", type=int, default=10)
    alerts.add_argument("--duplicate-ratio-threshold", type=float, default=0.25)

    ingest_repair = subparsers.add_parser("ingest-repair")
    ingest_repair.add_argument("--ingest-dir", required=True)

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


def _dashboard_payload(args: argparse.Namespace) -> dict:
    return build_dashboard_snapshot(
        args.registry_path,
        args.ingest_dir,
        collector_spool_dir=args.collector_spool_dir,
        postprocess_queue_dir=args.postprocess_queue_dir,
        spool_ttl_seconds=args.spool_ttl_seconds,
        queue_ttl_seconds=args.queue_ttl_seconds,
        queue_alert_threshold=args.queue_alert_threshold,
        spool_alert_threshold=args.spool_alert_threshold,
        duplicate_ratio_threshold=args.duplicate_ratio_threshold,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "train-model":
        model = train_baseline_model_from_raw(args.baseline_tetragon, args.baseline_prometheus, args.model_path, threshold=args.threshold, model_type=args.model_type, registry_path=args.registry_path, tags=args.tags, activate=args.activate)
        print(json.dumps(model.to_dict(), indent=2)); return 0
    if args.command == "show-model":
        print(json.dumps(describe_model_file(args.model_path), indent=2)); return 0
    if args.command == "migrate-model":
        migrated = migrate_model_file(args.source_path, args.output_path, target_schema_version=args.target_schema_version)
        print(json.dumps(migrated.to_dict(), indent=2)); return 0
    if args.command == "api":
        serve_api(
            args.host,
            args.port,
            registry_path=args.registry_path,
            ingest_dir=args.ingest_dir,
            shared_token=args.shared_token,
            collector_spool_dir=args.collector_spool_dir,
            postprocess_queue_dir=args.postprocess_queue_dir,
            spool_ttl_seconds=args.spool_ttl_seconds,
            queue_ttl_seconds=args.queue_ttl_seconds,
            queue_alert_threshold=args.queue_alert_threshold,
            spool_alert_threshold=args.spool_alert_threshold,
            duplicate_ratio_threshold=args.duplicate_ratio_threshold,
        )
        return 0
    if args.command == "push-report":
        print(json.dumps(post_report(args.api_url, node_name=args.node_name, report_path=args.report_path, shared_token=args.shared_token, timeout=args.timeout, retries=args.retries), indent=2)); return 0
    if args.command == "ship-report":
        print(json.dumps(ship_report(args.api_url, node_name=args.node_name, report_path=args.report_path, spool_dir=args.spool_dir, shared_token=args.shared_token, timeout=args.timeout, retries=args.retries, spool_ttl_seconds=args.spool_ttl_seconds), indent=2)); return 0
    if args.command == "drain-spool":
        print(json.dumps(drain_spool(args.api_url, spool_dir=args.spool_dir, shared_token=args.shared_token, timeout=args.timeout, retries=args.retries, ttl_seconds=args.ttl_seconds, quarantine_dir=args.quarantine_dir, max_items=args.max_items), indent=2)); return 0
    if args.command == "spool-status":
        print(json.dumps(spool_status(args.spool_dir, ttl_seconds=args.ttl_seconds), indent=2)); return 0
    if args.command == "spool-prune":
        print(json.dumps(prune_spool(args.spool_dir, ttl_seconds=args.ttl_seconds, quarantine_dir=args.quarantine_dir), indent=2)); return 0
    if args.command == "queue-status":
        print(json.dumps(queue_status(args.queue_dir, ttl_seconds=args.ttl_seconds, quarantine_dir=args.quarantine_dir), indent=2)); return 0
    if args.command == "queue-prune":
        print(json.dumps(prune_queue(args.queue_dir, ttl_seconds=args.ttl_seconds, quarantine_dir=args.quarantine_dir), indent=2)); return 0
    if args.command == "ingest-status":
        print(json.dumps(load_ingest_index(args.ingest_dir, repair=True), indent=2)); return 0
    if args.command == "workflow-status":
        print(json.dumps(load_workflow_summary(args.ingest_dir, repair=True), indent=2)); return 0
    if args.command == "dashboard-status":
        print(json.dumps(_dashboard_payload(args), indent=2)); return 0
    if args.command == "alerts-status":
        dashboard = _dashboard_payload(args)
        print(json.dumps({
            "status": dashboard["summary"]["state"],
            "component": dashboard["component"],
            "timestamp": dashboard["timestamp"],
            "summary": dashboard["summary"],
            "alerts": dashboard["alerts"],
        }, indent=2)); return 0
    if args.command == "ingest-repair":
        print(json.dumps(rebuild_ingest_index(args.ingest_dir), indent=2)); return 0
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
        print(json.dumps(payload, indent=2)); return 0
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
    print(json.dumps(report.to_dict(), indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
