# Step 16 Baseline and Threshold Analysis

- Input directory: `results/step20/run_01`
- CSV output: `results/step20/run_01/threshold-analysis.csv`
- Evaluation scope: workload `fault-target` (matches analyzer `ANALYZER_TARGET_WORKLOAD`)
- Conclusion: baseline workflow verdict is anomalous, so the existing baseline artifact is contaminated and must not be used as a clean normal distribution.

## Verdict Summary

| Scenario | Expected | Workflow verdict | Dashboard state | Alerts | Detected |
| --- | --- | --- | --- | ---: | --- |
| baseline | normal | anomalous | warning | 1 | false positive |
| exec-storm | fault | normal | warning | 1 | no |
| network-burst | fault | anomalous | warning | 2 | yes |
| cpu-stress | fault | anomalous | warning | 2 | yes |
| memory-pressure | fault | anomalous | warning | 2 | yes |

## Score Distribution (target workload only)

| Scenario | Expected | Target samples | Total scored | Min | Mean | Max | Anomalous (target) | Workflow verdict | Dashboard alerts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| baseline | normal | 3 | 3 | 0.4664 | 0.6028 | 0.8755 | 3 | anomalous | 1 |
| exec-storm | fault | 4 | 4 | 0.4323 | 0.6283 | 0.8073 | 3 | normal | 1 |
| network-burst | fault | 5 | 5 | 1.0000 | 1.0000 | 1.0000 | 5 | anomalous | 2 |
| cpu-stress | fault | 2 | 2 | 1.0000 | 1.0000 | 1.0000 | 2 | anomalous | 2 |
| memory-pressure | fault | 0 | 3 | n/a | n/a | n/a | 0 | anomalous | 2 |

## Threshold Candidates (target workload only)

| Threshold | Baseline samples | Fault samples | False positives | FP rate | False negatives | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 3 | 11 | 3 | 1.0000 | 0 | 0.0000 |
| 0.45 | 3 | 11 | 3 | 1.0000 | 1 | 0.0909 |
| 0.55 | 3 | 11 | 1 | 0.3333 | 1 | 0.0909 |
| 0.65 | 3 | 11 | 1 | 0.3333 | 2 | 0.1818 |
| 0.75 | 3 | 11 | 1 | 0.3333 | 3 | 0.2727 |
| 0.85 | 3 | 11 | 1 | 0.3333 | 4 | 0.3636 |
| 0.95 | 3 | 11 | 0 | 0.0000 | 4 | 0.3636 |

## Calibration Rule

- Score samples are filtered to workload `fault-target` so the evaluation matches the analyzer's live target filter.
- Treat `baseline` as the only normal class and all fault scenarios as fault class.
- `score >= threshold` is counted as anomalous.
- Baseline false positives measure clean-normal over-alerting on the target workload.
- Fault false negatives measure missed fault samples on the target workload.
- When per-sample scores for the target workload are absent (collector log tails may not capture every scoring window), use the dashboard workflow verdict and alert summary as the verdict-level evidence.
