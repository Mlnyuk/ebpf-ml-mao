#!/usr/bin/env python3
"""Retrain the active baseline model using fault-target windows captured
during the baseline period of the Step 20 repeated runs.

The default registry model (`baseline-v2-01`) was trained on Step 2 sample
data and does not match the deployed fault-target workload (busybox idle pod
with intermittent warmup activity). As a result, idle fault-target windows
score above the 0.45 threshold even with no fault injection. This script
fits a new baseline model from the actual fault-target baseline windows
recorded across all Step 20 runs, so the active model is calibrated against
the production workload distribution.

Inputs:
- results/step20/run_NN/fault-target-ingest-scores.jsonl (windows + values)
- results/step20/run_NN/baseline-dashboard.json          (boundary timestamp)
- results/step20/run_NN/{exec-storm,...}-dashboard.json  (other boundaries)

Output:
- results/step20/baseline-v3.json  (new model)
- results/step20/baseline-training-windows.json (debug — windows used)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "app"))

from ebpf_ml_mao.models import FeatureWindow  # noqa: E402
from ebpf_ml_mao.scoring import BaselineScorer  # noqa: E402

SCENARIOS = ("baseline", "exec-storm", "network-burst", "cpu-stress", "memory-pressure")
BASE_DIR = Path(REPO_ROOT, "results/step20")
MODEL_OUT = BASE_DIR / "baseline-v3.json"
WINDOWS_OUT = BASE_DIR / "baseline-training-windows.json"


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


def baseline_cutoff(run_dir: Path) -> float | None:
    return dashboard_timestamp(run_dir, "baseline")


def baseline_windows_from_run(run_dir: Path) -> list[FeatureWindow]:
    path = run_dir / "fault-target-ingest-scores.jsonl"
    if not path.exists():
        return []
    cutoff = baseline_cutoff(run_dir)
    if cutoff is None:
        return []
    windows: list[FeatureWindow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
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
        if ws > cutoff:
            continue
        values = obj.get("values")
        if not isinstance(values, dict):
            continue
        try:
            num_values = {k: float(v) for k, v in values.items()}
        except (TypeError, ValueError):
            continue
        workload = str(obj.get("workload") or "fault-target")
        windows.append(
            FeatureWindow(
                window_start=ws, window_end=we, workload=workload, values=num_values
            )
        )
    return windows


def main() -> int:
    run_dirs = sorted(p for p in BASE_DIR.glob("run_*") if p.is_dir())
    if not run_dirs:
        print(f"no run directories under {BASE_DIR}", file=sys.stderr)
        return 1

    all_windows: list[FeatureWindow] = []
    per_run_counts: list[tuple[str, int]] = []
    for run_dir in run_dirs:
        windows = baseline_windows_from_run(run_dir)
        per_run_counts.append((run_dir.name, len(windows)))
        all_windows.extend(windows)

    if not all_windows:
        print("no baseline windows extracted; cannot fit model", file=sys.stderr)
        return 1

    scorer = BaselineScorer(model_type="baseline")
    model = scorer.fit(all_windows, threshold=0.45, model_type="baseline")
    scorer.save_model(MODEL_OUT)

    snapshot = {
        "total_windows": len(all_windows),
        "per_run_counts": per_run_counts,
        "feature_keys": model.feature_keys,
        "baseline": model.baseline,
        "threshold": model.threshold,
    }
    WINDOWS_OUT.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    print(f"wrote {MODEL_OUT}")
    print(f"wrote {WINDOWS_OUT}")
    print(f"trained on {len(all_windows)} fault-target baseline windows from {len(run_dirs)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
