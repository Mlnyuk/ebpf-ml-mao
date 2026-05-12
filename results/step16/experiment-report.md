# Step 16 Fault Scenario Experiment Report

- Generated at: `2026-04-28T01:48:20.835799+00:00`
- Result directory: `results/step16`

## Input Files

- `results/step16/baseline-dashboard.json`: found, 1609 bytes
- `results/step16/baseline-alerts.json`: found, 423 bytes
- `results/step16/baseline-workflow.json`: found, 317 bytes
- `results/step16/exec-storm-dashboard.json`: found, 1609 bytes
- `results/step16/exec-storm-alerts.json`: found, 423 bytes
- `results/step16/exec-storm-workflow.json`: found, 317 bytes
- `results/step16/exec-storm-analyzer.log`: found, 14576 bytes
- `results/step16/exec-storm-collector.log`: found, 23666 bytes
- `results/step16/network-burst-dashboard.json`: found, 1609 bytes
- `results/step16/network-burst-alerts.json`: found, 423 bytes
- `results/step16/network-burst-workflow.json`: found, 317 bytes
- `results/step16/network-burst-analyzer.log`: found, 14568 bytes
- `results/step16/network-burst-collector.log`: found, 23664 bytes
- `results/step16/cpu-stress-dashboard.json`: found, 1609 bytes
- `results/step16/cpu-stress-alerts.json`: found, 423 bytes
- `results/step16/cpu-stress-workflow.json`: found, 317 bytes
- `results/step16/cpu-stress-analyzer.log`: found, 14565 bytes
- `results/step16/cpu-stress-collector.log`: found, 23664 bytes
- `results/step16/cpu-stress-kubectl-top.txt`: found, 124 bytes
- `results/step16/memory-pressure-dashboard.json`: found, 1609 bytes
- `results/step16/memory-pressure-alerts.json`: found, 423 bytes
- `results/step16/memory-pressure-workflow.json`: found, 317 bytes
- `results/step16/memory-pressure-analyzer.log`: found, 14552 bytes
- `results/step16/memory-pressure-collector.log`: found, 23664 bytes
- `results/step16/memory-pressure-kubectl-top.txt`: found, 124 bytes

## Scenario Summary

| Scenario | Snapshot status | Alerts | anomalous | score | exec | network | cpu | memory |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| exec-storm | complete | 1 | no | no | no | no | no | no |
| network-burst | complete | 1 | no | no | no | no | no | no |
| cpu-stress | complete | 1 | no | no | no | no | no | no |
| memory-pressure | complete | 1 | no | no | no | no | no | no |

## Baseline

- Snapshot status: `complete`
- Alerts: `1`
- `baseline-dashboard.json`: `ok`
- `baseline-alerts.json`: `ok`
- `baseline-workflow.json`: `ok`
- Contains `anomalous`: no
- Contains `score`: no
- Contains `exec`: no
- Contains `network`: no
- Contains `cpu`: no
- Contains `memory`: no

## exec-storm

- Snapshot status: `complete`
- Alerts: `1`
- `exec-storm-dashboard.json`: `ok`
- `exec-storm-alerts.json`: `ok`
- `exec-storm-workflow.json`: `ok`
- Contains `anomalous`: no
- Contains `score`: no
- Contains `exec`: no
- Contains `network`: no
- Contains `cpu`: no
- Contains `memory`: no

## network-burst

- Snapshot status: `complete`
- Alerts: `1`
- `network-burst-dashboard.json`: `ok`
- `network-burst-alerts.json`: `ok`
- `network-burst-workflow.json`: `ok`
- Contains `anomalous`: no
- Contains `score`: no
- Contains `exec`: no
- Contains `network`: no
- Contains `cpu`: no
- Contains `memory`: no

## cpu-stress

- Snapshot status: `complete`
- Alerts: `1`
- `cpu-stress-dashboard.json`: `ok`
- `cpu-stress-alerts.json`: `ok`
- `cpu-stress-workflow.json`: `ok`
- Contains `anomalous`: no
- Contains `score`: no
- Contains `exec`: no
- Contains `network`: no
- Contains `cpu`: no
- Contains `memory`: no

## memory-pressure

- Snapshot status: `complete`
- Alerts: `1`
- `memory-pressure-dashboard.json`: `ok`
- `memory-pressure-alerts.json`: `ok`
- `memory-pressure-workflow.json`: `ok`
- Contains `anomalous`: no
- Contains `score`: no
- Contains `exec`: no
- Contains `network`: no
- Contains `cpu`: no
- Contains `memory`: no

## Notes

- Absence of an anomaly does not necessarily mean pipeline failure. It may indicate that thresholds, feature calibration, scrape timing, or Tetragon/Prometheus coverage need adjustment.
- This report is generated from available files only. Missing or malformed JSON is reported instead of stopping report generation.
- This does not introduce advanced ML, modify eBPF programs, or make the analyzer production-HA.
