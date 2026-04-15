# Step 7

Step 7 범위는 `모델 레지스트리 + schema migration + 기본 모델 해상도`입니다.

이번 단계에서는 Step 6에서 추가한 `schema_version`/`model_type`을 실제 운영 흐름으로 묶었습니다. 저장된 모델을 레지스트리에 등록하고, 활성 모델을 지정하고, 레거시 `v1` 모델을 `v2`로 올리는 CLI를 추가했습니다.

## Added

- `app/ebpf_ml_mao/registry.py`
  - 로컬 `registry.json` 로드/저장
  - 모델 등록, 활성화, active model path 해상도
- `app/ebpf_ml_mao/scoring.py`
  - `MODEL_REGISTRY` 추가
  - `migrate_model_dict(...)`, `migrate_model_file(...)` 추가
  - `describe_model_file(...)` 추가
- `app/ebpf_ml_mao/pipeline.py`
  - 학습 시 registry 등록 지원
  - `phase5`에서 `model_path` 없이 active model 사용 가능
- `app/ebpf_ml_mao/cli.py`
  - `show-model`
  - `migrate-model`
  - `registry list`
  - `registry activate`

## Registry Shape

```json
{
  "active_model_id": "baseline-v2-01",
  "models": [
    {
      "id": "baseline-v2-01",
      "path": "docs/steps/step7/output/models/baseline-v2.json",
      "model_type": "baseline",
      "schema_version": "v2",
      "threshold": 0.45,
      "feature_count": 10,
      "created_at": "2026-04-15T12:00:00+00:00",
      "tags": ["baseline"]
    }
  ]
}
```

## Run

baseline 모델 학습 + registry 등록:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao train-model   --baseline-tetragon samples/step2/baseline_tetragon.jsonl   --baseline-prometheus samples/step2/baseline_prometheus.json   --model-type baseline   --model-path docs/steps/step7/output/models/baseline-v2.json   --registry-path docs/steps/step7/output/registry.json   --tag baseline   --activate
```

zscore 모델 학습 + registry 등록:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao train-model   --baseline-tetragon samples/step2/baseline_tetragon.jsonl   --baseline-prometheus samples/step2/baseline_prometheus.json   --model-type zscore   --model-path docs/steps/step7/output/models/zscore-v2.json   --registry-path docs/steps/step7/output/registry.json   --tag candidate
```

registry 조회:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao registry list   --registry-path docs/steps/step7/output/registry.json
```

active model 전환:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao registry activate   --registry-path docs/steps/step7/output/registry.json   --model-id zscore-v2-02
```

레거시 모델 migration:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao migrate-model   --source-path docs/steps/step5/output/baseline-model.json   --output-path docs/steps/step7/output/models/baseline-migrated-v2.json
```

active model 기준 추론:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao phase5   --registry-path docs/steps/step7/output/registry.json   --input-tetragon samples/step7/input_tetragon.jsonl   --input-prometheus samples/step7/input_prometheus.json   --output-dir docs/steps/step7/output/inference
```

## Verification

```bash
python3 -m unittest discover -s tests -v
```

Step 7에서 추가 검증한 항목:

- registry에 모델 2개 등록
- active model 전환 후 기본 추론 경로 사용
- legacy `v1` 모델을 `v2`로 migration
- migrated model metadata 조회

## Limits

- registry는 단일 JSON 파일 기반이라 동시성 제어는 아직 없음
- backup/prune 같은 운영성 기능은 아직 없음
- active model은 하나만 둘 수 있음
