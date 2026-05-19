# Step 19

Step 19 범위는 `Analyzer Target Filter`입니다.

Step 16/17/18 검증 과정에서 fault scenario 외의 인프라 워크로드(`instance-manager`, `kuberay-operator`, `gpu-feature-discovery`, `longhorn-manager` 등)가 같이 scoring되어 baseline anomaly score를 오염시키는 구조적 문제가 확인되었습니다. Step 19는 analyzer scoring 파이프라인이 특정 namespace/workload 조합만 평가하도록 제한하는 target filter를 도입하고, threshold 분석이 동일한 scope에서 평가되도록 정렬합니다.

## Goal

- analyzer가 `ANALYZER_TARGET_NAMESPACE`/`ANALYZER_TARGET_WORKLOAD` 환경변수로 지정된 대상만 평가하도록 한다.
- live dashboard, alert, workflow verdict가 target workload만 반영하도록 한다.
- threshold/paper 분석 스크립트가 fault-target ingest 리포트만 사용하도록 한다.
- baseline 오탐을 제거하고 fault scenario 탐지의 결정적 증거(verdict=anomalous, alerts>=1)를 확보한다.

## Added

- `deploy/yaml/step19/kustomization.yaml`
- `deploy/yaml/step19/patch-configmap-target-filter.yaml`
- `scripts/step16_extract_fault_target_scores.py`
- `tests/test_step19_target_filter.py` (pipeline filter unit test)
- `tests/test_step19_artifacts.py` (deploy overlay/docs validation)

## ConfigMap Settings

`ebpf-ml-mao-runtime` ConfigMap에 다음 키를 설정합니다.

```yaml
ANALYZER_TARGET_NAMESPACE: ebpf-obs-test
ANALYZER_TARGET_WORKLOAD: fault-target
```

`app/ebpf_ml_mao/pipeline.py`의 `_filter_target_events`가 위 값을 읽어 namespace + workload가 일치하는 이벤트만 통과시킵니다.

## Apply

Step 18까지 적용된 클러스터에 step19 overlay를 적용합니다.

```bash
kubectl apply -k deploy/yaml/step19
kubectl rollout status deploy/ebpf-ml-mao-analyzer -n ebpf-obs --timeout=180s
kubectl rollout status ds/ebpf-ml-mao-collector -n ebpf-obs --timeout=300s
```

clean baseline 재수집을 위해 runtime history를 비웁니다.

```bash
DRY_RUN=false PRUNE_ALL=true bash scripts/analyzer_prune.sh
kubectl rollout restart deploy/ebpf-ml-mao-analyzer -n ebpf-obs
kubectl rollout status deploy/ebpf-ml-mao-analyzer -n ebpf-obs --timeout=180s
```

## Verification

Step 16 fault scenario를 다시 실행하고 결과를 검증합니다.

```bash
kubectl port-forward -n ebpf-obs svc/ebpf-ml-mao-analyzer 8080:8080
bash scripts/step16_collect_results.sh
python3 scripts/step16_generate_report.py
python3 scripts/step16_analyze_thresholds.py
python3 scripts/step16_generate_paper_tables.py
```

`scripts/step16_collect_results.sh`는 fault scenario 종료 후 analyzer PVC에서 `feature_window.workload == fault-target` 인 ingest 리포트만 추려서 `results/step16/fault-target-ingest-scores.jsonl`로 저장합니다. `step16_analyze_thresholds.py`는 dashboard timestamp 기준으로 각 record에 scenario 라벨을 자동 할당하고, threshold/paper 분석에 이 데이터를 primary source로 사용합니다.

## Expected Result

`results/step16/threshold-analysis.md`:

- baseline: `verdict=normal`, `alerts=0`, target samples=0 (clean)
- 4개 fault scenario: `verdict=anomalous`, `alerts>=1`, target samples>=1, min score >= 0.4323

`results/step16/paper-results.md`:

- scenario별 fault-target 워크로드 기준 score min/mean/max
- main feature changes 항목이 인프라 워크로드가 아닌 fault-target의 실제 feature 변화로 표시됨

## Limitations

- Step 19는 advanced ML 모델을 추가하지 않습니다.
- Step 19는 eBPF program이나 Tetragon policy를 수정하지 않습니다.
- Step 19는 analyzer를 production-HA 구조로 바꾸지 않습니다.
- Target filter는 단일 namespace/workload만 평가하므로, 멀티 워크로드 동시 평가가 필요할 경우 namespace selector / label selector 수준의 일반화가 필요합니다.
