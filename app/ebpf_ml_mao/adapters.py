from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re
from typing import Any

from .models import NormalizedEvent


TETRAGON_PAYLOAD_KEYS = (
    "process_exec",
    "process_kprobe",
    "process_exit",
    "process_dns",
    "network_flow",
)


def _parse_timestamp(value: Any) -> float:
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric / 1000.0 if numeric > 1_000_000_000_000 else numeric
    if isinstance(value, str):
        stripped = value.strip()
        try:
            numeric = float(stripped)
        except ValueError:
            numeric = None
        if numeric is not None:
            return numeric / 1000.0 if numeric > 1_000_000_000_000 else numeric
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        return datetime.fromisoformat(value).timestamp()
    raise ValueError(f"unsupported timestamp value: {value!r}")


def _tetragon_payload(raw: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for key in TETRAGON_PAYLOAD_KEYS:
        payload = raw.get(key)
        if isinstance(payload, dict):
            return key, payload
    return str(raw.get("type", "unknown")).lower(), raw


def _tetragon_event_type(raw: dict[str, Any], payload_key: str, payload: dict[str, Any]) -> str:
    explicit_type = raw.get("type")
    if explicit_type:
        return str(explicit_type).lower()

    function_name = str(
        payload.get("function_name")
        or payload.get("call")
        or payload.get("probe")
        or ""
    ).lower()
    if payload_key == "process_kprobe":
        if "execve" in function_name:
            return "process_exec"
        if function_name in {"tcp_connect", "udp_sendmsg"} or "connect" in function_name:
            return "network_connection"
        if function_name in {"security_file_open", "sys_open", "sys_openat"}:
            return "file_open"
        if "setuid" in function_name or "setgid" in function_name:
            return "privilege_escalation"
    return payload_key


def _pod_name(pod: dict[str, Any]) -> str:
    return str(pod.get("name") or pod.get("pod_name") or "unknown-pod")


def _workload_name(pod: dict[str, Any]) -> str:
    explicit = pod.get("workload") or pod.get("workload_name")
    if explicit:
        return str(explicit)
    labels = pod.get("labels", {})
    if isinstance(labels, dict):
        for key in ("app.kubernetes.io/name", "app", "k8s-app"):
            if labels.get(key):
                return str(labels[key])
    name = _pod_name(pod)
    replica_suffix = r"-[a-f0-9]{8,10}-[a-z0-9]{5}$"
    stateful_suffix = r"-[0-9]+$"
    return re.sub(stateful_suffix, "", re.sub(replica_suffix, "", name))


def _container_name(pod: dict[str, Any]) -> str:
    container = pod.get("container", {})
    if isinstance(container, dict):
        return str(container.get("name") or container.get("container_name") or "unknown-container")
    return "unknown-container"


def adapt_tetragon_event(raw: dict[str, Any]) -> NormalizedEvent:
    payload_key, payload = _tetragon_payload(raw)
    process = payload.get("process", raw.get("process", {}))
    pod = process.get("pod", {})
    event_type = _tetragon_event_type(raw, payload_key, payload)

    return NormalizedEvent(
        ts=_parse_timestamp(raw.get("time", payload.get("time", 0.0))),
        source="tetragon",
        event_type=event_type,
        node=str(process.get("node_name", payload.get("node_name", raw.get("node_name", "unknown-node")))),
        workload=_workload_name(pod),
        pod=_pod_name(pod),
        container=_container_name(pod),
        pid=int(process.get("pid", 0)),
        cpu_usage=0.0,
        memory_usage=0.0,
        network_connections=0,
        metadata={
            "binary": process.get("binary", ""),
            "arguments": process.get("arguments", ""),
            "namespace": pod.get("namespace", "default"),
            "raw_type": raw.get("type", payload_key),
            "function_name": payload.get("function_name", ""),
            "policy_name": payload.get("policy_name", ""),
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
    default_timestamp = _parse_timestamp(snapshot.get("timestamp", 0.0))
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "network_connections": 0,
            "namespace": "default",
            "timestamp": None,
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
        item_timestamp = _parse_timestamp(item.get("timestamp", default_timestamp))
        bucket["timestamp"] = (
            item_timestamp
            if bucket["timestamp"] is None
            else max(float(bucket["timestamp"]), item_timestamp)
        )

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
                source="prometheus",
                event_type="prometheus_snapshot",
                node=node,
                workload=workload,
                pod=pod,
                container=container,
                pid=0,
                ts=float(values["timestamp"] if values["timestamp"] is not None else default_timestamp),
                cpu_usage=float(values["cpu_usage"]),
                memory_usage=float(values["memory_usage"]),
                network_connections=int(values["network_connections"]),
                metadata={"namespace": values["namespace"]},
            )
        )

    return events
