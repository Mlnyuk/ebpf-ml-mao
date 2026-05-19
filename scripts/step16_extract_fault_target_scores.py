#!/usr/bin/env python3
"""Parse analyzer ingest reports streamed via stdin and emit fault-target scores as JSONL.

Used by scripts/step16_collect_results.sh after a `kubectl exec ... cat *.json`
to capture per-window scores for the analyzer target workload directly from the
PVC, instead of relying on log tails that may scroll past the fault-target
scoring entries.
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    text = sys.stdin.read()
    decoder = json.JSONDecoder()
    idx = 0
    records: list[dict] = []
    while idx < len(text):
        while idx < len(text) and text[idx] not in "{[":
            idx += 1
        if idx >= len(text):
            break
        try:
            value, end = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            idx += 1
            continue
        if isinstance(value, dict) and "report" in value:
            report = value["report"]
            window = report.get("feature_window", {}) if isinstance(report, dict) else {}
            if isinstance(window, dict) and window.get("workload") == "fault-target":
                records.append(
                    {
                        "workload": window.get("workload"),
                        "window_start": window.get("window_start"),
                        "window_end": window.get("window_end"),
                        "score": report.get("score"),
                        "verdict": report.get("verdict"),
                        "values": window.get("values", {}),
                        "scenario": "unknown",
                    }
                )
        idx += end
    for rec in sorted(records, key=lambda x: x.get("window_start") or 0):
        print(json.dumps(rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
