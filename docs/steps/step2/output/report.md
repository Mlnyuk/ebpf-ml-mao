# MVP Analysis Report

- Verdict: `anomalous`
- Score: `0.9608`
- Confidence: `0.9802`
- Workload: `checkout`

## Features

- event_count: `5.0`
- exec_count: `4.0`
- network_event_count: `0.0`
- unique_pids: `5.0`
- avg_cpu_usage: `17.2`
- max_cpu_usage: `86.0`
- avg_memory_usage: `74.4`
- max_memory_usage: `372.0`
- avg_network_connections: `5.2`
- max_network_connections: `26`

## Agents

- summarizer: checkout produced 5 events in 24s with 4 exec events and 0 network events.
- analyst: Score 0.96 driven by CPU spike, network burst, repeated process execution.
- correlator: Resource and event correlation suggests CPU 86.0% with 26 concurrent connections.
- reviewer: Final verdict is anomalous with score 0.96 and confidence 0.98.
