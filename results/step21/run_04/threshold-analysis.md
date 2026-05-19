# Step 16 Baseline and Threshold Analysis

- Input directory: `results/step21/run_04`
- CSV output: `results/step21/run_04/threshold-analysis.csv`
- Evaluation scope: workload `fault-target` (matches analyzer `ANALYZER_TARGET_WORKLOAD`)
- Conclusion: baseline score samples are present; choose the lowest threshold with acceptable false-positive and false-negative rates.

## Verdict Summary

| Scenario | Expected | Workflow verdict | Dashboard state | Alerts | Detected |
| --- | --- | --- | --- | ---: | --- |
| baseline | normal | normal | ok | 0 | yes |
| exec-storm | fault | normal | ok | 0 | no |
| network-burst | fault | normal | warning | 1 | no |
| cpu-stress | fault | normal | warning | 1 | no |
| memory-pressure | fault | normal | warning | 1 | no |

## Score Distribution (target workload only)

| Scenario | Expected | Target samples | Total scored | Min | Mean | Max | Anomalous (target) | Workflow verdict | Dashboard alerts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| baseline | normal | 1 | 1 | 0.0182 | 0.0182 | 0.0182 | 0 | normal | 0 |
| exec-storm | fault | 4 | 4 | 0.0026 | 0.3779 | 0.6818 | 2 | normal | 0 |
| network-burst | fault | 6 | 6 | 0.0085 | 0.8347 | 1.0000 | 5 | normal | 1 |
| cpu-stress | fault | 2 | 2 | 0.0085 | 0.5042 | 1.0000 | 1 | normal | 1 |
| memory-pressure | fault | 2 | 2 | 0.0085 | 0.4474 | 0.8864 | 1 | normal | 1 |

## Threshold Candidates (target workload only)

| Threshold | Baseline samples | Fault samples | False positives | FP rate | False negatives | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 1 | 14 | 0 | 0.0000 | 4 | 0.2857 |
| 0.45 | 1 | 14 | 0 | 0.0000 | 5 | 0.3571 |
| 0.55 | 1 | 14 | 0 | 0.0000 | 6 | 0.4286 |
| 0.65 | 1 | 14 | 0 | 0.0000 | 6 | 0.4286 |
| 0.75 | 1 | 14 | 0 | 0.0000 | 7 | 0.5000 |
| 0.85 | 1 | 14 | 0 | 0.0000 | 7 | 0.5000 |
| 0.95 | 1 | 14 | 0 | 0.0000 | 8 | 0.5714 |

## Calibration Rule

- Score samples are filtered to workload `fault-target` so the evaluation matches the analyzer's live target filter.
- Treat `baseline` as the only normal class and all fault scenarios as fault class.
- `score >= threshold` is counted as anomalous.
- Baseline false positives measure clean-normal over-alerting on the target workload.
- Fault false negatives measure missed fault samples on the target workload.
- When per-sample scores for the target workload are absent (collector log tails may not capture every scoring window), use the dashboard workflow verdict and alert summary as the verdict-level evidence.
