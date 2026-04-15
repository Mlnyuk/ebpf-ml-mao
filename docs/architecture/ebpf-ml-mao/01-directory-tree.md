# 1. Final Directory Tree

아래 구조는 `eBPF 이벤트 수집`, `특징 추출`, `ML 추론`, `멀티에이전트 분석`, `리포트 생성`을 중심으로 잡은 최종 트리다.

```text
ebpf-ml-orchestrator/
├── cmd/
│   └── orchestrator/
│       └── main.go
├── config/
│   ├── config.yaml
│   └── prompts/
│       ├── summarizer.md
│       ├── analyst.md
│       ├── correlator.md
│       └── reviewer.md
├── deploy/
│   ├── tetragon/
│   │   └── tracingpolicy.yaml
│   ├── prometheus/
│   │   └── scrape-config.yaml
│   └── k8s/
│       └── orchestrator.yaml
├── internal/
│   ├── config/
│   │   └── loader.go
│   ├── domain/
│   │   ├── event.go
│   │   ├── feature.go
│   │   ├── anomaly.go
│   │   ├── context.go
│   │   └── report.go
│   ├── collector/
│   │   ├── ebpf.go
│   │   ├── tetragon.go
│   │   ├── metrics.go
│   │   └── normalizer.go
│   ├── features/
│   │   ├── extractor.go
│   │   ├── windowing.go
│   │   └── encoder.go
│   ├── ml/
│   │   ├── model.go
│   │   ├── inference.go
│   │   ├── scorer.go
│   │   └── threshold.go
│   ├── agents/
│   │   ├── interfaces.go
│   │   ├── summarizer.go
│   │   ├── analyst.go
│   │   ├── correlator.go
│   │   ├── reviewer.go
│   │   └── broker.go
│   ├── pipeline/
│   │   ├── coordinator.go
│   │   ├── dispatcher.go
│   │   ├── context_builder.go
│   │   └── circuit_breaker.go
│   ├── report/
│   │   ├── formatter.go
│   │   └── exporter.go
│   └── storage/
│       ├── memory.go
│       └── artifacts.go
├── testdata/
│   ├── benign/
│   └── anomalous/
├── Dockerfile
├── go.mod
└── README.md
```

## 설계 의도

- `collector/`: Tetragon, eBPF, 메트릭 입력을 하나의 내부 이벤트 포맷으로 정규화한다.
- `features/`: 이벤트를 ML 입력으로 바꾸는 계층이다.
- `ml/`: 모델 로딩, 추론, 점수화, 임계값 판정을 담당한다.
- `agents/`: 모델이 낸 수치 결과를 사람이 읽을 수 있는 분석으로 바꾸고, 여러 에이전트가 역할 분담한다.
- `pipeline/`: 전체 협업 순서와 장애 격리를 조정한다.
- `report/`: 최종 결과를 JSON, Markdown, API 응답 등으로 내보낸다.
- `storage/`: 실험 단계에서는 로컬 메모리와 아티팩트 저장만 두고, 나중에 DB를 붙일 수 있게 한다.

## 지금 단계에서 빼는 것

- 자동 복구 전용 `executor`
- `kubectl` 중심 실행 계층
- rollback, remediation policy, change approval

이 요소들은 현재 프로젝트의 핵심이 아니라 다음 단계 프로젝트로 넘기는 것이 맞다.
