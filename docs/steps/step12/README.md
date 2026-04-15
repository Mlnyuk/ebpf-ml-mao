# Step 12

Step 12 범위는 `운영 안정화`입니다.

이번 단계에서는 Step 11의 spool/replay와 ingest index를 실제 운영 관점에서 보강했습니다. 핵심은 `spool TTL`, `stale spool 정리`, `corrupt spool quarantine`, `ingest index 손상 복구`, `analyzer restart 후 상태 재구성`입니다.

## Added

- `app/ebpf_ml_mao/transport.py`
  - spool envelope (`queued_at`, `expires_at`, `payload`)
  - `spool_status(...)`
  - `prune_spool(...)`
  - TTL 기반 drain 정책
  - corrupt spool quarantine
- `app/ebpf_ml_mao/api.py`
  - atomic save
  - `rebuild_ingest_index(...)`
  - corrupt `index.json` 자동 백업 후 재생성
  - `readyz/status`에서 repair-aware ingest 확인
- `app/ebpf_ml_mao/cli.py`
  - `spool-status`
  - `spool-prune`
  - `ingest-repair`
- `deploy/yaml/step12/`
- `tests/test_step12_transport.py`
- `tests/test_step12_api.py`

## Runtime Changes

- `collector`
  - spool prune 선행
  - TTL 내 spool만 replay
  - 손상 spool은 quarantine으로 이동
- `analyzer`
  - corrupt ingest index 발견 시 backup 후 rebuild
  - restart 후 기존 ingest 파일을 기반으로 index/workflow 재구성 가능

## Validation

```bash
python3 -m unittest discover -s tests -v
kubectl kustomize deploy/yaml/step12
```

## Remaining Risks

- spool/ingest 모두 파일 기반이라 atomicity 한계는 여전히 있음
- rebuild는 저장된 payload 파일 기준이라 완전한 감사 로그는 아님
- replay 우선순위, rate limit, alerting은 아직 없음
