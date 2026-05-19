# Step 16 Baseline and Threshold Analysis

- Input directory: `results/step16`
- CSV output: `results/step16/threshold-analysis.csv`
- Conclusion: baseline workflow verdict is anomalous, so the existing baseline artifact is contaminated and must not be used as a clean normal distribution.

## Score Distribution

| Scenario | Expected | Samples | Min | Mean | Max | Analyzer anomalous samples | Workflow latest verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| baseline | normal | 3 | 1.0000 | 1.0000 | 1.0000 | 3 | anomalous |
| exec-storm | fault | 3 | 1.0000 | 1.0000 | 1.0000 | 3 | anomalous |
| network-burst | fault | 3 | 0.7583 | 0.8597 | 1.0000 | 3 | anomalous |
| cpu-stress | fault | 3 | 0.3958 | 0.7180 | 1.0000 | 2 | normal |
| memory-pressure | fault | 3 | 0.3958 | 0.7986 | 1.0000 | 2 | anomalous |

## Threshold Candidates

| Threshold | Baseline samples | Fault samples | False positives | FP rate | False negatives | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 3 | 12 | 3 | 1.0000 | 0 | 0.0000 |
| 0.45 | 3 | 12 | 3 | 1.0000 | 2 | 0.1667 |
| 0.55 | 3 | 12 | 3 | 1.0000 | 2 | 0.1667 |
| 0.65 | 3 | 12 | 3 | 1.0000 | 2 | 0.1667 |
| 0.75 | 3 | 12 | 3 | 1.0000 | 2 | 0.1667 |
| 0.85 | 3 | 12 | 3 | 1.0000 | 5 | 0.4167 |
| 0.95 | 3 | 12 | 3 | 1.0000 | 5 | 0.4167 |

## Calibration Rule

- Treat `baseline` as the only normal class and all fault scenarios as fault class.
- `score >= threshold` is counted as anomalous.
- Baseline false positives measure clean-normal over-alerting.
- Fault false negatives measure missed fault samples.
- Do not finalize a threshold while baseline is contaminated or lacks score samples.
