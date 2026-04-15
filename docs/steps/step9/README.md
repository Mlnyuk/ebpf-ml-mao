# Step 9

Step 9 범위는 `실제 배포를 위한 런타임 구조 고정 + Kubernetes 배포 초안`입니다.

이번 단계에서는 Step 1~8에서 만든 MVP를 클러스터에 올릴 수 있도록 최소 배포 단위를 정했습니다. 현재 앱이 배치 CLI 구조라는 점을 기준으로, `node collector 배치 worker`와 `central analyzer 상태 관리자`를 분리하는 방향으로 초안을 잡았습니다.

## Runtime Layout

- `Tetragon`
  - 노드별 eBPF 이벤트 생성기
  - `/var/run/cilium/tetragon/tetragon.log` 에 JSON 로그를 남김
- `Prometheus`
  - 클러스터 메트릭 제공자
  - collector가 scrape URL로 접근
- `ebpf-ml-mao-collector` (`DaemonSet`)
  - 각 노드에서 Tetragon 로그를 tail
  - Prometheus scrape 수행
  - `phase3` 파이프라인 실행
  - 노드별 live report 생성
  - 상태 저장은 노드 로컬 `hostPath` scratch 사용
- `ebpf-ml-mao-analyzer` (`Deployment`)
  - 현재는 상시 API 서버가 아니라 상태 고정과 registry/model mount 검증용 control point
  - 모델 경로와 registry 상태를 고정
  - 이후 Step 10에서 API 또는 controller 역할로 확장 예정
- `PersistentVolumeClaim`
  - analyzer용 registry/model/report 저장

## Why This Split

- Tetragon 로그는 노드 로컬 경로라서 `DaemonSet`이 자연스럽습니다.
- 모델/registry는 여러 노드가 동시에 쓰면 꼬일 수 있어서 `Deployment 1 replica`로 고정했습니다.
- collector는 다중 노드 실행이므로 공유 PVC 대신 노드 로컬 scratch를 씁니다.
- Step 9는 “배포 가능 구조”를 만드는 단계이고, Step 10에서 rollout/API/Secret 세부화를 합니다.
- collector command는 현재 배치 CLI를 shell loop로 감싼 형태이며, 네이티브 long-running worker는 아직 없습니다.

## Added

- `deploy/yaml/step9/kustomization.yaml`
- `deploy/yaml/step9/namespace.yaml`
- `deploy/yaml/step9/serviceaccount.yaml`
- `deploy/yaml/step9/rbac.yaml`
- `deploy/yaml/step9/configmap.yaml`
- `deploy/yaml/step9/pvc.yaml`
- `deploy/yaml/step9/collector-daemonset.yaml`
- `deploy/yaml/step9/analyzer-service.yaml`
- `deploy/yaml/step9/analyzer-deployment.yaml`

## Deployment Draft

적용 예시:

```bash
kubectl apply -k deploy/yaml/step9
```

사전 조건:

- Tetragon이 `/var/run/cilium/tetragon/tetragon.log` 를 쓰고 있어야 함
- Prometheus 서비스 DNS를 `configmap.yaml` 값과 맞춰야 함
- PVC가 바인딩 가능해야 함
- 이미지 `ghcr.io/mlnyuk/ebpf-ml-mao:step9` 는 placeholder라 실제 빌드/푸시가 필요함
- baseline 샘플 파일은 이미지 내부 `/app/samples/step2/` 경로에 들어있어야 함

## Validation

YAML 렌더링 확인:

```bash
kubectl kustomize deploy/yaml/step9
```

## Risks Fixed In This Step

- collector와 analyzer 책임 경계 고정
- registry/model/report 경로 고정
- Tetragon hostPath, collector hostPath, analyzer PVC 분리
- analyzer 단일 writer 구조 확정

## Remaining Risks

- collector 결과를 중앙 집계로 보내는 경로는 아직 없음
- Tetragon 로그 로테이션/중복 처리 정책은 아직 없음
- analyzer는 아직 placeholder control point이고, 실제 API/worker 분리는 Step 10 이후 과제임
- Secret/TLS/NetworkPolicy는 Step 10에서 정리 필요
