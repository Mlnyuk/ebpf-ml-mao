# Analyzer 저장소 부족 방지를 위한 PVC 확장 및 retention 정책 적용

## Background

Step 16 재실행 중 analyzer PVC에서 inode 고갈이 발생했다. 디스크 용량 자체는 남아 있었지만 `ingest`와 `postprocess-queue`에 작은 JSON 파일이 과도하게 쌓여 `OSError: [Errno 28] No space left on device`가 발생했다. 장기 실험을 위해 PVC 용량과 retention 정책을 함께 정리해야 한다.

Related commit: `35ebcec` (`Finalize Step 16 fault coverage validation`)

## Tasks

- Analyzer PVC 또는 Longhorn 볼륨 용량을 확장한다.
- inode 고갈을 방지할 수 있는 파일 수 기준 retention 정책을 추가한다.
- `ingest`, `postprocess-queue`, `reports`, `spool`, `queue` 대상 자동 삭제 정책을 정리한다.
- `scripts/analyzer_prune.sh`를 운영용 cron/Job 형태로 연결할지 검토한다.
- 장기 실험 전 storage preflight를 강화한다.

## Recommended Direction

- PVC 용량 확장: 2Gi보다 큰 실험용 용량으로 증설
- retention 기준: age 기준 + max file count 기준 병행
- preflight: disk usage뿐 아니라 inode/file count도 검사
- prune: registry/models는 제외하고 generated runtime/experiment data만 삭제

## Deliverables

- PVC/Longhorn 확장 매니페스트 또는 운영 절차
- 자동 prune Job 또는 수동 운영 스크립트 개선
- storage preflight 개선 결과
- 장기 실험 가능 기준 문서

## Done

- Step 16~18 반복 실행 중 inode 고갈이 재발하지 않는다.
- analyzer 저장소 상태를 사전에 감지하고 정리할 수 있다.
- registry/models는 보존하면서 generated runtime data만 안전하게 정리된다.
