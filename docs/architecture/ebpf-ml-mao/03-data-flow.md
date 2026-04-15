# 3. Data Flow

이 프로젝트의 데이터 플로우는 `수집 -> 정규화 -> 특징 추출 -> ML 추론 -> 에이전트 협업 -> 리포트 출력`의 6단계로 본다.

## End-to-End Flow

```text
eBPF / Tetragon / Prometheus
        |
        v
Collector
        |
        v
Normalizer
        |
        v
Feature Extractor + Windowing
        |
        v
ML Inference + Scoring
        |
        v
Summarizer
        |
        +-------------------+
        |                   |
        v                   v
    Analyst            Correlator
        |                   |
        +---------+---------+
                  |
                  v
               Reviewer
                  |
                  v
         Final Anomaly Report
```

## 단계별 설명

### 1. Collector

- Tetragon 이벤트를 구독한다.
- eBPF 기반 런타임 이벤트를 수집한다.
- Prometheus 메트릭을 동일 시간대 스냅샷으로 가져온다.

출력 예시:
- `process_exec`
- `file_open`
- `dns_request`
- `cpu_usage`
- `memory_usage`

### 2. Normalizer

- 서로 다른 소스의 이벤트를 내부 공통 스키마로 바꾼다.
- 타임스탬프, pod, container, pid, node 같은 키를 통일한다.
- 누락 필드를 표준 기본값으로 채운다.

핵심 이유:
- 이 계층이 없으면 feature 추출과 에이전트 프롬프트가 소스별 조건문으로 오염된다.

### 3. Feature Extractor + Windowing

- 일정 시간 윈도우 단위로 이벤트를 묶는다.
- 프로세스 수, 네트워크 연결 수, 파일 접근 유형, syscall burst, CPU/메모리 변동 같은 feature를 만든다.
- 모델이 바로 사용할 수 있는 벡터 또는 집계 구조로 변환한다.

### 4. ML Inference

- 사전 학습된 anomaly detection 모델에 feature를 넣는다.
- anomaly score, 클래스, 기준선 편차를 출력한다.
- 단일 점수뿐 아니라 top feature contribution도 함께 남긴다.

### 5. Multi-Agent Analysis

- `Summarizer`: 원시 사건을 짧은 타임라인으로 요약
- `Analyst`: ML 점수와 feature 의미를 해석
- `Correlator`: 이벤트와 메트릭을 묶어 시나리오 생성
- `Reviewer`: 최종 판정과 confidence 산출

### 6. Report Output

- JSON 리포트 생성
- Markdown 설명 리포트 생성
- 나중에 API 또는 UI 응답 포맷으로 확장 가능

## 처리 단위

MVP에서는 `time window + workload identity`를 기본 처리 단위로 잡는 것이 현실적이다.

예:
- 최근 30초
- 특정 Pod 또는 컨테이너

이유:
- 지나치게 큰 범위는 설명 가능성이 떨어진다.
- 지나치게 작은 범위는 상관분석이 약해진다.

## 재분석 규칙

- Reviewer confidence가 임계값 이하이면 한 번 더 추가 컨텍스트를 수집한다.
- 재분석은 최대 1회만 허용한다.
- 무한 루프형 오케스트레이션은 현재 단계에서 금지한다.
