from __future__ import annotations

import json
from pathlib import Path

from .models import AnalysisReport


def write_json_report(report: AnalysisReport, output_path: str | Path) -> None:
    Path(output_path).write_text(
        json.dumps(report.to_dict(), indent=2),
        encoding="utf-8",
    )


def write_markdown_report(report: AnalysisReport, output_path: str | Path) -> None:
    data = report.to_dict()
    lines = [
        "# Phase 1 Analysis Report",
        "",
        f"- Verdict: `{data['verdict']}`",
        f"- Score: `{data['score']}`",
        f"- Confidence: `{data['confidence']}`",
        f"- Workload: `{data['feature_window']['workload']}`",
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

