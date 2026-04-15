# Step 6 Agent Notes

## Claude Input 반영

Claude 제안에서 반영한 포인트:

- `schema_version` 필드 추가
- `model_type` 필드 추가
- `baseline` + `zscore` 2개 모델 타입 지원
- unknown schema version reject

## Gemini Input 반영

Gemini 제안에서 반영한 포인트:

- zscore 계열 모델 추가
- zero variance guard 필요성 반영
- metadata integrity 테스트 추가

## Local Design Choice

이번 단계에서 `IQR` 대신 `zscore`를 먼저 넣은 이유:

- 구현이 단순함
- 저장 포맷이 직관적임
- 평균/표준편차 모델이 baseline과 비교해 설명하기 쉬움
- 외부 의존성이 필요 없음

## Validation Focus

- 모델 파일이 version metadata를 가지는가
- 모델 타입이 올바르게 저장/로드되는가
- zscore 모델로 실제 추론이 되는가
- schema mismatch가 명확히 실패하는가
