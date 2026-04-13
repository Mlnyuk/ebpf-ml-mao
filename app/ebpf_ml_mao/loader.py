from __future__ import annotations

import json
from pathlib import Path


def load_jsonl(path: str | Path) -> list[dict]:
    """Load newline-delimited JSON records from disk."""
    path = Path(path)
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def load_json(path: str | Path) -> dict | list:
    """Load a JSON document from disk."""
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8"))
