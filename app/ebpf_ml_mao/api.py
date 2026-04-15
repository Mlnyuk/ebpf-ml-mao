from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any

from .models import AlertRecord, DashboardSnapshot
from .registry import load_registry, registry_status
from .transport import enqueue_postprocess, queue_status, spool_status


def _payload_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _index_path(ingest_dir: Path) -> Path:
    return ingest_dir / "index.json"


def _workflow_path(ingest_dir: Path) -> Path:
    return ingest_dir / "workflow-summary.json"


def _corrupt_index_path(ingest_dir: Path) -> Path:
    return ingest_dir / f"index-corrupt-{int(time.time())}.json"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def rebuild_ingest_index(ingest_dir: str | Path) -> dict[str, Any]:
    base = Path(ingest_dir)
    base.mkdir(parents=True, exist_ok=True)
    items: dict[str, dict[str, Any]] = {}
    for path in sorted(base.rglob("*.json")):
        if path.name in {"index.json", "workflow-summary.json"} or path.name.startswith("index-corrupt-"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("report"), dict):
            continue
        digest = _payload_digest(payload)
        report = payload.get("report", {})
        items[digest] = {
            "node_name": str(payload.get("node_name", path.parent.name)),
            "report_name": str(payload.get("report_name", path.name)),
            "path": str(path),
            "phase": str(payload.get("phase", "unknown")),
            "verdict": report.get("verdict", "unknown") if isinstance(report, dict) else "unknown",
        }
    index = {
        "received_count": len(items),
        "unique_count": len(items),
        "duplicates_count": 0,
        "items": items,
        "repaired_at": int(time.time()),
    }
    _save_ingest_index(base, index)
    _save_workflow_summary(base, index)
    return index


