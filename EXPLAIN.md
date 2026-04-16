아래는 요청한 내용을 **Notion/문서 바로 붙여넣기 가능한 Markdown(.md)** 형식으로 정리한 버전이다.

---

# eBPF-ML-MAO vs Prometheus + Grafana 비교 분석

## 개요

`ebpf-ml-mao` 프로젝트는 단순한 메트릭 수집 및 시각화를 넘어서,
**eBPF 기반 실시간 데이터 수집 + 머신러닝 기반 이상 탐지**를 결합한
차세대 옵저버빌리티 시스템으로 판단된다.

기존의 `Prometheus + Grafana` 스택과 비교하면,
**데이터 깊이 / 분석 방식 / 아키텍처 / 목적**에서 본질적인 차이가 존재한다.

---

## 1. 데이터 수집 계층 (Data Collection)

### Prometheus

* HTTP 엔드포인트 기반 Pull 방식
* Counter, Gauge 등의 메트릭 수집
* 애플리케이션이 노출한 데이터에 의존 (L7 중심)

### ebpf-ml-mao

* eBPF 기반 커널 이벤트 직접 수집
* `tetragon-tracingpolicy.yaml` 활용 (Cilium Tetragon)
* 시스템 호출, 네트워크 흐름, 파일 접근 등 캡처

#### 관련 구성

* `adapters.py`
* `features.py`

→ 원시 커널 이벤트를 ML 입력용 Feature로 변환

### 핵심 차이

| 항목        | Prometheus   | ebpf-ml-mao        |
| --------- | ------------ | ------------------ |
| 데이터 수집 방식 | Pull (HTTP)  | Kernel Hook (eBPF) |
| 의존성       | 애플리케이션 노출 필요 | 애플리케이션 수정 불필요      |
| 수집 범위     | L7 중심        | L3~L7 + Syscall    |
| 실시간성      | 상대적으로 낮음     | 매우 높음              |

---

## 2. 분석 및 처리 엔진 (Analysis Engine)

### Prometheus

* PromQL 기반 규칙 처리
* Static Threshold (정적 임계치)

  * 예: `CPU > 80%`

### ebpf-ml-mao

* 머신러닝 기반 이상 탐지

#### 주요 구성

* `models.py`
* `scoring.py`
* `normalizer.py`
* `pipeline.py`

#### 데이터 구성

* `samples/benign.jsonl`
* `samples/anomalous.jsonl`

→ 정상 / 이상 데이터 기반 학습 및 검증

### 핵심 차이

| 항목     | Prometheus | ebpf-ml-mao   |
| ------ | ---------- | ------------- |
| 분석 방식  | 규칙 기반      | ML 기반         |
| 탐지 대상  | 알려진 패턴     | 알려지지 않은 이상 패턴 |
| 유연성    | 낮음         | 매우 높음         |
| 자동화 수준 | 제한적        | 높은 수준         |

---

## 3. 아키텍처 및 오케스트레이션 (MAO)

### Prometheus + Grafana

* 중앙 집중형 구조
* 시계열 DB + 시각화 중심

### ebpf-ml-mao

* 멀티 에이전트 오케스트레이션 (MAO)

#### 주요 구성

* `agents.py`
* `transport.py`

#### Kubernetes 리소스

* `collector-daemonset.yaml`
* `analyzer-deployment.yaml`

### 구조 특징

* Collector (데이터 수집)
* Analyzer (ML 분석)
* Agent 간 통신 (분산 처리)

### 핵심 차이

| 항목    | Prometheus | ebpf-ml-mao |
| ----- | ---------- | ----------- |
| 구조    | 중앙 집중형     | 분산형         |
| 확장성   | 제한적        | 매우 높음       |
| 처리 방식 | 단일 파이프라인   | 역할 기반 분산 처리 |
| 지능성   | 없음         | 에이전트 기반 협력  |

---

## 4. 시각화 및 UI (UI/UX)

### Grafana

* 범용 대시보드
* 다양한 데이터 소스 지원
* 커스터마이징 중심

### ebpf-ml-mao

* 전용 UI 제공

#### 구성

* `dashboard.html`
* JS / CSS 기반 UI

### 특징

* ML 결과 중심 시각화

  * 이상 점수
  * 위협 수준
  * 이벤트 흐름

### 핵심 차이

| 항목     | Grafana | ebpf-ml-mao    |
| ------ | ------- | -------------- |
| 목적     | 범용 시각화  | ML 결과 특화       |
| 데이터 표현 | 메트릭 중심  | 이상 탐지 중심       |
| 커스터마이징 | 높음      | 제한적 but 목적 최적화 |

---

## 종합 비교표

```
┌─────────────┬───────────────────────────────┬───────────────────────────────────────┐
│ 비교 항목   │ Prometheus + Grafana          │ ebpf-ml-mao                           │
├─────────────┼───────────────────────────────┼───────────────────────────────────────┤
│ 데이터 소스 │ 애플리케이션 메트릭 (L7 중심) │ eBPF 커널 이벤트 (L3-L7, 시스템 전체) │
│ 분석 방식   │ 정적 임계치 및 규칙 (PromQL)  │ 머신러닝 기반 이상 탐지 (Scoring/ML)  │
│ 가시성 깊이 │ 서비스 지표 중심              │ 커널/시스템 호출 수준의 딥 가시성     │
│ 구조        │ 중앙 집중형 시계열 DB         │ 분산 멀티 에이전트 (MAO)              │
│ 주요 목적   │ 성능 모니터링 및 상태 확인    │ 보안 위협 탐지 및 지능형 가시성 확보  │
└─────────────┴───────────────────────────────┴───────────────────────────────────────┘
```

---

## 결론

`ebpf-ml-mao`는 단순 모니터링 도구가 아니라, 다음을 목표로 하는 시스템이다:

* 커널 레벨의 Deep Observability 확보
* ML 기반 자동 이상 탐지
* 분산 에이전트 기반 지능형 분석

특히:

> **eBPF + ML + Multi-Agent 구조의 결합 = Runtime Security & Intelligent Observability**

이는 기존 Prometheus 스택이 제공하지 못하는
**보안 중심 관측 + 실시간 이상 탐지** 영역을 커버한다.



