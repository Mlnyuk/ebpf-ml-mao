# Step 16 Fault Scenario Experiment Report

- Generated at: `2026-05-19T13:29:26.815678+00:00`
- Result directory: `results/step21/run_03`

## Input Files

- `results/step21/run_03/baseline-dashboard.json`: found, 1400 bytes
- `results/step21/run_03/baseline-alerts.json`: found, 231 bytes
- `results/step21/run_03/baseline-workflow.json`: found, 310 bytes
- `results/step21/run_03/baseline-tetragon-tail.jsonl`: found, 1228893 bytes
- `results/step21/run_03/baseline-tetragon-fault-target.jsonl`: found, 275033 bytes
- `results/step21/run_03/baseline-analyzer.log`: found, 14647 bytes
- `results/step21/run_03/baseline-collector.log`: found, 9977 bytes
- `results/step21/run_03/exec-storm-dashboard.json`: found, 1449 bytes
- `results/step21/run_03/exec-storm-alerts.json`: found, 231 bytes
- `results/step21/run_03/exec-storm-workflow.json`: found, 347 bytes
- `results/step21/run_03/exec-storm-tetragon-tail.jsonl`: found, 1224910 bytes
- `results/step21/run_03/exec-storm-tetragon-fault-target.jsonl`: found, 255370 bytes
- `results/step21/run_03/exec-storm-analyzer.log`: found, 5246 bytes
- `results/step21/run_03/exec-storm-collector.log`: found, 10185 bytes
- `results/step21/run_03/network-burst-dashboard.json`: found, 1635 bytes
- `results/step21/run_03/network-burst-alerts.json`: found, 422 bytes
- `results/step21/run_03/network-burst-workflow.json`: found, 347 bytes
- `results/step21/run_03/network-burst-tetragon-tail.jsonl`: found, 1230659 bytes
- `results/step21/run_03/network-burst-tetragon-fault-target.jsonl`: found, 270537 bytes
- `results/step21/run_03/network-burst-analyzer.log`: found, 11748 bytes
- `results/step21/run_03/network-burst-collector.log`: found, 10522 bytes
- `results/step21/run_03/cpu-stress-dashboard.json`: found, 1839 bytes
- `results/step21/run_03/cpu-stress-alerts.json`: found, 613 bytes
- `results/step21/run_03/cpu-stress-workflow.json`: found, 353 bytes
- `results/step21/run_03/cpu-stress-tetragon-tail.jsonl`: found, 1234109 bytes
- `results/step21/run_03/cpu-stress-tetragon-fault-target.jsonl`: found, 280033 bytes
- `results/step21/run_03/cpu-stress-analyzer.log`: found, 14225 bytes
- `results/step21/run_03/cpu-stress-collector.log`: found, 10677 bytes
- `results/step21/run_03/cpu-stress-kubectl-top.txt`: found, 124 bytes
- `results/step21/run_03/memory-pressure-dashboard.json`: found, 1646 bytes
- `results/step21/run_03/memory-pressure-alerts.json`: found, 423 bytes
- `results/step21/run_03/memory-pressure-workflow.json`: found, 350 bytes
- `results/step21/run_03/memory-pressure-tetragon-tail.jsonl`: found, 1224131 bytes
- `results/step21/run_03/memory-pressure-tetragon-fault-target.jsonl`: found, 277853 bytes
- `results/step21/run_03/memory-pressure-analyzer.log`: found, 14598 bytes
- `results/step21/run_03/memory-pressure-collector.log`: found, 10795 bytes
- `results/step21/run_03/memory-pressure-kubectl-top.txt`: found, 124 bytes

## Scenario Summary

| Scenario | Snapshot status | Alerts | Tetragon lines | anomalous | score | process_exec | process_kprobe | tcp_connect | fault-target |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| exec-storm | complete | 0 | 200 | yes | no | yes | yes | yes | yes |
| network-burst | complete | 1 | 200 | yes | no | yes | yes | yes | yes |
| cpu-stress | complete | 2 | 200 | yes | no | yes | yes | yes | yes |
| memory-pressure | complete | 1 | 200 | yes | no | yes | yes | yes | yes |

## Baseline

- Snapshot status: `complete`
- Alerts: `0`
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
- Alerts: `0`
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
