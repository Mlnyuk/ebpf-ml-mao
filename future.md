# Future Architecture After Full eBPF Integration

작성 기준일: 2026-04-14 UTC

이 문서는 현재 클러스터 구조([spec.md](/root/Capstone/spec.md))를 바탕으로, 나중에 eBPF 수집과 분석 파이프라인이 실제 운영 경로에 완전히 연결됐을 때 아키텍처가 어떻게 바뀌는지 정리한 미래 구조 문서다.

핵심 가정은 다음과 같다.

- Tetragon은 계속 커널 이벤트 수집의 기본 축으로 유지한다.
- Prometheus는 메트릭 수집 축으로 유지한다.
- 저장소의 Python 파이프라인은 오프라인 샘플 처리에서 벗어나 실시간 입력 소비기로 확장된다.
- 멀티 에이전트는 최종 설명, 상관분석, 판정 리포트 계층으로 남는다.
- 초기에는 탐지 중심으로 가고, 자동 조치는 나중 단계로 분리한다.

## 1. 현재와 미래의 가장 큰 차이

현재 구조:

```text
Tetragon / Prometheus
  -> 파일 또는 샘플 기반 입력
  -> Python adapter
  -> feature extraction
  -> anomaly scoring
  -> report
```

미래 구조:

```text
Kernel / Container / Process / Network events
  -> eBPF probes / Tetragon
  -> event transport layer
  -> normalization + enrichment
  -> stream windowing
  -> online inference
  -> multi-agent analysis
  -> report / alert / optional response
```

즉, 가장 큰 변화는 `샘플 기반 분석기`가 `실시간 운영 분석 시스템`으로 바뀌는 것이다.

## 2. 목표 아키텍처 한눈에 보기

```text
                                +----------------------------------+
                                |        Kubernetes Cluster         |
                                | control / infra / worker / gpu   |
                                +----------------+-----------------+
                                                 |
                      +--------------------------+---------------------------+
                      |                          |                           |
            +---------v---------+      +---------v---------+       +---------v---------+
            |   Tetragon DS     |      |  Prometheus Stack |       | Optional eBPF DS  |
            | process/file/net  |      | cpu/mem/net/gpu   |       | custom probes      |
            +---------+---------+      +---------+---------+       +---------+---------+
                      |                          |                           |
                      +-------------+------------+---------------------------+
                                    |
                           +--------v--------+
                           | Event Ingestion |
                           | gRPC / file bus |
                           | queue / stream  |
                           +--------+--------+
                                    |
                    +---------------+----------------+
                    |                                |
          +---------v---------+            +---------v---------+
          | Normalizer        |            | Enricher          |
          | common schema     |            | pod/node/meta     |
          | dedupe / cleanup  |            | labels/baseline   |
          +---------+---------+            +---------+---------+
                    |                                |
                    +---------------+----------------+
                                    |
                           +--------v--------+
                           | Window / State  |
                           | 30s / 1m / 5m   |
                           | workload scope  |
                           +--------+--------+
                                    |
                     +--------------+---------------+
                     |                              |
           +---------v---------+          +---------v---------+
           | Online Inference  |          | Rules / Heuristics |
           | anomaly score     |          | hard signals       |
           | feature weights   |          | allow/block lists  |
           +---------+---------+          +---------+---------+
                     |                              |
                     +--------------+---------------+
                                    |
                           +--------v--------+
                           | Case Builder    |
                           | timeline /      |
                           | correlated case |
                           +--------+--------+
                                    |
                    +---------------+----------------+
                    |                                |
          +---------v---------+            +---------v---------+
          | Multi-Agent       |            | Alert/Storage/API |
          | summarizer        |            | JSON, Markdown,   |
          | analyst           |            | webhook, UI       |
          | correlator        |            +-------------------+
          | reviewer          |
          +-------------------+
```

## 3. 새로 추가되거나 커지는 계층

현재 `spec.md` 기준 실제 운영 스택은 이미 충분히 갖춰져 있다. eBPF가 본격적으로 들어가면 아래 계층이 추가되거나 비중이 커진다.

### 3.1 Event Ingestion Layer

