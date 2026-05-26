# Step 16 Baseline and Threshold Analysis

- Input directory: `results/step22/run_02`
- CSV output: `results/step22/run_02/threshold-analysis.csv`
- Evaluation scope: workload `fault-target` (matches analyzer `ANALYZER_TARGET_WORKLOAD`)
- Conclusion: baseline score samples are present; choose the lowest threshold with acceptable false-positive and false-negative rates.

## Verdict Summary

| Scenario | Expected | Workflow verdict | Dashboard state | Alerts | Detected |
| --- | --- | --- | --- | ---: | --- |
| baseline | normal | None | ok | 0 | yes |
| exec-storm | fault | anomalous | warning | 1 | yes |
| network-burst | fault | anomalous | warning | 1 | yes |
| cpu-stress | fault | anomalous | warning | 1 | yes |
| memory-pressure | fault | anomalous | warning | 1 | yes |

## Score Distribution (target workload only)

| Scenario | Expected | Target samples | Total scored | Min | Mean | Max | Anomalous (target) | Workflow verdict | Dashboard alerts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| baseline | normal | 1 | 1 | 0.0167 | 0.0167 | 0.0167 | 0 | None | 0 |
| exec-storm | fault | 3 | 3 | 0.6818 | 0.8106 | 1.0000 | 3 | anomalous | 1 |
| network-burst | fault | 6 | 6 | 0.3500 | 0.8917 | 1.0000 | 6 | anomalous | 1 |
| cpu-stress | fault | 3 | 3 | 0.0026 | 0.6675 | 1.0000 | 2 | anomalous | 1 |
| memory-pressure | fault | 2 | 2 | 0.0167 | 0.1833 | 0.3500 | 1 | anomalous | 1 |

## Threshold Candidates (target workload only)

| Threshold | Baseline samples | Fault samples | False positives | FP rate | False negatives | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 1 | 14 | 0 | 0.0000 | 2 | 0.1429 |
| 0.45 | 1 | 14 | 0 | 0.0000 | 4 | 0.2857 |
| 0.55 | 1 | 14 | 0 | 0.0000 | 4 | 0.2857 |
| 0.65 | 1 | 14 | 0 | 0.0000 | 4 | 0.2857 |
| 0.75 | 1 | 14 | 0 | 0.0000 | 5 | 0.3571 |
| 0.85 | 1 | 14 | 0 | 0.0000 | 6 | 0.4286 |
| 0.95 | 1 | 14 | 0 | 0.0000 | 6 | 0.4286 |

## Calibration Rule

- Score samples are filtered to workload `fault-target` so the evaluation matches the analyzer's live target filter.
- Treat `baseline` as the only normal class and all fault scenarios as fault class.
- `score >= threshold` is counted as anomalous.
- Baseline false positives measure clean-normal over-alerting on the target workload.
- Fault false negatives measure missed fault samples on the target workload.
- When per-sample scores for the target workload are absent (collector log tails may not capture every scoring window), use the dashboard workflow verdict and alert summary as the verdict-level evidence.
