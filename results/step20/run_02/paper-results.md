# Step 16 Paper Result Tables

- Input directory: `results/step20/run_02`
- CSV output: `results/step20/run_02/paper-results.csv`

## Scenario Detection Table

| Scenario | Alerts | Tetragon lines | fault-target lines | Score min | Score mean | Score max | Detected | Main feature changes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| exec-storm | 2 | 200 | 50 | 0.7391 | 0.8214 | 1.0000 | yes | event_count=20.00, unique_pids=1.00, network_event_count=0.00 |
| network-burst | 2 | 200 | 50 | 1.0000 | 1.0000 | 1.0000 | yes | event_count=57.00, network_event_count=51.00, unique_pids=3.00 |
| cpu-stress | 2 | 7 | 6 | 0.7050 | 0.8525 | 1.0000 | yes | event_count=20.00, network_event_count=11.00, unique_pids=1.00 |
| memory-pressure | 2 | 143 | 33 | 0.7732 | 0.7732 | 0.7732 | yes | event_count=29.00, network_event_count=20.00, unique_pids=3.00 |

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
