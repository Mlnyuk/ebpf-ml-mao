# Step 1 Agent Notes

## Claude Code

`claude` CLI에는 Phase 1 MVP 구현 구조를 검토시키고, 아래 방향을 반영했습니다.

- 오프라인 샘플 데이터 기반으로 먼저 파이프라인 고정
- 정규화 스키마와 feature window를 별도 타입으로 분리
- scorer와 report 단계를 독립 모듈로 분리
- 최소 2개 이상 agent 결과를 report에 포함

실제 반영 내용:

- `NormalizedEvent`, `FeatureWindow`, `AnalysisReport` 타입 정의
- `summarizer`, `analyst`, `correlator`, `reviewer` 결과를 리포트에 포함
- 단일 진입점 `run_phase1(...)` 구성

## Gemini CLI

`gemini` CLI도 같은 목적의 짧은 리뷰 프롬프트로 호출했지만, 이 환경에서는 제한 시간 내에 유효한 응답을 반환하지 못했습니다.

관찰 결과:

- CLI 바이너리 자체는 존재함
- 짧은 headless 호출은 25초 제한 내 결과를 주지 못함

따라서 Step 1 구현 판단은 로컬 테스트와 `claude` 응답을 기준으로 진행했습니다.

## Local Decisions

이번 단계에서 고정한 구현 판단은 아래와 같습니다.

- 외부 Python 패키지 없이 표준 라이브러리만 사용
- 테스트는 `pytest` 대신 `unittest` 사용
- 샘플 입력은 JSONL로 단순화
- anomaly score는 benign baseline 평균 대비 상대 거리로 계산
- 리포트는 JSON과 Markdown 둘 다 생성
