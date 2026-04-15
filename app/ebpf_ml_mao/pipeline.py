from __future__ import annotations

import json
from pathlib import Path

from .adapters import adapt_prometheus_snapshot, adapt_tetragon_events
from .agents import analyze, correlate, review, summarize
from .features import extract_features, window_events
from .live import scrape_prometheus_snapshot, tail_jsonl
from .loader import load_json, load_jsonl
from .models import AnalysisReport, BatchAnalysisReport, NormalizedEvent
from .normalizer import normalize_event
from .report import (
    write_batch_json_report,
    write_batch_markdown_report,
    write_json_report,
    write_markdown_report,
)
from .scoring import BaselineModel, BaselineScorer, verdict_for_score



def _build_single_report(feature_window, scorer: BaselineScorer) -> AnalysisReport:
    score, confidence = scorer.score(feature_window)
    threshold = scorer.model.threshold if scorer.model is not None else 0.45
    verdict = verdict_for_score(score, threshold=threshold)
    return AnalysisReport(
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



def _feature_windows(events: list[NormalizedEvent]):
    return [extract_features(window) for window in window_events(events)]



def _build_single_report_from_model(
    input_events: list[NormalizedEvent],
    output_dir: str | Path,
    scorer: BaselineScorer,
) -> AnalysisReport:
    input_windows = _feature_windows(input_events)
    if not input_windows:
        raise ValueError("input dataset did not produce any feature windows")
    report = _build_single_report(input_windows[0], scorer)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json_report(report, output_dir / "report.json")
    write_markdown_report(report, output_dir / "report.md")
    return report



def _build_batch_report_from_model(
    input_events: list[NormalizedEvent],
    output_dir: str | Path,
    scorer: BaselineScorer,
) -> BatchAnalysisReport:
    input_windows = _feature_windows(input_events)
    if not input_windows:
        raise ValueError("input dataset did not produce any feature windows")

    reports = [_build_single_report(feature_window, scorer) for feature_window in input_windows]
    reports.sort(key=lambda report: (report.feature_window.workload, report.feature_window.window_start))

    batch_report = BatchAnalysisReport(reports=reports)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_batch_json_report(batch_report, output_dir / "report-index.json")
    write_batch_markdown_report(batch_report, output_dir / "report-index.md")
    for index, report in enumerate(batch_report.reports, start=1):
        write_json_report(report, reports_dir / f"report-{index:02d}.json")
        write_markdown_report(report, reports_dir / f"report-{index:02d}.md")
    return batch_report



def train_baseline_model(
    baseline_events: list[NormalizedEvent],
    model_path: str | Path,
    *,
    threshold: float = 0.45,
) -> BaselineModel:
    baseline_windows = _feature_windows(baseline_events)
    if not baseline_windows:
        raise ValueError("baseline dataset did not produce any feature windows")
    scorer = BaselineScorer()
    model = scorer.fit(baseline_windows, threshold=threshold)
    scorer.save_model(model_path)
    return model



def train_baseline_model_from_raw(
    baseline_tetragon_path: str | Path,
    baseline_prometheus_path: str | Path,
    model_path: str | Path,
    *,
    threshold: float = 0.45,
) -> BaselineModel:
    baseline_tetragon = load_jsonl(baseline_tetragon_path)
    baseline_prometheus = load_json(baseline_prometheus_path)
    baseline_events = adapt_tetragon_events(baseline_tetragon) + adapt_prometheus_snapshot(
        baseline_prometheus
    )
    return train_baseline_model(
        sorted(baseline_events, key=lambda event: event.ts),
        model_path,
        threshold=threshold,
    )



def build_report(
    baseline_events: list[NormalizedEvent],
    input_events: list[NormalizedEvent],
    output_dir: str | Path,
) -> AnalysisReport:
    baseline_windows = _feature_windows(baseline_events)
    if not baseline_windows:
        raise ValueError("baseline dataset did not produce any feature windows")
    scorer = BaselineScorer()
    scorer.fit(baseline_windows)
    return _build_single_report_from_model(input_events, output_dir, scorer)



def build_batch_report(
    baseline_events: list[NormalizedEvent],
    input_events: list[NormalizedEvent],
    output_dir: str | Path,
) -> BatchAnalysisReport:
    baseline_windows = _feature_windows(baseline_events)
    if not baseline_windows:
        raise ValueError("baseline dataset did not produce any feature windows")
    scorer = BaselineScorer()
    scorer.fit(baseline_windows)
    return _build_batch_report_from_model(input_events, output_dir, scorer)



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



def run_phase4(
    baseline_tetragon_path: str | Path,
    baseline_prometheus_path: str | Path,
    input_tetragon_path: str | Path,
    input_prometheus_path: str | Path,
    output_dir: str | Path,
) -> BatchAnalysisReport:
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
    return build_batch_report(
        sorted(baseline_events, key=lambda event: event.ts),
        sorted(input_events, key=lambda event: event.ts),
        output_dir,
    )



def run_phase5(
    model_path: str | Path,
    input_tetragon_path: str | Path,
    input_prometheus_path: str | Path,
    output_dir: str | Path,
) -> BatchAnalysisReport:
    input_tetragon = load_jsonl(input_tetragon_path)
    input_prometheus = load_json(input_prometheus_path)
    input_events = adapt_tetragon_events(input_tetragon) + adapt_prometheus_snapshot(
        input_prometheus
    )
    scorer = BaselineScorer()
    scorer.load_model(model_path)
    return _build_batch_report_from_model(
        sorted(input_events, key=lambda event: event.ts),
        output_dir,
        scorer,
    )
