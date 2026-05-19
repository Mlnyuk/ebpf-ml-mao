#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from step16_analyze_thresholds import iter_json_objects, read_text, scores_for

RESULT_DIR = Path("results/step16")
REPORT_PATH = RESULT_DIR / "paper-results.md"
CSV_PATH = RESULT_DIR / "paper-results.csv"
SCENARIOS = ["exec-storm", "network-burst", "cpu-stress", "memory-pressure"]
FEATURES = [
    "event_count",
    "exec_count",
    "network_event_count",
    "unique_pids",
    "avg_cpu_usage",
    "max_cpu_usage",
    "avg_memory_usage",
    "max_memory_usage",
    "avg_network_connections",
    "max_network_connections",
]


@dataclass(frozen=True)
class ScenarioRow:
    scenario: str
    alerts: int | None
    tetragon_lines: int
    fault_target_lines: int
    score_min: float | None
    score_mean: float | None
    score_max: float | None
    detected: str
    top_features: str


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


def alert_count(prefix: str) -> int | None:
    for path in [RESULT_DIR / f"{prefix}-alerts.json", RESULT_DIR / f"{prefix}-dashboard.json"]:
        text = read_text(path)
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        counts = find_values(payload, "alert_count")
        for value in counts:
            if isinstance(value, int):
                return value
        alerts = find_values(payload, "alerts")
        for value in alerts:
            if isinstance(value, list):
                return len(value)
    return None


def feature_values(prefix: str) -> dict[str, list[float]]:
    values: dict[str, list[float]] = defaultdict(list)
    for suffix in ["collector.log", "analyzer.log"]:
        for obj in iter_json_objects(read_text(RESULT_DIR / f"{prefix}-{suffix}")):
            if not isinstance(obj, dict):
                continue
            feature_window = obj.get("feature_window")
            if not isinstance(feature_window, dict):
                continue
            raw_values = feature_window.get("values")
            if not isinstance(raw_values, dict):
                continue
            for feature in FEATURES:
                try:
                    values[feature].append(float(raw_values[feature]))
                except (KeyError, TypeError, ValueError):
                    continue
    return dict(values)


def top_features(prefix: str) -> str:
    values = feature_values(prefix)
    scored: list[tuple[float, str]] = []
    for feature, samples in values.items():
        if samples:
            scored.append((max(samples), feature))
    if not scored:
        return "n/a"
    scored.sort(reverse=True)
    return ", ".join(f"{name}={value:.2f}" for value, name in scored[:3])


def fmt_float(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def scenario_row(prefix: str) -> ScenarioRow:
    score_set = scores_for(prefix)
    scores = score_set.scores
    return ScenarioRow(
        scenario=prefix,
        alerts=alert_count(prefix),
        tetragon_lines=len([line for line in read_text(RESULT_DIR / f"{prefix}-tetragon-tail.jsonl").splitlines() if line.strip()]),
        fault_target_lines=len([line for line in read_text(RESULT_DIR / f"{prefix}-tetragon-fault-target.jsonl").splitlines() if line.strip()]),
        score_min=min(scores) if scores else None,
        score_mean=mean(scores) if scores else None,
        score_max=max(scores) if scores else None,
        detected="yes" if score_set.latest_workflow_verdict == "anomalous" or any(verdict == "anomalous" for verdict in score_set.verdicts) else "no",
        top_features=top_features(prefix),
    )


def write_csv(rows: list[ScenarioRow]) -> None:
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scenario",
                "alerts",
                "tetragon_lines",
                "fault_target_lines",
                "score_min",
                "score_mean",
                "score_max",
                "detected",
                "top_features",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.scenario,
                    "" if row.alerts is None else row.alerts,
                    row.tetragon_lines,
                    row.fault_target_lines,
                    fmt_float(row.score_min),
                    fmt_float(row.score_mean),
                    fmt_float(row.score_max),
                    row.detected,
                    row.top_features,
                ]
            )


def scenario_table(rows: list[ScenarioRow]) -> list[str]:
    lines = [
        "| Scenario | Alerts | Tetragon lines | fault-target lines | Score min | Score mean | Score max | Detected | Main feature changes |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.scenario,
                    str(row.alerts if row.alerts is not None else "unknown"),
                    str(row.tetragon_lines),
                    str(row.fault_target_lines),
                    fmt_float(row.score_min),
                    fmt_float(row.score_mean),
                    fmt_float(row.score_max),
                    row.detected,
                    row.top_features,
                ]
            )
            + " |"
        )
    return lines


def comparison_table() -> list[str]:
    return [
        "| Item | Prometheus + Grafana | eBPF/Tetragon + ML analyzer |",
        "| --- | --- | --- |",
        "| Detection target | Metric time series | Metric plus kernel event context |",
        "| Unit of judgment | Human dashboard inspection | Workload-level anomaly score and verdict |",
        "| Fault signal | CPU, memory, connection counters | process_exec, process_kprobe, tcp_connect, resource features |",
        "| Explainability | Panel changes require manual interpretation | Report includes feature window, score, verdict, and Tetragon evidence |",
        "| Automation | Alert rules and dashboards | API/UI reports with scenario-level detection summary |",
    ]


def main() -> int:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [scenario_row(scenario) for scenario in SCENARIOS]
    write_csv(rows)
    lines = [
        "# Step 16 Paper Result Tables",
        "",
        f"- Input directory: `{RESULT_DIR}`",
        f"- CSV output: `{CSV_PATH}`",
        "",
        "## Scenario Detection Table",
        "",
        *scenario_table(rows),
        "",
        "## Prometheus + Grafana Comparison",
        "",
        *comparison_table(),
        "",
        "## Result Interpretation Draft",
        "",
        "Step 16 shows that Tetragon event coverage is present for all four injected fault scenarios, while the analyzer converts the observed event/resource windows into anomaly scores and verdicts. The result table should be read together with the baseline calibration report because a contaminated baseline can inflate false-positive risk even when fault scenarios are detectable.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    print(f"wrote {CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
