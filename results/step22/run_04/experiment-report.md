# Step 16 Fault Scenario Experiment Report

- Generated at: `2026-05-26T04:48:50.622310+00:00`
- Result directory: `results/step22/run_04`

## Input Files

- `results/step22/run_04/baseline-dashboard.json`: found, 1281 bytes
- `results/step22/run_04/baseline-alerts.json`: found, 231 bytes
- `results/step22/run_04/baseline-workflow.json`: found, 206 bytes
- `results/step22/run_04/baseline-tetragon-tail.jsonl`: found, 1220414 bytes
- `results/step22/run_04/baseline-tetragon-fault-target.jsonl`: found, 274315 bytes
- `results/step22/run_04/baseline-analyzer.log`: found, 8763 bytes
- `results/step22/run_04/baseline-collector.log`: found, 18956 bytes
- `results/step22/run_04/exec-storm-dashboard.json`: found, 1305 bytes
- `results/step22/run_04/exec-storm-alerts.json`: found, 231 bytes
- `results/step22/run_04/exec-storm-workflow.json`: found, 226 bytes
- `results/step22/run_04/exec-storm-tetragon-tail.jsonl`: found, 1227023 bytes
- `results/step22/run_04/exec-storm-tetragon-fault-target.jsonl`: found, 257217 bytes
- `results/step22/run_04/exec-storm-analyzer.log`: found, 2616 bytes
- `results/step22/run_04/exec-storm-collector.log`: found, 18890 bytes
- `results/step22/run_04/network-burst-dashboard.json`: found, 1315 bytes
- `results/step22/run_04/network-burst-alerts.json`: found, 231 bytes
- `results/step22/run_04/network-burst-workflow.json`: found, 229 bytes
- `results/step22/run_04/network-burst-tetragon-tail.jsonl`: found, 1227163 bytes
- `results/step22/run_04/network-burst-tetragon-fault-target.jsonl`: found, 270552 bytes
- `results/step22/run_04/network-burst-analyzer.log`: found, 5588 bytes
- `results/step22/run_04/network-burst-collector.log`: found, 19516 bytes
- `results/step22/run_04/cpu-stress-dashboard.json`: found, 1516 bytes
- `results/step22/run_04/cpu-stress-alerts.json`: found, 433 bytes
- `results/step22/run_04/cpu-stress-workflow.json`: found, 233 bytes
- `results/step22/run_04/cpu-stress-tetragon-tail.jsonl`: found, 1206517 bytes
- `results/step22/run_04/cpu-stress-tetragon-fault-target.jsonl`: found, 280512 bytes
- `results/step22/run_04/cpu-stress-analyzer.log`: found, 6790 bytes
- `results/step22/run_04/cpu-stress-collector.log`: found, 19628 bytes
- `results/step22/run_04/cpu-stress-kubectl-top.txt`: found, 124 bytes
- `results/step22/run_04/memory-pressure-dashboard.json`: found, 1316 bytes
- `results/step22/run_04/memory-pressure-alerts.json`: found, 231 bytes
- `results/step22/run_04/memory-pressure-workflow.json`: found, 230 bytes
- `results/step22/run_04/memory-pressure-tetragon-tail.jsonl`: found, 1225556 bytes
- `results/step22/run_04/memory-pressure-tetragon-fault-target.jsonl`: found, 274678 bytes
- `results/step22/run_04/memory-pressure-analyzer.log`: found, 8137 bytes
- `results/step22/run_04/memory-pressure-collector.log`: found, 19852 bytes
- `results/step22/run_04/memory-pressure-kubectl-top.txt`: found, 124 bytes

## Scenario Summary

| Scenario | Snapshot status | Alerts | Tetragon lines | anomalous | score | process_exec | process_kprobe | tcp_connect | fault-target |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| exec-storm | complete | 0 | 200 | yes | no | yes | yes | yes | yes |
| network-burst | complete | 0 | 200 | yes | no | yes | yes | yes | yes |
| cpu-stress | complete | 1 | 200 | yes | no | yes | yes | yes | yes |
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
