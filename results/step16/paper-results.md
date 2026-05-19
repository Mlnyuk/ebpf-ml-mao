# Step 16 Paper Result Tables

- Input directory: `results/step16`
- CSV output: `results/step16/paper-results.csv`

## Scenario Detection Table

| Scenario | Alerts | Tetragon lines | fault-target lines | Score min | Score mean | Score max | Detected | Main feature changes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| exec-storm | 2 | 142 | 6 | 0.4323 | 0.7693 | 1.0000 | yes | event_count=51.00, unique_pids=26.00, exec_count=25.00 |
| network-burst | 2 | 200 | 50 | 1.0000 | 1.0000 | 1.0000 | yes | event_count=78.00, exec_count=40.00, unique_pids=20.00 |
| cpu-stress | 2 | 200 | 50 | 1.0000 | 1.0000 | 1.0000 | yes | event_count=100.00, exec_count=75.00, unique_pids=26.00 |
| memory-pressure | 2 | 200 | 50 | 0.7732 | 0.7732 | 0.7732 | yes | event_count=18.00, exec_count=13.00, unique_pids=5.00 |

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
