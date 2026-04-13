from __future__ import annotations

from .models import NormalizedEvent


def normalize_event(raw: dict) -> NormalizedEvent:
    metrics = raw.get("metrics", {})
    return NormalizedEvent(
        ts=float(raw.get("timestamp", 0.0)),
        source=str(raw.get("source", "unknown")),
        event_type=str(raw.get("event_type", "unknown")),
        node=str(raw.get("node", "unknown-node")),
        workload=str(raw.get("workload", raw.get("pod", "unknown-workload"))),
        pod=str(raw.get("pod", "unknown-pod")),
        container=str(raw.get("container", "unknown-container")),
        pid=int(raw.get("pid", 0)),
        cpu_usage=float(metrics.get("cpu_usage", raw.get("cpu_usage", 0.0))),
        memory_usage=float(
            metrics.get("memory_usage", raw.get("memory_usage", 0.0))
        ),
        network_connections=int(
            metrics.get(
                "network_connections",
                raw.get("network_connections", 0),
            )
        ),
        metadata={
            key: value
            for key, value in raw.items()
            if key
            not in {
                "timestamp",
                "source",
                "event_type",
                "node",
                "workload",
                "pod",
                "container",
                "pid",
                "metrics",
                "cpu_usage",
                "memory_usage",
                "network_connections",
            }
        },
    )

