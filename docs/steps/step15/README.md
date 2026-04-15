# Step 15

Step 15 범위는 `시각화`입니다.

이번 단계에서는 Step 13에서 만든 운영 상태 API를 바로 볼 수 있도록 analyzer 안에 읽기 전용 웹 UI를 붙였고, 이어서 Kubernetes `Service`로 바로 접근할 수 있게 정리했습니다. 핵심은 `/ui` 한 페이지에서 `dashboard`, `alerts`, `workflow`, `queue`, `spool` 상태를 카드형으로 보는 것과, 이를 `ebpf-ml-mao-ui` Service로 노출하는 것입니다.

## Added

- `app/ebpf_ml_mao/ui/dashboard.html`
- `app/ebpf_ml_mao/ui/dashboard.css`
- `app/ebpf_ml_mao/ui/dashboard.js`
- `app/ebpf_ml_mao/api.py`
  - `/ui`
  - `/assets/dashboard.css`
  - `/assets/dashboard.js`
- `deploy/yaml/step15/kustomization.yaml`
- `deploy/yaml/step15/ui-service.yaml`
- `tests/test_step15_ui.py`
- `tests/test_step15_artifacts.py`

## Service Access

- Service 이름: `ebpf-ml-mao-ui`
- Namespace: `ebpf-obs`
- 경로: `http://ebpf-ml-mao-ui.ebpf-obs.svc.cluster.local:8080/ui`
- analyzer 기존 Service도 동일하게 `/ui`를 제공하지만, 시각화 접근 경로를 분리하려고 UI alias Service를 추가했습니다.

## Visualization Scope

- 상태 pill: `ok`, `warning`, `critical`
- 주요 수치: ingest, queue, spool, alert count
- alert feed
- registry / workflow / queue / spool health 카드
- 15초 주기 자동 새로고침

## Validation

```bash
python3 -m unittest discover -s tests -v
kubectl kustomize deploy/yaml/step15
```

## Notes

- 현재는 analyzer API에 붙는 서버 렌더 없는 정적 대시보드입니다.
- 인증/세분화된 RBAC를 붙이지 않았기 때문에 운영 공개 범위는 배포 환경에서 따로 통제해야 합니다.
