# Step 14 Agent Notes

## Orchestration

- `Jason`
  - Step 14를 `이미지 빌드`, `CI 검증`, `배포 overlay`, `runbook` 중심으로 좁히는 안을 제안
- `Aquinas`
  - 운영 문서와 릴리스 workflow를 분리해 `runbook`, `rollback`, `checklist`, `CI/release workflow` 최소 세트를 권장

## Integration Notes

- Step 14는 새 기능보다 `실제로 어떻게 배포하고 검증할지`를 고정하는 단계로 처리했습니다.
- GitHub Actions는 검증용 `ci`와 수동 릴리스용 `release-image` 두 갈래로 분리했습니다.
- Step 14 overlay는 Step 13 위에 얹히며, 이미지 태그와 배포 메타데이터를 명시적으로 남깁니다.
