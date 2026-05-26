# Step 16 Fault Scenario Experiment Report

- Generated at: `2026-05-26T04:40:11.177989+00:00`
- Result directory: `results/step22/run_03`

## Input Files

- `results/step22/run_03/baseline-dashboard.json`: found, 1282 bytes
- `results/step22/run_03/baseline-alerts.json`: found, 231 bytes
- `results/step22/run_03/baseline-workflow.json`: found, 206 bytes
- `results/step22/run_03/baseline-tetragon-tail.jsonl`: found, 1198631 bytes
- `results/step22/run_03/baseline-tetragon-fault-target.jsonl`: found, 270928 bytes
- `results/step22/run_03/baseline-analyzer.log`: found, 641 bytes
- `results/step22/run_03/baseline-collector.log`: found, 17948 bytes
- `results/step22/run_03/exec-storm-dashboard.json`: found, 1305 bytes
- `results/step22/run_03/exec-storm-alerts.json`: found, 231 bytes
- `results/step22/run_03/exec-storm-workflow.json`: found, 226 bytes
- `results/step22/run_03/exec-storm-tetragon-tail.jsonl`: found, 1227162 bytes
- `results/step22/run_03/exec-storm-tetragon-fault-target.jsonl`: found, 257205 bytes
- `results/step22/run_03/exec-storm-analyzer.log`: found, 2833 bytes
- `results/step22/run_03/exec-storm-collector.log`: found, 18172 bytes
- `results/step22/run_03/network-burst-dashboard.json`: found, 1315 bytes
- `results/step22/run_03/network-burst-alerts.json`: found, 231 bytes
- `results/step22/run_03/network-burst-workflow.json`: found, 229 bytes
- `results/step22/run_03/network-burst-tetragon-tail.jsonl`: found, 438703 bytes
- `results/step22/run_03/network-burst-tetragon-fault-target.jsonl`: found, 53966 bytes
- `results/step22/run_03/network-burst-analyzer.log`: found, 5875 bytes
- `results/step22/run_03/network-burst-collector.log`: found, 18508 bytes
- `results/step22/run_03/cpu-stress-dashboard.json`: found, 1515 bytes
- `results/step22/run_03/cpu-stress-alerts.json`: found, 433 bytes
- `results/step22/run_03/cpu-stress-workflow.json`: found, 232 bytes
- `results/step22/run_03/cpu-stress-tetragon-tail.jsonl`: found, 1091670 bytes
- `results/step22/run_03/cpu-stress-tetragon-fault-target.jsonl`: found, 97554 bytes
- `results/step22/run_03/cpu-stress-analyzer.log`: found, 7002 bytes
- `results/step22/run_03/cpu-stress-collector.log`: found, 18732 bytes
- `results/step22/run_03/cpu-stress-kubectl-top.txt`: found, 124 bytes
- `results/step22/run_03/memory-pressure-dashboard.json`: found, 1315 bytes
- `results/step22/run_03/memory-pressure-alerts.json`: found, 231 bytes
- `results/step22/run_03/memory-pressure-workflow.json`: found, 229 bytes
- `results/step22/run_03/memory-pressure-tetragon-tail.jsonl`: found, 1230971 bytes
- `results/step22/run_03/memory-pressure-tetragon-fault-target.jsonl`: found, 275411 bytes
- `results/step22/run_03/memory-pressure-analyzer.log`: found, 8279 bytes
- `results/step22/run_03/memory-pressure-collector.log`: found, 18844 bytes
- `results/step22/run_03/memory-pressure-kubectl-top.txt`: found, 124 bytes

## Scenario Summary

| Scenario | Snapshot status | Alerts | Tetragon lines | anomalous | score | process_exec | process_kprobe | tcp_connect | fault-target |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| exec-storm | complete | 0 | 200 | yes | no | yes | yes | yes | yes |
| network-burst | complete | 0 | 74 | yes | no | yes | yes | yes | yes |
| cpu-stress | complete | 1 | 180 | yes | no | yes | yes | yes | yes |
| memory-pressure | complete | 0 | 200 | yes | no | yes | yes | yes | yes |

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
- Alerts: `0`
- Tetragon tail lines: `74`
- Tetragon fault-target lines: `10`
- `network-burst-dashboard.json`: `ok`
- `network-burst-alerts.json`: `ok`
- `network-burst-workflow.json`: `ok`
- `network-burst-tetragon-tail.jsonl`: `ok`
- `network-burst-tetragon-fault-target.jsonl`: `ok`
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

## cpu-stress

- Snapshot status: `complete`
- Alerts: `1`
- Tetragon tail lines: `180`
- Tetragon fault-target lines: `18`
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
- Alerts: `0`
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
