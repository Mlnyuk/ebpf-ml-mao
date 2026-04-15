# Step 11

Step 11 범위는 `analyzer ingest 후처리 + collector 재전송/spool + dedupe + 운영 워크플로 연결`입니다.

이번 단계에서는 Step 10의 중앙 전송 경로를 운영 가능한 형태로 보강했습니다. collector는 전송 실패 시 spool에 남기고, 다음 루프에서 replay합니다. analyzer는 ingest index와 workflow summary를 유지하고, 같은 payload는 digest 기준으로 중복 처리합니다.

## Added

- `app/ebpf_ml_mao/api.py`
  - ingest index
  - workflow summary
  - duplicate-safe `POST /v1/reports`
  - `GET /v1/ingest`
- `app/ebpf_ml_mao/transport.py`
  - `ship_report(...)`
  - `drain_spool(...)`
  - local spool 파일 관리
- `app/ebpf_ml_mao/cli.py`
  - `ship-report`
  - `drain-spool`
  - `ingest-status`
- `deploy/yaml/step11/`
- `tests/test_step11_api.py`
- `tests/test_step11_transport.py`

## Runtime Changes

- `collector`
  - 먼저 spool replay 시도
  - 새 report 생성
  - 전송 실패 시 spool 저장
- `analyzer`
  - ingest index로 `received/unique/duplicate` 카운트 유지
  - workflow summary 파일 갱신
  - duplicate payload는 idempotent ack

## Validation

```bash
python3 -m unittest discover -s tests -v
kubectl kustomize deploy/yaml/step11
```

## Remaining Risks

- spool 파일도 JSON 파일 기반이라 동시성/손상 대비가 약함
- replay 정책은 단순 순차 재전송이라 우선순위/TTL 없음
- ingest workflow summary는 운영 메타 수준이고 실제 후속 분석 큐는 아직 아님
