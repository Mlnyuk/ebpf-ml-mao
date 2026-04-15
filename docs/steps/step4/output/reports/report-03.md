# MVP Analysis Report

- Verdict: `anomalous`
- Score: `0.7031`
- Confidence: `0.8385`
- Workload: `payment`
- Window: `1776211208.0` -> `1776211220.0`

## Features

- event_count: `3.0`
- exec_count: `2.0`
- network_event_count: `0.0`
- unique_pids: `3.0`
- avg_cpu_usage: `22.3333`
- max_cpu_usage: `67.0`
- avg_memory_usage: `106.6667`
- max_memory_usage: `320.0`
- avg_network_connections: `5.0`
- max_network_connections: `15`

## Agents

- summarizer: payment produced 3 events in 12s with 2 exec events and 0 network events.
- analyst: Score 0.70 driven by no strong outliers.
- correlator: Resource and event correlation suggests CPU 67.0% with 15 concurrent connections.
- reviewer: Final verdict is anomalous with score 0.70 and confidence 0.84.
