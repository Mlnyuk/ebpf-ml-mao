# Step 2 Agent Notes

## Claude Code

`claude` CLI는 60초 제한 안에서 유효 응답을 반환했습니다.

반영한 포인트:

- 어댑터가 `NormalizedEvent`를 직접 만들도록 구성
- Tetragon은 nested process/pod/container 필드만 우선 추출
- Prometheus는 snapshot series를 label 기준으로 집계
- mixed source 입력이 기존 pipeline 계약을 깨지 않는지 테스트 추가

## Gemini CLI

`gemini` CLI는 60초 제한에서는 응답이 없었지만, 사용자 요청에 따라 120초로 늘린 뒤 유효 응답을 반환했습니다.

반영 가능한 포인트:

- Tetragon 스키마 drift 가능성 고려
- Tetragon 이벤트와 Prometheus snapshot 사이 timestamp 정렬 중요
- sparse metric 상황에서도 점수 계산이 깨지지 않도록 검증 필요

실제 반영 내용:

- raw nested field 누락에 대한 기본값 처리 유지
- UTC 기준 timestamp 파싱 유지
- mixed source 입력 테스트 추가

## Local Design Choice

- Step 2도 외부 Python 패키지 없이 유지
- raw source parser는 입력별 adapter 함수로 분리
- 기존 `normalize -> feature -> score -> report` 경로는 유지
- CLI는 `phase1`/`phase2` subcommand 구조로 정리
