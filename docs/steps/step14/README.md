# Step 14

Step 14 범위는 `실배포 마감`입니다.

이번 단계에서는 Step 13까지 쌓인 기능과 배포 초안을 실제 운영 진입점 기준으로 마감했습니다. 핵심은 `이미지 빌드 경로`, `CI 검증`, `릴리스 이미지 푸시 workflow`, `Step 14 overlay`, `운영 runbook/checklist`를 하나의 절차로 고정하는 것입니다.

## Added

- `Makefile`
  - `test`
  - `render-step14`
  - `dry-run-step14`
  - `build-image`
  - `deploy-step14`
- `.github/workflows/ci.yaml`
  - unittest
  - `kubectl kustomize deploy/yaml/step14`
  - `kubectl apply --dry-run=client -k deploy/yaml/step14`
  - Docker build smoke test
- `.github/workflows/release-image.yaml`
  - GHCR 수동 릴리스 이미지 푸시
  - Step 14 렌더 artifact 업로드
- `deploy/yaml/step14/`
  - Step 13 overlay 위에 Step 14 이미지 태그와 analyzer resources 고정
- `docs/steps/step14/runbook.md`
- `docs/steps/step14/checklist.md`
- `docs/operations/`
  - `runbook.md`
  - `rollback.md`
  - `release-checklist.md`
  - `incident-checklist.md`
  - `ci-cd.md`
- `tests/test_step14_artifacts.py`

## Runtime Closure

- Step 14부터 표준 이미지는 `ghcr.io/mlnyuk/ebpf-ml-mao:step14`로 가정합니다.
- 로컬 검증은 `make test`, `make render-step14`, `make dry-run-step14`, `make build-image` 순서로 고정합니다.
- 클러스터 반영은 `kubectl apply -k deploy/yaml/step14`로 고정합니다.
- GitHub Actions는 PR/merge 시 기본 검증을 수행하고, 수동 workflow로 이미지 릴리스를 수행합니다.

## Validation

```bash
python3 -m unittest discover -s tests -v
kubectl kustomize deploy/yaml/step14
kubectl apply --dry-run=client -k deploy/yaml/step14
```

## Remaining Risks

- 실제 클러스터 credentials와 GHCR 권한은 이 저장소 바깥의 GitHub secrets 설정이 필요합니다.
- collector spool은 여전히 노드 로컬 상태라 중앙 집계 체계가 추가되면 더 안정적입니다.
- postprocess queue는 파일 기반 초안이라 장기적으로는 별도 worker/queue backend로 교체하는 편이 맞습니다.
