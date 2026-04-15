# Step 10

Step 10 범위는 `이미지 빌드 경로 고정 + analyzer API 엔트리포인트 + collector 결과 중앙 전송 + Secret/NetworkPolicy 초안`입니다.

이번 단계에서는 Step 9의 배포 초안을 실제 런타임에 더 가깝게 만들었습니다. analyzer에 HTTP 엔트리포인트를 추가했고, collector가 생성한 report를 analyzer로 POST할 수 있는 전송 경로를 넣었습니다. 또한 Dockerfile과 Step 10 배포 매니페스트를 추가해 이미지 빌드와 배포 경로를 고정했습니다.

## Added

- `Dockerfile`
- `.dockerignore`
- `app/ebpf_ml_mao/api.py`
- `app/ebpf_ml_mao/transport.py`
- `app/ebpf_ml_mao/cli.py` 에 `api`, `push-report` 서브커맨드 추가
- `deploy/yaml/step10/`
- `tests/test_step10_api.py`
- `tests/test_step10_transport.py`
- `tests/test_step10_cli.py`

## Runtime Changes

- `analyzer`
  - `python3 -m ebpf_ml_mao api` 로 HTTP API 실행
  - `/healthz`, `/readyz`, `/v1/status`, `/v1/reports` 제공
- `collector`
  - `phase3` 실행 후 생성된 JSON report를 analyzer API로 전송
  - analyzer가 중앙 ingest 디렉터리에 노드별로 저장
- `shared token`
  - Secret 기반 bearer token 전송 초안 추가

## Build

```bash
docker build -t ghcr.io/mlnyuk/ebpf-ml-mao:step10 .
```

## Deployment Draft

```bash
kubectl apply -k deploy/yaml/step10
```

## Validation

```bash
python3 -m unittest discover -s tests -v
kubectl kustomize deploy/yaml/step10
```

## Remaining Risks

- collector가 마지막 report 한 개만 POST하는 단순 경로라 재전송/중복 제거는 아직 없음
- analyzer API 인증은 shared token 초안만 있고, 세밀한 authz는 아직 없음
- NetworkPolicy는 최소 초안이라 실제 CNI 정책과 맞춰 추가 검증 필요
- analyzer가 ingest한 report를 다시 모델 registry나 워크플로와 연결하는 후처리는 Step 11 이후 과제
