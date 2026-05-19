# Step 16 Fault Scenario Experiment Report

- Generated at: `2026-05-19T04:38:05.238173+00:00`
- Result directory: `results/step16`

## Input Files

- `results/step16/baseline-dashboard.json`: found, 1453 bytes
- `results/step16/baseline-alerts.json`: found, 231 bytes
- `results/step16/baseline-workflow.json`: found, 346 bytes
- `results/step16/baseline-tetragon-tail.jsonl`: found, 1258139 bytes
- `results/step16/baseline-tetragon-fault-target.jsonl`: found, 32160 bytes
- `results/step16/baseline-analyzer.log`: found, 3491 bytes
- `results/step16/baseline-collector.log`: found, 9130 bytes
- `results/step16/exec-storm-dashboard.json`: found, 1833 bytes
- `results/step16/exec-storm-alerts.json`: found, 612 bytes
- `results/step16/exec-storm-workflow.json`: found, 349 bytes
- `results/step16/exec-storm-tetragon-tail.jsonl`: found, 898693 bytes
- `results/step16/exec-storm-tetragon-fault-target.jsonl`: found, 32531 bytes
- `results/step16/exec-storm-analyzer.log`: found, 7873 bytes
- `results/step16/exec-storm-collector.log`: found, 9331 bytes
- `results/step16/network-burst-dashboard.json`: found, 1845 bytes
- `results/step16/network-burst-alerts.json`: found, 613 bytes
- `results/step16/network-burst-workflow.json`: found, 353 bytes
- `results/step16/network-burst-tetragon-tail.jsonl`: found, 1200749 bytes
- `results/step16/network-burst-tetragon-fault-target.jsonl`: found, 265305 bytes
- `results/step16/network-burst-analyzer.log`: found, 14160 bytes
- `results/step16/network-burst-collector.log`: found, 9739 bytes
- `results/step16/cpu-stress-dashboard.json`: found, 1846 bytes
- `results/step16/cpu-stress-alerts.json`: found, 613 bytes
- `results/step16/cpu-stress-workflow.json`: found, 354 bytes
- `results/step16/cpu-stress-tetragon-tail.jsonl`: found, 1184198 bytes
- `results/step16/cpu-stress-tetragon-fault-target.jsonl`: found, 280256 bytes
- `results/step16/cpu-stress-analyzer.log`: found, 14595 bytes
- `results/step16/cpu-stress-collector.log`: found, 9802 bytes
- `results/step16/cpu-stress-kubectl-top.txt`: found, 124 bytes
- `results/step16/memory-pressure-dashboard.json`: found, 1846 bytes
- `results/step16/memory-pressure-alerts.json`: found, 613 bytes
- `results/step16/memory-pressure-workflow.json`: found, 354 bytes
- `results/step16/memory-pressure-tetragon-tail.jsonl`: found, 1222596 bytes
- `results/step16/memory-pressure-tetragon-fault-target.jsonl`: found, 274482 bytes
- `results/step16/memory-pressure-analyzer.log`: found, 14598 bytes
- `results/step16/memory-pressure-collector.log`: found, 9927 bytes
- `results/step16/memory-pressure-kubectl-top.txt`: found, 124 bytes

## Scenario Summary

| Scenario | Snapshot status | Alerts | Tetragon lines | anomalous | score | process_exec | process_kprobe | tcp_connect | fault-target |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| exec-storm | complete | 2 | 142 | yes | no | yes | yes | yes | yes |
| network-burst | complete | 2 | 200 | yes | no | yes | yes | yes | yes |
| cpu-stress | complete | 2 | 200 | yes | no | yes | yes | yes | yes |
| memory-pressure | complete | 2 | 200 | yes | no | yes | yes | yes | yes |

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

## exec-storm

- Snapshot status: `complete`
- Alerts: `2`
- Tetragon tail lines: `142`
- Tetragon fault-target lines: `6`
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
- Alerts: `2`
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
- Alerts: `2`
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
- Alerts: `2`
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
