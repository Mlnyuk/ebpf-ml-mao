# Step 14 Runbook

## 1. Preflight

1. `python3 -m unittest discover -s tests -v`
2. `kubectl kustomize deploy/yaml/step14 > /tmp/step14-rendered.yaml`
3. `docker build -t ghcr.io/mlnyuk/ebpf-ml-mao:step14 .`
4. active model registry 경로와 secret 값을 확인

## 2. Release Image

1. GitHub Actions `release-image` workflow를 실행
2. `image_tag=step14` 또는 배포용 태그 입력
3. GHCR에 이미지가 올라왔는지 확인

## 3. Apply To Cluster

1. `kubectl apply -k deploy/yaml/step14`
2. `kubectl -n ebpf-obs rollout status deploy/ebpf-ml-mao-analyzer`
3. `kubectl -n ebpf-obs rollout status ds/ebpf-ml-mao-collector`

## 4. Post-Deploy Checks

1. `kubectl -n ebpf-obs port-forward svc/ebpf-ml-mao-analyzer 8080:8080`
2. `curl http://127.0.0.1:8080/readyz`
3. `curl http://127.0.0.1:8080/v1/dashboard`
4. `curl http://127.0.0.1:8080/v1/alerts`
5. analyzer 로그와 collector spool backlog를 확인

## 5. Rollback

1. 이전 정상 이미지 태그를 확인
2. `kubectl set image deploy/ebpf-ml-mao-analyzer analyzer=ghcr.io/mlnyuk/ebpf-ml-mao:<previous-tag> -n ebpf-obs`
3. 필요하면 Step 13 overlay로 재적용: `kubectl apply -k deploy/yaml/step13`
4. `/readyz`, `/v1/dashboard`로 복구 여부 확인

## 6. Failure Signals

- `/readyz` 503
- `/v1/alerts`에서 `critical`
- `queue_backlog`, `spool_backlog`, `missing_model_artifact` 경보
- collector hostPath에 spool 파일이 지속적으로 증가
