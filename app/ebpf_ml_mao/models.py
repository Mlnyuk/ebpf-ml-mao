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


@dataclass(slots=True)
class AlertRecord:
    name: str
    severity: str
    message: str
    value: float | int | str
    threshold: float | int | str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class QueueSnapshot:
    count: int
    pending_count: int
    failed_count: int
    expired_count: int
    oldest_age_seconds: int | None
    ttl_seconds: int
    quarantined_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DashboardSnapshot:
    component: str
    timestamp: int
    summary: dict[str, Any]
    counters: dict[str, Any]
    registry: dict[str, Any]
    ingest: dict[str, Any]
    workflow: dict[str, Any]
    queue: dict[str, Any]
    spool: dict[str, Any]
    alerts: list[AlertRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "component": self.component,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "counters": self.counters,
            "registry": self.registry,
            "ingest": self.ingest,
            "workflow": self.workflow,
            "queue": self.queue,
            "spool": self.spool,
            "alerts": [alert.to_dict() for alert in self.alerts],
        }
