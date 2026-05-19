# Step 20 Aggregated Threshold Analysis

- Base directory: `results/step21`
- Runs aggregated: 5 (run_01, run_02, run_03, run_04, run_05)
- Detection CSV: `results/step21/aggregated-detection.csv`
- Threshold CSV: `results/step21/aggregated-threshold-analysis.csv`

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
| baseline | 5 | 0.0026 | 0.0081 | 0.0057 | 0.0182 | 0.0081 ± 0.0057 |
| exec-storm | 21 | 0.0026 | 0.4801 | 0.2945 | 0.8864 | 0.4867 ± 0.1166 |
| network-burst | 29 | 0.0059 | 0.7853 | 0.3744 | 1.0000 | 0.7805 ± 0.0706 |
| cpu-stress | 11 | 0.0026 | 0.5383 | 0.4861 | 1.0000 | 0.5291 ± 0.0504 |
| memory-pressure | 6 | 0.0026 | 0.2994 | 0.4151 | 0.8864 | 0.2252 ± 0.2226 |

## Threshold Sweep (pooled samples)

| Threshold | Baseline samples | Fault samples | FP | FP rate | FN | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 5 | 67 | 0 | 0.0000 | 18 | 0.2687 |
| 0.45 | 5 | 67 | 0 | 0.0000 | 24 | 0.3582 |
| 0.55 | 5 | 67 | 0 | 0.0000 | 28 | 0.4179 |
| 0.65 | 5 | 67 | 0 | 0.0000 | 28 | 0.4179 |
| 0.75 | 5 | 67 | 0 | 0.0000 | 31 | 0.4627 |
| 0.85 | 5 | 67 | 0 | 0.0000 | 35 | 0.5224 |
| 0.95 | 5 | 67 | 0 | 0.0000 | 43 | 0.6418 |

## Calibration Result

- Aggregated baseline samples: 5
- Aggregated fault samples: 67
- Optimal threshold (FP=0 and FN=0): no single threshold satisfies both; pick the threshold that matches the desired FP/FN trade-off
