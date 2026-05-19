# Anomaly detection 결과를 논문 및 발표용 결과표로 정리

## Background

Step 16에서 Tetragon, Prometheus, analyzer API 결과가 complete 상태로 수집되었다. 이제 raw artifact를 논문 및 발표에 바로 사용할 수 있는 결과표 형태로 정리해야 한다.

Related commit: `35ebcec` (`Finalize Step 16 fault coverage validation`)

## Tasks

- 장애 시나리오별 주요 feature 변화를 표로 구성한다.
- scenario별 anomaly score 변화와 탐지 여부를 표로 구성한다.
- Tetragon 이벤트 coverage, Prometheus metric 변화, analyzer verdict를 한 표에서 비교한다.
- Prometheus + Grafana 방식과 비교할 수 있는 항목을 정리한다.
- 논문 본문/발표 슬라이드에 들어갈 요약 문장을 작성한다.

## Comparison Items

- 탐지 대상: metric-only vs event+metric
- 탐지 단위: dashboard 관찰 vs workload-level anomaly score
- 장애별 signal: exec storm, network burst, CPU stress, memory pressure
- 설명 가능성: 주요 feature 변화와 Tetragon event 근거
- 운영성: 자동 report/API/UI 제공 여부

## Deliverables

- 논문용 결과표 Markdown/CSV
- 발표용 요약 표
- Prometheus + Grafana 비교 표
- 결과 해석 문단 초안

## Done

- 장애 시나리오별 feature, score, verdict가 한눈에 비교된다.
- Prometheus + Grafana 대비 본 시스템의 차별점이 표로 설명된다.
- 결과표가 현재 `results/step16` artifact와 연결된다.
