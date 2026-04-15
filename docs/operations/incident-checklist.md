# Incident Checklist

## readyz fail
- analyzer pod 로그 확인
- registry active model / artifact path 확인
- 최근 ConfigMap/Secret 변경 확인

## queue backlog 증가
- `/v1/queue` 확인
- postprocess queue 디렉터리 파일 수 확인
- analyzer 후처리 worker 부재 여부 확인

## duplicate ratio 급증
- `/v1/alerts` 확인
- collector 재전송/중복 ship 여부 확인
- ingest index와 workflow summary 비교

## spool backlog 증가
- collector hostPath spool 디렉터리 확인
- analyzer API 도달성, shared token, network policy 확인
