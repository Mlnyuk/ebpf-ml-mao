# eBPF ML MAO

`eBPF + ML` 기반 운영 분석 시스템을 `멀티 에이전트 오케스트레이션` 방식으로 설계하는 저장소입니다.

이 저장소는 코드 구현체보다는 초기 설계 문서, 아키텍처 정리, Kubernetes/eBPF 실험용 매니페스트를 함께 관리하는 작업 공간에 가깝습니다.

## What This Repo Covers

- eBPF 이벤트 수집 기반 운영 관측
- ML 추론을 포함한 이상 징후 분석 흐름
- 여러 에이전트가 역할을 나눠 협업하는 오케스트레이션 구조
- Kubernetes 배포 및 정책 실험용 YAML

## Repository Layout

```text
.
├── MAO/          # 멀티 에이전트 운영 방식과 아키텍처 문서
├── ebpf-ml-mao/  # eBPF + ML 청사진 문서 세트
├── yaml/         # Tetragon 및 eBPF 실험용 매니페스트
├── spec.txt      # 인프라/환경 메모
├── requirement.txt
└── README.md
```

## Key Documents

- [`MAO/Architecture.md`](./MAO/Architecture.md): 멀티 에이전트 오케스트레이션 아키텍처
- [`MAO/Agent.md`](./MAO/Agent.md): 에이전트 역할 분리와 운영 메모
- [`ebpf-ml-mao/README.md`](./ebpf-ml-mao/README.md): 하위 설계 문서 묶음 개요
- [`ebpf-ml-mao/04-mvp-scope.md`](./ebpf-ml-mao/04-mvp-scope.md): MVP 범위 정리
- [`yaml/tetragon-tracingpolicy.yaml`](./yaml/tetragon-tracingpolicy.yaml): Tetragon 정책 실험 예시

## Current Focus

현재 기준으로 이 저장소의 중심은 아래 세 축입니다.

1. eBPF 이벤트를 어떤 형태로 수집하고 표준화할지 정의
2. 수집 데이터를 ML 추론과 연결할 처리 흐름 설계
3. 설계, 구현, 검증을 에이전트별로 분리해 병렬 작업 구조를 만드는 것

## How To Use

- 설계 흐름을 먼저 보려면 `MAO/`부터 읽는 것이 좋습니다.
- eBPF + ML 기능 범위를 보려면 `ebpf-ml-mao/` 문서를 보면 됩니다.
- 배포/정책 실험은 `yaml/` 아래 파일을 기준으로 진행하면 됩니다.

## Notes

- 현재는 문서 중심 저장소입니다.
- `spec.txt`에는 환경 메모가 포함되어 있어 공개 범위는 계속 점검하는 편이 안전합니다.
- 로컬 실행 부산물은 `.gitignore`로 제외되어 있습니다.
