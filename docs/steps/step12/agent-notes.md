# Step 12 Agent Notes

## Explorer 1

Step 12 최소 범위를 `spool TTL`, `replay 정책`, `ingest index 손상 복구`, `analyzer restart 복구`로 정리했습니다.

반영한 내용:
- transport TTL/prune/status
- api rebuild/repair
- 운영 CLI 추가

## Explorer 2

핵심 edge case를 `spool 무한 누적`, `stale spool 정리 없음`, `corrupt ingest index`, `restart 후 일관성 검증 부재`로 정리했습니다.

반영한 내용:
- corrupt spool quarantine
- readyz/status repair-aware 처리
- Step 12 문서에 운영 리스크 정리
