from __future__ import annotations

import json
import re
import time
import urllib.request
from collections import deque
from pathlib import Path

from .adapters import adapt_prometheus_snapshot
from .models import NormalizedEvent


def tail_jsonl(path: str | Path, max_lines: int = 100) -> list[dict]:
    """Read the last non-empty JSONL lines from a local log file."""
    path = Path(path)
    tail: deque[str] = deque(maxlen=max_lines)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            tail.append(line)
    return [json.loads(line) for line in tail]


def scrape_prometheus_text(url: str, timeout: float = 5.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = response.read()
    return payload.decode("utf-8")


def _parse_labels(raw_labels: str) -> dict[str, str]:
    """Parse Prometheus label string, handling quoted values that contain commas."""
    if not raw_labels:
        return {}
    return {
        m.group(1): m.group(2).replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n")
        for m in re.finditer(r'(\w+)="((?:[^"\\]|\\.)*)"', raw_labels)
    }


def parse_prometheus_text(text: str, scraped_at: float | None = None) -> dict:
    timestamp = scraped_at if scraped_at is not None else time.time()
    series: list[dict] = []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        metric_and_labels, _, remainder = line.partition(" ")
        parts = remainder.split()
        if not parts:
            continue
        value = float(parts[0])
        sample_ts: float | str = timestamp
        if len(parts) > 1:
            sample_ts = float(parts[1])

        if "{" in metric_and_labels:
            metric, raw_labels = metric_and_labels.split("{", 1)
            raw_labels = raw_labels.rstrip("}")
            labels = _parse_labels(raw_labels)
        else:
            metric = metric_and_labels
            labels = {}

        series.append(
            {
                "metric": metric,
                "labels": labels,
                "value": value,
                "timestamp": sample_ts,
            }
        )

    return {"timestamp": timestamp, "series": series}


def scrape_prometheus_snapshot(url: str, timeout: float = 5.0) -> list[NormalizedEvent]:
    scraped_at = time.time()
    text = scrape_prometheus_text(url, timeout=timeout)
    snapshot = parse_prometheus_text(text, scraped_at=scraped_at)
    return adapt_prometheus_snapshot(snapshot)
