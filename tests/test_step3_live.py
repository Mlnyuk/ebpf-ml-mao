from __future__ import annotations

import json
import socketserver
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ebpf_ml_mao.live import parse_prometheus_text, scrape_prometheus_snapshot, tail_jsonl
from ebpf_ml_mao.pipeline import run_phase3


class _MetricsHandler(BaseHTTPRequestHandler):
    response_text = ""

    def do_GET(self) -> None:  # noqa: N802
        body = self.response_text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class Step3LiveTest(unittest.TestCase):
    def test_tail_jsonl_reads_last_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir, "tetragon.log")
            log_path.write_text(
                "\n".join(
                    [
                        '{"time":"2026-04-15T00:00:00Z","type":"PROCESS_EXEC","process":{"pid":1}}',
                        '{"time":"2026-04-15T00:00:01Z","type":"PROCESS_EXEC","process":{"pid":2}}',
                        '{"time":"2026-04-15T00:00:02Z","type":"PROCESS_EXEC","process":{"pid":3}}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            records = tail_jsonl(log_path, max_lines=2)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["process"]["pid"], 2)
            self.assertEqual(records[1]["process"]["pid"], 3)

    def test_parse_prometheus_text_extracts_metrics(self) -> None:
        text = Path("samples/step3/metrics.prom").read_text(encoding="utf-8")
        snapshot = parse_prometheus_text(text, scraped_at=1776211224.0)
        self.assertEqual(len(snapshot["series"]), 3)
        self.assertEqual(snapshot["series"][0]["metric"], "container_cpu_usage_percent")

    def test_phase3_pipeline_generates_anomalous_report(self) -> None:
        metrics_text = Path("samples/step3/metrics.prom").read_text(encoding="utf-8")
        _MetricsHandler.response_text = metrics_text

        with socketserver.TCPServer(("127.0.0.1", 0), _MetricsHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_address[1]}/metrics"
                events = scrape_prometheus_snapshot(url, timeout=2.0)
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0].cpu_usage, 86.0)

                with tempfile.TemporaryDirectory() as temp_dir:
                    report = run_phase3(
                        "samples/step2/baseline_tetragon.jsonl",
                        "samples/step2/baseline_prometheus.json",
                        "samples/step3/tetragon-live.log",
                        url,
                        temp_dir,
                        tetragon_tail_lines=10,
                        scrape_timeout=2.0,
                    )
                    self.assertEqual(report.verdict, "anomalous")
                    self.assertGreater(report.score, 0.45)
                    report_json = json.loads(
                        Path(temp_dir, "report.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual(report_json["verdict"], "anomalous")
            finally:
                server.shutdown()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
