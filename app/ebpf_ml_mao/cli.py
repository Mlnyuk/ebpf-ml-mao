from __future__ import annotations

import argparse
import json

from .pipeline import run_phase1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Phase 1 MVP pipeline.")
    parser.add_argument("--baseline", required=True, help="Path to benign baseline JSONL")
    parser.add_argument("--input", required=True, help="Path to target JSONL")
    parser.add_argument("--output-dir", required=True, help="Directory for generated reports")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    report = run_phase1(args.baseline, args.input, args.output_dir)
    print(json.dumps(report.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
