# Step 16

Step 16 범위는 `live fault scenario validation`입니다.

이번 단계에서는 정적 샘플 분석이 아니라 실제 Kubernetes workload에 장애성 행위를 주입하고, 그 결과가 기존 Tetragon/eBPF 이벤트, Prometheus 메트릭, feature extraction, anomaly scoring, report/API/UI 흐름으로 이어지는지 확인합니다. Step 16은 Step 15 배포 위에 안전한 test workload만 추가하는 additive overlay입니다. analyzer replica 수는 변경하지 않습니다.

## Added

- `deploy/yaml/step16/kustomization.yaml`
- `deploy/yaml/step16/fault-workloads.yaml`
- `scripts/fault-scenarios/exec-storm.sh`
- `scripts/fault-scenarios/network-burst.sh`
- `scripts/fault-scenarios/cpu-stress.sh`
- `scripts/fault-scenarios/memory-pressure.sh`
- `tests/test_step16_artifacts.py`

## Fault Target

Step 16은 `ebpf-obs-test` namespace에 `fault-target` Deployment를 생성합니다.

- Image: `busybox:1.36`
- Label: `app: fault-target`
- Resources:
  - requests: CPU `50m`, memory `64Mi`
  - limits: CPU `500m`, memory `256Mi`

이 workload는 장애성 행위를 주입하기 위한 안전한 관측 대상이며, 운영 analyzer의 PVC/registry/ingest 동작은 바꾸지 않습니다.

## Scenarios

### exec-storm

- Trigger: `kubectl exec`를 약 100회 반복 실행한다.
- Expected feature changes:
  - Tetragon process execution 이벤트 증가
  - workload window의 `event_count`, `exec_count`, `unique_pids` 증가 가능
- Expected anomaly behavior:
  - baseline 대비 process activity가 충분히 커지면 해당 window score가 상승하고 `anomalous` verdict가 나올 수 있다.

### network-burst

- Trigger: pod 내부에서 `http://kubernetes.default.svc`로 약 80회 네트워크 요청을 시도한다.
- Expected feature changes:
  - 네트워크 관련 eBPF/Tetragon 이벤트 또는 Prometheus network metric 변화 가능
  - workload window의 `event_count`, `network_event_count`, `avg_network_connections`, `max_network_connections` 증가 가능
- Expected anomaly behavior:
  - baseline에 비해 network activity가 높은 window에서 score가 상승할 수 있다. 개별 요청 실패는 안전하게 무시한다.

### cpu-stress

- Trigger: pod 내부에서 약 30초 동안 짧은 busy loop를 실행한다.
- Expected feature changes:
  - Prometheus CPU usage metric 증가
  - workload window의 `avg_cpu_usage`, `max_cpu_usage` 증가 가능
- Expected anomaly behavior:
  - CPU 사용량이 baseline보다 높게 관측되면 score와 confidence가 상승할 수 있다.

### memory-pressure

- Trigger: pod 내부에 임시 128Mi 파일을 만들고 삭제한다.
- Expected feature changes:
  - 파일 생성 중 page cache 또는 container memory working set 변화 가능
  - workload window의 `avg_memory_usage`, `max_memory_usage` 증가 가능
- Expected anomaly behavior:
  - memory metric 변화가 baseline보다 충분히 크면 anomalous report가 생성될 수 있다.

## Commands

배포:

```bash
kubectl apply -k deploy/yaml/step16
```

pod 확인:

```bash
kubectl get pod -n ebpf-obs
kubectl get pod -n ebpf-obs-test
```

UI/API port-forward:

```bash
kubectl port-forward -n ebpf-obs svc/ebpf-ml-mao-ui 8080:8080
```

fault scenario 실행:

```bash
bash scripts/fault-scenarios/exec-storm.sh
bash scripts/fault-scenarios/network-burst.sh
bash scripts/fault-scenarios/cpu-stress.sh
bash scripts/fault-scenarios/memory-pressure.sh
```

상태 확인:

```bash
curl -s http://localhost:8080/v1/dashboard | jq
curl -s http://localhost:8080/v1/alerts | jq
curl -s http://localhost:8080/v1/workflow | jq
```

## Interpretation

Step 16은 Tetragon/eBPF telemetry와 Prometheus metrics가 workload-level feature 변화로 변환되고, 기존 scoring/reporting pipeline을 통해 anomaly report로 이어질 수 있음을 검증한다.

이 단계는 프로젝트가 eBPF program을 직접 수정한다는 의미가 아니다. 현재 구현은 Tetragon이 제공하는 eBPF 기반 관측 이벤트와 Prometheus metric을 수집, 정규화, feature화, scoring하는 pipeline이다.

또한 Step 16은 production-grade HA나 advanced ML anomaly detection이 완료되었다는 의미도 아니다. analyzer는 여전히 파일 기반 registry/ingest/postprocess queue와 ReadWriteOnce PVC를 쓰는 단일 writer 성격이 있으며, Step 16은 이 동작을 변경하지 않는다.

## Korean Summary

Step 16은 실제 Kubernetes workload에 장애성 행위를 주입하고, eBPF/Tetragon 이벤트와 Prometheus 메트릭이 feature 변화 및 anomaly report로 연결되는지 검증한다. 이를 통해 본 시스템이 단순 샘플 분석이 아니라 live workload 관측 기반의 이상 징후 분석 파이프라인임을 확인한다.

## Validation

```bash
python3 -m unittest discover -s tests -v
kubectl kustomize deploy/yaml/step16
```
