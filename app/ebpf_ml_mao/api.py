from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .registry import load_registry, registry_status


class AnalyzerAPIHandler(BaseHTTPRequestHandler):
    server_version = "ebpf-ml-mao/step10"

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
        header = self.headers.get("Authorization", "")
        return header == f"Bearer {shared_token}"

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
            except ValueError as exc:
                self._json_response(HTTPStatus.SERVICE_UNAVAILABLE, {"status": "error", "error": str(exc)})
                return
            self._json_response(HTTPStatus.OK, {"status": "ready", "registry": status})
            return
        if self.path == "/v1/status":
            try:
                registry = registry_status(self.registry_path)
            except ValueError as exc:
                self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            payload = {
                "status": "ok",
                "registry": registry,
                "ingest_dir": str(self.ingest_dir),
            }
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

        node_name = str(payload.get("node_name", "unknown-node"))
        report_name = str(payload.get("report_name", "report.json"))
        report_body = payload.get("report")
        if not isinstance(report_body, dict):
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": "report must be a JSON object"})
            return

        target_dir = self.ingest_dir / node_name
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / report_name
        target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._json_response(
            HTTPStatus.ACCEPTED,
            {
                "status": "stored",
                "path": str(target_path),
            },
        )


def serve_api(
    host: str,
    port: int,
    *,
    registry_path: str | Path,
    ingest_dir: str | Path,
    shared_token: str = "",
) -> None:
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
    serve_api(
        args.host,
        args.port,
        registry_path=args.registry_path,
        ingest_dir=args.ingest_dir,
        shared_token=args.shared_token,
    )
    return 0
