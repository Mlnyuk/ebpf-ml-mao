#!/usr/bin/env python3
"""Train a fresh baseline model from the Step 21 fault-target idle workload.

Reads the file_open-only baseline windows captured by
`scripts/step21_collect_baseline.sh` (default
`results/step21/baseline_collect/fault-target-baseline.jsonl`) and emits a
baseline-type model JSON (default `results/step21/baseline-v4.json`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "app"))

from ebpf_ml_mao.models import FeatureWindow  # noqa: E402
from ebpf_ml_mao.scoring import BaselineScorer  # noqa: E402

DEFAULT_INPUT = REPO_ROOT / "results/step21/baseline_collect/fault-target-baseline.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "results/step21/baseline-v4.json"


def load_windows(path: Path) -> list[FeatureWindow]:
    windows: list[FeatureWindow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            ws = float(obj["window_start"])
            we = float(obj["window_end"])
        except (TypeError, ValueError, KeyError):
            continue
        values = obj.get("values") or {}
        try:
            num_values = {k: float(v) for k, v in values.items()}
        except (TypeError, ValueError):
            continue
        windows.append(
            FeatureWindow(
                window_start=ws,
                window_end=we,
                workload=str(obj.get("workload") or "fault-target"),
                values=num_values,
            )
        )
    return windows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--threshold", type=float, default=0.45)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"input not found: {args.input}", file=sys.stderr)
        return 1
    windows = load_windows(args.input)
    if not windows:
        print(f"no usable windows in {args.input}", file=sys.stderr)
        return 1

    scorer = BaselineScorer(model_type="baseline")
    model = scorer.fit(windows, threshold=args.threshold, model_type="baseline")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    scorer.save_model(args.output)
    print(f"trained baseline model on {len(windows)} windows; threshold={args.threshold}")
    print(f"saved {args.output}")
    print(json.dumps(model.baseline, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
