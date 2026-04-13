from __future__ import annotations

from pathlib import Path

from .agents import analyze, correlate, review, summarize
from .features import extract_features, window_events
from .loader import load_jsonl
from .models import AnalysisReport
from .normalizer import normalize_event
from .report import write_json_report, write_markdown_report
from .scoring import BaselineScorer, verdict_for_score


def run_phase1(
    baseline_path: str | Path,
    input_path: str | Path,
    output_dir: str | Path,
) -> AnalysisReport:
    baseline_raw = load_jsonl(baseline_path)
    input_raw = load_jsonl(input_path)

    baseline_events = [normalize_event(item) for item in baseline_raw]
    input_events = [normalize_event(item) for item in input_raw]

    baseline_windows = [extract_features(window) for window in window_events(baseline_events)]
    input_windows = [extract_features(window) for window in window_events(input_events)]
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