현재는 샘플 파일 입력이지만, 미래에는 실제 이벤트 수집 레이어가 필요하다.

가능한 입력 소스:

- Tetragon gRPC stream
- Tetragon export file tail
- Prometheus HTTP query 또는 remote read
- 필요 시 custom eBPF agent output

권장 방향:

- 1차는 `Tetragon gRPC + Prometheus API`
- 2차는 버퍼링을 위해 경량 queue를 둔다

이 레이어가 들어가면 파이프라인이 배치형이 아니라 연속 처리형으로 바뀐다.

### 3.2 Normalization + Enrichment Layer

단순 파싱만으로는 부족해지고, 운영 컨텍스트를 붙이는 계층이 필요하다.

추가될 enrichment 예시:

- pod -> deployment / statefulset / daemonset 매핑
- namespace risk tier
- node pool 정보
- GPU workload 여부
- baseline profile ID
- known benign process profile

즉 이벤트는 단순한 `execve 발생`이 아니라:

`gpu-2의 research-jupyter pod에서 baseline에 없던 python child process가 높은 CPU와 함께 발생`

같은 해석 가능한 레코드로 바뀌어야 한다.

### 3.3 Stateful Window / Feature Store

현재도 30초 window 개념은 있지만, 미래에는 실시간 상태 저장이 필요하다.

필요한 상태:

- 최근 N분 이벤트 window
- workload별 이전 baseline
- 이미 발행한 case ID
- suppression / dedupe 상태
- 동일 pod의 이전 score 추이

이 계층은 최소한 메모리 + 로컬 상태로 시작할 수 있지만, 운영화되면 외부 저장소가 필요해질 가능성이 높다.

### 3.4 Online Inference Layer

미래 구조에서는 모델이 오프라인 보고서용이 아니라 운영 중 점수화 엔진이 된다.

추천 방향:

- baseline 학습은 오프라인
- 추론은 온라인
- 룰 기반 시그널과 ML 점수를 함께 사용

예:

- `privilege escalation`은 룰 기반 high severity
- `exec burst + cpu spike + new outbound connection`은 ML + correlation 기반 anomaly

즉 순수 ML 하나로 가지 않고 `rules + ML hybrid` 구조가 더 현실적이다.

### 3.5 Case Management Layer

이 계층은 현재 코드에는 거의 없지만, 운영 시스템으로 가면 중요해진다.

역할:

- 같은 사건 묶기
- alert storm 줄이기
- 동일 원인 재발 식별
- severity / confidence 계산
- 사람이 읽는 incident 단위로 정리

결과적으로 미래 시스템의 단위는 `event`가 아니라 `case`가 된다.

## 4. 노드별 역할은 어떻게 바뀌는가

현재 노드 풀은 `control / infra / worker / gpu` 4계층이다. eBPF가 실전 배치되면 각 풀의 역할이 조금 더 분명해진다.

### 4.1 Control Plane

계속 control-plane 역할이 중심이다.

추가 변화:

- Tetragon이 control-plane 이벤트도 계속 수집
- API server, scheduler, controller-manager 주변 비정상 syscall/event 관측 가능
- 단, 분석 엔진 자체를 control-plane에 올리는 것은 가능하면 피하는 편이 안전하다

즉 control-plane은 `수집 대상`이지 `분석 실행 장소`로 쓰지 않는 것이 맞다.

### 4.2 Infra Nodes

미래에는 infra 노드가 가장 중요한 `분석 플랫폼 노드`가 될 가능성이 높다.

적합한 배치:

- ingestion service
- normalization service
- inference service
- alert dispatcher
- case API

이유:

- control-plane과 분리 가능
- GPU 노드와도 분리 가능
- 현재도 공용 인프라 성격이 강함

즉 infra pool은 미래 구조에서 `security analytics plane` 역할로 커질 수 있다.

### 4.3 General Workers

일반 워커는 계속 관측 대상이자 일부 분석 워크로드 실행 노드가 된다.

가능한 변화:

- per-node lightweight collector sidecar/daemon 유지
- 일부 stream processor replica 분산 실행
- 고비용 추론은 infra 또는 gpu로 넘김

