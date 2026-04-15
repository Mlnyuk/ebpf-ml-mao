# Step 5 Agent Notes

## Local Design

Step 5의 핵심은 모델 학습과 추론의 분리입니다.

이번 단계에서 고정한 판단:

- baseline distance scorer는 유지
- 모델 표현은 JSON 파일로 단순화
- 학습은 `train-model`
- 추론은 `phase5`
- 다중 window / 다중 workload batch 출력은 유지

## Why This Structure

현재 MVP 목표는 복잡한 ML 프레임워크 도입보다 `offline trained model + online inference` 구조를 먼저 확정하는 것입니다.

따라서 이번 단계에서는 아래를 우선했습니다.

- 저장 가능한 모델 포맷 확보
- 로드 후 추론 경로 확보
- Step 4 batch 처리와의 호환성 유지

## Validation Focus

- 저장된 모델이 다시 로드되는가
- baseline 없이도 saved model로 inference가 가능한가
- phase4에서 만든 batch 출력 구조가 그대로 유지되는가
