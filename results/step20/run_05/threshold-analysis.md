# Step 16 Baseline and Threshold Analysis

- Input directory: `results/step20/run_05`
- CSV output: `results/step20/run_05/threshold-analysis.csv`
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
| baseline | normal | 2 | 2 | 0.7391 | 0.8696 | 1.0000 | 2 | anomalous | 1 |
| exec-storm | fault | 3 | 3 | 0.7050 | 0.7959 | 0.8755 | 3 | normal | 1 |
| network-burst | fault | 6 | 6 | 0.8573 | 0.9762 | 1.0000 | 6 | anomalous | 2 |
| cpu-stress | fault | 2 | 2 | 1.0000 | 1.0000 | 1.0000 | 2 | anomalous | 2 |
| memory-pressure | fault | 1 | 1 | 0.7732 | 0.7732 | 0.7732 | 1 | anomalous | 2 |

## Threshold Candidates (target workload only)

| Threshold | Baseline samples | Fault samples | False positives | FP rate | False negatives | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 2 | 12 | 2 | 1.0000 | 0 | 0.0000 |
| 0.45 | 2 | 12 | 2 | 1.0000 | 0 | 0.0000 |
| 0.55 | 2 | 12 | 2 | 1.0000 | 0 | 0.0000 |
| 0.65 | 2 | 12 | 2 | 1.0000 | 0 | 0.0000 |
| 0.75 | 2 | 12 | 1 | 0.5000 | 1 | 0.0833 |
| 0.85 | 2 | 12 | 1 | 0.5000 | 3 | 0.2500 |
| 0.95 | 2 | 12 | 1 | 0.5000 | 5 | 0.4167 |

## Calibration Rule

- Score samples are filtered to workload `fault-target` so the evaluation matches the analyzer's live target filter.
- Treat `baseline` as the only normal class and all fault scenarios as fault class.
- `score >= threshold` is counted as anomalous.
- Baseline false positives measure clean-normal over-alerting on the target workload.
- Fault false negatives measure missed fault samples on the target workload.
- When per-sample scores for the target workload are absent (collector log tails may not capture every scoring window), use the dashboard workflow verdict and alert summary as the verdict-level evidence.
