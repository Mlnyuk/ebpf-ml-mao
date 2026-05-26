# Step 16 Fault Scenario Experiment Report

- Generated at: `2026-05-26T02:08:25.472392+00:00`
- Result directory: `results/step16`

## Input Files

- `results/step16/baseline-dashboard.json`: found, 1208 bytes
- `results/step16/baseline-alerts.json`: found, 227 bytes
- `results/step16/baseline-workflow.json`: found, 146 bytes
- `results/step16/baseline-tetragon-tail.jsonl`: found, 1635400 bytes
- `results/step16/baseline-tetragon-fault-target.jsonl`: found, 44917 bytes
- `results/step16/baseline-analyzer.log`: found, 702 bytes
- `results/step16/baseline-collector.log`: found, 16308 bytes
- `results/step16/exec-storm-dashboard.json`: found, 1483 bytes
- `results/step16/exec-storm-alerts.json`: found, 433 bytes
- `results/step16/exec-storm-workflow.json`: found, 209 bytes
- `results/step16/exec-storm-tetragon-tail.jsonl`: found, 1649478 bytes
- `results/step16/exec-storm-tetragon-fault-target.jsonl`: found, 355739 bytes
- `results/step16/exec-storm-analyzer.log`: found, 2609 bytes
- `results/step16/exec-storm-collector.log`: found, 16656 bytes
- `results/step16/network-burst-dashboard.json`: found, 1483 bytes
- `results/step16/network-burst-alerts.json`: found, 433 bytes
- `results/step16/network-burst-workflow.json`: found, 209 bytes
- `results/step16/network-burst-tetragon-tail.jsonl`: found, 1651235 bytes
- `results/step16/network-burst-tetragon-fault-target.jsonl`: found, 375328 bytes
- `results/step16/network-burst-analyzer.log`: found, 5506 bytes
- `results/step16/network-burst-collector.log`: found, 17004 bytes
- `results/step16/cpu-stress-dashboard.json`: found, 1483 bytes
- `results/step16/cpu-stress-alerts.json`: found, 433 bytes
- `results/step16/cpu-stress-workflow.json`: found, 209 bytes
- `results/step16/cpu-stress-tetragon-tail.jsonl`: found, 1618473 bytes
- `results/step16/cpu-stress-tetragon-fault-target.jsonl`: found, 389127 bytes
- `results/step16/cpu-stress-analyzer.log`: found, 6633 bytes
- `results/step16/cpu-stress-collector.log`: found, 17120 bytes
- `results/step16/cpu-stress-kubectl-top.txt`: found, 124 bytes
- `results/step16/memory-pressure-dashboard.json`: found, 1494 bytes
- `results/step16/memory-pressure-alerts.json`: found, 433 bytes
- `results/step16/memory-pressure-workflow.json`: found, 213 bytes
- `results/step16/memory-pressure-tetragon-tail.jsonl`: found, 1609162 bytes
- `results/step16/memory-pressure-tetragon-fault-target.jsonl`: found, 387498 bytes
- `results/step16/memory-pressure-analyzer.log`: found, 7905 bytes
- `results/step16/memory-pressure-collector.log`: found, 17352 bytes
- `results/step16/memory-pressure-kubectl-top.txt`: found, 124 bytes

## Scenario Summary

| Scenario | Snapshot status | Alerts | Tetragon lines | anomalous | score | process_exec | process_kprobe | tcp_connect | fault-target |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| exec-storm | complete | 1 | 200 | yes | no | yes | yes | yes | yes |
| network-burst | complete | 1 | 200 | yes | no | yes | yes | yes | yes |
| cpu-stress | complete | 1 | 200 | yes | no | yes | yes | yes | yes |
| memory-pressure | complete | 1 | 200 | yes | no | yes | yes | yes | yes |

## Baseline

