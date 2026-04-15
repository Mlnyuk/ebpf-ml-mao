# Step 4 Agent Notes

## Local Design

Step 4의 핵심 판단은 아래였습니다.

- 기존 `window_events()`는 그대로 재사용
- 대표 window 하나만 고르던 파이프라인만 batch 형태로 확장
- 기존 `phase1~3`는 깨지지 않게 유지
- 새 기능은 `phase4`로 분리

## Why Separate Phase 4

기존 단계는 단일 report 반환을 기준으로 문서와 테스트가 이미 고정돼 있었습니다.

따라서 Step 4에서는 다음 전략을 사용했습니다.

- 기존 단계는 backward-compatible 유지
- 다중 report 동작은 `phase4`에서만 활성화
- 출력은 batch index + per-report 파일 구조로 분리

## Validation Focus

- input window 수와 output report 수가 일치하는가
- 서로 다른 workload가 따로 분리되는가
- 기존 phase1~3 테스트가 계속 통과하는가
