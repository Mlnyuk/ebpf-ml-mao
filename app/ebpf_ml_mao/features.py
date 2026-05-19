from __future__ import annotations

from collections import defaultdict

from .models import FeatureWindow, NormalizedEvent


WINDOW_SECONDS = 30


def window_events(
    events: list[NormalizedEvent],
    window_seconds: int = WINDOW_SECONDS,
) -> list[list[NormalizedEvent]]:
    grouped: dict[tuple[str, int], list[NormalizedEvent]] = defaultdict(list)
    for event in events:
        bucket = int(event.ts // window_seconds)
        grouped[(event.workload, bucket)].append(event)
    return list(grouped.values())


def extract_features(events: list[NormalizedEvent]) -> FeatureWindow:
    if not events:
        raise ValueError("cannot extract features from an empty event list")

    ordered_events = sorted(events, key=lambda event: event.ts)
    cpu_values = [event.cpu_usage for event in ordered_events]
    memory_values = [event.memory_usage for event in ordered_events]
    network_values = [event.network_connections for event in ordered_events]
    exec_events = sum(1 for event in ordered_events if event.event_type == "process_exec")
    network_events = sum(
        1 for event in ordered_events if event.event_type == "network_connection"
    )
    tetragon_events = sum(1 for event in ordered_events if event.source == "tetragon")
    prometheus_events = sum(1 for event in ordered_events if event.source == "prometheus")
    file_events = sum(1 for event in ordered_events if event.event_type == "file_open")
    privilege_events = sum(
        1 for event in ordered_events if event.event_type == "privilege_escalation"
    )
    duration_seconds = max(ordered_events[-1].ts - ordered_events[0].ts, 1.0)
    per_minute_scale = 60.0 / duration_seconds

    values = {
        "event_count": float(len(ordered_events)),
        "tetragon_event_count": float(tetragon_events),
        "prometheus_event_count": float(prometheus_events),
        "exec_count": float(exec_events),
        "network_event_count": float(network_events),
        "file_event_count": float(file_events),
        "privilege_event_count": float(privilege_events),
        "unique_pids": float(len({event.pid for event in ordered_events})),
        "window_duration_seconds": float(duration_seconds),
        "event_rate_per_minute": float(len(ordered_events)) * per_minute_scale,
        "exec_rate_per_minute": float(exec_events) * per_minute_scale,
        "network_event_rate_per_minute": float(network_events) * per_minute_scale,
        "avg_cpu_usage": sum(cpu_values) / len(cpu_values),
        "max_cpu_usage": max(cpu_values),
        "cpu_pressure_ratio": max(cpu_values) / 100.0,
        "avg_memory_usage": sum(memory_values) / len(memory_values),
        "max_memory_usage": max(memory_values),
        "avg_network_connections": sum(network_values) / len(network_values),
        "max_network_connections": max(network_values),
        "network_connection_pressure": float(max(network_values)),
    }

    return FeatureWindow(
        window_start=ordered_events[0].ts,
        window_end=ordered_events[-1].ts,
        workload=ordered_events[0].workload,
        values=values,
    )
