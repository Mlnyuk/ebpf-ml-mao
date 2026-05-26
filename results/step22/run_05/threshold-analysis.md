# Step 16 Baseline and Threshold Analysis

- Input directory: `results/step22/run_05`
- CSV output: `results/step22/run_05/threshold-analysis.csv`
- Evaluation scope: workload `fault-target` (matches analyzer `ANALYZER_TARGET_WORKLOAD`)
- Conclusion: baseline score samples are present; choose the lowest threshold with acceptable false-positive and false-negative rates.

## Verdict Summary

| Scenario | Expected | Workflow verdict | Dashboard state | Alerts | Detected |
| --- | --- | --- | --- | ---: | --- |
| baseline | normal | normal | ok | 0 | yes |
| exec-storm | fault | normal | ok | 0 | no |
| network-burst | fault | normal | ok | 0 | no |
| cpu-stress | fault | anomalous | warning | 1 | yes |
| memory-pressure | fault | anomalous | warning | 1 | yes |

## Score Distribution (target workload only)

| Scenario | Expected | Target samples | Total scored | Min | Mean | Max | Anomalous (target) | Workflow verdict | Dashboard alerts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| baseline | normal | 1 | 1 | 0.0026 | 0.0026 | 0.0026 | 0 | normal | 0 |
| exec-storm | fault | 4 | 4 | 0.0085 | 0.4624 | 0.8864 | 3 | normal | 0 |
| network-burst | fault | 6 | 6 | 0.0182 | 0.6614 | 1.0000 | 5 | normal | 0 |
| cpu-stress | fault | 2 | 2 | 0.3500 | 0.6750 | 1.0000 | 2 | anomalous | 1 |
| memory-pressure | fault | 3 | 3 | 0.0085 | 0.2362 | 0.3500 | 2 | anomalous | 1 |

## Threshold Candidates (target workload only)

| Threshold | Baseline samples | Fault samples | False positives | FP rate | False negatives | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 1 | 15 | 0 | 0.0000 | 3 | 0.2000 |
| 0.45 | 1 | 15 | 0 | 0.0000 | 8 | 0.5333 |
| 0.55 | 1 | 15 | 0 | 0.0000 | 9 | 0.6000 |
| 0.65 | 1 | 15 | 0 | 0.0000 | 9 | 0.6000 |
| 0.75 | 1 | 15 | 0 | 0.0000 | 9 | 0.6000 |
| 0.85 | 1 | 15 | 0 | 0.0000 | 11 | 0.7333 |
| 0.95 | 1 | 15 | 0 | 0.0000 | 12 | 0.8000 |

## Calibration Rule

- Score samples are filtered to workload `fault-target` so the evaluation matches the analyzer's live target filter.
- Treat `baseline` as the only normal class and all fault scenarios as fault class.
- `score >= threshold` is counted as anomalous.
- Baseline false positives measure clean-normal over-alerting on the target workload.
- Fault false negatives measure missed fault samples on the target workload.
- When per-sample scores for the target workload are absent (collector log tails may not capture every scoring window), use the dashboard workflow verdict and alert summary as the verdict-level evidence.
