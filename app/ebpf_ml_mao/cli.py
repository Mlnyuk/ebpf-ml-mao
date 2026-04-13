from __future__ import annotations

import argparse
import json

from .pipeline import run_phase1, run_phase2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the eBPF ML MAO MVP pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

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
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "phase1":
        report = run_phase1(args.baseline, args.input, args.output_dir)
    else:
        report = run_phase2(
            args.baseline_tetragon,
            args.baseline_prometheus,
            args.input_tetragon,
            args.input_prometheus,
            args.output_dir,
        )
    print(json.dumps(report.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
