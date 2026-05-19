#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

RESULT_DIR = Path("results/step16")
REPORT_PATH = RESULT_DIR / "threshold-analysis.md"
CSV_PATH = RESULT_DIR / "threshold-analysis.csv"
DEFAULT_THRESHOLDS = [0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
SCENARIOS = ["baseline", "exec-storm", "network-burst", "cpu-stress", "memory-pressure"]
FAULT_SCENARIOS = [scenario for scenario in SCENARIOS if scenario != "baseline"]


@dataclass(frozen=True)
class ScenarioScores:
    name: str
    scores: list[float]
    verdicts: list[str]
    latest_workflow_verdict: str | None

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


def scores_for(prefix: str) -> ScenarioScores:
    scores: list[float] = []
    verdicts: list[str] = []
    for suffix in ["collector.log", "analyzer.log"]:
        for obj in iter_json_objects(read_text(RESULT_DIR / f"{prefix}-{suffix}")):
            if not isinstance(obj, dict):
                continue
            if "score" not in obj or "verdict" not in obj:
                continue
            try:
                scores.append(float(obj["score"]))
            except (TypeError, ValueError):
                continue
            verdicts.append(str(obj["verdict"]))
    return ScenarioScores(prefix, scores, verdicts, workflow_latest_verdict(prefix))


def fmt_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def distribution_table(scenarios: list[ScenarioScores]) -> list[str]:
    lines = [
        "| Scenario | Expected | Samples | Min | Mean | Max | Analyzer anomalous samples | Workflow latest verdict |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
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
                    fmt_float(min(scores) if scores else None),
                    fmt_float(mean(scores) if scores else None),
                    fmt_float(max(scores) if scores else None),
                    str(anomalous),
                    scenario.latest_workflow_verdict or "unknown",
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
    contamination = baseline.latest_workflow_verdict == "anomalous"
    baseline_missing_scores = not baseline.scores
    if contamination:
        conclusion = "baseline workflow verdict is anomalous, so the existing baseline artifact is contaminated and must not be used as a clean normal distribution."
    elif baseline_missing_scores:
        conclusion = "baseline score samples are absent from the current artifact set; rerun Step 16 collection after clean baseline recapture before selecting a final threshold."
    else:
        conclusion = "baseline score samples are present; choose the lowest threshold with acceptable false-positive and false-negative rates."

    lines = [
        "# Step 16 Baseline and Threshold Analysis",
        "",
        f"- Input directory: `{RESULT_DIR}`",
        f"- CSV output: `{CSV_PATH}`",
        f"- Conclusion: {conclusion}",
        "",
        "## Score Distribution",
        "",
        *distribution_table(scenarios),
        "",
        "## Threshold Candidates",
        "",
        *threshold_table(rows),
        "",
        "## Calibration Rule",
        "",
        "- Treat `baseline` as the only normal class and all fault scenarios as fault class.",
        "- `score >= threshold` is counted as anomalous.",
        "- Baseline false positives measure clean-normal over-alerting.",
        "- Fault false negatives measure missed fault samples.",
        "- Do not finalize a threshold while baseline is contaminated or lacks score samples.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    print(f"wrote {CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
