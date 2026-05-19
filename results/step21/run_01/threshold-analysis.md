# Step 16 Baseline and Threshold Analysis

- Input directory: `results/step21/run_01`
- CSV output: `results/step21/run_01/threshold-analysis.csv`
- Evaluation scope: workload `fault-target` (matches analyzer `ANALYZER_TARGET_WORKLOAD`)
- Conclusion: baseline workflow verdict is anomalous, so the existing baseline artifact is contaminated and must not be used as a clean normal distribution.

## Verdict Summary

| Scenario | Expected | Workflow verdict | Dashboard state | Alerts | Detected |
| --- | --- | --- | --- | ---: | --- |
| baseline | normal | anomalous | warning | 1 | false positive |
| exec-storm | fault | normal | ok | 0 | no |
| network-burst | fault | anomalous | warning | 2 | yes |
| cpu-stress | fault | normal | warning | 1 | no |
| memory-pressure | fault | normal | warning | 1 | no |

## Score Distribution (target workload only)

| Scenario | Expected | Target samples | Total scored | Min | Mean | Max | Anomalous (target) | Workflow verdict | Dashboard alerts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| baseline | normal | 1 | 1 | 0.0085 | 0.0085 | 0.0085 | 0 | anomalous | 1 |
| exec-storm | fault | 5 | 5 | 0.0085 | 0.3481 | 0.6818 | 1 | normal | 0 |
| network-burst | fault | 6 | 6 | 0.0059 | 0.8010 | 1.0000 | 5 | anomalous | 2 |
| cpu-stress | fault | 2 | 2 | 0.0182 | 0.5091 | 1.0000 | 1 | normal | 1 |
| memory-pressure | fault | 0 | 3 | n/a | n/a | n/a | 0 | normal | 1 |

## Threshold Candidates (target workload only)

| Threshold | Baseline samples | Fault samples | False positives | FP rate | False negatives | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 1 | 13 | 0 | 0.0000 | 3 | 0.2308 |
| 0.45 | 1 | 13 | 0 | 0.0000 | 6 | 0.4615 |
| 0.55 | 1 | 13 | 0 | 0.0000 | 6 | 0.4615 |
| 0.65 | 1 | 13 | 0 | 0.0000 | 6 | 0.4615 |
| 0.75 | 1 | 13 | 0 | 0.0000 | 7 | 0.5385 |
| 0.85 | 1 | 13 | 0 | 0.0000 | 8 | 0.6154 |
| 0.95 | 1 | 13 | 0 | 0.0000 | 8 | 0.6154 |

## Calibration Rule

- Score samples are filtered to workload `fault-target` so the evaluation matches the analyzer's live target filter.
- Treat `baseline` as the only normal class and all fault scenarios as fault class.
- `score >= threshold` is counted as anomalous.
- Baseline false positives measure clean-normal over-alerting on the target workload.
- Fault false negatives measure missed fault samples on the target workload.
- When per-sample scores for the target workload are absent (collector log tails may not capture every scoring window), use the dashboard workflow verdict and alert summary as the verdict-level evidence.
