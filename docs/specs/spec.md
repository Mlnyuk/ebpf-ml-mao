# Kubernetes Cluster Spec

작성 기준일: 2026-04-14 UTC

이 문서는 `/root/Capstone` 저장소의 Kubernetes 관련 매니페스트와 실제 클러스터 조회 결과를 합쳐 현재 구조를 빠르게 파악할 수 있도록 정리한 스펙 문서다.

실측에 사용한 주요 명령:

- `kubectl get nodes -o wide`
- `kubectl get ns`
- `kubectl get pods -A -o wide`
- `kubectl get ds,deploy,sts -A -o wide`
- `kubectl get svc -A -o wide`
- `kubectl get tracingpolicies.cilium.io`
- `kubectl get storageclass`

## 1. 한눈에 보는 구조

현재 클러스터는 `11노드`로 구성되어 있다.

- Control Plane: `3`
- Infra Node: `3`
- General Worker: `3`
- GPU Worker: `2`

실제 노드명:

- `control-1`, `control-2`, `control-3`
- `infra-1`, `infra-2`, `infra-3`
- `worker-1`, `worker-2`, `worker-3`
- `gpu-1`, `gpu-2`

핵심 스택은 아래처럼 보인다.

- Kubernetes `v1.34.2`
- Container runtime: `containerd://2.1.5`
- CNI: `Kube-OVN v1.12.21`
- Storage: `Longhorn`
- Monitoring: `kube-prometheus-stack`
- GPU stack: `NVIDIA GPU Operator`
- eBPF security/observability: `Tetragon v1.6.1`

대략적인 아키텍처는 다음과 같다.

```text
                               +----------------------+
                               |   Control Plane x3   |
                               | apiserver/controller |
                               | scheduler/etcd etc.  |
                               +----------+-----------+
                                          |
                    +---------------------+----------------------+
                    |                                            |
          +---------v---------+                        +---------v---------+
          |   Kube-OVN CNI    |                        |  Monitoring Stack  |
          | ovn-central x3    |                        | Prometheus/Grafana |
          | cni/kube-proxy DS |                        | Alertmanager       |
          +---------+---------+                        +---------+---------+
                    |                                            |
   +----------------+----------------+----------------------------+----------------+
   |                                 |                                             |
+--v-------------+         +---------v---------+                         +---------v---------+
| Infra Nodes x3 |         | Worker Nodes x3   |                         | GPU Nodes x2      |
| shared infra   |         | general compute   |                         | ML/Jupyter/GPU    |
| Longhorn       |         | Longhorn          |                         | GPU Operator       |
| ebpf-agent     |         | ebpf-agent        |                         | Tetragon+ebpf      |
+----------------+         +-------------------+                         +-------------------+

Across all 11 nodes:
- kube-ovn-cni / kube-proxy / nodelocaldns
- Prometheus node-exporter
- Tetragon

Across 8 non-control nodes:
- ebpf-agent (repo YAML)
- Longhorn manager / CSI / engine image
```

## 2. 실제 노드 풀 구성

### 2.1 Control Plane

`control-1~3`는 모두 `control-plane` 역할이며 `NoSchedule` taint가 걸려 있다.

- IP: `172.30.0.231-233`
- CPU allocatable: 노드당 `3.4 cores`
- Memory allocatable: 노드당 약 `14.7 Gi`

이 노드들에는 다음이 올라간다.

- `kube-apiserver`
- `kube-controller-manager`
- `kube-scheduler`
- `ovn-central`
- 일부 모니터링 컴포넌트
- `tetragon` DaemonSet

주의할 점:

- 저장소의 `deploy/yaml/ebpf-step1.yaml`에 있는 `ebpf-agent`는 control-plane toleration이 없어서 control-plane에는 배포되지 않는다.
- 반면 실제 `tetragon-values.yaml`의 toleration 설정 덕분에 `tetragon`은 control-plane 포함 전체 노드에 올라가 있다.

### 2.2 Infra Nodes

`infra-1~3`는 별도 taint 없이 일반 스케줄링이 가능하지만, 네이밍과 현재 워크로드를 보면 공용 인프라 성격으로 쓰고 있다.

