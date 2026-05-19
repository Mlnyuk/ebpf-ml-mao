# Step 20

Step 20 범위는 `Repeated Experiment Validation`입니다.

Step 16~19까지의 한 차례 실험은 fault scenario 탐지가 가능함을 보여주었지만, 단일 실행이라 통계적 신뢰도를 보장하지 못합니다. 또한 fault-target 워크로드가 baseline period에 거의 idle이라서 baseline 구간의 anomaly score 샘플이 비어 있고, FP rate를 정량적으로 보고하지 못했습니다. Step 20은 N회 반복 실험과 warm baseline 주입을 통해 다음 두 가지를 동시에 해결합니다.

- 통계적 신뢰도 확보: scenario별 detection rate, score mean ± std
- baseline FP rate 정량 측정: warm baseline으로 fault-target scoring window 생성

## Goal

- step16_collect_results.sh를 N회 반복 실행하고 각 실행 결과를 독립 디렉토리에 보존한다.
- baseline period에 fault-target 워크로드에 저강도 합성 부하를 주입해 scoring window를 생성한다.
- N개 실행을 합쳐 threshold sweep, detection rate, score 분포를 집계한 보고서를 만든다.
- 학습(retraining) 없이 calibration(threshold 최적화) + validation(반복 검증)만 수행한다.

## Added

- `scripts/step16_warmup_baseline.sh`: fault-target 워크로드에 저강도 exec 활동 주입
- `scripts/step16_repeat_experiments.sh`: N회 반복 실행 드라이버
- `scripts/step16_aggregate_repeated.py`: 실행 간 통계 집계 스크립트
- `docs/steps/step20/README.md`: 본 문서
- `tests/test_step20_artifacts.py`: 스크립트/문서 존재 검증
- step16_collect_results.sh: `WARMUP_BASELINE=true` 옵션 추가
- step16_analyze_thresholds.py / step16_generate_paper_tables.py / step16_generate_report.py: `RESULT_DIR` env 오버라이드 지원

## Commands

Step 19까지 적용된 클러스터에서 analyzer port-forward가 열려 있는 상태로 다음을 실행합니다.

```bash
kubectl port-forward -n ebpf-obs svc/ebpf-ml-mao-analyzer 8080:8080 &
bash scripts/step16_repeat_experiments.sh 5 results/step20
```

각 실행은 다음 순서로 진행됩니다.

1. analyzer runtime history prune (clean baseline)
2. analyzer deployment 재시작
3. WARMUP_BASELINE=true로 fault-target에 60초간 저강도 exec 주입
4. settle 15초
5. baseline snapshot 수집
6. 4개 fault scenario 실행 및 snapshot 수집
7. analyzer PVC에서 fault-target ingest 리포트 덤프
8. per-run threshold-analysis.md, paper-results.md, experiment-report.md 생성

모든 실행 종료 후 집계 보고서를 생성합니다.

```bash
python3 scripts/step16_aggregate_repeated.py results/step20
```

## Output Files

- `results/step20/run_NN/`: 각 실행의 raw 결과 (step16과 동일한 구조)
- `results/step20/aggregated-threshold-analysis.md`: 집계 threshold sweep + detection rate
- `results/step20/aggregated-threshold-analysis.csv`: threshold sweep CSV
- `results/step20/aggregated-paper-results.md`: per-run 표 + scenario별 score 통계
- `results/step20/aggregated-detection.csv`: per-run detection 결과 CSV

## Interpretation

- **Detection rate**: N개 실행 중 dashboard `latest_verdict`가 정답(`baseline=normal`, `fault=anomalous`)이었던 비율
- **Score mean ± std**: 각 실행의 평균 score를 모은 분포의 평균 ± 표준편차. 표준편차가 작을수록 threshold 견고성 높음
- **Threshold sweep**: N개 실행의 sample을 합쳐서 각 threshold 후보의 FP/FN rate 계산. FP=0이고 FN=0인 최소 threshold를 권장값으로 보고

## Limitations

- Step 20은 모델을 학습/재학습하지 않습니다. registry의 active model은 그대로 사용합니다.
- Step 20은 fault-target 외 워크로드에는 scoring을 적용하지 않습니다 (Step 19의 target filter 그대로).
- N개 실행은 같은 클러스터/같은 시간대에 수행되므로 노드/네트워크 장애가 동시에 영향을 줄 수 있습니다. 완전한 독립 시행이 필요하면 다른 시간대 또는 다른 클러스터에서 추가 실행이 필요합니다.
- Warm baseline은 인위적 부하이므로 실제 production traffic 분포와 차이가 있을 수 있습니다.
