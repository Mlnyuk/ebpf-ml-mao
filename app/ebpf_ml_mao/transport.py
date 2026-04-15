from __future__ import annotations

import json
import time
from pathlib import Path
from urllib import error, request


def post_report(
    api_url: str,
    *,
    node_name: str,
    report_path: str | Path,
    timeout: float = 5.0,
    shared_token: str = "",
    retries: int = 3,
    phase: str = "phase3",
) -> dict:
    path = Path(report_path)
    payload = {
        "node_name": node_name,
        "phase": phase,
        "report_name": path.name,
        "report": json.loads(path.read_text(encoding="utf-8")),
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if shared_token:
        headers["Authorization"] = f"Bearer {shared_token}"

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        req = request.Request(
            f"{api_url.rstrip('/')}/v1/reports",
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (error.URLError, error.HTTPError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(0.2 * attempt)
    raise ValueError(f"failed to POST report to analyzer API: {api_url}") from last_error
