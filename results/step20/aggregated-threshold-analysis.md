# Step 20 Aggregated Threshold Analysis

- Base directory: `results/step20`
- Runs aggregated: 5 (run_01, run_02, run_03, run_04, run_05)
- Detection CSV: `results/step20/aggregated-detection.csv`
- Threshold CSV: `results/step20/aggregated-threshold-analysis.csv`

## Per-Scenario Detection Rate

| Scenario | Expected | Runs | Detected | Detection rate |
| --- | --- | ---: | ---: | ---: |
| baseline | normal | 5 | 0 | 0.0% |
| exec-storm | fault | 5 | 5 | 100.0% |
| network-burst | fault | 5 | 5 | 100.0% |
| cpu-stress | fault | 5 | 5 | 100.0% |
| memory-pressure | fault | 5 | 5 | 100.0% |

## Per-Scenario fault-target Score Distribution (all samples pooled)

| Scenario | Samples | Min | Mean | Std | Max | Per-run mean (mean ± std) |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| baseline | 12 | 0.4664 | 0.6690 | 0.1934 | 1.0000 | 0.6913 ± 0.1299 |
| exec-storm | 18 | 0.4323 | 0.7044 | 0.1578 | 1.0000 | 0.7147 ± 0.1253 |
| network-burst | 29 | 0.5937 | 0.9701 | 0.0853 | 1.0000 | 0.9745 ± 0.0402 |
| cpu-stress | 9 | 0.7050 | 0.9672 | 0.0927 | 1.0000 | 0.9705 ± 0.0590 |
| memory-pressure | 3 | 0.7732 | 0.7732 | 0.0000 | 0.7732 | 0.7732 ± 0.0000 |

## Threshold Sweep (pooled samples)

| Threshold | Baseline samples | Fault samples | FP | FP rate | FN | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 12 | 59 | 12 | 1.0000 | 0 | 0.0000 |
| 0.45 | 12 | 59 | 12 | 1.0000 | 1 | 0.0169 |
| 0.55 | 12 | 59 | 8 | 0.6667 | 4 | 0.0678 |
| 0.65 | 12 | 59 | 5 | 0.4167 | 7 | 0.1186 |
| 0.75 | 12 | 59 | 3 | 0.2500 | 12 | 0.2034 |
| 0.85 | 12 | 59 | 3 | 0.2500 | 21 | 0.3559 |
| 0.95 | 12 | 59 | 2 | 0.1667 | 25 | 0.4237 |

## Calibration Result

- Aggregated baseline samples: 12
- Aggregated fault samples: 59
- Optimal threshold (FP=0 and FN=0): no single threshold satisfies both; pick the threshold that matches the desired FP/FN trade-off
