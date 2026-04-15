# MVP Analysis Report

- Verdict: `normal`
- Score: `0.3292`
- Confidence: `0.5737`
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
- analyst: Score 0.33 driven by no strong outliers.
- correlator: Resource and event correlation suggests CPU 0.0% with 0 concurrent connections.
- reviewer: Final verdict is normal with score 0.33 and confidence 0.57.
