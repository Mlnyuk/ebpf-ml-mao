# Step 16 Paper Result Tables

- Input directory: `results/step21/run_02`
- CSV output: `results/step21/run_02/paper-results.csv`

## Scenario Detection Table

| Scenario | Alerts | Tetragon lines | fault-target lines | Score min | Score mean | Score max | Detected | Main feature changes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| exec-storm | 1 | 9 | 7 | 0.0026 | 0.6313 | 0.8864 | yes | network_event_count=23.00, event_count=23.00, unique_pids=1.00 |
| network-burst | 1 | 200 | 50 | 0.0085 | 0.8234 | 1.0000 | yes | event_count=44.00, exec_count=25.00, unique_pids=8.00 |
| cpu-stress | 2 | 200 | 50 | 0.0026 | 0.5013 | 1.0000 | yes | event_count=16.00, network_event_count=15.00, exec_count=8.00 |
| memory-pressure | 1 | 161 | 14 | 0.0097 | 0.4481 | 0.8864 | yes | event_count=16.00, network_event_count=15.00, exec_count=8.00 |

## Prometheus + Grafana Comparison

| Item | Prometheus + Grafana | eBPF/Tetragon + ML analyzer |
| --- | --- | --- |
| Detection target | Metric time series | Metric plus kernel event context |
| Unit of judgment | Human dashboard inspection | Workload-level anomaly score and verdict |
| Fault signal | CPU, memory, connection counters | process_exec, process_kprobe, tcp_connect, resource features |
| Explainability | Panel changes require manual interpretation | Report includes feature window, score, verdict, and Tetragon evidence |
| Automation | Alert rules and dashboards | API/UI reports with scenario-level detection summary |

## Result Interpretation Draft

Step 16 shows that Tetragon event coverage is present for all four injected fault scenarios, while the analyzer converts the observed event/resource windows into anomaly scores and verdicts. The result table should be read together with the baseline calibration report because a contaminated baseline can inflate false-positive risk even when fault scenarios are detectable.