- IP: `172.30.0.221-223`
- CPU allocatable: 노드당 `3.4 cores`
- Memory allocatable: 노드당 약 `6.9 Gi`

현재 주요 역할:

- `ebpf-agent`
- `Longhorn`
- `node-exporter`
- `kube-ovn-cni`, `kube-proxy`, `nodelocaldns`

### 2.3 General Workers

`worker-1~3`는 일반 연산 노드다.

- IP: `172.30.0.224-226`
- CPU allocatable:
  - `worker-1`: `15.4 cores`
  - `worker-2`: `31.4 cores`
  - `worker-3`: `19.4 cores`
- Memory allocatable:
  - `worker-1`: 약 `30.4 Gi`
  - `worker-2`: 약 `62.0 Gi`
  - `worker-3`: 약 `30.1 Gi`

현재 주요 역할:

- `ebpf-agent`
- `Longhorn`
- `Prometheus Operator` 일부 컴포넌트
- `metrics-server`, `CoreDNS` 일부 파드

### 2.4 GPU Workers

`gpu-1`, `gpu-2`는 GPU 자원이 붙은 고성능 노드다.

- IP: `172.30.0.227-228`
- GPU: 각 노드 `2`, 총 `4 GPUs`
- CPU allocatable: 노드당 `71.4 cores`
- Memory allocatable:
  - `gpu-1`: 약 `61.6 Gi`
  - `gpu-2`: 약 `124.6 Gi`

현재 주요 역할:

- `NVIDIA GPU Operator`
- `nvidia-device-plugin`
- `nvidia-dcgm-exporter`
- `nvidia-container-toolkit`
- Jupyter 워크로드
  - `research-jupyter`
  - `video-study-jupyter`
  - `quantum-jupyter`
- `ebpf-agent`
- `tetragon`

## 3. 클러스터 총 용량

`allocatable` 기준 총 리소스:

- CPU: 약 `229.4 cores`
- Memory: 약 `373.7 Gi`
- GPU: `4`

`kubectl top nodes` 기준으로 2026-04-14 UTC 시점 현재 전체적으로 여유가 있는 편이다. 다만 `control-3`는 메모리 사용률이 `84%`로 다른 노드보다 높게 보였다.

## 4. 네트워크 구조

실제 배포를 보면 CNI는 `Cilium`이 아니라 `Kube-OVN`이다.

확인된 컴포넌트:

- DaemonSet: `kube-ovn-cni`
- DaemonSet: `ovs-ovn`
- Deployment: `kube-ovn-controller`
- Deployment: `ovn-central`
- Deployment: `kube-ovn-monitor`
- DaemonSet: `kube-proxy`
- DaemonSet: `nodelocaldns`

관찰된 주소 대역을 보면 다음처럼 추정된다.

- Node Internal IP: `172.30.0.0/24` 대역 사용
- Pod/Service 네트워크: `10.233.0.0/16` 계열 사용

위 CIDR 값은 서비스/파드 IP 분포를 보고 한 추정이며, `cluster-cidr`나 `service-cidr` 설정 파일을 직접 읽은 값은 아니다.

외부 노출 방식은 현재 대부분 `NodePort` 중심이다.

- Grafana: `30000`
- Longhorn UI: `30001`
- Jupyter:
  - `quantum-jupyter-svc`: `30128`
  - `video-study-svc`: `30129`
  - `research-jupyter-svc`: `30130`

## 5. 스토리지 구조

스토리지는 `Longhorn`이 기본값이다.

- Default StorageClass: `longhorn`
- 추가 StorageClass: `longhorn-static`

Longhorn 관련 특징:

- `longhorn-manager`, `longhorn-csi-plugin`, `engine-image`는 `8개 non-control 노드`에만 올라가 있다.
- 즉 현재 설계는 control-plane을 스토리지 데이터 경로에서 제외하고 있다.
- UI는 `NodePort 30001`로 노출된다.

