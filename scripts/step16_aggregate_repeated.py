#!/usr/bin/env python3
"""Aggregate metrics across N step16 runs produced by step16_repeat_experiments.sh.

Reads each run_NN/ directory under the supplied base directory, extracts
per-scenario fault-target scores and dashboard verdicts, and writes:

- aggregated-threshold-analysis.md: mean/std of FP/FN per threshold candidate
- aggregated-paper-results.md: per-scenario detection rate and score stats

Detection at run-level is determined by the dashboard ``latest_verdict``:
baseline ``normal`` and fault ``anomalous`` count as correct detections.
Per-sample scores come from each run's ``fault-target-ingest-scores.jsonl``
(written by the analyzer PVC dump in step16_collect_results.sh) and are
labelled by scenario using the dashboard timestamps in that run.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


SCENARIOS = ["baseline", "exec-storm", "network-burst", "cpu-stress", "memory-pressure"]
FAULT_SCENARIOS = [s for s in SCENARIOS if s != "baseline"]
THRESHOLDS = [0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]


def fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def dashboard_timestamp(run_dir: Path, scenario: str) -> float | None:
    payload = read_json(run_dir / f"{scenario}-dashboard.json")
    if not isinstance(payload, dict):
        return None
    ts = payload.get("timestamp")
    try:
        return float(ts) if ts is not None else None
    except (TypeError, ValueError):
        return None


def dashboard_verdict(run_dir: Path, scenario: str) -> str | None:
    payload = read_json(run_dir / f"{scenario}-dashboard.json")
    if not isinstance(payload, dict):
        return None
    summary = payload.get("summary")
    if isinstance(summary, dict):
        verdict = summary.get("latest_verdict")
        if isinstance(verdict, str):
            return verdict
    return None


def scenario_boundaries(run_dir: Path) -> list[tuple[str, float]]:
    boundaries: list[tuple[str, float]] = []
    for name in SCENARIOS:
        ts = dashboard_timestamp(run_dir, name)
        if ts is None:
            continue
        boundaries.append((name, ts))
    if boundaries:
        boundaries[-1] = (boundaries[-1][0], float("inf"))
    return boundaries


def assign_scenario(window_start: float | None, boundaries: list[tuple[str, float]]) -> str:
    if window_start is None:
        return "unknown"
    for name, snap_ts in boundaries:
        if window_start <= snap_ts:
            return name
    return "unknown"


def load_run_scores(run_dir: Path) -> dict[str, list[float]]:
    path = run_dir / "fault-target-ingest-scores.jsonl"
    by_scenario: dict[str, list[float]] = {name: [] for name in SCENARIOS}
    if not path.exists():
        return by_scenario
    boundaries = scenario_boundaries(run_dir)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        scenario = obj.get("scenario")
        if scenario in (None, "", "unknown"):
            try:
                ws = float(obj.get("window_start"))
            except (TypeError, ValueError):
                ws = None
            scenario = assign_scenario(ws, boundaries)
        if scenario not in by_scenario:
            continue
        try:
            score = float(obj["score"])
        except (TypeError, ValueError, KeyError):
            continue
        by_scenario[scenario].append(score)
    return by_scenario


def list_run_dirs(base_dir: Path) -> list[Path]:
    if not base_dir.exists():
        return []
    runs = sorted(p for p in base_dir.iterdir() if p.is_dir() and p.name.startswith("run_"))
    return runs


def detection_correct(scenario: str, verdict: str | None) -> bool | None:
    if verdict is None:
        return None
    if scenario == "baseline":
        return verdict == "normal"
    return verdict == "anomalous"


def fault_target_verdict(
    scenario_scores: list[float], threshold: float = 0.45
) -> str | None:
    """Return a verdict for this scenario based solely on the fault-target
    scoring windows, not the cluster-wide dashboard latest_verdict. The latter
    can be polluted by other nodes' collectors whose input filter falls back
    to all events when fault-target is not present on that node.

    - Returns "anomalous" if any window meets the threshold.
    - Returns "normal" if all windows are below the threshold and at least
      one window exists.
    - Returns None if there are no fault-target windows for this scenario.
    """
    if not scenario_scores:
        return None
    if any(score >= threshold for score in scenario_scores):
        return "anomalous"
    return "normal"


def main() -> int:
    if len(sys.argv) < 2:
        base_dir = Path("results/step20")
    else:
        base_dir = Path(sys.argv[1])

    if not base_dir.exists():
        print(f"[aggregate] base directory not found: {base_dir}", file=sys.stderr)
        return 2

    runs = list_run_dirs(base_dir)
    if not runs:
        print(f"[aggregate] no run_NN directories found under {base_dir}", file=sys.stderr)
        return 2

    # Per-run detection outcomes and per-scenario score samples
    detection_rows: list[dict[str, str]] = []
    scenario_scores: dict[str, list[float]] = {name: [] for name in SCENARIOS}
    scenario_run_means: dict[str, list[float]] = {name: [] for name in SCENARIOS}
    scenario_detection_count: dict[str, int] = {name: 0 for name in SCENARIOS}
    scenario_total_runs: dict[str, int] = {name: 0 for name in SCENARIOS}

    for run_dir in runs:
        scores_by_scenario = load_run_scores(run_dir)
        per_run = {"run": run_dir.name}
        for name in SCENARIOS:
            scores = scores_by_scenario.get(name, [])
            # Prefer a fault-target-only verdict over the dashboard one so
            # noise from non-target nodes' collectors does not pollute the
            # detection statistics (see Step 21 docs on filter fallback).
            verdict = fault_target_verdict(scores) or dashboard_verdict(run_dir, name)
            correct = detection_correct(name, verdict)
            per_run[f"{name}_verdict"] = verdict or "missing"
            per_run[f"{name}_correct"] = "yes" if correct else ("no" if correct is False else "missing")
            if correct is not None:
                scenario_total_runs[name] += 1
                if correct:
                    scenario_detection_count[name] += 1
            scenario_scores[name].extend(scores)
            if scores:
                scenario_run_means[name].append(mean(scores))
            per_run[f"{name}_samples"] = str(len(scores))
        detection_rows.append(per_run)

    # Threshold sweep on aggregated samples
    baseline_scores = scenario_scores["baseline"]
    fault_scores = [s for name in FAULT_SCENARIOS for s in scenario_scores[name]]

    threshold_rows: list[dict[str, str]] = []
    for t in THRESHOLDS:
        fp = sum(1 for s in baseline_scores if s >= t)
        fn = sum(1 for s in fault_scores if s < t)
        threshold_rows.append({
            "threshold": f"{t:.2f}",
            "baseline_samples": str(len(baseline_scores)),
            "fault_samples": str(len(fault_scores)),
            "false_positives": str(fp),
            "false_positive_rate": fmt(fp / len(baseline_scores) if baseline_scores else None),
            "false_negatives": str(fn),
            "false_negative_rate": fmt(fn / len(fault_scores) if fault_scores else None),
        })

    # write per-run CSV
    detection_csv = base_dir / "aggregated-detection.csv"
    with detection_csv.open("w", encoding="utf-8", newline="") as fh:
        cols = ["run"] + [
            f"{name}_{suffix}" for name in SCENARIOS for suffix in ("verdict", "correct", "samples")
        ]
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        writer.writerows(detection_rows)

    threshold_csv = base_dir / "aggregated-threshold-analysis.csv"
    with threshold_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(threshold_rows[0].keys()))
        writer.writeheader()
        writer.writerows(threshold_rows)

    # markdown reports
    md_threshold = base_dir / "aggregated-threshold-analysis.md"
    md_paper = base_dir / "aggregated-paper-results.md"

    threshold_lines = [
        "# Step 20 Aggregated Threshold Analysis",
        "",
        f"- Base directory: `{base_dir}`",
        f"- Runs aggregated: {len(runs)} ({', '.join(r.name for r in runs)})",
        f"- Detection CSV: `{detection_csv}`",
        f"- Threshold CSV: `{threshold_csv}`",
        "",
        "## Per-Scenario Detection Rate",
        "",
        "| Scenario | Expected | Runs | Detected | Detection rate |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for name in SCENARIOS:
        runs_seen = scenario_total_runs[name]
        detected = scenario_detection_count[name]
        rate = (detected / runs_seen) if runs_seen else None
        expected = "normal" if name == "baseline" else "fault"
        threshold_lines.append(
            f"| {name} | {expected} | {runs_seen} | {detected} | {fmt_pct(rate)} |"
        )
    threshold_lines.extend([
        "",
        "## Per-Scenario fault-target Score Distribution (all samples pooled)",
        "",
        "| Scenario | Samples | Min | Mean | Std | Max | Per-run mean (mean ± std) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ])
    for name in SCENARIOS:
        scores = scenario_scores[name]
        run_means = scenario_run_means[name]
        if scores:
            score_mean = mean(scores)
            score_std = pstdev(scores) if len(scores) > 1 else 0.0
            cell = (
                f"| {name} | {len(scores)} | {fmt(min(scores))} | {fmt(score_mean)} | "
                f"{fmt(score_std)} | {fmt(max(scores))} | "
            )
            if run_means:
                rm_mean = mean(run_means)
                rm_std = pstdev(run_means) if len(run_means) > 1 else 0.0
                cell += f"{rm_mean:.4f} ± {rm_std:.4f} |"
            else:
                cell += "n/a |"
        else:
            cell = f"| {name} | 0 | n/a | n/a | n/a | n/a | n/a |"
        threshold_lines.append(cell)
    threshold_lines.extend([
        "",
        "## Threshold Sweep (pooled samples)",
        "",
        "| Threshold | Baseline samples | Fault samples | FP | FP rate | FN | FN rate |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in threshold_rows:
        threshold_lines.append(
            f"| {row['threshold']} | {row['baseline_samples']} | {row['fault_samples']} | "
            f"{row['false_positives']} | {row['false_positive_rate']} | "
            f"{row['false_negatives']} | {row['false_negative_rate']} |"
        )

    best_t = None
    for row in threshold_rows:
        if int(row["false_positives"]) == 0 and int(row["false_negatives"]) == 0:
            best_t = row["threshold"]
            break

    threshold_lines.extend([
        "",
        "## Calibration Result",
        "",
        f"- Aggregated baseline samples: {len(baseline_scores)}",
        f"- Aggregated fault samples: {len(fault_scores)}",
        f"- Optimal threshold (FP=0 and FN=0): "
        f"{'threshold ' + best_t if best_t else 'no single threshold satisfies both; pick the threshold that matches the desired FP/FN trade-off'}",
        "",
    ])
    md_threshold.write_text("\n".join(threshold_lines), encoding="utf-8")

    paper_lines = [
        "# Step 20 Aggregated Paper Result",
        "",
        f"- Base directory: `{base_dir}`",
        f"- Runs aggregated: {len(runs)}",
        "",
        "## Per-Run Detection Summary",
        "",
        "| Run | baseline | exec-storm | network-burst | cpu-stress | memory-pressure |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in detection_rows:
        cells = [row["run"]]
        for name in SCENARIOS:
            cells.append(f"{row.get(f'{name}_verdict', 'missing')} ({row.get(f'{name}_correct', 'missing')})")
        paper_lines.append("| " + " | ".join(cells) + " |")

    paper_lines.extend([
        "",
        "## Detection Rate Summary",
        "",
        "| Scenario | Expected | Detection rate | Score mean (per-run mean ± std) |",
        "| --- | --- | ---: | --- |",
    ])
    for name in SCENARIOS:
        runs_seen = scenario_total_runs[name]
        detected = scenario_detection_count[name]
        rate = (detected / runs_seen) if runs_seen else None
        expected = "normal" if name == "baseline" else "fault"
        rm = scenario_run_means[name]
        if rm:
            rm_mean = mean(rm)
            rm_std = pstdev(rm) if len(rm) > 1 else 0.0
            score_cell = f"{rm_mean:.4f} ± {rm_std:.4f} (over {len(rm)} runs)"
        else:
            score_cell = "n/a"
        paper_lines.append(
            f"| {name} | {expected} | {fmt_pct(rate)} | {score_cell} |"
        )

    paper_lines.extend([
        "",
        "## Interpretation",
        "",
        f"Across {len(runs)} independent runs, fault scenario detection is reported as "
        f"the fraction of runs where the analyzer dashboard reported `latest_verdict='anomalous'` "
        f"after the scenario, and baseline detection is the fraction of runs where the verdict "
        f"stayed `normal`. Per-run mean scores capture how consistently the analyzer scored each "
        f"scenario; tight standard deviations indicate the calibrated threshold is robust.",
        "",
    ])
    md_paper.write_text("\n".join(paper_lines), encoding="utf-8")

    print(f"wrote {md_threshold}")
    print(f"wrote {threshold_csv}")
    print(f"wrote {md_paper}")
    print(f"wrote {detection_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
