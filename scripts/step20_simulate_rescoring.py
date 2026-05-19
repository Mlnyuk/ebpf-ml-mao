#!/usr/bin/env python3
"""Re-score all Step 20 fault-target windows against a candidate baseline
model without restarting the analyzer.

This lets us iterate on calibration (model parameters + threshold) using the
already-collected windows from run_01..run_05 before committing to another
~30 min N=5 cluster re-run.

Usage:
  python3 scripts/step20_simulate_rescoring.py [--model PATH] [--threshold X]
                                              [--trim-baseline N]

By default trains a fresh baseline model from the lowest-exec-count baseline
samples (trim parameter), then reports detection rates per scenario.
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

BASE_DIR = Path(REPO_ROOT, "results/step20")
SCENARIOS = ("baseline", "exec-storm", "network-burst", "cpu-stress", "memory-pressure")


def dashboard_timestamp(run_dir: Path, scenario: str) -> float | None:
    path = run_dir / f"{scenario}-dashboard.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    for key in ("timestamp", "snapshot_timestamp", "generated_at"):
        if key in payload:
            try:
                return float(payload[key])
            except (TypeError, ValueError):
                continue
    return None


def scenario_boundaries(run_dir: Path) -> list[tuple[str, float]]:
    bnds = []
    for s in SCENARIOS:
        ts = dashboard_timestamp(run_dir, s)
        if ts:
            bnds.append((s, ts))
    if bnds:
        bnds[-1] = (bnds[-1][0], float("inf"))
    return bnds


def assign_scenario(ws: float, bnds: list[tuple[str, float]]) -> str:
    for name, ts in bnds:
        if ws <= ts:
            return name
    return "unknown"


def load_all_windows() -> list[tuple[str, FeatureWindow]]:
    out: list[tuple[str, FeatureWindow]] = []
    for run_dir in sorted(BASE_DIR.glob("run_*")):
        path = run_dir / "fault-target-ingest-scores.jsonl"
        if not path.exists():
            continue
        bnds = scenario_boundaries(run_dir)
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                ws = float(obj.get("window_start"))
                we = float(obj.get("window_end"))
            except (TypeError, ValueError):
                continue
            values = obj.get("values") or {}
            try:
                num_values = {k: float(v) for k, v in values.items()}
            except (TypeError, ValueError):
                continue
            scenario = assign_scenario(ws, bnds)
            fw = FeatureWindow(
                window_start=ws,
                window_end=we,
                workload=str(obj.get("workload") or "fault-target"),
                values=num_values,
            )
            out.append((scenario, fw))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trim-baseline",
        type=int,
        default=6,
        help="train on this many lowest-exec_count baseline windows (default 6)",
    )
    parser.add_argument("--threshold", type=float, default=0.45)
    parser.add_argument(
        "--model-type", choices=["baseline", "zscore"], default="zscore"
    )
    parser.add_argument(
        "--out-model", type=Path, default=BASE_DIR / "baseline-v3.json"
    )
    args = parser.parse_args()

    all_pairs = load_all_windows()
    baseline_pairs = [(s, fw) for s, fw in all_pairs if s == "baseline"]
    baseline_pairs.sort(key=lambda p: p[1].values.get("exec_count", 0.0))
    selected = [fw for _, fw in baseline_pairs[: args.trim_baseline]]
    if not selected:
        print("no baseline windows", file=sys.stderr)
        return 1

    scorer = BaselineScorer(model_type=args.model_type)
    model = scorer.fit(selected, threshold=args.threshold, model_type=args.model_type)
    args.out_model.parent.mkdir(parents=True, exist_ok=True)
    scorer.save_model(args.out_model)

    print(
        f"trained {args.model_type} on {len(selected)}/"
        f"{len(baseline_pairs)} lowest-exec baseline windows; threshold={args.threshold}"
    )
    print(f"saved model -> {args.out_model}")
    print()
    print("Re-scoring all windows against new model:")
    print(f"{'scenario':<18} {'samples':>7} {'mean':>7} {'std':>7} {'min':>7} {'max':>7} {'>=thr':>6} {'rate':>6}")

    by_scenario: dict[str, list[float]] = {s: [] for s in SCENARIOS}
    for scenario, fw in all_pairs:
        if scenario not in by_scenario:
            continue
        score, _ = scorer.score(fw)
        by_scenario[scenario].append(score)

    import statistics
    for s in SCENARIOS:
        vals = by_scenario[s]
        if not vals:
            print(f"{s:<18} {0:>7}  (no samples)")
            continue
        m = statistics.fmean(vals)
        sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        flagged = sum(1 for v in vals if v >= args.threshold)
        rate = flagged / len(vals)
        print(f"{s:<18} {len(vals):>7} {m:>7.3f} {sd:>7.3f} {min(vals):>7.3f} {max(vals):>7.3f} {flagged:>6} {rate:>6.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
