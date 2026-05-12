#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${1:-ebpf-obs-test}"
LABEL_SELECTOR="app=fault-target"
ITERATIONS="${ITERATIONS:-100}"

echo "[exec-storm] locating fault-target pod in namespace ${NAMESPACE}"
POD="$(kubectl get pod -n "${NAMESPACE}" -l "${LABEL_SELECTOR}" -o jsonpath='{.items[0].metadata.name}')"

echo "[exec-storm] starting ${ITERATIONS} kubectl exec iterations against ${POD}"
for i in $(seq 1 "${ITERATIONS}"); do
  kubectl exec -n "${NAMESPACE}" "${POD}" -- /bin/sh -c "echo exec-storm-${i} >/dev/null"
done

echo "[exec-storm] completed ${ITERATIONS} kubectl exec iterations"
