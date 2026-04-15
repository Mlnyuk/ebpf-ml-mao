from __future__ import annotations

import json
import time
from pathlib import Path
from urllib import error, request


def build_report_payload(node_name: str, report_path: str | Path, *, phase: str = "phase3") -> dict:
    path = Path(report_path)
    return {
        "node_name": node_name,
        "phase": phase,
        "report_name": path.name,
        "report": json.loads(path.read_text(encoding="utf-8")),
    }


def _post_payload(api_url: str, payload: dict, *, timeout: float = 5.0, shared_token: str = "", retries: int = 3) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if shared_token:
        headers["Authorization"] = f"Bearer {shared_token}"

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        req = request.Request(f"{api_url.rstrip('/')}/v1/reports", data=data, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (error.URLError, error.HTTPError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(0.2 * attempt)
    raise ValueError(f"failed to POST report to analyzer API: {api_url}") from last_error


def post_report(api_url: str, *, node_name: str, report_path: str | Path, timeout: float = 5.0, shared_token: str = "", retries: int = 3, phase: str = "phase3") -> dict:
    payload = build_report_payload(node_name, report_path, phase=phase)
    return _post_payload(api_url, payload, timeout=timeout, shared_token=shared_token, retries=retries)


def spool_report(spool_dir: str | Path, payload: dict) -> Path:
    spool = Path(spool_dir)
    spool.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    path = spool / f"{ts}-{payload.get('node_name', 'node')}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def ship_report(api_url: str, *, node_name: str, report_path: str | Path, spool_dir: str | Path, timeout: float = 5.0, shared_token: str = "", retries: int = 3, phase: str = "phase3") -> dict:
    payload = build_report_payload(node_name, report_path, phase=phase)
    try:
        response = _post_payload(api_url, payload, timeout=timeout, shared_token=shared_token, retries=retries)
        response["spooled"] = False
        return response
    except ValueError:
        path = spool_report(spool_dir, payload)
        return {"status": "spooled", "path": str(path), "spooled": True}


def drain_spool(api_url: str, *, spool_dir: str | Path, timeout: float = 5.0, shared_token: str = "", retries: int = 3) -> dict:
    spool = Path(spool_dir)
    spool.mkdir(parents=True, exist_ok=True)
    sent = 0
    failed = 0
    remaining: list[str] = []
    for path in sorted(spool.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        try:
            _post_payload(api_url, payload, timeout=timeout, shared_token=shared_token, retries=retries)
            path.unlink()
            sent += 1
        except ValueError:
            failed += 1
            remaining.append(str(path))
    return {"sent": sent, "failed": failed, "remaining": remaining}
