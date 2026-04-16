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
- `deploy/yaml/step15/patch-serviceaccounts.yaml`
- `deploy/yaml/step15/ghcr-pull-secret.example.yaml`
- `deploy/yaml/step15/kustomization.yaml`
  - `configMapGenerator` 로 `generated/live.py` 기반 `ebpf-ml-mao-live-py` 생성
- `tests/test_step15_ui.py`
- `tests/test_step15_artifacts.py`

## Service Access

- Service 이름: `ebpf-ml-mao-ui`
- Namespace: `ebpf-obs`
- 타입: `NodePort`
- 내부 경로: `http://ebpf-ml-mao-ui.ebpf-obs.svc.cluster.local:8080/ui`
- 외부 노드 포트: `30002`
- analyzer 기존 Service도 동일하게 `/ui`를 제공하지만, 시각화 접근 경로를 분리하려고 UI alias Service를 추가했습니다.

## Visualization Scope

- 상태 pill: `ok`, `warning`, `critical`
- 주요 수치: ingest, queue, spool, alert count
- alert feed
- registry / workflow / queue / spool health 카드
- 15초 주기 자동 새로고침


## GHCR Pull Secret

현재 이미지가 `ghcr.io/mlnyuk/ebpf-ml-mao:step14` 이고 클러스터에서 anonymous pull이 막혀 있으면 `ghcr-pull-secret` 이 필요합니다.

```bash
kubectl create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username=<github-user> \
  --docker-password=<pat-with-read:packages> \
  --docker-email=unused@example.com \
  -n ebpf-obs
```

생성 후 `kubectl apply -k deploy/yaml/step15` 를 다시 적용하면 analyzer/collector ServiceAccount가 이 secret을 사용합니다.

## Reproducibility

- `ebpf-ml-mao-live-py` ConfigMap은 이제 `deploy/yaml/step15/kustomization.yaml`의 `configMapGenerator`가 직접 생성합니다.
- 따라서 fresh cluster에서도 별도 수동 `kubectl create configmap` 없이 `kubectl apply -k deploy/yaml/step15` 만으로 동일한 collector patch가 재현됩니다.


## Scaling

- `ANALYZER_ALERT_QUEUE_THRESHOLD` 는 `50` 으로 상향했습니다.
- Step 15 overlay는 analyzer `HPA` 를 추가해서 CPU/메모리 압력에 따라 `minReplicas=1`, `maxReplicas=3` 범위에서 자동 확장할 수 있게 했습니다.
- 다만 analyzer는 현재 `ReadWriteOnce` PVC 와 파일 기반 `registry/ingest/postprocess-queue` 를 공유하는 단일 writer 성격이 강하므로, 고정 `replicas: 2~3` 을 강제하는 것은 권장하지 않습니다.
- backlog 기반 자동 확장은 아직 구현되지 않았습니다. 현재 HPA 는 `metrics-server` 의 CPU/메모리 메트릭만 사용합니다. backlog 대응은 별도 worker 또는 custom metrics/KEDA 단계가 필요합니다.

## Validation

```bash
python3 -m unittest discover -s tests -v
kubectl kustomize deploy/yaml/step15
```

## Notes

- 현재는 analyzer API에 붙는 서버 렌더 없는 정적 대시보드입니다.
- 인증/세분화된 RBAC를 붙이지 않았기 때문에 운영 공개 범위는 배포 환경에서 따로 통제해야 합니다.
