# Step 21

Step 21 범위는 `Baseline Workload Redesign + Model Retraining`입니다.

Step 20에서 N=5 반복 실험을 수행했으나 두 가지 한계가 드러났습니다.

1. **Baseline FP 100%**: warmup이 `kubectl exec`를 사용해 baseline 구간에 exec event를 주입했고, 활성 모델 `baseline-v2-01`이 cpu/memory baseline을 다른 워크로드에서 학습한 값(`avg_cpu_usage=6.0`, `avg_memory_usage=61.25`)이라 fault-target idle 상태에서도 distance가 커서 anomalous로 판정되었습니다.
2. **exec-storm 60% 검출**: warmup의 exec rate와 exec-storm의 exec rate가 통계적으로 겹쳐 같은 feature(`exec_count`)로 두 시나리오를 분리할 수 없었습니다.

Step 21은 이 두 문제를 한 번에 해결합니다.

- fault-target 워크로드를 busybox idle pod → Python pod의 `open()`+`time.sleep` 루프로 교체합니다. 이렇게 하면 워크로드가 스스로 `security_file_open` 이벤트를 만들면서 exec event는 발생시키지 않으므로, 모든 4개 fault scenario(exec-storm/network-burst/cpu-stress/memory-pressure)와 feature 시그널이 겹치지 않는 baseline을 확보할 수 있습니다.
- Tetragon TracingPolicy에 `security_file_open` kprobe를 추가해 collector가 file_open 이벤트를 정규화 가능하게 합니다.
- **Collector phase3는 매 사이클마다 `--baseline-tetragon`/`--baseline-prometheus` 파일을 fit합니다(`pipeline.run_phase3`).** 따라서 registry의 active model을 바꿔도 점수는 안 변합니다. Step 21은 실제 idle fault-target에서 수집한 raw Tetragon JSONL을 ConfigMap으로 mount하고 `BASELINE_*_PATH`를 그 경로로 override해서 collector가 진짜 fault-target idle 분포로 fit하도록 만듭니다.
- 참고용으로 `baseline-v4-01` 모델도 학습해 registry active model로 활성화합니다(dashboard 표시·향후 API 기반 scoring에 사용).

## Goal

- baseline 구간에서 fault-target이 file_open 이벤트만 발생시키는 deterministic 워크로드를 갖는다.
- 활성 모델이 deploy된 fault-target의 실제 idle 분포로 학습되어 있다.
- N=5 반복 실험에서 baseline detection rate가 100% normal에 가깝고, 모든 fault scenario(exec-storm 포함)가 100% anomalous에 가까운 detection rate를 보인다.

## Added

- `deploy/yaml/step21/kustomization.yaml`: step19 overlay 위에 file_open policy + fault-target 패치 추가, baseline ConfigMap generate
- `deploy/yaml/step21/tetragon-fault-file-coverage-policy.yaml`: `security_file_open` kprobe를 fault-target 라벨에 한정
- `deploy/yaml/step21/patch-fault-target-deployment.yaml`: fault-target 컨테이너를 `python:3.11-alpine` + file_open 루프로 교체
- `deploy/yaml/step21/patch-configmap-baseline-paths.yaml`: collector runtime ConfigMap의 `BASELINE_TETRAGON_PATH`/`BASELINE_PROMETHEUS_PATH`를 ConfigMap mount 경로로 변경
- `deploy/yaml/step21/patch-collector-baseline-mount.yaml`: collector DaemonSet에 `ebpf-ml-mao-baseline-data` ConfigMap을 `/etc/ebpf-ml-mao/baseline`로 마운트
- `deploy/yaml/step21/baseline_tetragon.jsonl`: 실제 fault-target file_open 50 윈도우 raw 이벤트 (ConfigMap 입력)
- `deploy/yaml/step21/baseline_prometheus.json`: 빈 prometheus snapshot (fault-target은 prometheus target이 아님)
- `scripts/step21_collect_baseline.sh`: fault-target idle 구간을 수집해 baseline 학습용 JSONL 생성
- `scripts/step21_train_baseline.py`: 수집한 JSONL을 입력으로 baseline 모델 JSON 생성 (registry용; phase3 scorer는 ConfigMap baseline을 자체적으로 fit하므로 검증·문서화 용도)
- `scripts/step21_activate_model.sh`: 학습한 모델을 analyzer PVC에 복사하고 registry.json에 등록·활성화
- `docs/steps/step21/README.md`: 본 문서
- `tests/test_step21_artifacts.py`: overlay/scripts/docs 존재 검증

