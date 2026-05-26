# Step 20 Aggregated Threshold Analysis

- Base directory: `results/step22`
- Runs aggregated: 5 (run_01, run_02, run_03, run_04, run_05)
- Detection CSV: `results/step22/aggregated-detection.csv`
- Threshold CSV: `results/step22/aggregated-threshold-analysis.csv`

## Per-Scenario Detection Rate

| Scenario | Expected | Runs | Detected | Detection rate |
| --- | --- | ---: | ---: | ---: |
| baseline | normal | 5 | 5 | 100.0% |
| exec-storm | fault | 5 | 5 | 100.0% |
| network-burst | fault | 5 | 5 | 100.0% |
| cpu-stress | fault | 5 | 5 | 100.0% |
| memory-pressure | fault | 5 | 2 | 40.0% |

## Per-Scenario fault-target Score Distribution (all samples pooled)

| Scenario | Samples | Min | Mean | Std | Max | Per-run mean (mean ± std) |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| baseline | 8 | 0.0026 | 0.0103 | 0.0047 | 0.0182 | 0.0098 ± 0.0046 |
| exec-storm | 19 | 0.0026 | 0.5377 | 0.3516 | 1.0000 | 0.5513 ± 0.1936 |
| network-burst | 30 | 0.0026 | 0.7349 | 0.3502 | 1.0000 | 0.7349 ± 0.0913 |
| cpu-stress | 11 | 0.0026 | 0.7208 | 0.3882 | 1.0000 | 0.7262 ± 0.1520 |
| memory-pressure | 13 | 0.0026 | 0.2240 | 0.3147 | 0.8864 | 0.2068 ± 0.1104 |

## Threshold Sweep (pooled samples)

| Threshold | Baseline samples | Fault samples | FP | FP rate | FN | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 8 | 73 | 0 | 0.0000 | 17 | 0.2329 |
| 0.45 | 8 | 73 | 0 | 0.0000 | 33 | 0.4521 |
| 0.55 | 8 | 73 | 0 | 0.0000 | 34 | 0.4658 |
| 0.65 | 8 | 73 | 0 | 0.0000 | 34 | 0.4658 |
| 0.75 | 8 | 73 | 0 | 0.0000 | 37 | 0.5068 |
| 0.85 | 8 | 73 | 0 | 0.0000 | 42 | 0.5753 |
| 0.95 | 8 | 73 | 0 | 0.0000 | 46 | 0.6301 |

## Calibration Result

- Aggregated baseline samples: 8
- Aggregated fault samples: 73
- Optimal threshold (FP=0 and FN=0): no single threshold satisfies both; pick the threshold that matches the desired FP/FN trade-off
