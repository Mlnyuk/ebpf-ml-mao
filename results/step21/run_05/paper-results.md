# Step 16 Paper Result Tables

- Input directory: `results/step21/run_05`
- CSV output: `results/step21/run_05/paper-results.csv`

## Scenario Detection Table

| Scenario | Alerts | Tetragon lines | fault-target lines | Score min | Score mean | Score max | Detected | Main feature changes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| exec-storm | 1 | 200 | 50 | 0.4000 | 0.6114 | 0.8864 | yes | event_count=33.00, exec_count=18.00, unique_pids=11.00 |
| network-burst | 1 | 200 | 50 | 0.0085 | 0.6417 | 1.0000 | yes | event_count=20.00, exec_count=12.00, network_event_count=7.00 |
| cpu-stress | 1 | 200 | 50 | 0.0026 | 0.6297 | 1.0000 | yes | event_count=29.00, network_event_count=23.00, unique_pids=2.00 |
| memory-pressure | 2 | 200 | 50 | 0.0026 | 0.0026 | 0.0026 | yes | event_count=29.00, network_event_count=23.00, unique_pids=2.00 |

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
