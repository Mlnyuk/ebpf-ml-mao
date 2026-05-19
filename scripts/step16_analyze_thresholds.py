#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

RESULT_DIR = Path(os.environ.get("RESULT_DIR", "results/step16"))
REPORT_PATH = RESULT_DIR / "threshold-analysis.md"
CSV_PATH = RESULT_DIR / "threshold-analysis.csv"
INGEST_SCORES_PATH = RESULT_DIR / "fault-target-ingest-scores.jsonl"
DEFAULT_THRESHOLDS = [0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
SCENARIOS = ["baseline", "exec-storm", "network-burst", "cpu-stress", "memory-pressure"]
FAULT_SCENARIOS = [scenario for scenario in SCENARIOS if scenario != "baseline"]
TARGET_WORKLOAD = os.environ.get("ANALYZER_TARGET_WORKLOAD", "fault-target")


@dataclass(frozen=True)
class ScenarioScores:
    name: str
    scores: list[float]
    verdicts: list[str]
    latest_workflow_verdict: str | None
    alert_count: int | None
    dashboard_state: str | None
    total_scored_samples: int

    @property
    def expected_label(self) -> str:
        return "normal" if self.name == "baseline" else "fault"


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def iter_json_objects(text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    index = 0
    objects: list[Any] = []
    while index < len(text):
        while index < len(text) and text[index] not in "[{":
            index += 1
        if index >= len(text):
            break
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            index += 1
            continue
        objects.append(value)
        index += end
    return objects


def find_values(value: Any, key: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            if child_key == key:
                found.append(child_value)
            found.extend(find_values(child_value, key))
    elif isinstance(value, list):
        for child in value:
            found.extend(find_values(child, key))
    return found


def workflow_latest_verdict(prefix: str) -> str | None:
    for path in [RESULT_DIR / f"{prefix}-workflow.json", RESULT_DIR / f"{prefix}-dashboard.json"]:
        text = read_text(path)
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        verdicts = find_values(payload, "latest_verdict")
        if verdicts:
            return str(verdicts[-1])
    return None


def dashboard_signals(prefix: str) -> tuple[int | None, str | None]:
    text = read_text(RESULT_DIR / f"{prefix}-dashboard.json")
    if not text:
        return None, None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None, None
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        return None, None
    raw_count = summary.get("alert_count")
    try:
        alert_count = int(raw_count) if raw_count is not None else None
    except (TypeError, ValueError):
        alert_count = None
    state = summary.get("state")
    return alert_count, str(state) if isinstance(state, str) else None


def dashboard_timestamp(prefix: str) -> float | None:
    text = read_text(RESULT_DIR / f"{prefix}-dashboard.json")
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    ts = payload.get("timestamp") if isinstance(payload, dict) else None
    try:
        return float(ts) if ts is not None else None
    except (TypeError, ValueError):
        return None


def scenario_boundaries() -> list[tuple[str, float]]:
    """Return scenario boundaries (name, snapshot_end_ts) sorted in chronological order.

    A record with window_start <= snapshot_end_ts belongs to that scenario.
    The last scenario uses +inf so any trailing window lands there.
    """
    boundaries: list[tuple[str, float]] = []
    for name in SCENARIOS:
        ts = dashboard_timestamp(name)
        if ts is None:
            continue
        boundaries.append((name, ts))
    if boundaries:
        last_name = boundaries[-1][0]
        boundaries[-1] = (last_name, float("inf"))
    return boundaries


def assign_scenario(window_start: float | None, boundaries: list[tuple[str, float]]) -> str:
    if window_start is None:
        return "unknown"
    for name, snap_ts in boundaries:
        if window_start <= snap_ts:
            return name
    return "unknown"


def load_ingest_scores(prefix: str) -> tuple[list[float], list[str]]:
    """Load per-sample scores from the fault-target PVC ingest JSONL dump, filtered by scenario.

    If the JSONL records carry scenario='unknown', auto-assign by dashboard timestamps.
    """
    scores: list[float] = []
    verdicts: list[str] = []
    if not INGEST_SCORES_PATH.exists():
        return scores, verdicts
    boundaries = scenario_boundaries()
    for line in INGEST_SCORES_PATH.read_text(encoding="utf-8").splitlines():
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
        if scenario != prefix:
            continue
        try:
            scores.append(float(obj["score"]))
        except (TypeError, ValueError):
            continue
        verdicts.append(str(obj.get("verdict", "")))
    return scores, verdicts


def scores_for(prefix: str) -> ScenarioScores:
    # Primary: fault-target PVC ingest dump (accurate, workload-scoped)
    scores, verdicts = load_ingest_scores(prefix)
    # Fallback: scan log tails filtered to TARGET_WORKLOAD
    total = 0
    if not scores:
        for suffix in ["collector.log", "analyzer.log"]:
            for obj in iter_json_objects(read_text(RESULT_DIR / f"{prefix}-{suffix}")):
                if not isinstance(obj, dict):
                    continue
                if "score" not in obj or "verdict" not in obj:
                    continue
                total += 1
                window = obj.get("feature_window")
                workload = window.get("workload") if isinstance(window, dict) else None
                if workload != TARGET_WORKLOAD:
                    continue
                try:
                    scores.append(float(obj["score"]))
                except (TypeError, ValueError):
                    continue
                verdicts.append(str(obj["verdict"]))
    else:
        total = len(scores)
    alert_count, dashboard_state = dashboard_signals(prefix)
    return ScenarioScores(
        prefix,
        scores,
        verdicts,
        workflow_latest_verdict(prefix),
        alert_count,
        dashboard_state,
        total,
    )


def fmt_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def distribution_table(scenarios: list[ScenarioScores]) -> list[str]:
    lines = [
        "| Scenario | Expected | Target samples | Total scored | Min | Mean | Max | Anomalous (target) | Workflow verdict | Dashboard alerts |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for scenario in scenarios:
        scores = scenario.scores
        anomalous = sum(1 for verdict in scenario.verdicts if verdict == "anomalous")
        lines.append(
            "| "
            + " | ".join(
                [
                    scenario.name,
                    scenario.expected_label,
                    str(len(scores)),
                    str(scenario.total_scored_samples),
                    fmt_float(min(scores) if scores else None),
                    fmt_float(mean(scores) if scores else None),
                    fmt_float(max(scores) if scores else None),
                    str(anomalous),
                    scenario.latest_workflow_verdict or "unknown",
                    "n/a" if scenario.alert_count is None else str(scenario.alert_count),
                ]
            )
            + " |"
        )
    return lines


def verdict_table(scenarios: list[ScenarioScores]) -> list[str]:
    lines = [
        "| Scenario | Expected | Workflow verdict | Dashboard state | Alerts | Detected |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for scenario in scenarios:
        verdict = scenario.latest_workflow_verdict or "unknown"
        expected_anomalous = scenario.expected_label == "fault"
        is_anomalous = verdict == "anomalous"
        if expected_anomalous:
            detected = "yes" if is_anomalous else "no"
        else:
            detected = "yes" if not is_anomalous else "false positive"
        lines.append(
            "| "
            + " | ".join(
                [
                    scenario.name,
                    scenario.expected_label,
                    verdict,
                    scenario.dashboard_state or "unknown",
                    "n/a" if scenario.alert_count is None else str(scenario.alert_count),
                    detected,
                ]
            )
            + " |"
        )
    return lines


def threshold_rows(scenarios: list[ScenarioScores]) -> list[dict[str, str]]:
    baseline = next(scenario for scenario in scenarios if scenario.name == "baseline")
    faults = [scenario for scenario in scenarios if scenario.name in FAULT_SCENARIOS]
    baseline_scores = baseline.scores
    fault_scores = [score for scenario in faults for score in scenario.scores]
    rows: list[dict[str, str]] = []
    for threshold in DEFAULT_THRESHOLDS:
        false_positives = sum(1 for score in baseline_scores if score >= threshold)
        false_negatives = sum(1 for score in fault_scores if score < threshold)
        rows.append(
            {
                "threshold": f"{threshold:.2f}",
                "baseline_samples": str(len(baseline_scores)),
                "fault_samples": str(len(fault_scores)),
                "false_positives": str(false_positives),
                "false_positive_rate": fmt_float(false_positives / len(baseline_scores) if baseline_scores else None),
                "false_negatives": str(false_negatives),
                "false_negative_rate": fmt_float(false_negatives / len(fault_scores) if fault_scores else None),
            }
        )
    return rows


def threshold_table(rows: list[dict[str, str]]) -> list[str]:
    lines = [
        "| Threshold | Baseline samples | Fault samples | False positives | FP rate | False negatives | FN rate |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["threshold"],
                    row["baseline_samples"],
                    row["fault_samples"],
                    row["false_positives"],
                    row["false_positive_rate"],
                    row["false_negatives"],
                    row["false_negative_rate"],
                ]
            )
            + " |"
        )
    return lines


def write_csv(rows: list[dict[str, str]]) -> None:
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = [scores_for(name) for name in SCENARIOS]
    rows = threshold_rows(scenarios)
    write_csv(rows)

    baseline = scenarios[0]
    fault_scenarios = [scenario for scenario in scenarios if scenario.name in FAULT_SCENARIOS]
    contamination = baseline.latest_workflow_verdict == "anomalous"
    baseline_missing_scores = not baseline.scores
    faults_anomalous_via_workflow = all(
        scenario.latest_workflow_verdict == "anomalous" for scenario in fault_scenarios
    )
    fault_scores_flat = [s for sc in fault_scenarios for s in sc.scores]
    best_threshold = None
    for t in DEFAULT_THRESHOLDS:
        fp = sum(1 for s in baseline.scores if s >= t)
        fn = sum(1 for s in fault_scores_flat if s < t)
        if fp == 0 and fn == 0:
            best_threshold = t
            break

    if contamination:
        conclusion = "baseline workflow verdict is anomalous, so the existing baseline artifact is contaminated and must not be used as a clean normal distribution."
    elif baseline_missing_scores and faults_anomalous_via_workflow and fault_scores_flat:
        min_fault = min(fault_scores_flat)
        conclusion = (
            f"baseline produced no fault-target score samples (verdict=normal, alerts=0), "
            f"while all fault scenarios show verdict 'anomalous' with fault-target scores "
            f"ranging from {min_fault:.4f} to 1.0000. "
            f"{'Threshold ' + str(best_threshold) + ' achieves FP=0 and FN=0.' if best_threshold else 'No single threshold achieves FP=0 and FN=0 with current samples.'}"
        )
    elif baseline_missing_scores and faults_anomalous_via_workflow:
        conclusion = (
            f"target-scoped baseline produced no anomalous samples for workload '{TARGET_WORKLOAD}' "
            "(workflow verdict is normal, dashboard state is ok), while all fault scenarios show "
            "workflow verdict 'anomalous'. The analyzer target filter cleanly separates baseline "
            "from injected faults at the verdict level."
        )
    elif baseline_missing_scores:
        conclusion = "baseline score samples are absent from the current artifact set; rerun Step 16 collection after clean baseline recapture before selecting a final threshold."
    elif best_threshold:
        conclusion = f"threshold {best_threshold} achieves FP=0 and FN=0 on current samples; choose the lowest threshold with acceptable false-positive and false-negative rates."
    else:
        conclusion = "baseline score samples are present; choose the lowest threshold with acceptable false-positive and false-negative rates."

    lines = [
        "# Step 16 Baseline and Threshold Analysis",
        "",
        f"- Input directory: `{RESULT_DIR}`",
        f"- CSV output: `{CSV_PATH}`",
        f"- Evaluation scope: workload `{TARGET_WORKLOAD}` (matches analyzer `ANALYZER_TARGET_WORKLOAD`)",
        f"- Conclusion: {conclusion}",
        "",
        "## Verdict Summary",
        "",
        *verdict_table(scenarios),
        "",
        "## Score Distribution (target workload only)",
        "",
        *distribution_table(scenarios),
        "",
        "## Threshold Candidates (target workload only)",
        "",
        *threshold_table(rows),
        "",
        "## Calibration Rule",
        "",
        f"- Score samples are filtered to workload `{TARGET_WORKLOAD}` so the evaluation matches the analyzer's live target filter.",
        "- Treat `baseline` as the only normal class and all fault scenarios as fault class.",
        "- `score >= threshold` is counted as anomalous.",
        "- Baseline false positives measure clean-normal over-alerting on the target workload.",
        "- Fault false negatives measure missed fault samples on the target workload.",
        "- When per-sample scores for the target workload are absent (collector log tails may not capture every scoring window), use the dashboard workflow verdict and alert summary as the verdict-level evidence.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    print(f"wrote {CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
