# Step 16 Baseline and Threshold Analysis

- Input directory: `results/step22/run_01`
- CSV output: `results/step22/run_01/threshold-analysis.csv`
- Evaluation scope: workload `fault-target` (matches analyzer `ANALYZER_TARGET_WORKLOAD`)
- Conclusion: baseline score samples are present; choose the lowest threshold with acceptable false-positive and false-negative rates.

## Verdict Summary

| Scenario | Expected | Workflow verdict | Dashboard state | Alerts | Detected |
| --- | --- | --- | --- | ---: | --- |
| baseline | normal | normal | ok | 0 | yes |
| exec-storm | fault | anomalous | warning | 1 | yes |
| network-burst | fault | anomalous | warning | 1 | yes |
| cpu-stress | fault | anomalous | warning | 1 | yes |
| memory-pressure | fault | normal | ok | 0 | no |

## Score Distribution (target workload only)

| Scenario | Expected | Target samples | Total scored | Min | Mean | Max | Anomalous (target) | Workflow verdict | Dashboard alerts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| baseline | normal | 3 | 3 | 0.0085 | 0.0117 | 0.0182 | 0 | normal | 0 |
| exec-storm | fault | 4 | 4 | 0.0226 | 0.7557 | 1.0000 | 3 | anomalous | 1 |
| network-burst | fault | 6 | 6 | 0.3500 | 0.7583 | 1.0000 | 6 | anomalous | 1 |
| cpu-stress | fault | 2 | 2 | 0.6818 | 0.8409 | 1.0000 | 2 | anomalous | 1 |
| memory-pressure | fault | 3 | 3 | 0.0085 | 0.3044 | 0.8864 | 1 | normal | 0 |

## Threshold Candidates (target workload only)

| Threshold | Baseline samples | Fault samples | False positives | FP rate | False negatives | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 3 | 15 | 0 | 0.0000 | 3 | 0.2000 |
| 0.45 | 3 | 15 | 0 | 0.0000 | 5 | 0.3333 |
| 0.55 | 3 | 15 | 0 | 0.0000 | 5 | 0.3333 |
| 0.65 | 3 | 15 | 0 | 0.0000 | 5 | 0.3333 |
| 0.75 | 3 | 15 | 0 | 0.0000 | 6 | 0.4000 |
| 0.85 | 3 | 15 | 0 | 0.0000 | 7 | 0.4667 |
| 0.95 | 3 | 15 | 0 | 0.0000 | 8 | 0.5333 |

## Calibration Rule

- Score samples are filtered to workload `fault-target` so the evaluation matches the analyzer's live target filter.
- Treat `baseline` as the only normal class and all fault scenarios as fault class.
- `score >= threshold` is counted as anomalous.
- Baseline false positives measure clean-normal over-alerting on the target workload.
- Fault false negatives measure missed fault samples on the target workload.
- When per-sample scores for the target workload are absent (collector log tails may not capture every scoring window), use the dashboard workflow verdict and alert summary as the verdict-level evidence.
