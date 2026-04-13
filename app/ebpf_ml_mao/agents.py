from __future__ import annotations

from .models import AgentResult, FeatureWindow


def summarize(feature_window: FeatureWindow) -> AgentResult:
    values = feature_window.values
    summary = (
        f"{feature_window.workload} produced {int(values['event_count'])} events in "
        f"{feature_window.window_end - feature_window.window_start:.0f}s with "
        f"{int(values['exec_count'])} exec events and "
        f"{int(values['network_event_count'])} network events."
    )
    return AgentResult(name="summarizer", summary=summary)


def analyze(feature_window: FeatureWindow, score: float) -> AgentResult:
    values = feature_window.values
    hot_spots: list[str] = []
    if values["max_cpu_usage"] >= 80:
        hot_spots.append("CPU spike")
    if values["max_network_connections"] >= 20:
        hot_spots.append("network burst")
    if values["exec_count"] >= 3:
        hot_spots.append("repeated process execution")

    detail = ", ".join(hot_spots) if hot_spots else "no strong outliers"
    summary = f"Score {score:.2f} driven by {detail}."
    return AgentResult(name="analyst", summary=summary)


def correlate(feature_window: FeatureWindow) -> AgentResult:
    values = feature_window.values
    summary = (
        "Resource and event correlation suggests "
        f"CPU {values['max_cpu_usage']:.1f}% with "
        f"{values['max_network_connections']:.0f} concurrent connections."
    )
    return AgentResult(name="correlator", summary=summary)


def review(score: float, verdict: str, confidence: float) -> AgentResult:
    summary = (
        f"Final verdict is {verdict} with score {score:.2f} "
        f"and confidence {confidence:.2f}."
    )
    return AgentResult(name="reviewer", summary=summary)

