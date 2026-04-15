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



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the eBPF ML MAO MVP pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_model = subparsers.add_parser("train-model", help="Train and save a model")
    train_model.add_argument("--baseline-tetragon", required=True, help="Path to benign Tetragon JSONL")
    train_model.add_argument("--baseline-prometheus", required=True, help="Path to benign Prometheus snapshot JSON")
    train_model.add_argument("--model-path", required=True, help="Path to write the trained model JSON")
    train_model.add_argument("--threshold", type=float, default=0.45, help="Anomaly threshold stored in the model")
    train_model.add_argument("--model-type", choices=["baseline", "zscore"], default="baseline", help="Model type to train")

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
    phase5.add_argument("--model-path", required=True, help="Path to the trained model JSON")
    phase5.add_argument("--input-tetragon", required=True, help="Path to target Tetragon JSONL")
    phase5.add_argument("--input-prometheus", required=True, help="Path to target Prometheus snapshot JSON")
    phase5.add_argument("--output-dir", required=True, help="Directory for generated reports")
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
        )
        print(json.dumps(model.to_dict(), indent=2))
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
        )
    print(json.dumps(report.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
