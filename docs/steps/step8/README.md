# Step 8

Step 8 범위는 `registry 운영 기능 강화`입니다.

Step 7에서 모델을 등록하고 active model을 고를 수 있게 만들었고, 이번 단계에서는 실제 운영 중 필요한 기본 관리 기능을 붙였습니다. 핵심은 `tag`, `backup`, `prune`, `status`입니다.

## Added

- `app/ebpf_ml_mao/registry.py`
  - registry 정규화 보강
  - `backup_registry(...)`
  - `tag_model(...)`
  - `prune_registry(...)`
  - `registry_status(...)`
- `app/ebpf_ml_mao/cli.py`
  - `registry status`
  - `registry tag`
  - `registry backup`
  - `registry prune`
- `tests/test_step8_registry_ops.py`
  - 운영성 기능 회귀 테스트 추가

## What It Solves

- 모델에 운영 태그를 붙일 수 있음
- registry 변경 전에 백업 파일을 남길 수 있음
- artifact가 사라진 모델 entry를 정리할 수 있음
- 특정 모델 entry를 registry에서 제거할 수 있음
- active model이 제거될 때 남은 모델로 자동 재선정됨

## Run

registry 상태 조회:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao registry status   --registry-path docs/steps/step8/output/registry.json
```

모델 태그 추가:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao registry tag   --registry-path docs/steps/step8/output/registry.json   --model-id <baseline-model-id>   --tag prod   --tag reviewed
```

registry 백업:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao registry backup   --registry-path docs/steps/step8/output/registry.json
```

artifact가 없는 entry 정리:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao registry prune   --registry-path docs/steps/step8/output/registry.json   --missing-only
```

특정 모델 제거:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao registry prune   --registry-path docs/steps/step8/output/registry.json   --model-id <model-id>
```

## Verification

```bash
python3 -m unittest discover -s tests -v
```

Step 8에서 추가 검증한 항목:

- tag merge 동작
- missing artifact prune
- active model 재선정
- artifact 삭제 옵션
- registry backup/status 출력

## Limits

- registry는 여전히 단일 JSON 파일 기반
- prune는 age 기반 정책이 아니라 `missing-only` 또는 `model-id` 기준
- concurrent write lock은 아직 없음
