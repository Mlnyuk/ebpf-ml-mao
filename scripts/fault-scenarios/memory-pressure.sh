#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${1:-ebpf-obs-test}"
LABEL_SELECTOR="app=fault-target"
SIZE_MB="${SIZE_MB:-128}"
# Hold the exec open long enough for at least one 30s scoring window to complete.
# Without this, the exec finishes in ~5s and timing misalignment leaves 0 scored
# windows in some runs (fault_target_verdict returns None → normal verdict → FN).
HOLD_SECONDS="${HOLD_SECONDS:-35}"
TARGET_FILE="/tmp/ebpf-ml-mao-memory-pressure.bin"

echo "[memory-pressure] locating fault-target pod in namespace ${NAMESPACE}"
POD="$(kubectl get pod -n "${NAMESPACE}" -l "${LABEL_SELECTOR}" -o jsonpath='{.items[0].metadata.name}')"

echo "[memory-pressure] writing temporary ${SIZE_MB}Mi file then holding ${HOLD_SECONDS}s in ${POD}"
kubectl exec -n "${NAMESPACE}" "${POD}" -- /bin/sh -c "
  set -eu
  rm -f '${TARGET_FILE}'
  dd if=/dev/zero of='${TARGET_FILE}' bs=1M count='${SIZE_MB}' 2>/dev/null
  sync
  sleep ${HOLD_SECONDS}
  rm -f '${TARGET_FILE}'
"

echo "[memory-pressure] completed temporary file pressure and cleanup"
