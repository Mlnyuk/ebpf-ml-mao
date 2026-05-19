# Step 16 Fault Scenario Experiment Report

- Generated at: `2026-05-19T07:40:24.864657+00:00`
- Result directory: `results/step20/run_02`

## Input Files

- `results/step20/run_02/baseline-dashboard.json`: found, 1648 bytes
- `results/step20/run_02/baseline-alerts.json`: found, 433 bytes
- `results/step20/run_02/baseline-workflow.json`: found, 349 bytes
- `results/step20/run_02/baseline-tetragon-tail.jsonl`: found, 1239839 bytes
- `results/step20/run_02/baseline-tetragon-fault-target.jsonl`: found, 251555 bytes
- `results/step20/run_02/baseline-analyzer.log`: found, 3134 bytes
- `results/step20/run_02/baseline-collector.log`: found, 24144 bytes
- `results/step20/run_02/exec-storm-dashboard.json`: found, 1827 bytes
- `results/step20/run_02/exec-storm-alerts.json`: found, 612 bytes
- `results/step20/run_02/exec-storm-workflow.json`: found, 349 bytes
- `results/step20/run_02/exec-storm-tetragon-tail.jsonl`: found, 1190838 bytes
- `results/step20/run_02/exec-storm-tetragon-fault-target.jsonl`: found, 240624 bytes
- `results/step20/run_02/exec-storm-analyzer.log`: found, 7881 bytes
- `results/step20/run_02/exec-storm-collector.log`: found, 24039 bytes
- `results/step20/run_02/network-burst-dashboard.json`: found, 1840 bytes
- `results/step20/run_02/network-burst-alerts.json`: found, 613 bytes
- `results/step20/run_02/network-burst-workflow.json`: found, 354 bytes
- `results/step20/run_02/network-burst-tetragon-tail.jsonl`: found, 1185167 bytes
- `results/step20/run_02/network-burst-tetragon-fault-target.jsonl`: found, 265317 bytes
- `results/step20/run_02/network-burst-analyzer.log`: found, 14523 bytes
- `results/step20/run_02/network-burst-collector.log`: found, 24181 bytes
- `results/step20/run_02/cpu-stress-dashboard.json`: found, 1840 bytes
- `results/step20/run_02/cpu-stress-alerts.json`: found, 613 bytes
- `results/step20/run_02/cpu-stress-workflow.json`: found, 354 bytes
- `results/step20/run_02/cpu-stress-tetragon-tail.jsonl`: found, 39367 bytes
- `results/step20/run_02/cpu-stress-tetragon-fault-target.jsonl`: found, 32172 bytes
- `results/step20/run_02/cpu-stress-analyzer.log`: found, 14598 bytes
- `results/step20/run_02/cpu-stress-collector.log`: found, 24170 bytes
- `results/step20/run_02/cpu-stress-kubectl-top.txt`: found, 124 bytes
- `results/step20/run_02/memory-pressure-dashboard.json`: found, 1840 bytes
- `results/step20/run_02/memory-pressure-alerts.json`: found, 613 bytes
- `results/step20/run_02/memory-pressure-workflow.json`: found, 354 bytes
- `results/step20/run_02/memory-pressure-tetragon-tail.jsonl`: found, 859250 bytes
- `results/step20/run_02/memory-pressure-tetragon-fault-target.jsonl`: found, 179098 bytes
- `results/step20/run_02/memory-pressure-analyzer.log`: found, 14593 bytes
- `results/step20/run_02/memory-pressure-collector.log`: found, 24124 bytes
- `results/step20/run_02/memory-pressure-kubectl-top.txt`: found, 124 bytes

## Scenario Summary

| Scenario | Snapshot status | Alerts | Tetragon lines | anomalous | score | process_exec | process_kprobe | tcp_connect | fault-target |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| exec-storm | complete | 2 | 200 | yes | no | yes | yes | yes | yes |
| network-burst | complete | 2 | 200 | yes | no | yes | yes | yes | yes |
| cpu-stress | complete | 2 | 7 | yes | no | yes | yes | no | yes |
| memory-pressure | complete | 2 | 143 | yes | no | yes | yes | yes | yes |

## Baseline

- Snapshot status: `complete`
- Alerts: `1`
- Tetragon tail lines: `200`
- Tetragon fault-target lines: `50`
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
- Tetragon tail lines: `7`
- Tetragon fault-target lines: `6`
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
- Contains `tcp_connect`: no
- Contains `fault-target`: yes

## memory-pressure

- Snapshot status: `complete`
- Alerts: `2`
- Tetragon tail lines: `143`
- Tetragon fault-target lines: `33`
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
