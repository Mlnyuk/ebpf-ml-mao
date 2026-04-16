# eBPF-ML-MAO 현재 구현 기준 요약

## 개요

현재 `/root/Capstone`의 `ebpf-ml-mao` 구현은 **직접 eBPF 프로그램을 로드하는 엔진**이라기보다,
**Tetragon이 수집한 eBPF 기반 런타임 이벤트**와 **Prometheus 메트릭**을 받아서
정규화, 특징 추출, 이상 탐지, 상태 시각화까지 수행하는 **analyzer/collector 시스템**에 가깝다.

즉 현재 구조는 아래처럼 이해하는 것이 정확하다.

- `eBPF 실행/관측`: Tetragon
- `메트릭 수집`: Prometheus
- `이벤트 정규화/이상 탐지`: ebpf-ml-mao
- `운영 상태 API/UI`: ebpf-ml-mao analyzer
- `시각화 보조`: Grafana는 별도 모니터링 계층

---

## 현재 구현된 핵심 범위

### 1. 입력 수집

현재 시스템은 두 가지 입력원을 사용한다.

- `Tetragon raw event`
  - JSONL 형태의 런타임 이벤트 입력
  - 파일 tail 기반 live ingestion 구현
- `Prometheus metrics`
  - snapshot JSON 어댑터 구현
  - HTTP scrape 기반 live ingestion 구현

관련 구현:

- `app/ebpf_ml_mao/adapters.py`
- `app/ebpf_ml_mao/live.py`
- `app/ebpf_ml_mao/pipeline.py`

중요한 점:

- 현재 앱이 직접 커널에 eBPF probe를 붙이는 구조는 아님
- eBPF 이벤트 생산은 `Tetragon`이 담당하고,
- 현재 앱은 그 결과를 소비해서 분석함

---

### 2. 분석 파이프라인

현재 파이프라인은 다음 단계를 수행한다.

1. raw event / metrics 입력 수집
2. 공통 이벤트 스키마로 정규화
3. time window 기준 feature 추출
4. anomaly score 계산
5. verdict 산출
6. JSON/Markdown 리포트 생성

관련 구현:

- `app/ebpf_ml_mao/normalizer.py`
- `app/ebpf_ml_mao/features.py`
- `app/ebpf_ml_mao/scoring.py`
- `app/ebpf_ml_mao/report.py`
- `app/ebpf_ml_mao/pipeline.py`

현재 지원하는 분석 모델:

- `baseline`
- `zscore`

---

### 3. 모델 관리

현재 시스템은 모델 파일을 저장하고 다시 불러와서 사용할 수 있다.
또한 registry를 통해 active model을 관리한다.

현재 구현된 기능:

- 모델 저장/로드
- schema version 관리
- model type 관리
- registry 등록/조회
- active model 전환
- registry 운영 기능 일부

관련 구현:

- `app/ebpf_ml_mao/scoring.py`
- `app/ebpf_ml_mao/registry.py`

현재 운영상 중요한 상태:

- analyzer는 active model이 없으면 `critical` 상태가 됨
- active model이 있어야 정상 분석 경로가 유지됨

---

### 4. 운영 API

analyzer는 운영 상태를 조회할 수 있는 HTTP API를 제공한다.

현재 제공되는 주요 API 범위:

- `/healthz`
- `/readyz`
- `/v1/dashboard`
- `/v1/alerts`
- `/v1/workflow`
- `/v1/queue`
- `/v1/ingest`
- `/v1/status`
- `/ui`

관련 구현:

- `app/ebpf_ml_mao/api.py`

현재 API가 다루는 운영 상태:

- ingest 누적 현황
- workflow 요약
- queue backlog
- spool 상태
- registry / active model 상태
- alert summary

---

### 5. UI / 시각화

현재 analyzer는 자체 UI를 직접 제공한다.

현재 구현:

- `/ui` 정적 대시보드
- dashboard / alerts / workflow / queue / spool 카드 표시
- 15초 주기 자동 새로고침

관련 구현:

- `app/ebpf_ml_mao/ui/dashboard.html`
- `app/ebpf_ml_mao/ui/dashboard.css`
- `app/ebpf_ml_mao/ui/dashboard.js`

Kubernetes 노출 상태:

- `ebpf-ml-mao-ui` Service
- `NodePort 30002`

외부 접근 예시:

- `http://<node-ip>:30002/ui`

---

### 6. Kubernetes 배포 상태

현재 배포 자산은 Step 15 기준까지 정리되어 있다.

주요 컴포넌트:

- `collector` DaemonSet
- `analyzer` Deployment
- `ui` alias Service
- runtime ConfigMap / Secret / PVC / NetworkPolicy
- GHCR image pull secret 연동

관련 경로:

- `deploy/yaml/step15/`

현재 클러스터 기준 상태는 다음을 목표로 운영된다.

- analyzer `1/1 Running`
- collector `2/2 Running` per node
- analyzer service endpoint 정상 등록
- UI service endpoint 정상 등록

---

## 현재 구현 수준에서 가능한 것

현재 구현으로 가능한 것:

- Tetragon 이벤트와 Prometheus 데이터를 함께 받아 분석
- 이상 점수 계산 및 verdict 산출
- active model 기반 운영
- ingest / queue / spool 상태 조회
- UI를 통한 운영 상태 확인
- Kubernetes에 analyzer/collector 배포
- CPU/메모리 기준 analyzer HPA 초안 적용

---

## 현재 구현 수준에서 아직 아닌 것

현재 구현이 아직 하지 않는 것:

- 앱 자체가 직접 eBPF probe를 로드/제어하는 구조
- active-active 다중 writer analyzer 구조
- backlog 기반 진짜 autoscaling
- 후처리 queue를 실제로 소비하는 dedicated worker
- Redis/Kafka/DB 기반 durable queue
- 완전한 runtime security product 수준의 정책 엔진

특히 중요한 제약:

- analyzer는 `ReadWriteOnce` PVC와 파일 기반 state를 공유하므로
  고정 `replicas: 2~3`을 바로 올리는 것은 안전하지 않음
- 현재 postprocess queue는 파일 기반 초안이라
  backlog를 실제로 소비하는 worker가 아직 없음
- 현재 HPA는 `CPU/메모리` 기준일 뿐,
  `queue backlog` 기준 autoscaling은 아직 구현되지 않음

---

## Prometheus + Grafana와의 현재 관계

현재 구현을 기준으로 보면,
`ebpf-ml-mao`는 `Prometheus + Grafana`를 완전히 대체하는 시스템이라기보다
다음 역할에 더 가깝다.

- Prometheus:
  - metric source
- Grafana:
  - 범용 대시보드 계층
- ebpf-ml-mao:
  - runtime event + metrics 기반 anomaly analyzer
  - 운영 상태 판단과 경보 요약 계층

즉 현재는 경쟁재라기보다,
**Prometheus/Tetragon 위에 얹는 분석 계층**으로 보는 것이 더 정확하다.

---

## 현재 코드 기준 핵심 파일

운영상 중요한 핵심 파일은 아래다.

- `app/ebpf_ml_mao/api.py`
- `app/ebpf_ml_mao/pipeline.py`
- `app/ebpf_ml_mao/live.py`
- `app/ebpf_ml_mao/adapters.py`
- `app/ebpf_ml_mao/scoring.py`
- `app/ebpf_ml_mao/registry.py`
- `app/ebpf_ml_mao/transport.py`
- `deploy/yaml/step15/`

---

## 현재 상태 한 줄 요약

현재 `ebpf-ml-mao`는
**Tetragon의 eBPF 런타임 이벤트와 Prometheus 메트릭을 받아 이상 탐지와 운영 시각화를 수행하는 Kubernetes 배포형 analyzer 시스템**까지는 구현되어 있다.

다만 아직은
**직접 eBPF를 제어하는 엔진**, **다중 writer 고가용성 analyzer**, **queue backlog 기반 autoscaling worker 구조**까지는 완성되지 않았다.