- Snapshot status: `complete`
- Alerts: `0`
- Tetragon tail lines: `200`
- Tetragon fault-target lines: `6`
- `baseline-dashboard.json`: `ok`
- `baseline-alerts.json`: `ok`
- `baseline-workflow.json`: `ok`
- `baseline-tetragon-tail.jsonl`: `ok`
- `baseline-tetragon-fault-target.jsonl`: `ok`
- Contains `anomalous`: no
- Contains `score`: no
- Contains `exec`: yes
- Contains `network`: no
- Contains `cpu`: yes
- Contains `memory`: yes
- Contains `process_exec`: yes
- Contains `process_kprobe`: yes
- Contains `tcp_connect`: yes
- Contains `fault-target`: yes

## exec-storm

- Snapshot status: `complete`
- Alerts: `1`
- Tetragon tail lines: `200`
- Tetragon fault-target lines: `50`
- `exec-storm-dashboard.json`: `ok`
- `exec-storm-alerts.json`: `ok`
- `exec-storm-workflow.json`: `ok`
- `exec-storm-tetragon-tail.jsonl`: `ok`
- `exec-storm-tetragon-fault-target.jsonl`: `ok`
- Contains `anomalous`: yes
- Contains `score`: no
- Contains `exec`: yes
- Contains `network`: no
- Contains `cpu`: yes
- Contains `memory`: yes
- Contains `process_exec`: yes
- Contains `process_kprobe`: yes
- Contains `tcp_connect`: yes
- Contains `fault-target`: yes

## network-burst

- Snapshot status: `complete`
- Alerts: `1`
- Tetragon tail lines: `200`
- Tetragon fault-target lines: `50`
- `network-burst-dashboard.json`: `ok`
- `network-burst-alerts.json`: `ok`
- `network-burst-workflow.json`: `ok`
- `network-burst-tetragon-tail.jsonl`: `ok`
- `network-burst-tetragon-fault-target.jsonl`: `ok`
- Contains `anomalous`: yes
- Contains `score`: no
- Contains `exec`: yes
- Contains `network`: yes
- Contains `cpu`: yes
- Contains `memory`: yes
- Contains `process_exec`: yes
- Contains `process_kprobe`: yes
- Contains `tcp_connect`: yes
- Contains `fault-target`: yes

## cpu-stress

- Snapshot status: `complete`
- Alerts: `1`
- Tetragon tail lines: `200`
- Tetragon fault-target lines: `50`
- `cpu-stress-dashboard.json`: `ok`
- `cpu-stress-alerts.json`: `ok`
- `cpu-stress-workflow.json`: `ok`
- `cpu-stress-tetragon-tail.jsonl`: `ok`
- `cpu-stress-tetragon-fault-target.jsonl`: `ok`
- Contains `anomalous`: yes
- Contains `score`: no
- Contains `exec`: yes
- Contains `network`: no
- Contains `cpu`: yes
- Contains `memory`: yes
- Contains `process_exec`: yes
- Contains `process_kprobe`: yes
- Contains `tcp_connect`: yes
- Contains `fault-target`: yes

## memory-pressure

- Snapshot status: `complete`
- Alerts: `1`
- Tetragon tail lines: `200`
- Tetragon fault-target lines: `50`
- `memory-pressure-dashboard.json`: `ok`
- `memory-pressure-alerts.json`: `ok`
- `memory-pressure-workflow.json`: `ok`
- `memory-pressure-tetragon-tail.jsonl`: `ok`
- `memory-pressure-tetragon-fault-target.jsonl`: `ok`
- Contains `anomalous`: yes
- Contains `score`: no
- Contains `exec`: yes
- Contains `network`: no
- Contains `cpu`: yes
- Contains `memory`: yes
- Contains `process_exec`: yes
- Contains `process_kprobe`: yes
- Contains `tcp_connect`: yes
- Contains `fault-target`: yes

## Notes

- Absence of an anomaly does not necessarily mean pipeline failure. It may indicate that thresholds, feature calibration, scrape timing, or Tetragon/Prometheus coverage need adjustment.
- This report is generated from available files only. Missing or malformed JSON is reported instead of stopping report generation.
- This does not introduce advanced ML, modify eBPF programs, or make the analyzer production-HA.
