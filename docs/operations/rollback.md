# Rollback

1. 이전 정상 이미지 태그를 확인합니다.
2. `kubectl set image deploy/ebpf-ml-mao-analyzer analyzer=ghcr.io/mlnyuk/ebpf-ml-mao:<previous-tag> -n ebpf-obs`
3. 필요하면 `kubectl apply -k deploy/yaml/step13`로 이전 overlay를 재적용합니다.
4. PVC, ingest, queue, spool 디렉터리는 보존하고 애플리케이션만 되돌립니다.
5. `/readyz`, `/v1/dashboard`로 복구 여부를 확인합니다.