def load_ingest_index(ingest_dir: str | Path, *, repair: bool = False) -> dict[str, Any]:
    base = Path(ingest_dir)
    path = _index_path(base)
    if not path.exists():
        return {
            "received_count": 0,
            "unique_count": 0,
            "duplicates_count": 0,
            "items": {},
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        if not repair:
            raise ValueError(f"ingest index is not valid JSON: {path}") from exc
        path.replace(_corrupt_index_path(base))
        return rebuild_ingest_index(base)


def load_workflow_summary(ingest_dir: str | Path, *, repair: bool = False) -> dict[str, Any]:
    base = Path(ingest_dir)
    path = _workflow_path(base)
    if not path.exists():
        index = load_ingest_index(base, repair=repair)
        return _save_workflow_summary(base, index)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        if not repair:
            raise ValueError(f"workflow summary is not valid JSON: {path}") from exc
        index = load_ingest_index(base, repair=True)
        return _save_workflow_summary(base, index)


def _save_ingest_index(ingest_dir: Path, index: dict[str, Any]) -> None:
    _atomic_write_json(_index_path(ingest_dir), index)


def _save_workflow_summary(ingest_dir: Path, index: dict[str, Any]) -> dict[str, Any]:
    items = list(index.get("items", {}).values())
    verdicts: dict[str, int] = {}
    phases: dict[str, int] = {}
    for item in items:
        verdict = item.get("verdict", "unknown")
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
        phase = item.get("phase", "unknown")
        phases[phase] = phases.get(phase, 0) + 1
    workflow = {
        "received_count": index.get("received_count", 0),
        "unique_count": index.get("unique_count", 0),
        "duplicates_count": index.get("duplicates_count", 0),
        "nodes": sorted({item["node_name"] for item in items}),
        "verdicts": verdicts,
        "phases": phases,
        "latest_verdict": items[-1].get("verdict", "unknown") if items else None,
    }
    _atomic_write_json(_workflow_path(ingest_dir), workflow)
    return workflow


def store_ingest_payload(
    ingest_dir: str | Path,
    payload: dict[str, Any],
    *,
    queue_dir: str | Path | None = None,
    queue_ttl_seconds: int = 86400,
) -> dict[str, Any]:
    base = Path(ingest_dir)
    base.mkdir(parents=True, exist_ok=True)
    queue_base = Path(queue_dir) if queue_dir is not None else base / "postprocess-queue"
    index = load_ingest_index(base, repair=True)
    digest = _payload_digest(payload)
    index["received_count"] = int(index.get("received_count", 0)) + 1
    node_name = str(payload.get("node_name", "unknown-node"))
    report_name = str(payload.get("report_name", "report.json"))
    report = payload.get("report", {})
    verdict = report.get("verdict", "unknown") if isinstance(report, dict) else "unknown"

    existing = index["items"].get(digest)
    if existing is not None:
        index["duplicates_count"] = int(index.get("duplicates_count", 0)) + 1
        _save_ingest_index(base, index)
        workflow = _save_workflow_summary(base, index)
        return {
            "status": "duplicate",
            "digest": digest,
            "path": existing["path"],
            "workflow": workflow,
            "queue": {"status": "skipped", "reason": "duplicate"},
        }

    target_dir = base / node_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{digest[:12]}-{report_name}"
    _atomic_write_json(target_path, payload)
    index["items"][digest] = {
        "node_name": node_name,
        "report_name": report_name,
        "path": str(target_path),
        "phase": str(payload.get("phase", "unknown")),
        "verdict": verdict,
    }
    index["unique_count"] = len(index["items"])
    _save_ingest_index(base, index)
    workflow = _save_workflow_summary(base, index)
    queue_payload = {
        "digest": digest,
        "node_name": node_name,
        "report_name": report_name,
        "stored_path": str(target_path),
        "phase": str(payload.get("phase", "unknown")),
        "verdict": verdict,
        "received_at": int(time.time()),
    }
    queued_path = enqueue_postprocess(queue_base, queue_payload, ttl_seconds=queue_ttl_seconds)
    return {
        "status": "stored",
        "digest": digest,
        "path": str(target_path),
        "workflow": workflow,
        "queue": {"status": "queued", "path": str(queued_path)},
    }


def _alert_state(alerts: list[AlertRecord]) -> str:
    severities = {alert.severity for alert in alerts}
    if "critical" in severities:
        return "critical"
    if "warning" in severities:
        return "warning"
    return "ok"


def _build_alerts(
    registry: dict[str, Any],
    ingest: dict[str, Any],
    workflow: dict[str, Any],
    queue: dict[str, Any],
    spool: dict[str, Any],
    *,
    queue_alert_threshold: int,
    spool_alert_threshold: int,
    duplicate_ratio_threshold: float,
) -> list[AlertRecord]:
    alerts: list[AlertRecord] = []
    if registry.get("active_model_id") is None:
        alerts.append(AlertRecord(
            name="active_model",
            severity="critical",
            message="registry has no active model",
            value="missing",
            threshold="configured",
        ))
    if int(registry.get("missing_artifact_count", 0)) > 0:
        alerts.append(AlertRecord(
            name="missing_model_artifact",
            severity="critical",
            message="registry references model artifacts that do not exist",
            value=int(registry.get("missing_artifact_count", 0)),
            threshold=0,
        ))
    queue_count = int(queue.get("count", 0))
    if queue_count > queue_alert_threshold:
        alerts.append(AlertRecord(
            name="queue_backlog",
            severity="warning",
            message="postprocess queue backlog exceeded threshold",
            value=queue_count,
            threshold=queue_alert_threshold,
        ))
    spool_count = int(spool.get("count", 0))
    if spool_count > spool_alert_threshold:
        alerts.append(AlertRecord(
            name="spool_backlog",
            severity="warning",
            message="collector spool backlog exceeded threshold",
            value=spool_count,
            threshold=spool_alert_threshold,
        ))
    received_count = int(ingest.get("received_count", 0))
    duplicate_count = int(ingest.get("duplicates_count", 0))
    duplicate_ratio = (duplicate_count / received_count) if received_count else 0.0
    if duplicate_ratio > duplicate_ratio_threshold:
        alerts.append(AlertRecord(
            name="duplicate_ratio",
            severity="warning",
            message="ingest duplicate ratio exceeded threshold",
            value=round(duplicate_ratio, 4),
            threshold=duplicate_ratio_threshold,
        ))
    if int(queue.get("quarantined_count", 0)) > 0:
        alerts.append(AlertRecord(
            name="queue_quarantine",
            severity="warning",
            message="corrupt queue items were quarantined",
            value=int(queue.get("quarantined_count", 0)),
            threshold=0,
        ))
    if int(spool.get("quarantined_count", 0)) > 0:
        alerts.append(AlertRecord(
            name="spool_quarantine",
            severity="warning",
            message="corrupt spool items were quarantined",
            value=int(spool.get("quarantined_count", 0)),
            threshold=0,
        ))
    if workflow.get("latest_verdict") == "anomalous":
        alerts.append(AlertRecord(
            name="latest_verdict",
            severity="warning",
            message="latest workflow verdict is anomalous",
            value="anomalous",
            threshold="normal",
        ))
    return alerts


def build_dashboard_snapshot(
    registry_path: str | Path,
    ingest_dir: str | Path,
    *,
    collector_spool_dir: str | Path | None = None,
    postprocess_queue_dir: str | Path | None = None,
    spool_ttl_seconds: int = 3600,
    queue_ttl_seconds: int = 86400,
    queue_alert_threshold: int = 20,
    spool_alert_threshold: int = 10,
    duplicate_ratio_threshold: float = 0.25,
) -> dict[str, Any]:
    registry = registry_status(registry_path)
    ingest = load_ingest_index(ingest_dir, repair=True)
    workflow = load_workflow_summary(ingest_dir, repair=True)
    queue_dir = Path(postprocess_queue_dir) if postprocess_queue_dir else Path(ingest_dir) / "postprocess-queue"
    queue = queue_status(queue_dir, ttl_seconds=queue_ttl_seconds)
    if collector_spool_dir:
        spool = spool_status(collector_spool_dir, ttl_seconds=spool_ttl_seconds)
    else:
        spool = {
            "count": 0,
            "expired_count": 0,
            "ttl_seconds": spool_ttl_seconds,
            "oldest_age_seconds": None,
            "quarantined_count": 0,
            "available": False,
        }
    alerts = _build_alerts(
        registry,
        ingest,
        workflow,
        queue,
        spool,
        queue_alert_threshold=queue_alert_threshold,
        spool_alert_threshold=spool_alert_threshold,
        duplicate_ratio_threshold=duplicate_ratio_threshold,
    )
    state = _alert_state(alerts)
    snapshot = DashboardSnapshot(
        component="analyzer",
        timestamp=int(time.time()),
        summary={
            "state": state,
            "alert_count": len(alerts),
            "warning_count": sum(1 for alert in alerts if alert.severity == "warning"),
            "critical_count": sum(1 for alert in alerts if alert.severity == "critical"),
            "latest_verdict": workflow.get("latest_verdict"),
        },
        counters={
            "received_count": ingest.get("received_count", 0),
            "unique_count": ingest.get("unique_count", 0),
            "duplicates_count": ingest.get("duplicates_count", 0),
            "queue_count": queue.get("count", 0),
            "spool_count": spool.get("count", 0),
        },
        registry=registry,
        ingest={
            "received_count": ingest.get("received_count", 0),
            "unique_count": ingest.get("unique_count", 0),
            "duplicates_count": ingest.get("duplicates_count", 0),
            "repaired_at": ingest.get("repaired_at"),
        },
        workflow=workflow,
        queue=queue,
        spool=spool,
        alerts=alerts,
    )
    return snapshot.to_dict()


def _ui_asset(name: str) -> bytes:
    return resources.files("ebpf_ml_mao.ui").joinpath(name).read_bytes()


def _ui_text(name: str) -> str:
    return resources.files("ebpf_ml_mao.ui").joinpath(name).read_text(encoding="utf-8")


class AnalyzerAPIHandler(BaseHTTPRequestHandler):
    server_version = "ebpf-ml-mao/step15"

    def _bytes_response(self, status: int, body: bytes, *, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_response(self, status: int, payload: dict[str, Any]) -> None:
        self._bytes_response(status, json.dumps(payload, indent=2).encode("utf-8"), content_type="application/json")

    def _text_response(self, status: int, body: str, *, content_type: str = "text/html; charset=utf-8") -> None:
        self._bytes_response(status, body.encode("utf-8"), content_type=content_type)

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("request body is not valid JSON") from exc

    def _authorized(self) -> bool:
        shared_token = getattr(self.server, "shared_token", "")  # type: ignore[attr-defined]
        if not shared_token:
            return True
        return self.headers.get("Authorization", "") == f"Bearer {shared_token}"

    @property
    def registry_path(self) -> Path:
        return Path(self.server.registry_path)  # type: ignore[attr-defined]

    @property
    def ingest_dir(self) -> Path:
        return Path(self.server.ingest_dir)  # type: ignore[attr-defined]

    @property
    def collector_spool_dir(self) -> str:
        return str(getattr(self.server, "collector_spool_dir", ""))  # type: ignore[attr-defined]

    @property
    def postprocess_queue_dir(self) -> Path:
        return Path(self.server.postprocess_queue_dir)  # type: ignore[attr-defined]

    @property
    def spool_ttl_seconds(self) -> int:
        return int(getattr(self.server, "spool_ttl_seconds", 3600))  # type: ignore[attr-defined]

    @property
    def queue_ttl_seconds(self) -> int:
        return int(getattr(self.server, "queue_ttl_seconds", 86400))  # type: ignore[attr-defined]

    @property
    def queue_alert_threshold(self) -> int:
        return int(getattr(self.server, "queue_alert_threshold", 20))  # type: ignore[attr-defined]

    @property
    def spool_alert_threshold(self) -> int:
        return int(getattr(self.server, "spool_alert_threshold", 10))  # type: ignore[attr-defined]

    @property
    def duplicate_ratio_threshold(self) -> float:
        return float(getattr(self.server, "duplicate_ratio_threshold", 0.25))  # type: ignore[attr-defined]

    def _dashboard(self) -> dict[str, Any]:
        return build_dashboard_snapshot(
            self.registry_path,
            self.ingest_dir,
            collector_spool_dir=self.collector_spool_dir,
            postprocess_queue_dir=self.postprocess_queue_dir,
            spool_ttl_seconds=self.spool_ttl_seconds,
            queue_ttl_seconds=self.queue_ttl_seconds,
            queue_alert_threshold=self.queue_alert_threshold,
            spool_alert_threshold=self.spool_alert_threshold,
            duplicate_ratio_threshold=self.duplicate_ratio_threshold,
        )

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/ui"}:
            self._text_response(HTTPStatus.OK, _ui_text("dashboard.html"))
            return
        if self.path.startswith("/assets/"):
            name = self.path.removeprefix("/assets/")
            if name not in {"dashboard.css", "dashboard.js"}:
                self._json_response(HTTPStatus.NOT_FOUND, {"status": "error", "error": "not found"})
                return
            body = _ui_asset(name)
            content_type, _ = mimetypes.guess_type(name)
            self._bytes_response(HTTPStatus.OK, body, content_type=content_type or "application/octet-stream")
            return
        if self.path == "/healthz":
            self._json_response(HTTPStatus.OK, {"status": "ok", "component": "analyzer"})
            return
        if self.path == "/readyz":
            try:
                dashboard = self._dashboard()
            except ValueError as exc:
                self._json_response(HTTPStatus.SERVICE_UNAVAILABLE, {"status": "error", "error": str(exc)})
                return
            if dashboard["summary"]["state"] == "critical":
                self._json_response(HTTPStatus.SERVICE_UNAVAILABLE, dashboard)
                return
            self._json_response(HTTPStatus.OK, dashboard)
            return
        if self.path == "/v1/status":
            try:
                payload = self._dashboard()
            except ValueError as exc:
                self._json_response(HTTPStatus.BAD_REQUEST, {"status": "error", "error": str(exc)})
                return
            self._json_response(HTTPStatus.OK, payload)
            return
        if self.path == "/v1/dashboard":
            try:
                payload = self._dashboard()
            except ValueError as exc:
                self._json_response(HTTPStatus.BAD_REQUEST, {"status": "error", "error": str(exc)})
                return
            self._json_response(HTTPStatus.OK, payload)
            return
        if self.path == "/v1/alerts":
            try:
                dashboard = self._dashboard()
            except ValueError as exc:
                self._json_response(HTTPStatus.BAD_REQUEST, {"status": "error", "error": str(exc)})
                return
            self._json_response(HTTPStatus.OK, {
                "status": dashboard["summary"]["state"],
                "component": dashboard["component"],
                "timestamp": dashboard["timestamp"],
                "summary": dashboard["summary"],
                "alerts": dashboard["alerts"],
            })
            return
        if self.path == "/v1/workflow":
            try:
                payload = load_workflow_summary(self.ingest_dir, repair=True)
            except ValueError as exc:
                self._json_response(HTTPStatus.BAD_REQUEST, {"status": "error", "error": str(exc)})
                return
            self._json_response(HTTPStatus.OK, payload)
            return
        if self.path == "/v1/queue":
            payload = queue_status(self.postprocess_queue_dir, ttl_seconds=self.queue_ttl_seconds)
            self._json_response(HTTPStatus.OK, payload)
            return
        if self.path == "/v1/ingest":
            try:
                payload = load_ingest_index(self.ingest_dir, repair=True)
            except ValueError as exc:
                self._json_response(HTTPStatus.BAD_REQUEST, {"status": "error", "error": str(exc)})
                return
            self._json_response(HTTPStatus.OK, payload)
            return
        if self.path == "/registry":
            try:
                payload = load_registry(self.registry_path)
            except ValueError as exc:
                self._json_response(HTTPStatus.BAD_REQUEST, {"status": "error", "error": str(exc)})
                return
            self._json_response(HTTPStatus.OK, payload)
            return
        self._json_response(HTTPStatus.NOT_FOUND, {"status": "error", "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/reports":
            self._json_response(HTTPStatus.NOT_FOUND, {"status": "error", "error": "not found"})
            return
        if not self._authorized():
            self._json_response(HTTPStatus.UNAUTHORIZED, {"status": "error", "error": "unauthorized"})
            return
        try:
            payload = self._read_json()
        except ValueError as exc:
            self._json_response(HTTPStatus.BAD_REQUEST, {"status": "error", "error": str(exc)})
            return
        if not isinstance(payload.get("report"), dict):
            self._json_response(HTTPStatus.BAD_REQUEST, {"status": "error", "error": "report must be a JSON object"})
            return
        if "node_name" not in payload:
            self._json_response(HTTPStatus.BAD_REQUEST, {"status": "error", "error": "node_name is required"})
            return
        result = store_ingest_payload(
            self.ingest_dir,
            payload,
            queue_dir=self.postprocess_queue_dir,
            queue_ttl_seconds=self.queue_ttl_seconds,
        )
        self._json_response(HTTPStatus.OK if result["status"] == "duplicate" else HTTPStatus.ACCEPTED, result)


def serve_api(
    host: str,
    port: int,
    *,
    registry_path: str | Path,
    ingest_dir: str | Path,
    shared_token: str = "",
    collector_spool_dir: str | Path | None = None,
    postprocess_queue_dir: str | Path | None = None,
    spool_ttl_seconds: int = 3600,
    queue_ttl_seconds: int = 86400,
    queue_alert_threshold: int = 20,
    spool_alert_threshold: int = 10,
    duplicate_ratio_threshold: float = 0.25,
) -> None:
    server = ThreadingHTTPServer((host, port), AnalyzerAPIHandler)
    server.registry_path = str(Path(registry_path))  # type: ignore[attr-defined]
    server.ingest_dir = str(Path(ingest_dir))  # type: ignore[attr-defined]
    server.shared_token = shared_token  # type: ignore[attr-defined]
    server.collector_spool_dir = str(collector_spool_dir or "")  # type: ignore[attr-defined]
    server.postprocess_queue_dir = str(Path(postprocess_queue_dir) if postprocess_queue_dir else Path(ingest_dir) / "postprocess-queue")  # type: ignore[attr-defined]
    server.spool_ttl_seconds = spool_ttl_seconds  # type: ignore[attr-defined]
    server.queue_ttl_seconds = queue_ttl_seconds  # type: ignore[attr-defined]
    server.queue_alert_threshold = queue_alert_threshold  # type: ignore[attr-defined]
    server.spool_alert_threshold = spool_alert_threshold  # type: ignore[attr-defined]
    server.duplicate_ratio_threshold = duplicate_ratio_threshold  # type: ignore[attr-defined]
    Path(ingest_dir).mkdir(parents=True, exist_ok=True)
    Path(server.postprocess_queue_dir).mkdir(parents=True, exist_ok=True)  # type: ignore[arg-type]
    server.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the analyzer HTTP API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--registry-path", required=True)
    parser.add_argument("--ingest-dir", required=True)
    parser.add_argument("--shared-token", default="")
    parser.add_argument("--collector-spool-dir", default="")
    parser.add_argument("--postprocess-queue-dir", default="")
    parser.add_argument("--spool-ttl-seconds", type=int, default=3600)
    parser.add_argument("--queue-ttl-seconds", type=int, default=86400)
    parser.add_argument("--queue-alert-threshold", type=int, default=20)
    parser.add_argument("--spool-alert-threshold", type=int, default=10)
    parser.add_argument("--duplicate-ratio-threshold", type=float, default=0.25)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    serve_api(
        args.host,
        args.port,
        registry_path=args.registry_path,
        ingest_dir=args.ingest_dir,
        shared_token=args.shared_token,
        collector_spool_dir=args.collector_spool_dir,
        postprocess_queue_dir=args.postprocess_queue_dir,
        spool_ttl_seconds=args.spool_ttl_seconds,
        queue_ttl_seconds=args.queue_ttl_seconds,
        queue_alert_threshold=args.queue_alert_threshold,
        spool_alert_threshold=args.spool_alert_threshold,
        duplicate_ratio_threshold=args.duplicate_ratio_threshold,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
