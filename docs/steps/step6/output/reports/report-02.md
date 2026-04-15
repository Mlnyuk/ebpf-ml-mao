# MVP Analysis Report

- Verdict: `anomalous`
- Score: `1.0`
- Confidence: `1.0`
- Workload: `checkout`
- Window: `1776211231.0` -> `1776211254.0`

## Features

- event_count: `3.0`
- exec_count: `2.0`
- network_event_count: `0.0`
- unique_pids: `3.0`
- avg_cpu_usage: `30.3333`
- max_cpu_usage: `91.0`
- avg_memory_usage: `130.6667`
- max_memory_usage: `392.0`
- avg_network_connections: `10.3333`
- max_network_connections: `31`

## Agents

- summarizer: checkout produced 3 events in 23s with 2 exec events and 0 network events.
- analyst: Score 1.00 driven by CPU spike, network burst.
- correlator: Resource and event correlation suggests CPU 91.0% with 31 concurrent connections.
- reviewer: Final verdict is anomalous with score 1.00 and confidence 1.00.
