# Step 11 Agent Notes

## Explorer 1

Step 11은 `실패해도 다시 보내고, 서버는 중복을 무해하게 처리하는 운영 레이어`를 붙이는 단계라고 정리했습니다.

반영한 내용:
- ingest digest dedupe
- collector spool/replay
- 운영용 ingest-status

## Explorer 2

핵심 리스크를 `중복 ingest`, `analyzer restart`, `network failure`, `spool replay`, `ingest index 손상`, `registry 경로 불일치`로 정리했습니다.

반영한 내용:
- duplicate-safe API
- ingest index/workflow summary 파일
- Step 11 문서에 남은 리스크 명시
