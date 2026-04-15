# MVP Analysis Report

- Verdict: `anomalous`
- Score: `1.0`
- Confidence: `1.0`
- Workload: `checkout`
- Window: `1776211200.0` -> `1776211204.0`

## Features

- event_count: `2.0`
- exec_count: `2.0`
- network_event_count: `0.0`
- unique_pids: `2.0`
- avg_cpu_usage: `0.0`
- max_cpu_usage: `0.0`
- avg_memory_usage: `0.0`
- max_memory_usage: `0.0`
- avg_network_connections: `0.0`
- max_network_connections: `0`

## Agents

- summarizer: checkout produced 2 events in 4s with 2 exec events and 0 network events.
- analyst: Score 1.00 driven by no strong outliers.
- correlator: Resource and event correlation suggests CPU 0.0% with 0 concurrent connections.
- reviewer: Final verdict is anomalous with score 1.00 and confidence 1.00.
