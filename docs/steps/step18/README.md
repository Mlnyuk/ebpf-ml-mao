# Step 18

Step 18 범위는 `Analyzer Storage Recovery & Single-Writer Safety`입니다.

Step 16/17 live validation 이후 아래 운영 문제가 확인되었습니다.

- analyzer API가 timeout, empty reply, port-forward loss로 불안정하게 응답했다.
- analyzer log에서 `/var/lib/ebpf-ml-mao/ingest/...` 쓰기 중 `OSError: [Errno 28] No space left on device`가 발생했다.
- live cluster에서 analyzer HPA가 analyzer를 3 replicas로 scale했다.
- 현재 analyzer는 ReadWriteOnce PVC와 파일 기반 registry/ingest/postprocess queue를 사용하므로 storage/queue backend가 바뀌기 전까지 단일 writer로 취급해야 한다.

## Goal

Step 18은 production HA를 구현하는 단계가 아니라 Step 16/17 실험을 다시 안정적으로 수행하기 위한 운영 안정화 단계입니다.

- analyzer storage diagnosis
- storage check command for PVC and directory usage
- generated runtime data safe pruning
- Step 16/17 preflight validation
- analyzer를 single-writer 조건으로 유지하는 experiment overlay 제공

## Added

- `scripts/analyzer_storage_check.sh`
- `scripts/analyzer_prune.sh`
- `scripts/step16_preflight.sh`
- `deploy/yaml/step18/kustomization.yaml`
- `deploy/yaml/step18/patch-analyzer-hpa-single-writer.yaml`
- `deploy/yaml/step18/patch-analyzer-pvc-storage.yaml`
- `deploy/yaml/step18/analyzer-prune-cronjob.yaml`
- `tests/test_step18_artifacts.py`

## Commands

저장소 사용량 진단:

```bash
bash scripts/analyzer_storage_check.sh
```

안전한 prune 후보 확인:

```bash
DRY_RUN=true bash scripts/analyzer_prune.sh
```

명시적 prune 실행:

```bash
DRY_RUN=false OLDER_THAN_DAYS=1 bash scripts/analyzer_prune.sh
```

파일 수 기준 prune 후보 확인:

```bash
DRY_RUN=true MAX_FILES_PER_DIR=5000 bash scripts/analyzer_prune.sh
```

실험 history를 완전히 비우고 clean baseline부터 다시 시작:

```bash
DRY_RUN=false PRUNE_ALL=true bash scripts/analyzer_prune.sh
```

실험 전 preflight:

```bash
bash scripts/step16_preflight.sh
```

Step 18 실험 overlay 적용:

```bash
kubectl apply -k deploy/yaml/step18
```

이 overlay는 analyzer PVC 요청 용량을 8Gi로 늘리고, generated runtime data를 6시간마다 정리하는 CronJob을 추가하며, `ghcr.io/mlnyuk/ebpf-ml-mao:step18-calibrated` 이미지를 사용한다. Step 16 live scoring은 `ANALYZER_TARGET_NAMESPACE=ebpf-obs-test`, `ANALYZER_TARGET_WORKLOAD=fault-target`로 제한해 인프라 워크로드가 baseline을 오염시키지 않게 한다.

Step 18 render 검증:

```bash
kubectl kustomize deploy/yaml/step18
```

## Recommended Recovery Flow

1. Inspect storage.

```bash
bash scripts/analyzer_storage_check.sh
```

2. Scale analyzer to 1 if needed.

```bash
kubectl scale deploy -n ebpf-obs ebpf-ml-mao-analyzer --replicas=1
```

3. Disable/delete analyzer HPA or use the Step 18 overlay.

```bash
kubectl delete hpa -n ebpf-obs ebpf-ml-mao-analyzer
kubectl apply -k deploy/yaml/step18
```

4. Dry-run prune.

```bash
DRY_RUN=true bash scripts/analyzer_prune.sh
```

5. Prune only if the candidate list is safe.

```bash
DRY_RUN=false OLDER_THAN_DAYS=1 bash scripts/analyzer_prune.sh
```

6. Rerun preflight.

```bash
bash scripts/step16_preflight.sh
```

7. Rerun Step 16/17 validation.

```bash
bash scripts/step16_collect_results.sh
python3 scripts/step16_generate_report.py
```

## Safety Notes

- `analyzer_storage_check.sh` never deletes data.
- `analyzer_prune.sh` defaults to `DRY_RUN=true`.
- prune targets only generated runtime directories: `ingest`, `reports`, `spool`, `postprocess-queue`, `queue`.
- prune never targets `registry` or `models`.
- `MAX_FILES_PER_DIR` enables count-based pruning to reduce inode exhaustion risk.
- `PRUNE_ALL=true` clears generated runtime history for clean baseline reruns.
- Step 18 overlay patches the inherited analyzer HPA to `minReplicas: 1` and `maxReplicas: 1` for experiment safety.
- Step 18 overlay patches `ebpf-ml-mao-state` from 2Gi to 8Gi. The storage class must allow volume expansion for an existing Longhorn/PVC resize to complete.

## Limitations

- This does not make analyzer production HA.
- This does not replace file-based queue/storage.
- This does not add advanced ML.
- This does not modify eBPF programs.

## Korean Summary

Step 18은 Step 16/17 실험 중 발견된 analyzer 저장소 부족과 단일 writer 구조 문제를 해결하기 위한 운영 안정화 단계이다. 저장소 사용량 진단, 안전한 prune, 실험 전 preflight 점검, analyzer 단일 replica 보장을 통해 장애 시나리오 검증을 다시 수행할 수 있는 상태를 만든다.
