from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class NormalizedEvent:
    ts: float
    source: str
    event_type: str
    node: str
    workload: str
    pod: str
    container: str
    pid: int
    cpu_usage: float
    memory_usage: float
    network_connections: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FeatureWindow:
    window_start: float
    window_end: float
    workload: str
    values: dict[str, float]


@dataclass(slots=True)
class AgentResult:
    name: str
    summary: str


@dataclass(slots=True)
class AnalysisReport:
    score: float
    verdict: str
    confidence: float
    feature_window: FeatureWindow
    agent_results: list[AgentResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "verdict": self.verdict,
            "confidence": round(self.confidence, 4),
            "feature_window": {
                "window_start": self.feature_window.window_start,
                "window_end": self.feature_window.window_end,
                "workload": self.feature_window.workload,
                "values": {
                    key: round(value, 4)
                    for key, value in self.feature_window.values.items()
                },
            },
            "agents": [asdict(agent_result) for agent_result in self.agent_results],
        }


@dataclass(slots=True)
class BatchAnalysisReport:
    reports: list[AnalysisReport]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_count": len(self.reports),
            "reports": [report.to_dict() for report in self.reports],
        }
