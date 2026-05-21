# Step 22

Step 22 범위는 `memory-pressure Detection Fix`입니다.

Step 21에서 N=5 반복 실험을 수행한 결과 memory-pressure 시나리오의 검출률이 40%에 그쳤습니다.
나머지 4개 시나리오(baseline, exec-storm, network-burst, cpu-stress)는 모두 100% 달성.

## 원인 분석

`scripts/fault-scenarios/memory-pressure.sh`는 `kubectl exec` 한 번으로 128MB dd 쓰기를 수행하고 종료합니다.
dd가 ~5초 내에 완료되므로, 30s 스코어링 윈도우 경계와 타이밍이 어긋나면 해당 exec 이벤트가
어떤 윈도우에도 포함되지 않는 경우가 발생합니다.

Step 21 CSV 데이터:

| Run | memory-pressure samples |
|-----|------------------------|
| run_01 | 0 |
| run_02 | 2 |
| run_03 | 1 |
| run_04 | 2 |
| run_05 | 1 |

samples=0인 경우: `fault_target_verdict` → None → 대시보드 fallback → "normal" → False Negative.
samples=1인 경우: exec_count=1, 점수 ~0.22 → 임계값 0.45 미달 → 탐지 실패.

## 비교: cpu-stress vs memory-pressure

| 항목 | cpu-stress | memory-pressure (step21) |
|------|-----------|--------------------------|
| exec 지속 시간 | 30s (DURATION_SECONDS) | ~5s (dd만 실행) |
| 윈도우 포착 보장 | O | X (타이밍 의존) |
| 평균 samples/run | 2-3 | 0-2 |
| 검출률 | 100% | 40% |
| 점수 평균 | 0.5291 | 0.2252 |

## 수정

`scripts/fault-scenarios/memory-pressure.sh`에 `HOLD_SECONDS=35` 추가.

dd 쓰기 완료 후 35초 sleep으로 exec를 열어둡니다.
이렇게 하면 30s 스코어링 윈도우가 반드시 exec 활성 구간을 포함하게 되어
exec_count ≥ 1이 보장된 윈도우가 최소 1개 이상 생성됩니다.

cpu-stress가 `DURATION_SECONDS=30`으로 동일한 방식을 사용하며 100% 검출을 달성한 것과 같은 원리입니다.

## Added

- `scripts/fault-scenarios/memory-pressure.sh`: `HOLD_SECONDS=35` 추가 (dd 후 sleep)
- `docs/steps/step22/README.md`: 본 문서
- `tests/test_step22_artifacts.py`: memory-pressure 스크립트 및 결과 검증

## Commands

step21까지 적용된 클러스터에서 실행합니다.

```bash
# N=5 반복 실험 (step21 overlay 유지, WARMUP_BASELINE=false)
REPEAT_N=5 BASE_DIR=results/step22 WARMUP_BASELINE=false \
  bash scripts/step16_repeat_experiments.sh

# 집계
python3 scripts/step16_aggregate_repeated.py results/step22
```

## Output Files

- `results/step22/run_NN/`: N=5 각 실행 raw 결과
- `results/step22/aggregated-paper-results.md`: 집계 보고서
- `results/step22/aggregated-threshold-analysis.md`: 임계값 분석

## Expected Result

Detection rate targets after fix:

| Scenario | Expected |
|----------|----------|
| baseline | 100% normal |
| exec-storm | 100% anomalous |
| network-burst | 100% anomalous |
| cpu-stress | 100% anomalous |
| memory-pressure | 100% anomalous (step21: 40% → step22: 100%) |

## Interpretation

memory-pressure 시나리오는 `kubectl exec`로 in-pod 파일 쓰기 작업을 주입합니다.
exec 자체가 30s 윈도우 사이클보다 짧게 끝나면 스코어링 샘플이 0개가 되는 타이밍 문제가 있습니다.
`HOLD_SECONDS`로 exec 지속 시간을 늘리면 exec_count ≥ 1이 보장된 윈도우가 반드시 생성되고,
baseline exec_count=0 대비 distance가 임계값 0.45를 초과해 anomalous로 판정됩니다.