### 4.4 GPU Workers

GPU 노드는 두 가지 역할 중 하나로 분화될 수 있다.

1. 단순히 GPU workload를 관측하는 대상
2. GPU를 쓰는 고비용 inference 노드

초기에는 1번이 더 현실적이다. 현재 파이프라인 규모라면 GPU inference가 꼭 필요하지는 않다.

따라서 미래 초반 설계는:

- GPU 노드는 `관측 대상`
- 분석 엔진은 `infra 노드`

로 두는 편이 깔끔하다.

## 5. 데이터 흐름은 어떻게 바뀌는가

현재:

```text
raw file
  -> normalize
  -> feature
  -> score
  -> report
```

미래:

```text
Tetragon stream + Prometheus scrape + optional custom eBPF
  -> ingestion
  -> normalize
  -> enrich
  -> window/state
  -> online score
  -> correlate
  -> case
  -> agent explanation
  -> alert/report/api
```

여기서 새로 중요한 지점:

- `enrich`
- `state`
- `case`
- `alert/api`

즉 운영 시스템이 되려면 단순 분석보다 `사건 관리`와 `지속 상태`가 필요하다.

## 6. Tetragon만으로 충분한가

초기와 중기 단계에서는 `대체로 충분`하다.

이유:

- 이미 실제 클러스터에 배포되어 있음
- process/file/network 관측 범위가 현재 목적에 맞음
- Prometheus와 메트릭 결합도 가능함

하지만 미래에 아래가 필요해지면 custom eBPF가 추가될 수 있다.

- 특정 애플리케이션 syscall profile
- ring buffer 기반 초저지연 이벤트
- Tetragon 정책으로 표현하기 어려운 세밀한 probe
- 사용자 정의 kernel/user-space correlation

따라서 미래 구조는 아래 우선순위가 적절하다.

1. `Tetragon first`
2. 부족한 지점만 custom eBPF supplement

즉 처음부터 별도 eBPF agent를 크게 키우기보다 `Tetragon 확장 + 부족분 보강`이 맞다.

## 7. 저장소 코드 구조는 어떻게 바뀌는가

현재 Python 코드의 중심은 batch-style pipeline이다.

미래에는 대략 아래 모듈이 추가될 가능성이 높다.

```text
app/ebpf_ml_mao/
  adapters.py
  pipeline.py
  normalizer.py
  features.py
  scoring.py
  agents.py
  report.py
  cli.py

  ingest/
    tetragon_stream.py
    prometheus_client.py
    event_bus.py

  enrich/
    kubernetes_metadata.py
    baselines.py

  state/
    windows.py
    dedupe.py
    cases.py

  serving/
    api.py
    alerts.py
    sinks.py

  models/
    offline_training.py
    online_inference.py
```

핵심 변화:

- `batch CLI` 중심에서 `long-running service` 중심으로 이동
- 단발성 report 생성기에서 `stream consumer + case builder`로 이동

## 8. 배포 아키텍처는 어떻게 바뀌는가

미래에는 아래처럼 배포 경계가 나뉘는 것이 가장 현실적이다.

### 8.1 Node-level collectors

DaemonSet 계층:

- `tetragon`
- 필요 시 lightweight custom `ebpf-agent`

역할:

- 노드 로컬 이벤트 수집
- 커널/컨테이너 레벨 관측

### 8.2 Cluster-level analytics services

Deployment 또는 StatefulSet 계층:

- `event-ingestor`
- `normalizer-enricher`
- `inference-engine`
- `case-manager`
- `report-api`

권장 배치:

- 초기에는 `infra` 노드 선호
- control-plane에는 배치하지 않음

### 8.3 State and Storage

미래에는 아래 저장이 필요해질 수 있다.

- baseline model artifact
- recent case state
- suppression rule
- alert history
- feature snapshots

초기에는 `Longhorn PVC + 간단한 DB/파일 저장`으로 시작 가능하다.

## 9. 멀티 에이전트 역할은 어떻게 바뀌는가

현재 멀티 에이전트는 보고서 생성용 논리 계층에 가깝다. 미래에는 `운영 판단 보조 계층`으로 올라간다.

