# Step 3 Agent Notes

## Local Design

Step 3에서는 live ingestion을 위해 외부 서비스 의존성을 최소로 유지했습니다.

- Prometheus: `urllib.request` 기반 HTTP scrape
- parser: Prometheus text exposition 직접 파싱
- Tetragon: local JSONL log tail

## Why File Tail Instead Of gRPC

- 현재 단계 목표는 live ingestion 진입점 확보
- 파일 tail은 재현성과 테스트성이 높음
- gRPC는 다음 단계에서 reconnect, stream state, proto version까지 같이 다뤄야 해서 범위가 커짐

## Validation Focus

- tail이 마지막 줄만 읽는지
- scrape 응답에서 필요한 metric만 추출하는지
- baseline 대비 anomaly scoring이 그대로 유지되는지
