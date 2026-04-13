from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from .models import NormalizedEvent


def _parse_timestamp(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        return datetime.fromisoformat(value).timestamp()
    raise ValueError(f"unsupported timestamp value: {value!r}")
def adapt_tetragon_event(raw: dict[str, Any]) -> NormalizedEvent:
    process = raw.get("process", {})
    pod = process.get("pod", {})
    container = pod.get("container", {})
    event_type = str(raw.get("type", "unknown")).lower()

    return NormalizedEvent(
        ts=_parse_timestamp(raw.get("time", 0.0)),
        source="tetragon",
        event_type=event_type,
        node=str(process.get("node_name", raw.get("node_name", "unknown-node"))),
        workload=str(pod.get("workload", pod.get("workload_name", pod.get("name", "unknown-workload")))),
        pod=str(pod.get("name", "unknown-pod")),
        container=str(container.get("name", "unknown-container")),
        pid=int(process.get("pid", 0)),
        cpu_usage=0.0,
        memory_usage=0.0,
        network_connections=0,
        metadata={
            "binary": process.get("binary", ""),
            "arguments": process.get("arguments", ""),
            "namespace": pod.get("namespace", "default"),
            "raw_type": raw.get("type", "unknown"),
        },
    )


def adapt_tetragon_events(raw_events: list[dict[str, Any]]) -> list[NormalizedEvent]:
    return [adapt_tetragon_event(raw_event) for raw_event in raw_events]


def _coerce_value(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list) and len(value) == 2:
        return float(value[1])
    return float(value)


def adapt_prometheus_snapshot(snapshot: dict[str, Any]) -> list[NormalizedEvent]:
    timestamp = _parse_timestamp(snapshot.get("timestamp", 0.0))
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "network_connections": 0,
            "namespace": "default",
        }
    )

    series = snapshot.get("series", [])
    for item in series:
        labels = item.get("labels", {})
        pod = str(labels.get("pod", "unknown-pod"))
        workload = str(labels.get("workload", pod))
        container = str(labels.get("container", "unknown-container"))
        node = str(labels.get("node", "unknown-node"))
        key = (workload, pod, container, node)
        bucket = grouped[key]
        bucket["namespace"] = str(labels.get("namespace", "default"))

        metric = str(item.get("metric", ""))
        value = _coerce_value(item.get("value", 0.0))
        if metric in {"container_cpu_usage_percent", "cpu_usage"}:
            bucket["cpu_usage"] = value
        elif metric in {"container_memory_working_set_bytes", "memory_usage"}:
            bucket["memory_usage"] = value
        elif metric in {"container_network_connections", "network_connections"}:
            bucket["network_connections"] = int(value)

    events: list[NormalizedEvent] = []
    for (workload, pod, container, node), values in grouped.items():
        events.append(
            NormalizedEvent(
                ts=timestamp,
                source="prometheus",
                event_type="prometheus_snapshot",
                node=node,
                workload=workload,
                pod=pod,
                container=container,
                pid=0,
                cpu_usage=float(values["cpu_usage"]),
                memory_usage=float(values["memory_usage"]),
                network_connections=int(values["network_connections"]),
                metadata={"namespace": values["namespace"]},
            )
        )

    return events