## Commands

step19까지 적용된 클러스터에서 실행합니다.

```bash
# 1. step21 overlay 적용 (fault-target = python pod, file_open policy,
#    baseline ConfigMap mount, BASELINE_*_PATH override 포함)
kubectl apply -k deploy/yaml/step21
kubectl rollout status deploy/fault-target -n ebpf-obs-test
kubectl rollout status ds/ebpf-ml-mao-collector -n ebpf-obs

# 2. analyzer history prune + restart (clean baseline)
DRY_RUN=false PRUNE_ALL=true bash scripts/analyzer_prune.sh
kubectl rollout restart deploy/ebpf-ml-mao-analyzer -n ebpf-obs
kubectl rollout status deploy/ebpf-ml-mao-analyzer -n ebpf-obs

# 3. (선택) registry 모델 갱신: collector phase3는 ConfigMap baseline을 직접 fit하므로
#    registry 모델은 dashboard 표시·향후 API 기반 scoring 용도입니다.
bash scripts/step21_collect_baseline.sh
python3 scripts/step21_train_baseline.py
bash scripts/step21_activate_model.sh
DRY_RUN=false PRUNE_ALL=true bash scripts/analyzer_prune.sh
kubectl rollout restart deploy/ebpf-ml-mao-analyzer -n ebpf-obs

# 4. N=5 반복 실험 (warmup OFF, fault-target 자체 워크로드가 baseline 생성)
REPEAT_N=5 BASE_DIR=results/step21 WARMUP_BASELINE=false \
  bash scripts/step16_repeat_experiments.sh

# 5. 집계
python3 scripts/step16_aggregate_repeated.py results/step21
```

## Output Files

- `results/step21/baseline_collect/fault-target-baseline.jsonl`: 새 모델 학습 입력
- `results/step21/baseline-v4.json`: 학습된 baseline 모델
- `results/step21/run_NN/`: N=5 각 실행 raw 결과
- `results/step21/aggregated-paper-results.md`, `aggregated-threshold-analysis.md`: 집계 보고서

## Interpretation

- fault-target은 5초 주기로 `/etc/hostname`, `/etc/resolv.conf`를 read합니다. 따라서 30s scoring window는 `file_event_count ≈ 12`, `exec_count = 0`, 모든 cpu/memory/network feature = 0의 일정한 분포를 보입니다.
- 4개 fault scenario는 모두 kubectl exec를 통해 부하를 주입하므로 `exec_count`가 baseline(0)에서 크게 벗어나며, network-burst는 추가로 `network_event_count`, cpu/memory-stress는 분명히 식별 가능한 exec burst를 만듭니다. **모든 시나리오가 baseline과 다른 feature 시그널을 가집니다.**
- baseline FP rate가 0%에 가깝게 떨어지고, exec-storm 포함 모든 fault scenario에서 detection rate가 100%에 근접하는 것이 Step 21의 성공 기준입니다.

## Limitations

- 모델 학습에 사용한 데이터는 idle workload의 한 차례 수집이므로 시간대/노드 다양성을 담지 못합니다. 본격 production 사용에는 다양한 워크로드와 시간대를 포함한 추가 학습이 필요합니다.
- Python pod은 `python:3.11-alpine` 이미지를 외부 레지스트리에서 pull해야 하므로 오프라인 클러스터에서는 추가 mirror 작업이 필요합니다.
- 4개 fault scenario는 여전히 kubectl exec를 통해 주입됩니다. 실제 production fault 패턴(예: 컨테이너 내부에서 발생하는 메모리 누수)을 더 잘 모사하려면 in-pod 자체 부하 generator 추가가 필요합니다.
