# 멀티 에이전트 오케스트레이션 아키텍처

이 문서는 `eBPF 기반 Kubernetes 환경 관리 시스템`을 만들기 위해 `claude code`, `codex`, `gemini cli`를 함께 사용하는 멀티 에이전트 오케스트레이션 구조를 설명한다. 핵심은 여러 모델을 동시에 쓰는 것이 아니라, 서로 다른 강점을 역할 단위로 분리하고 결과를 하나의 실행 파이프라인으로 통합하는 것이다.

## 1. 목표

오케스트레이션의 목표는 다음과 같다.

- 설계, 구현, 검증을 병렬화한다.
- 서로 다른 에이전트의 장점을 역할별로 활용한다.
- 결과물을 표준 포맷으로 수집해 충돌과 중복을 줄인다.
- eBPF, Kubernetes, 운영 자동화처럼 복합 도메인에서 생산성을 높인다.

## 2. 에이전트 역할 분리

### Claude Code

`Claude Code`는 문서화, 요구사항 구조화, 아키텍처 논리 정리에 적합하다.

- 요구사항 해석
- ADR, 설계 문서, 정책 모델 정의
- 각 작업 단위의 입력/출력 명세 작성
- 구현 결과에 대한 설명 문서 초안 작성

### Codex

`Codex`는 실제 코드 변경과 통합에 적합하다.

- controller, CLI, collector, operator 코드 구현
- 테스트 코드 작성
- 파일 단위 수정과 리팩터링
- 최종 통합 및 검증

### Gemini CLI

`Gemini CLI`는 긴 문맥 탐색과 비교 분석에 적합하다.

- 대규모 코드베이스 검색
- 설정 파일, 매니페스트, 로그 비교
- 복수 구현안 비교
- 긴 실행 로그나 스펙 문서 요약

## 3. 상위 아키텍처

전체 구조는 다음 흐름으로 동작한다.

1. 사용자가 목표를 입력한다.
2. 오케스트레이터가 목표를 작업 단위로 분해한다.
3. 각 작업을 가장 적합한 에이전트에 할당한다.
4. 에이전트는 결과를 표준 출력 형식으로 반환한다.
5. 통합 단계에서 결과를 병합하고 충돌을 검사한다.
6. 최종 실행자 또는 메인 에이전트가 저장소에 반영하고 테스트한다.

텍스트 기준 구조는 아래처럼 볼 수 있다.

```text
User Request
    |
    v
Orchestrator
    |
    +--> Planner
    |       |
    |       +--> Task A -> Claude Code
    |       +--> Task B -> Codex
    |       +--> Task C -> Gemini CLI
    |
    +--> Result Collector
    |
    +--> Judge / Merger
    |
    +--> Executor
    |
    v
Repository + Test + Docs
```

## 4. 내부 컴포넌트

### 4.1 Planner

`Planner`는 사용자 목표를 실행 가능한 작업으로 분해한다.

예를 들어 `eBPF 기반 k8s 환경 관리`라는 목표는 다음처럼 나뉠 수 있다.

- eBPF 이벤트 수집기 설계
- Kubernetes CRD 및 controller 설계
- DaemonSet 배포 구조 설계
- 관측 데이터 저장 포맷 정의
- 테스트 및 검증 시나리오 작성

Planner는 각 작업에 대해 아래 정보를 만든다.

- `goal`
- `scope`
- `constraints`
- `expected_output`
- `owner_agent`

### 4.2 Agent Runner

`Agent Runner`는 실제로 `claude code`, `codex`, `gemini cli`를 호출하는 계층이다. 이 계층은 각 에이전트 실행 방법이 달라도 외부에는 동일한 인터페이스를 제공해야 한다.

예를 들어 내부적으로는 다음 차이를 가질 수 있다.

- Claude Code는 문서 작성 중심 프롬프트 사용
- Codex는 파일 수정 및 테스트 실행 중심 프롬프트 사용
- Gemini CLI는 탐색 및 비교 분석 중심 프롬프트 사용

하지만 반환 형식은 통일한다.

```json
{
  "summary": "what was done",
  "files_changed": ["path/a", "path/b"],
  "commands_run": ["go test ./...", "kubectl kustomize ..."],
  "risks": ["kernel compatibility", "rbac missing"],
  "next_step": "implement controller reconciliation"
}
```

### 4.3 Result Collector

`Result Collector`는 각 에이전트의 결과를 저장하고, 메타데이터를 붙여 추적 가능하게 만든다.