이 구조는 control-plane 분리를 유지하면서 infra/worker/gpu 노드에 분산 스토리지를 두는 형태다.

## 6. 모니터링 구조

모니터링 네임스페이스는 `monitoring`이며 `kube-prometheus-stack` 기반이다.

핵심 컴포넌트:

- Prometheus: `prometheus-my-monitoring-kube-prometh-prometheus-0`
- Alertmanager: `alertmanager-my-monitoring-kube-prometh-alertmanager-0`
- Grafana: `my-monitoring-grafana`
- Prometheus Operator
- `kube-state-metrics`
- `prometheus-node-exporter` DaemonSet

실제 상태상 `node-exporter`는 `11개 전체 노드`에 배포되어 있다.

Grafana는 `NodePort 30000`으로 노출되고, Prometheus는 `ClusterIP`로 내부 접근하는 형태다.

## 7. GPU/ML 워크로드 구조

`gpu-operator` 네임스페이스가 별도로 운영 중이다.

주요 구성:

- `gpu-operator`
- `gpu-feature-discovery`
- `node-feature-discovery`
- `nvidia-driver-daemonset`
- `nvidia-device-plugin-daemonset`
- `nvidia-dcgm-exporter`
- `nvidia-container-toolkit-daemonset`

GPU 노드는 현재 별도 taint 없이 일반 스케줄도 가능한 상태다. 따라서 GPU 전용 워크로드를 강하게 격리하려면 이후 `taint + toleration` 정책을 추가하는 편이 명확하다.

## 8. eBPF / 보안 관측 구조

이 저장소의 관측 설계는 `ebpf-agent + Tetragon + Prometheus` 축으로 보인다.

### 8.1 저장소에 정의된 배포

`deploy/yaml/ebpf-step1.yaml` 기준:

- Namespace: `ebpf-obs`
- ServiceAccount / ClusterRole / ClusterRoleBinding 포함
- DaemonSet: `ebpf-agent`
- 설정 특징:
  - `hostPID: true`
  - `hostNetwork: true`
  - `privileged: true`
  - `/sys`, `/proc`, `/sys/fs/bpf`, `/lib/modules`, `/usr/src` 마운트

이 매니페스트는 사실상 "노드에 직접 붙어 eBPF 실험을 수행할 수 있는 privileged shell/agent" 성격이다. 현재 컨테이너 이미지는 `ubuntu:22.04`, 커맨드는 `sleep infinity`이므로 실제 로직 탑재 전의 실험용 골격에 가깝다.

### 8.2 실제 클러스터 배포 상태

실제 클러스터에서는 아래가 확인됐다.

- `ebpf-agent` DaemonSet: `8개 non-control 노드`
- `tetragon` DaemonSet: `11개 전체 노드`
- `tetragon-operator` Deployment: `kube-system`
- `tetragon` Service: `2112/TCP`
- `tetragon-operator-metrics` Service: `2113/TCP`
- `ServiceMonitor`: `tetragon`, `tetragon-operator`

즉, 현재는 `ebpf-agent`가 실험/직접접속용 베이스이고, 실운영 관측은 `Tetragon` 중심으로 넘어간 상태라고 보는 해석이 가장 자연스럽다.

### 8.3 실제 적용된 Tetragon 정책

2026-04-13에 생성된 TracingPolicy:

- `monitor-exec`
- `monitor-tcp-connect`
- `monitor-sensitive-files`
- `monitor-privilege-escalation`

저장소의 `[deploy/yaml/tetragon-tracingpolicy.yaml](../../deploy/yaml/tetragon-tracingpolicy.yaml)`와 이름이 일치한다. 따라서 이 파일은 현재 실제 클러스터에도 반영된 것으로 보인다.

정책 기준 관측 범위:

- 프로세스 실행
- TCP 연결
- 민감 파일 접근
- `setuid` / `setgid` 호출

### 8.4 Tetragon과 Prometheus 연결

`deploy/yaml/tetragon-values.yaml`에서는 다음이 활성화되어 있다.

