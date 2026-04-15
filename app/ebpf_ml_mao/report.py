from __future__ import annotations

import json
from pathlib import Path

from .models import AnalysisReport, BatchAnalysisReport



def write_json_report(report: AnalysisReport, output_path: str | Path) -> None:
    Path(output_path).write_text(
        json.dumps(report.to_dict(), indent=2),
        encoding="utf-8",
    )



def write_markdown_report(report: AnalysisReport, output_path: str | Path) -> None:
    data = report.to_dict()
    lines = [
        "# MVP Analysis Report",
        "",
        f"- Verdict: `{data['verdict']}`",
        f"- Score: `{data['score']}`",
        f"- Confidence: `{data['confidence']}`",
        f"- Workload: `{data['feature_window']['workload']}`",
        f"- Window: `{data['feature_window']['window_start']}` -> `{data['feature_window']['window_end']}`",
        "",
        "## Features",
        "",
    ]
    for key, value in data["feature_window"]["values"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Agents", ""])
    for agent in data["agents"]:
        lines.append(f"- {agent['name']}: {agent['summary']}")

    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")



def write_batch_json_report(batch_report: BatchAnalysisReport, output_path: str | Path) -> None:
    Path(output_path).write_text(
        json.dumps(batch_report.to_dict(), indent=2),
        encoding="utf-8",
    )



def write_batch_markdown_report(
    batch_report: BatchAnalysisReport,
    output_path: str | Path,
) -> None:
    lines = [
        "# MVP Batch Analysis Report",
        "",
        f"- Report count: `{len(batch_report.reports)}`",
        "",
        "## Reports",
        "",
    ]
    for index, report in enumerate(batch_report.reports, start=1):
        data = report.to_dict()
        lines.extend(
            [
                f"### Report {index}",
                f"- Workload: `{data['feature_window']['workload']}`",
                f"- Window: `{data['feature_window']['window_start']}` -> `{data['feature_window']['window_end']}`",
                f"- Verdict: `{data['verdict']}`",
                f"- Score: `{data['score']}`",
                f"- Confidence: `{data['confidence']}`",
                "",
            ]
        )
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
