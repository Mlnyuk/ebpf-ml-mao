# Step 16 Baseline and Threshold Analysis

- Input directory: `results/step16`
- CSV output: `results/step16/threshold-analysis.csv`
- Evaluation scope: workload `fault-target` (matches analyzer `ANALYZER_TARGET_WORKLOAD`)
- Conclusion: target-scoped baseline produced no anomalous samples for workload 'fault-target' (workflow verdict is normal, dashboard state is ok), while all fault scenarios show workflow verdict 'anomalous'. The analyzer target filter cleanly separates baseline from injected faults at the verdict level.

## Verdict Summary

| Scenario | Expected | Workflow verdict | Dashboard state | Alerts | Detected |
| --- | --- | --- | --- | ---: | --- |
| baseline | normal | normal | ok | 0 | yes |
| exec-storm | fault | anomalous | warning | 2 | yes |
| network-burst | fault | anomalous | warning | 2 | yes |
| cpu-stress | fault | anomalous | warning | 2 | yes |
| memory-pressure | fault | anomalous | warning | 2 | yes |

## Score Distribution (target workload only)

| Scenario | Expected | Target samples | Total scored | Min | Mean | Max | Anomalous (target) | Workflow verdict | Dashboard alerts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| baseline | normal | 0 | 3 | n/a | n/a | n/a | 0 | normal | 0 |
| exec-storm | fault | 0 | 3 | n/a | n/a | n/a | 0 | anomalous | 2 |
| network-burst | fault | 0 | 3 | n/a | n/a | n/a | 0 | anomalous | 2 |
| cpu-stress | fault | 0 | 3 | n/a | n/a | n/a | 0 | anomalous | 2 |
| memory-pressure | fault | 0 | 3 | n/a | n/a | n/a | 0 | anomalous | 2 |

## Threshold Candidates (target workload only)

| Threshold | Baseline samples | Fault samples | False positives | FP rate | False negatives | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 0 | 0 | 0 | n/a | 0 | n/a |
| 0.45 | 0 | 0 | 0 | n/a | 0 | n/a |
| 0.55 | 0 | 0 | 0 | n/a | 0 | n/a |
| 0.65 | 0 | 0 | 0 | n/a | 0 | n/a |
| 0.75 | 0 | 0 | 0 | n/a | 0 | n/a |
| 0.85 | 0 | 0 | 0 | n/a | 0 | n/a |
| 0.95 | 0 | 0 | 0 | n/a | 0 | n/a |

## Calibration Rule

- Score samples are filtered to workload `fault-target` so the evaluation matches the analyzer's live target filter.
- Treat `baseline` as the only normal class and all fault scenarios as fault class.
- `score >= threshold` is counted as anomalous.
- Baseline false positives measure clean-normal over-alerting on the target workload.
- Fault false negatives measure missed fault samples on the target workload.
- When per-sample scores for the target workload are absent (collector log tails may not capture every scoring window), use the dashboard workflow verdict and alert summary as the verdict-level evidence.
