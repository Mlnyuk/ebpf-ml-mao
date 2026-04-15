from __future__ import annotations

from pathlib import Path

from .adapters import adapt_prometheus_snapshot, adapt_tetragon_events
from .agents import analyze, correlate, review, summarize
from .features import extract_features, window_events
from .live import scrape_prometheus_snapshot, tail_jsonl
from .loader import load_json, load_jsonl
from .models import AnalysisReport, NormalizedEvent
from .normalizer import normalize_event
from .report import write_json_report, write_markdown_report
from .scoring import BaselineScorer, verdict_for_score


def build_report(
    baseline_events: list[NormalizedEvent],
    input_events: list[NormalizedEvent],
    output_dir: str | Path,
) -> AnalysisReport:
    baseline_windows = [extract_features(window) for window in window_events(baseline_events)]
    input_windows = [extract_features(window) for window in window_events(input_events)]
    if not baseline_windows:
        raise ValueError("baseline dataset did not produce any feature windows")
    if not input_windows:
        raise ValueError("input dataset did not produce any feature windows")

    scorer = BaselineScorer()
    scorer.fit(baseline_windows)
    feature_window = input_windows[0]
    score, confidence = scorer.score(feature_window)
    verdict = verdict_for_score(score)

    report = AnalysisReport(
        score=score,
        verdict=verdict,
        confidence=confidence,
        feature_window=feature_window,
        agent_results=[
            summarize(feature_window),
            analyze(feature_window, score),
            correlate(feature_window),
            review(score, verdict, confidence),
        ],
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json_report(report, output_dir / "report.json")
    write_markdown_report(report, output_dir / "report.md")
    return report


def run_phase1(
    baseline_path: str | Path,
    input_path: str | Path,
    output_dir: str | Path,
) -> AnalysisReport:
    baseline_raw = load_jsonl(baseline_path)
    input_raw = load_jsonl(input_path)

    baseline_events = [normalize_event(item) for item in baseline_raw]
    input_events = [normalize_event(item) for item in input_raw]
    return build_report(baseline_events, input_events, output_dir)


def run_phase2(
    baseline_tetragon_path: str | Path,
    baseline_prometheus_path: str | Path,
    input_tetragon_path: str | Path,
    input_prometheus_path: str | Path,
    output_dir: str | Path,
) -> AnalysisReport:
    baseline_tetragon = load_jsonl(baseline_tetragon_path)
    input_tetragon = load_jsonl(input_tetragon_path)
    baseline_prometheus = load_json(baseline_prometheus_path)
    input_prometheus = load_json(input_prometheus_path)

    baseline_events = adapt_tetragon_events(baseline_tetragon) + adapt_prometheus_snapshot(
        baseline_prometheus
    )
    input_events = adapt_tetragon_events(input_tetragon) + adapt_prometheus_snapshot(
        input_prometheus
    )
    return build_report(
        sorted(baseline_events, key=lambda event: event.ts),
        sorted(input_events, key=lambda event: event.ts),
        output_dir,
    )


def run_phase3(
    baseline_tetragon_path: str | Path,
    baseline_prometheus_path: str | Path,
    tetragon_log_path: str | Path,
    prometheus_url: str,
    output_dir: str | Path,
    *,
    tetragon_tail_lines: int = 100,
    scrape_timeout: float = 5.0,
) -> AnalysisReport:
    baseline_tetragon = load_jsonl(baseline_tetragon_path)
    baseline_prometheus = load_json(baseline_prometheus_path)

    live_tetragon = tail_jsonl(tetragon_log_path, max_lines=tetragon_tail_lines)
    live_prometheus_events = scrape_prometheus_snapshot(
        prometheus_url,
        timeout=scrape_timeout,
    )

    baseline_events = adapt_tetragon_events(baseline_tetragon) + adapt_prometheus_snapshot(
        baseline_prometheus
    )
    input_events = adapt_tetragon_events(live_tetragon) + live_prometheus_events
    return build_report(
        sorted(baseline_events, key=lambda event: event.ts),
        sorted(input_events, key=lambda event: event.ts),
        output_dir,
    )