수집 항목 예시는 다음과 같다.

- 작업 ID
- 에이전트 종류
- 시작/종료 시간
- 변경 파일 목록
- 테스트 결과
- 실패 여부 및 에러 메시지

이 레이어가 있어야 나중에 "누가 어떤 판단으로 어떤 파일을 바꿨는지"를 추적할 수 있다.

### 4.4 Judge / Merger

이 계층은 멀티 에이전트 구조에서 가장 중요하다. 여러 에이전트가 동시에 일하면 결과 품질보다 먼저 충돌 관리가 문제가 되기 때문이다.

Judge는 다음을 확인한다.

- 서로 다른 에이전트가 같은 파일을 수정했는지
- 설계 문서와 구현 내용이 일치하는지
- 테스트가 통과하는지
- 정책 모델과 런타임 구현이 어긋나지 않는지

필요하면 Judge는 재작업을 지시한다.

- 설계 누락이면 Claude Code에 재질문
- 구현 미완이면 Codex에 재할당
- 근거 확인이 필요하면 Gemini CLI에 재탐색 요청

### 4.5 Executor

`Executor`는 승인된 결과만 실제 저장소와 실행 환경에 반영한다.

역할은 다음과 같다.

- 변경사항 merge
- 테스트 실행
- 문서 업데이트 반영
- 필요한 경우 manifest 생성 또는 배포 스크립트 실행

실제 운영에서는 이 계층이 CI/CD와 연결될 수 있다.

## 5. eBPF + Kubernetes 도메인에 맞춘 작업 배치

이 프로젝트에서는 일반적인 웹 애플리케이션보다 작업 성격 차이가 크므로, 에이전트 역할을 아래처럼 두는 것이 적절하다.

### 트랙 A. eBPF 런타임

- probe attach 방식 결정
- kernel event 수집기 구현
- ring buffer event schema 정의

주 담당은 `Codex`가 적합하다.

### 트랙 B. Kubernetes Control Plane

- CRD 설계
- controller reconciliation 구조
- DaemonSet/operator 배포 구조

`Claude Code`가 설계를 정리하고 `Codex`가 구현하는 조합이 적절하다.

### 트랙 C. 탐색 및 검증

- 기존 오픈소스 구조 비교
- 로그/설정 차이 분석
- 대규모 파일 집합 탐색

`Gemini CLI`가 보조 분석 역할로 적절하다.

## 6. 충돌을 줄이는 운영 원칙

멀티 에이전트는 병렬성이 장점이지만, 파일 충돌과 책임 불분명으로 쉽게 무너진다. 따라서 아래 원칙이 필요하다.

- 하나의 작업은 하나의 책임 경계를 가진다.
- 서로 다른 에이전트는 가능한 한 다른 파일 집합을 담당한다.
- 설계와 구현이 연결되는 경우, 설계 산출물의 버전을 고정한 뒤 구현에 들어간다.
- 모든 에이전트는 동일한 출력 포맷을 사용한다.
- 최종 반영은 하나의 메인 실행자만 수행한다.

예를 들면 다음과 같이 소유권을 나눌 수 있다.

- `docs/` 및 ADR: Claude Code
- `pkg/controller/`, `cmd/`, `internal/`: Codex
- `research/`, 비교 보고서, 로그 분석: Gemini CLI

## 7. 추천 실행 순서

이 프로젝트에서 가장 현실적인 초기 오케스트레이션 순서는 다음과 같다.

1. Claude Code가 요구사항과 아키텍처 초안을 작성한다.
2. Gemini CLI가 참고 구현과 코드베이스 구조를 조사한다.
3. Codex가 실제 코드 골격과 테스트를 만든다.
4. Judge가 설계-구현 불일치를 검사한다.
5. 필요하면 보완 작업을 다시 각 에이전트에 배분한다.

## 8. 결론

이 아키텍처의 핵심은 "여러 에이전트를 동시에 쓰는 것"이 아니라 "각 에이전트를 표준화된 작업 단위 안에 넣는 것"이다. `claude code`, `codex`, `gemini cli`는 각각 잘하는 일이 다르기 때문에, 오케스트레이터가 작업 분해, 결과 수집, 충돌 판정, 최종 실행을 책임져야 전체 시스템이 안정적으로 돌아간다.

특히 `eBPF + Kubernetes`처럼 저수준 런타임과 고수준 control plane이 동시에 필요한 프로젝트에서는, 단일 에이전트보다 역할 분리형 멀티 에이전트 구조가 훨씬 실용적이다.
