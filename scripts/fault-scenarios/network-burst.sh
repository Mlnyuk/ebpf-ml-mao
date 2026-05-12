#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${1:-ebpf-obs-test}"
LABEL_SELECTOR="app=fault-target"
ITERATIONS="${ITERATIONS:-80}"
TARGET_URL="${TARGET_URL:-http://kubernetes.default.svc}"

echo "[network-burst] locating fault-target pod in namespace ${NAMESPACE}"
POD="$(kubectl get pod -n "${NAMESPACE}" -l "${LABEL_SELECTOR}" -o jsonpath='{.items[0].metadata.name}')"

echo "[network-burst] starting ${ITERATIONS} in-pod requests to ${TARGET_URL} from ${POD}"
for i in $(seq 1 "${ITERATIONS}"); do
  kubectl exec -n "${NAMESPACE}" "${POD}" -- /bin/sh -c "wget -q -T 2 -O /dev/null '${TARGET_URL}' || true"
done

echo "[network-burst] completed ${ITERATIONS} request attempts"
