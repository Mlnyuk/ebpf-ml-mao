# Step 20 Aggregated Paper Result

- Base directory: `results/step20`
- Runs aggregated: 5

## Per-Run Detection Summary

| Run | baseline | exec-storm | network-burst | cpu-stress | memory-pressure |
| --- | --- | --- | --- | --- | --- |
| run_01 | anomalous (no) | anomalous (yes) | anomalous (yes) | anomalous (yes) | anomalous (yes) |
| run_02 | anomalous (no) | anomalous (yes) | anomalous (yes) | anomalous (yes) | anomalous (yes) |
| run_03 | anomalous (no) | anomalous (yes) | anomalous (yes) | anomalous (yes) | anomalous (yes) |
| run_04 | anomalous (no) | anomalous (yes) | anomalous (yes) | anomalous (yes) | anomalous (yes) |
| run_05 | anomalous (no) | anomalous (yes) | anomalous (yes) | anomalous (yes) | anomalous (yes) |

## Detection Rate Summary

| Scenario | Expected | Detection rate | Score mean (per-run mean ± std) |
| --- | --- | ---: | --- |
| baseline | normal | 0.0% | 0.6913 ± 0.1299 (over 5 runs) |
| exec-storm | fault | 100.0% | 0.7147 ± 0.1253 (over 5 runs) |
| network-burst | fault | 100.0% | 0.9745 ± 0.0402 (over 5 runs) |
| cpu-stress | fault | 100.0% | 0.9705 ± 0.0590 (over 5 runs) |
| memory-pressure | fault | 100.0% | 0.7732 ± 0.0000 (over 3 runs) |

## Interpretation

Across 5 independent runs, fault scenario detection is reported as the fraction of runs where the analyzer dashboard reported `latest_verdict='anomalous'` after the scenario, and baseline detection is the fraction of runs where the verdict stayed `normal`. Per-run mean scores capture how consistently the analyzer scored each scenario; tight standard deviations indicate the calibrated threshold is robust.
