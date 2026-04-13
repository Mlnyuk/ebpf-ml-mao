# Phase 1 Analysis Report

- Verdict: `anomalous`
- Score: `1.0`
- Confidence: `1.0`
- Workload: `checkout`

## Features

- event_count: `5.0`
- exec_count: `3.0`
- network_event_count: `1.0`
- unique_pids: `3.0`
- avg_cpu_usage: `75.6`
- max_cpu_usage: `92.0`
- avg_memory_usage: `331.0`
- max_memory_usage: `370.0`
- avg_network_connections: `20.0`
- max_network_connections: `30`

## Agents

- summarizer: checkout produced 5 events in 22s with 3 exec events and 1 network events.
- analyst: Score 1.00 driven by CPU spike, network burst, repeated process execution.
- correlator: Resource and event correlation suggests CPU 92.0% with 30 concurrent connections.
- reviewer: Final verdict is anomalous with score 1.00 and confidence 1.00.
