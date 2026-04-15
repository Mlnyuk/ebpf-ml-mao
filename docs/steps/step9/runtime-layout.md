# Step 9 Runtime Layout

## Fixed Components

1. `Tetragon`
- 기존 Helm 배포 유지
- 노드 로컬 이벤트 생성기

2. `ebpf-ml-mao-collector`
- 타입: `DaemonSet`
- 이유: 노드 로컬 Tetragon 로그 접근 필요
- 주 프로세스: `python3 -m ebpf_ml_mao phase3`
- 실행 방식: 배치 CLI를 shell loop로 감싼 장기 실행 래퍼
- 입력:
  - Tetragon log hostPath
  - Prometheus scrape URL
  - 이미지 내부 baseline 샘플
- 출력:
  - 노드별 live report
- 저장:
  - `/var/lib/ebpf-ml-mao-collector` hostPath scratch

3. `ebpf-ml-mao-analyzer`
- 타입: `Deployment` 1 replica
- 이유: registry/model/report를 단일 writer로 관리
- 주 프로세스:
  - registry status 확인
  - mount/path 유효성 점검
  - 후속 Step에서 API/controller 확장 예정
- 입력:
  - PVC 내부 registry/model 경로
- 출력:
  - registry 상태 확인
  - 모델 운영 중심 제어점

## Fixed Paths

- Tetragon log: `/var/run/cilium/tetragon/tetragon.log`
- Registry: `/var/lib/ebpf-ml-mao/registry/registry.json`
- Model dir: `/var/lib/ebpf-ml-mao/models`
- Report dir: `/var/lib/ebpf-ml-mao/reports`
- Collector scratch: `/var/lib/ebpf-ml-mao-collector`
- Baseline sample: `/app/samples/step2/`

## Operational Assumptions

- analyzer는 registry/model의 단일 writer다.
- collector는 노드별 scratch에만 쓴다.
- baseline 파일은 현재 이미지 내부 샘플로 제공된다.
- Prometheus URL과 Tetragon log path는 ConfigMap으로 관리한다.

## Follow-up For Step 10

- analyzer에 실제 API 또는 controller 엔트리포인트 추가
- collector 결과를 중앙 analyzer로 전송하는 경로 추가
- Secret, NetworkPolicy, PodDisruptionBudget 추가
- image build pipeline 고정
