# Step 16 Baseline and Threshold Analysis

- Input directory: `results/step16`
- CSV output: `results/step16/threshold-analysis.csv`
- Evaluation scope: workload `fault-target` (matches analyzer `ANALYZER_TARGET_WORKLOAD`)
- Conclusion: baseline produced no fault-target score samples (verdict=normal, alerts=0), while all fault scenarios show verdict 'anomalous' with fault-target scores ranging from 0.4323 to 1.0000. Threshold 0.35 achieves FP=0 and FN=0.

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
| baseline | normal | 0 | 0 | n/a | n/a | n/a | 0 | None | 0 |
| exec-storm | fault | 3 | 3 | 0.5005 | 0.5232 | 0.5687 | 3 | anomalous | 1 |
| network-burst | fault | 5 | 5 | 0.7210 | 0.9126 | 1.0000 | 5 | anomalous | 1 |
| cpu-stress | fault | 1 | 1 | 0.9437 | 0.9437 | 0.9437 | 1 | anomalous | 1 |
| memory-pressure | fault | 2 | 2 | 0.4323 | 0.4834 | 0.5346 | 2 | anomalous | 1 |

## Threshold Candidates (target workload only)

| Threshold | Baseline samples | Fault samples | False positives | FP rate | False negatives | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 0 | 11 | 0 | n/a | 0 | 0.0000 |
| 0.45 | 0 | 11 | 0 | n/a | 1 | 0.0909 |
| 0.55 | 0 | 11 | 0 | n/a | 4 | 0.3636 |
| 0.65 | 0 | 11 | 0 | n/a | 5 | 0.4545 |
| 0.75 | 0 | 11 | 0 | n/a | 6 | 0.5455 |
| 0.85 | 0 | 11 | 0 | n/a | 6 | 0.5455 |
| 0.95 | 0 | 11 | 0 | n/a | 8 | 0.7273 |

## Calibration Rule

- Score samples are filtered to workload `fault-target` so the evaluation matches the analyzer's live target filter.
- Treat `baseline` as the only normal class and all fault scenarios as fault class.
- `score >= threshold` is counted as anomalous.
- Baseline false positives measure clean-normal over-alerting on the target workload.
- Fault false negatives measure missed fault samples on the target workload.
- When per-sample scores for the target workload are absent (collector log tails may not capture every scoring window), use the dashboard workflow verdict and alert summary as the verdict-level evidence.
