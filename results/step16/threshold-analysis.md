# Step 16 Baseline and Threshold Analysis

- Input directory: `results/step16`
- CSV output: `results/step16/threshold-analysis.csv`
- Conclusion: baseline workflow verdict is anomalous, so the existing baseline artifact is contaminated and must not be used as a clean normal distribution.

## Score Distribution

| Scenario | Expected | Samples | Min | Mean | Max | Analyzer anomalous samples | Workflow latest verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| baseline | normal | 0 | n/a | n/a | n/a | 0 | anomalous |
| exec-storm | fault | 3 | 0.8958 | 0.9653 | 1.0000 | 3 | anomalous |
| network-burst | fault | 3 | 0.4458 | 0.6291 | 0.9958 | 1 | normal |
| cpu-stress | fault | 3 | 0.3708 | 0.4125 | 0.4458 | 0 | anomalous |
| memory-pressure | fault | 3 | 0.3708 | 0.4083 | 0.4333 | 0 | anomalous |

## Threshold Candidates

| Threshold | Baseline samples | Fault samples | False positives | FP rate | False negatives | FN rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 0 | 12 | 0 | n/a | 0 | 0.0000 |
| 0.45 | 0 | 12 | 0 | n/a | 8 | 0.6667 |
| 0.55 | 0 | 12 | 0 | n/a | 8 | 0.6667 |
| 0.65 | 0 | 12 | 0 | n/a | 8 | 0.6667 |
| 0.75 | 0 | 12 | 0 | n/a | 8 | 0.6667 |
| 0.85 | 0 | 12 | 0 | n/a | 8 | 0.6667 |
| 0.95 | 0 | 12 | 0 | n/a | 9 | 0.7500 |

## Calibration Rule

- Treat `baseline` as the only normal class and all fault scenarios as fault class.
- `score >= threshold` is counted as anomalous.
- Baseline false positives measure clean-normal over-alerting.
- Fault false negatives measure missed fault samples.
- Do not finalize a threshold while baseline is contaminated or lacks score samples.
