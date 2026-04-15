# Step 9 Agent Notes

## Explorer 1

Step 9 최소 배포 구조로 `node collector + central analyzer + split state`를 권장했습니다. 필요한 리소스는 Namespace, ServiceAccount, RBAC, ConfigMap, PVC, DaemonSet, Deployment로 정리했습니다.

반영한 내용:
- collector를 `DaemonSet`으로 분리
- analyzer를 `Deployment` 단일 replica로 고정
- collector와 analyzer의 상태 경로를 분리하고, analyzer 경로를 PVC로 고정

## Explorer 2

배포 초안에서 가장 중요한 리스크로 `Tetragon 로그 경로`, `Prometheus scrape 실패`, `registry/model 경로 불일치`, `권한`, `동시 writer`를 지적했습니다.

반영한 내용:
- hostPath와 PVC 역할 분리
- analyzer 단일 writer 구조
- 문서에 remaining risk와 follow-up 명시

## Integration Note

최종 구현은 Codex가 수행했습니다. Step 9는 실클러스터 배포 전 단계의 초안이며, 이미지 빌드와 RWX 스토리지 전략은 Step 10에서 마무리해야 합니다.

## Additional Note

Explorer 1은 현재 앱이 배치 CLI이므로 서비스형 API보다 worker 중심으로 설명해야 한다고 지적했습니다. 이 점을 반영해 Step 9 문서에 shell loop wrapper와 placeholder control point 전제를 명시했습니다.
