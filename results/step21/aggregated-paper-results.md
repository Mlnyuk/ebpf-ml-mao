# Step 20 Aggregated Paper Result

- Base directory: `results/step21`
- Runs aggregated: 5

## Per-Run Detection Summary

| Run | baseline | exec-storm | network-burst | cpu-stress | memory-pressure |
| --- | --- | --- | --- | --- | --- |
| run_01 | normal (yes) | anomalous (yes) | anomalous (yes) | anomalous (yes) | normal (no) |
| run_02 | normal (yes) | anomalous (yes) | anomalous (yes) | anomalous (yes) | anomalous (yes) |
| run_03 | normal (yes) | anomalous (yes) | anomalous (yes) | anomalous (yes) | normal (no) |
| run_04 | normal (yes) | anomalous (yes) | anomalous (yes) | anomalous (yes) | anomalous (yes) |
| run_05 | normal (yes) | anomalous (yes) | anomalous (yes) | anomalous (yes) | normal (no) |

## Detection Rate Summary

| Scenario | Expected | Detection rate | Score mean (per-run mean ± std) |
| --- | --- | ---: | --- |
| baseline | normal | 100.0% | 0.0081 ± 0.0057 (over 5 runs) |
| exec-storm | fault | 100.0% | 0.4867 ± 0.1166 (over 5 runs) |
| network-burst | fault | 100.0% | 0.7805 ± 0.0706 (over 5 runs) |
| cpu-stress | fault | 100.0% | 0.5291 ± 0.0504 (over 5 runs) |
| memory-pressure | fault | 40.0% | 0.2252 ± 0.2226 (over 4 runs) |

## Interpretation

Across 5 independent runs, fault scenario detection is reported as the fraction of runs where the analyzer dashboard reported `latest_verdict='anomalous'` after the scenario, and baseline detection is the fraction of runs where the verdict stayed `normal`. Per-run mean scores capture how consistently the analyzer scored each scenario; tight standard deviations indicate the calibrated threshold is robust.
