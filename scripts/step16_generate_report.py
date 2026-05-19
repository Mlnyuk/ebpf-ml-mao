#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESULT_DIR = Path("results/step16")
REPORT_PATH = RESULT_DIR / "experiment-report.md"
SCENARIOS = ["exec-storm", "network-burst", "cpu-stress", "memory-pressure"]
KINDS = ["dashboard", "alerts", "workflow"]
KEYWORDS = [
    "anomalous",
    "score",
    "exec",
    "network",
    "cpu",
    "memory",
    "process_exec",
    "process_kprobe",
    "tcp_connect",
    "fault-target",
]


def read_text(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, ""
    try:
        return True, path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return True, f"read error: {exc}"


def read_json(path: Path) -> tuple[str, Any | None, str]:
    exists, text = read_text(path)
    if not exists:
        return "missing", None, ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return "malformed", None, f"{text}\n\nJSON error: {exc}"
    if isinstance(payload, dict) and payload.get("status") == "error":
        return "error", payload, text
    return "ok", payload, text


def find_key_values(value: Any, target_key: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == target_key:
                found.append(child)
            found.extend(find_key_values(child, target_key))
    elif isinstance(value, list):
        for child in value:
            found.extend(find_key_values(child, target_key))
    return found


def alert_count(payload: Any) -> int | None:
    if not isinstance(payload, (dict, list)):
        return None
    summary_counts = find_key_values(payload, "alert_count")
    for item in summary_counts:
        if isinstance(item, int):
            return item
    alerts = find_key_values(payload, "alerts")
    for item in alerts:
        if isinstance(item, list):
            return len(item)
    return None


def indicators_for(prefix: str) -> dict[str, Any]:
    texts: list[str] = []
    statuses: dict[str, str] = {}
    parsed_payloads: list[Any] = []
    for kind in KINDS:
        status, payload, text = read_json(RESULT_DIR / f"{prefix}-{kind}.json")
        statuses[kind] = status
        if text:
            texts.append(text)
        if payload is not None:
            parsed_payloads.append(payload)
            texts.append(json.dumps(payload, sort_keys=True))

    tetragon_exists, tetragon_text = read_text(RESULT_DIR / f"{prefix}-tetragon-tail.jsonl")
    statuses["tetragon-tail"] = "ok" if tetragon_exists and tetragon_text else "missing"
    if tetragon_text:
        texts.append(tetragon_text)

    target_exists, target_text = read_text(RESULT_DIR / f"{prefix}-tetragon-fault-target.jsonl")
    statuses["tetragon-fault-target"] = "ok" if target_exists and target_text else "missing"
    if target_text:
        texts.append(target_text)

    combined = "\n".join(texts).lower()
    count = None
    for payload in parsed_payloads:
        count = alert_count(payload)
        if count is not None:
            break

    return {
        "statuses": statuses,
        "alert_count": count,
        "tetragon_lines": len([line for line in tetragon_text.splitlines() if line.strip()]) if tetragon_text else 0,
        "tetragon_fault_target_lines": len([line for line in target_text.splitlines() if line.strip()]) if target_text else 0,
        "keywords": {keyword: (keyword in combined) for keyword in KEYWORDS},
    }


def status_label(statuses: dict[str, str]) -> str:
    if all(status == "ok" for status in statuses.values()):
        return "complete"
    if any(status == "ok" for status in statuses.values()):
        return "partial"
    if any(status == "error" for status in statuses.values()):
        return "error"
    return "missing"


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def file_inventory() -> list[str]:
    expected = [RESULT_DIR / f"baseline-{kind}.json" for kind in KINDS]
    expected.append(RESULT_DIR / "baseline-tetragon-tail.jsonl")
    expected.append(RESULT_DIR / "baseline-tetragon-fault-target.jsonl")
    expected.append(RESULT_DIR / "baseline-analyzer.log")
    expected.append(RESULT_DIR / "baseline-collector.log")
    for scenario in SCENARIOS:
        expected.extend(RESULT_DIR / f"{scenario}-{kind}.json" for kind in KINDS)
        expected.append(RESULT_DIR / f"{scenario}-tetragon-tail.jsonl")
        expected.append(RESULT_DIR / f"{scenario}-tetragon-fault-target.jsonl")
        expected.append(RESULT_DIR / f"{scenario}-analyzer.log")
        expected.append(RESULT_DIR / f"{scenario}-collector.log")
        if scenario in {"cpu-stress", "memory-pressure"}:
            expected.append(RESULT_DIR / f"{scenario}-kubectl-top.txt")

    lines = []
    for path in expected:
        state = "found" if path.exists() else "missing"
        size = path.stat().st_size if path.exists() else 0
        lines.append(f"- `{path}`: {state}, {size} bytes")
    return lines


def section_for(prefix: str, title: str) -> list[str]:
    indicators = indicators_for(prefix)
    lines = [
        f"## {title}",
        "",
        f"- Snapshot status: `{status_label(indicators['statuses'])}`",
        f"- Alerts: `{indicators['alert_count'] if indicators['alert_count'] is not None else 'unknown'}`",
        f"- Tetragon tail lines: `{indicators['tetragon_lines']}`",
        f"- Tetragon fault-target lines: `{indicators['tetragon_fault_target_lines']}`",
    ]
    for kind, status in indicators["statuses"].items():
        suffix = "jsonl" if kind.startswith("tetragon-") else "json"
        lines.append(f"- `{prefix}-{kind}.{suffix}`: `{status}`")
    lines.extend(
        [
            f"- Contains `anomalous`: {yes_no(indicators['keywords']['anomalous'])}",
            f"- Contains `score`: {yes_no(indicators['keywords']['score'])}",
            f"- Contains `exec`: {yes_no(indicators['keywords']['exec'])}",
            f"- Contains `network`: {yes_no(indicators['keywords']['network'])}",
            f"- Contains `cpu`: {yes_no(indicators['keywords']['cpu'])}",
            f"- Contains `memory`: {yes_no(indicators['keywords']['memory'])}",
            f"- Contains `process_exec`: {yes_no(indicators['keywords']['process_exec'])}",
            f"- Contains `process_kprobe`: {yes_no(indicators['keywords']['process_kprobe'])}",
            f"- Contains `tcp_connect`: {yes_no(indicators['keywords']['tcp_connect'])}",
            f"- Contains `fault-target`: {yes_no(indicators['keywords']['fault-target'])}",
            "",
        ]
    )
    return lines


def scenario_table() -> list[str]:
    lines = [
        "| Scenario | Snapshot status | Alerts | Tetragon lines | anomalous | score | process_exec | process_kprobe | tcp_connect | fault-target |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for scenario in SCENARIOS:
        indicators = indicators_for(scenario)
        keywords = indicators["keywords"]
        alerts = indicators["alert_count"] if indicators["alert_count"] is not None else "unknown"
        lines.append(
            "| "
            + " | ".join(
                [
                    scenario,
                    status_label(indicators["statuses"]),
                    str(alerts),
                    str(indicators["tetragon_lines"]),
                    yes_no(keywords["anomalous"]),
                    yes_no(keywords["score"]),
                    yes_no(keywords["process_exec"]),
                    yes_no(keywords["process_kprobe"]),
                    yes_no(keywords["tcp_connect"]),
                    yes_no(keywords["fault-target"]),
                ]
            )
            + " |"
        )
    return lines


def main() -> int:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Step 16 Fault Scenario Experiment Report",
        "",
        f"- Generated at: `{timestamp}`",
        f"- Result directory: `{RESULT_DIR}`",
        "",
        "## Input Files",
        "",
        *file_inventory(),
        "",
        "## Scenario Summary",
        "",
        *scenario_table(),
        "",
        *section_for("baseline", "Baseline"),
    ]
    for scenario in SCENARIOS:
        lines.extend(section_for(scenario, scenario))

    lines.extend(
        [
            "## Notes",
            "",
            "- Absence of an anomaly does not necessarily mean pipeline failure. It may indicate that thresholds, feature calibration, scrape timing, or Tetragon/Prometheus coverage need adjustment.",
            "- This report is generated from available files only. Missing or malformed JSON is reported instead of stopping report generation.",
            "- This does not introduce advanced ML, modify eBPF programs, or make the analyzer production-HA.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
