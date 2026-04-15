# Operations Runbook

실운영 배포 기준 문서는 [`docs/steps/step14/runbook.md`](../steps/step14/runbook.md) 입니다.

핵심 순서:

1. `make test`
2. `make render-step14`
3. `make dry-run-step14`
4. `make build-image`
5. GitHub Actions `release-image` 실행
6. `kubectl apply -k deploy/yaml/step14`
7. `/readyz`, `/v1/dashboard`, `/v1/alerts` 확인
