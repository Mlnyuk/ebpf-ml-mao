# Step 13

Step 13 범위는 `운영 인터페이스와 가시성`입니다.

이번 단계에서는 Step 12의 운영 안정화 위에 `대시보드용 상태 스냅샷`, `알림 임계값`, `파일 기반 후처리 큐 초안`을 추가했습니다. 핵심은 운영자가 analyzer 한 곳에서 `registry`, `ingest`, `workflow`, `queue`, `spool` 상태를 함께 볼 수 있게 만드는 것입니다.

## Added

- `app/ebpf_ml_mao/api.py`
  - `build_dashboard_snapshot(...)`
  - `/v1/dashboard`
  - `/v1/alerts`
  - `/v1/workflow`
  - `/v1/queue`
  - `readyz`의 active model / alert state 반영
- `app/ebpf_ml_mao/transport.py`
  - `enqueue_postprocess(...)`
  - `queue_status(...)`
  - `prune_queue(...)`
- `app/ebpf_ml_mao/models.py`
  - `AlertRecord`
  - `QueueSnapshot`
  - `DashboardSnapshot`
- `app/ebpf_ml_mao/cli.py`
  - `workflow-status`
  - `queue-status`
  - `queue-prune`
  - `dashboard-status`
  - `alerts-status`
- `deploy/yaml/step13/`
- `tests/test_step13_api.py`
- `tests/test_step13_transport.py`
- `tests/test_step13_cli.py`

## Runtime Changes

- analyzer는 보고서를 ingest한 직후 `postprocess-queue`에 후처리 작업 초안을 남깁니다.
- `/v1/dashboard`는 운영 판단용 단일 스냅샷을 제공합니다.
- `/v1/alerts`는 임계값 기반 경보만 분리해서 제공합니다.
- `readyz`는 active model 부재나 registry artifact 누락 시 실패합니다.

## Validation

```bash
python3 -m unittest discover -s tests -v
kubectl kustomize deploy/yaml/step13
```

## Remaining Risks

- collector spool은 노드별 로컬 상태라 analyzer에서 전역 집계를 자동으로 보지 못합니다.
- postprocess queue는 아직 파일 기반 초안이라 실제 worker/retry orchestration은 없습니다.
- 알림은 현재 API 스냅샷 단계이며 Slack/PagerDuty 같은 외부 통합은 아직 없습니다.
