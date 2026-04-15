from __future__ import annotations

import argparse
import hashlib
import json
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .registry import load_registry, registry_status


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


def _save_ingest_index(ingest_dir: Path, index: dict[str, Any]) -> None:
    _atomic_write_json(_index_path(ingest_dir), index)


def _save_workflow_summary(ingest_dir: Path, index: dict[str, Any]) -> dict[str, Any]:
    items = list(index.get("items", {}).values())
    verdicts: dict[str, int] = {}
    for item in items:
        verdict = item.get("verdict", "unknown")
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
    workflow = {
        "received_count": index.get("received_count", 0),
        "unique_count": index.get("unique_count", 0),
        "duplicates_count": index.get("duplicates_count", 0),
        "nodes": sorted({item["node_name"] for item in items}),
        "verdicts": verdicts,
    }
    _atomic_write_json(_workflow_path(ingest_dir), workflow)
    return workflow


def store_ingest_payload(ingest_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    base = Path(ingest_dir)
    base.mkdir(parents=True, exist_ok=True)
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
    return {
        "status": "stored",
        "digest": digest,
        "path": str(target_path),
        "workflow": workflow,
    }


class AnalyzerAPIHandler(BaseHTTPRequestHandler):
    server_version = "ebpf-ml-mao/step12"

    def _json_response(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._json_response(HTTPStatus.OK, {"status": "ok"})
            return
        if self.path == "/readyz":
            try:
                status = registry_status(self.registry_path)
                ingest = load_ingest_index(self.ingest_dir, repair=True)
            except ValueError as exc:
                self._json_response(HTTPStatus.SERVICE_UNAVAILABLE, {"status": "error", "error": str(exc)})
                return
            self._json_response(HTTPStatus.OK, {"status": "ready", "registry": status, "ingest": ingest["unique_count"]})
            return
        if self.path == "/v1/status":
            try:
                registry = registry_status(self.registry_path)
                ingest = load_ingest_index(self.ingest_dir, repair=True)
            except ValueError as exc:
                self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._json_response(HTTPStatus.OK, {
                "status": "ok",
                "registry": registry,
                "ingest_dir": str(self.ingest_dir),
                "ingest": {
                    "received_count": ingest.get("received_count", 0),
                    "unique_count": ingest.get("unique_count", 0),
                    "duplicates_count": ingest.get("duplicates_count", 0),
                    "repaired_at": ingest.get("repaired_at"),
                },
            })
            return
        if self.path == "/v1/ingest":
            try:
                payload = load_ingest_index(self.ingest_dir, repair=True)
            except ValueError as exc:
                self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._json_response(HTTPStatus.OK, payload)
            return
        if self.path == "/registry":
            try:
                payload = load_registry(self.registry_path)
            except ValueError as exc:
                self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._json_response(HTTPStatus.OK, payload)
            return
        self._json_response(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/reports":
            self._json_response(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        if not self._authorized():
            self._json_response(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        try:
            payload = self._read_json()
        except ValueError as exc:
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if not isinstance(payload.get("report"), dict):
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": "report must be a JSON object"})
            return
        if "node_name" not in payload:
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": "node_name is required"})
            return
        result = store_ingest_payload(self.ingest_dir, payload)
        self._json_response(HTTPStatus.OK if result["status"] == "duplicate" else HTTPStatus.ACCEPTED, result)


def serve_api(host: str, port: int, *, registry_path: str | Path, ingest_dir: str | Path, shared_token: str = "") -> None:
    server = ThreadingHTTPServer((host, port), AnalyzerAPIHandler)
    server.registry_path = str(Path(registry_path))  # type: ignore[attr-defined]
    server.ingest_dir = str(Path(ingest_dir))  # type: ignore[attr-defined]
    server.shared_token = shared_token  # type: ignore[attr-defined]
    Path(ingest_dir).mkdir(parents=True, exist_ok=True)
    server.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the analyzer HTTP API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--registry-path", required=True)
    parser.add_argument("--ingest-dir", required=True)
    parser.add_argument("--shared-token", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    serve_api(args.host, args.port, registry_path=args.registry_path, ingest_dir=args.ingest_dir, shared_token=args.shared_token)
    return 0
