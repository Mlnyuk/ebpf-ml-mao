# CI/CD

- `ci` workflow
  - unittest 실행
  - `kubectl kustomize deploy/yaml/step14`
  - `kubectl apply --dry-run=client -k deploy/yaml/step14`
  - Docker build smoke test
- `release-image` workflow
  - GHCR 로그인
  - 지정 태그로 이미지 빌드/푸시
  - Step 14 렌더 결과 artifact 업로드
