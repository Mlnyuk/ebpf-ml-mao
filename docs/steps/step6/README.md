# Step 6

Step 6 범위는 `모델 다변화 + 모델 스키마 versioning + 모델 선택 CLI`입니다.

이번 단계에서는 Step 5의 저장 모델 구조를 확장해서, 저장 파일 안에 `schema_version`과 `model_type`을 넣고, `baseline`과 `zscore` 두 모델 타입을 지원하도록 만들었습니다.

## Added

- `app/ebpf_ml_mao/scoring.py`
  - `schema_version` 지원
  - `model_type` 지원
  - `baseline`, `zscore` 모델 타입 지원
  - unknown schema/version validation 추가
- `app/ebpf_ml_mao/pipeline.py`
  - `train_baseline_model_from_raw(..., model_type=...)` 지원
- `app/ebpf_ml_mao/cli.py`
  - `train-model --model-type {baseline,zscore}` 추가
- `samples/step6/`
  - Step 6 추론용 입력 샘플 추가

## Model Schema

현재 모델 파일은 아래 메타데이터를 포함합니다.

```json
{
  "schema_version": "v2",
  "model_type": "baseline",
  "feature_keys": [...],
  "threshold": 0.45
}
```

모델 타입별 본문:

- `baseline`: `baseline`
- `zscore`: `mean`, `std`

## Run

baseline 모델 학습:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao train-model \
  --baseline-tetragon samples/step2/baseline_tetragon.jsonl \
  --baseline-prometheus samples/step2/baseline_prometheus.json \
  --model-type baseline \
  --model-path docs/steps/step6/output/baseline-v2.json
```

zscore 모델 학습:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao train-model \
  --baseline-tetragon samples/step2/baseline_tetragon.jsonl \
  --baseline-prometheus samples/step2/baseline_prometheus.json \
  --model-type zscore \
  --model-path docs/steps/step6/output/zscore-v2.json
```

저장된 모델로 추론:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao phase5 \
  --model-path docs/steps/step6/output/zscore-v2.json \
  --input-tetragon samples/step6/input_tetragon.jsonl \
  --input-prometheus samples/step6/input_prometheus.json \
  --output-dir docs/steps/step6/output
```

## Verification

```bash
python3 -m unittest discover -s tests -v
```

Step 6에서 추가 검증한 항목:

- versioned baseline model 저장
- zscore model 저장/로드/추론
- unknown schema version reject

## Limits

- 모델 레지스트리는 아직 파일 하나 안에 구현됨
- `iqr`, `iforest` 같은 추가 타입은 아직 없음
- 모델 migration 도구는 아직 없음
- inference 시 feature drift 경고는 예외 처리 수준까지만 구현됨
