# Release Checklist

- [ ] `make test`
- [ ] `make render-step14`
- [ ] `make dry-run-step14`
- [ ] `make build-image`
- [ ] active model 확인
- [ ] `ANALYZER_SHARED_TOKEN` secret 확인
- [ ] PVC와 registry path 확인
- [ ] NetworkPolicy 변경 여부 확인
- [ ] rollout 후 `/readyz` 확인
- [ ] rollout 후 `/v1/dashboard` 확인