예상 역할:

- `Summarizer`
  이벤트 타임라인 요약
- `Analyst`
  ML score와 규칙 신호 해석
- `Correlator`
  프로세스/네트워크/메트릭 연결
- `Reviewer`
  최종 severity, confidence, next action 제안

나중에는 추가 역할도 가능하다.

- `Responder`
  사람이 승인할 조치안 제시
- `Tuner`
  baseline drift나 과탐 규칙 제안

단, 자동 `kubectl` 조치까지 바로 연결하는 것은 초기에 넣지 않는 편이 좋다.

## 10. 운영상 바뀌는 의사결정 포인트

eBPF가 완전히 들어오면 설계 고민도 바뀐다.

### 10.1 이벤트 볼륨 관리

문제:

- exec/file/network 이벤트가 많아질 수 있음
- GPU/Jupyter 워크로드는 프로세스 churn이 클 수 있음

필요한 대응:

- policy filtering
- dedupe
- namespace/workload별 샘플링 정책
- severity-first routing

### 10.2 False Positive 관리

문제:

- 정상 admin 작업과 이상 행위를 구분하기 어려움
- Jupyter 기반 연구 워크로드는 실행 패턴이 불규칙함

필요한 대응:

- namespace/workload별 baseline 분리
- known good profile 등록
- reviewer 단계에서 confidence 분리

### 10.3 성능과 격리

문제:

- 분석 파이프라인이 무거워지면 클러스터 운영에 영향을 줄 수 있음

필요한 대응:

- analytics plane을 infra 노드에 격리
- GPU 노드와 control-plane에 과한 분석 부하 금지
- Tetragon policy 범위 단계적 확대

## 11. 단계별 추천 진화 순서

가장 현실적인 전개 순서는 아래다.

### Phase A. Live ingestion

- Tetragon gRPC 또는 export file 실시간 수집
- Prometheus API 조회 연결
- 기존 batch pipeline을 live input 대응으로 확장

### Phase B. Stateful scoring

- per-workload baseline 저장
- sliding window 상태 유지
- repeated alert suppression

### Phase C. Case management

- 동일 사건 묶기
- severity / confidence / owner 생성
- JSON/Markdown 외에 API 출력 제공

### Phase D. Semi-automated operations

- Slack/Webhook/Issue 발행
- human-in-the-loop 승인 구조
- 필요한 경우만 후속 조치안 추천

### Phase E. Optional active response

- quarantine
- scale down
- policy tighten

이 단계는 가장 마지막에 넣는 것이 맞다.

## 12. 최종적으로 바뀌는 시스템 성격

현재 시스템은:

- `관측 실험 + 오프라인 분석 파이프라인`

미래 시스템은:

- `실시간 eBPF 기반 Kubernetes 보안/운영 분석 플랫폼`

으로 바뀐다.

즉 앞으로 eBPF가 본격적으로 들어가면 바뀌는 핵심은 단순히 probe가 추가되는 것이 아니라 아래 네 가지다.

1. 입력이 파일에서 스트림으로 바뀜
2. 분석 단위가 이벤트에서 케이스로 바뀜
3. 파이프라인이 배치에서 상태 기반 서비스로 바뀜
4. 리포트가 사후 문서에서 운영 의사결정 입력으로 바뀜

## 13. 결론

나중에 eBPF까지 완전히 들어간 구조의 중심은 `Tetragon + Prometheus + 실시간 분석 서비스 + 멀티 에이전트 해석 계층`이다.

현재 클러스터 기준으로 가장 자연스러운 미래 아키텍처는 다음과 같다.

- 노드 단위 수집은 `Tetragon` 중심
- 필요 시 custom eBPF는 보조 수단
- 분석 서비스는 `infra 노드` 중심 배치
- GPU 노드는 우선 관측 대상
- 결과는 `case`, `alert`, `report`, `API` 형태로 제공

즉 이 프로젝트의 다음 진화는 `eBPF 이벤트를 더 많이 수집하는 것` 자체보다, `그 이벤트를 운영 가능한 사건 단위로 정리하고 설명하는 플랫폼`으로 가는 것이다.
