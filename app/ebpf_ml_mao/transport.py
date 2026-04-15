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


def spool_report(spool_dir: str | Path, payload: dict, *, ttl_seconds: int = 3600) -> Path:
    spool = Path(spool_dir)
    spool.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    envelope = {
        "queued_at": ts,
        "expires_at": ts + max(ttl_seconds, 0),
        "payload": payload,
    }
    path = spool / f"{int(time.time() * 1000)}-{payload.get('node_name', 'node')}.json"
    path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return path


def _quarantine_file(path: Path, quarantine_dir: Path) -> str:
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    target = quarantine_dir / path.name
    path.replace(target)
    return str(target)


def spool_status(spool_dir: str | Path, *, ttl_seconds: int = 3600) -> dict:
    spool = Path(spool_dir)
    spool.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    files = sorted(spool.glob("*.json"))
    expired = 0
    for path in files:
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            expires_at = int(envelope.get("expires_at", 0))
            if expires_at and expires_at <= now:
                expired += 1
        except Exception:
            expired += 1
    return {"count": len(files), "expired_count": expired, "ttl_seconds": ttl_seconds}


def prune_spool(spool_dir: str | Path, *, ttl_seconds: int = 3600, quarantine_dir: str | Path | None = None) -> dict:
    spool = Path(spool_dir)
    spool.mkdir(parents=True, exist_ok=True)
    quarantine = Path(quarantine_dir or spool / "quarantine")
    now = int(time.time())
    removed = 0
    quarantined: list[str] = []
    for path in sorted(spool.glob("*.json")):
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            expires_at = int(envelope.get("expires_at", 0))
            if expires_at and expires_at <= now:
                path.unlink()
                removed += 1
        except Exception:
            quarantined.append(_quarantine_file(path, quarantine))
    return {"removed": removed, "quarantined": quarantined}


def ship_report(api_url: str, *, node_name: str, report_path: str | Path, spool_dir: str | Path, timeout: float = 5.0, shared_token: str = "", retries: int = 3, phase: str = "phase3", spool_ttl_seconds: int = 3600) -> dict:
    payload = build_report_payload(node_name, report_path, phase=phase)
    try:
        response = _post_payload(api_url, payload, timeout=timeout, shared_token=shared_token, retries=retries)
        response["spooled"] = False
        return response
    except ValueError:
        path = spool_report(spool_dir, payload, ttl_seconds=spool_ttl_seconds)
        return {"status": "spooled", "path": str(path), "spooled": True}


def drain_spool(api_url: str, *, spool_dir: str | Path, timeout: float = 5.0, shared_token: str = "", retries: int = 3, ttl_seconds: int = 3600, quarantine_dir: str | Path | None = None, max_items: int | None = None) -> dict:
    spool = Path(spool_dir)
    spool.mkdir(parents=True, exist_ok=True)
    quarantine = Path(quarantine_dir or spool / "quarantine")
    sent = 0
    failed = 0
    expired = 0
    quarantined: list[str] = []
    remaining: list[str] = []
    processed = 0
    now = int(time.time())
    for path in sorted(spool.glob("*.json"), key=lambda p: p.stat().st_mtime):
        if max_items is not None and processed >= max_items:
            remaining.append(str(path))
            continue
        processed += 1
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            expires_at = int(envelope.get("expires_at", 0))
            payload = envelope["payload"]
        except Exception:
            quarantined.append(_quarantine_file(path, quarantine))
            continue
        if expires_at and expires_at <= now:
            path.unlink()
            expired += 1
            continue
        try:
            _post_payload(api_url, payload, timeout=timeout, shared_token=shared_token, retries=retries)
            path.unlink()
            sent += 1
        except ValueError:
            failed += 1
            remaining.append(str(path))
    return {"sent": sent, "failed": failed, "expired": expired, "quarantined": quarantined, "remaining": remaining}
