# Step 5

Step 5 범위는 `offline trained model + online inference` 구조 분리입니다.

이번 단계에서는 baseline을 실행 중에 즉석 계산하지 않고, 먼저 모델 파일로 저장한 뒤 그 모델을 로드해서 추론만 수행하는 경로를 추가했습니다.

## Added

- `app/ebpf_ml_mao/scoring.py`
  - `BaselineModel` 추가
  - scorer `save_model()` / `load_model()` 추가
- `app/ebpf_ml_mao/pipeline.py`
  - `train_baseline_model(...)` 추가
  - `train_baseline_model_from_raw(...)` 추가
  - `run_phase5(...)` 추가
- `app/ebpf_ml_mao/cli.py`
  - `train-model` subcommand 추가
  - `phase5` subcommand 추가
- `samples/step5/`
  - 모델 추론용 입력 샘플 추가

## Phase 5 Flow

```text
baseline raw input
  -> feature windows
  -> baseline model training
  -> model.json 저장

saved model + raw inference input
  -> adapters
  -> feature windows
  -> model load
  -> anomaly inference
  -> batch reports
```

## Run

먼저 모델 학습:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao train-model \
  --baseline-tetragon samples/step2/baseline_tetragon.jsonl \
  --baseline-prometheus samples/step2/baseline_prometheus.json \
  --model-path docs/steps/step5/output/baseline-model.json
```

그 다음 추론:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao phase5 \
  --model-path docs/steps/step5/output/baseline-model.json \
  --input-tetragon samples/step5/input_tetragon.jsonl \
  --input-prometheus samples/step5/input_prometheus.json \
  --output-dir docs/steps/step5/output
```

## Output

- `docs/steps/step5/output/baseline-model.json`
- `docs/steps/step5/output/report-index.json`
- `docs/steps/step5/output/report-index.md`
- `docs/steps/step5/output/reports/report-01.json`
- `docs/steps/step5/output/reports/report-02.json`
- `docs/steps/step5/output/reports/report-03.json`

## Verification

```bash
python3 -m unittest discover -s tests -v
```

Step 5에서 추가 검증한 항목:

- 모델 저장/로딩 roundtrip
- saved model 기반 추론 실행
- batch report 출력 유지

## Limits

- 모델 형식은 아직 단순 JSON baseline
- versioned schema는 아직 없음
- 여러 모델 종류를 선택하는 구조는 아직 없음
- 실제 ML 알고리즘 교체는 다음 단계 과제
