# Step 16 Paper Result Tables

- Input directory: `results/step22/run_04`
- CSV output: `results/step22/run_04/paper-results.csv`

## Scenario Detection Table

| Scenario | Alerts | Tetragon lines | fault-target lines | Score min | Score mean | Score max | Detected | Main feature changes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| exec-storm | 0 | 200 | 50 | 0.0182 | 0.3500 | 0.6818 | yes | event_count=34.00, unique_pids=11.00, exec_count=10.00 |
| network-burst | 0 | 200 | 50 | 0.0026 | 0.7338 | 1.0000 | yes | event_count=63.00, exec_count=16.00, unique_pids=11.00 |
| cpu-stress | 1 | 200 | 50 | 0.8864 | 0.9432 | 1.0000 | yes | event_count=100.00, exec_count=38.00, unique_pids=13.00 |
| memory-pressure | 0 | 200 | 50 | 0.0085 | 0.3044 | 0.8864 | yes | event_count=38.00, exec_count=13.00, unique_pids=6.00 |

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