- Tetragon Prometheus metrics `2112`
- Tetragon Operator metrics
- `ServiceMonitor` 자동 생성
- `tolerations: [{ operator: Exists }]`
- 이벤트 export file: `/var/run/cilium/tetragon/tetragon.log`
- gRPC server: `localhost:54321`

실제 클러스터에도 `ServiceMonitor`와 `tetragon` 서비스가 존재하므로, Prometheus가 Tetragon 메트릭을 수집하는 구조는 연결되어 있다고 봐도 무리가 없다.

## 9. 저장소 코드와 클러스터 아키텍처 연결

저장소의 Python 파이프라인은 현재 "실시간 연동 전 단계"에 있다.

구현된 흐름:

```text
Tetragon JSONL / Prometheus snapshot
  -> adapter
  -> normalize
  -> 30s windowing
  -> feature extraction
  -> baseline anomaly scoring
  -> multi-agent summarization
  -> report.json / report.md
```

즉 현재 저장소 아키텍처는 아래 두 층으로 나뉜다.

1. 클러스터 층
   Tetragon, Prometheus, GPU Operator, Longhorn, Kube-OVN 같은 실제 런타임 인프라
2. 분석 층
   수집된 Tetragon/Prometheus 데이터를 오프라인 샘플 또는 스냅샷으로 받아 ML/리포트 파이프라인을 돌리는 애플리케이션

이 관점에서 보면 프로젝트의 목표 구조는 아래처럼 이해하는 것이 맞다.

```text
Kubernetes Cluster
  -> Tetragon events
  -> Prometheus metrics
  -> adapters / normalization
  -> anomaly scoring
  -> multi-agent explanation
  -> security or ops report
```

## 10. 현재 해석한 역할 분담

실제 상태를 기준으로 보면 노드 역할은 아래처럼 정리할 수 있다.

- `control-*`
  Kubernetes control plane, 일부 모니터링, 일부 OVN control component
- `infra-*`
  스토리지/관측/공용 인프라 보조 노드
- `worker-*`
  일반 연산 및 일부 플랫폼 워크로드
- `gpu-*`
  Jupyter 및 GPU 연산 노드

즉 이 클러스터는 단순한 "control + worker" 2계층이 아니라, 실제 운영상 다음 4계층 구조다.

1. Control Plane
2. Infra Pool
3. General Compute Pool
4. GPU Compute Pool

## 11. 차이점과 리스크 메모

저장소 매니페스트와 실제 클러스터를 비교했을 때 중요한 차이:

- CNI는 Cilium이 아니라 `Kube-OVN`이다.
- 하지만 eBPF 보안/관측은 `Tetragon`을 별도로 사용하고 있다.
- `ebpf-agent`는 `8개 노드`만 커버하고, `Tetragon`은 `11개 전체 노드`를 커버한다.
- Longhorn도 `8개 non-control 노드`만 사용한다.
- GPU 노드에 taint가 없어서 일반 워크로드가 섞일 수 있다.
- `control-3` 메모리 사용률이 상대적으로 높다.

추가로 확인하면 좋은 항목:

- `Ingress` 또는 외부 LB 유무
- 실제 `etcd` 배치 방식과 백업 정책
- Prometheus retention / PVC 크기
- GPU 노드 전용 스케줄링 정책
- Tetragon 이벤트 소비자 구현 여부

## 12. 결론

현재 클러스터는 다음처럼 요약할 수 있다.

- `3 control-plane + 3 infra + 3 worker + 2 gpu`의 `11노드` 운영형 클러스터
- 네트워크는 `Kube-OVN`
- 스토리지는 `Longhorn`
- 관측은 `Prometheus + Grafana + node-exporter + Tetragon`
- GPU 워크로드는 `NVIDIA GPU Operator` 위에서 Jupyter 형태로 운용
- 저장소의 eBPF/ML 코드는 아직 실시간 소비기보다는 오프라인 분석 파이프라인 단계

즉, 인프라는 이미 꽤 운영형으로 갖춰져 있고, 이 저장소의 다음 핵심 과제는 `Tetragon/Prometheus 실시간 입력을 Python 분석 파이프라인에 직접 연결하는 것`이다.
