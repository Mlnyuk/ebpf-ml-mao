#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${1:-ebpf-obs-test}"
LABEL_SELECTOR="app=fault-target"
DURATION_SECONDS="${DURATION_SECONDS:-30}"

echo "[cpu-stress] locating fault-target pod in namespace ${NAMESPACE}"
POD="$(kubectl get pod -n "${NAMESPACE}" -l "${LABEL_SELECTOR}" -o jsonpath='{.items[0].metadata.name}')"

echo "[cpu-stress] starting ${DURATION_SECONDS}s bounded CPU busy loop in ${POD}"
kubectl exec -n "${NAMESPACE}" "${POD}" -- /bin/sh -c "
  set -eu
  cleanup() {
    kill \"\${worker:-}\" 2>/dev/null || true
  }
  trap cleanup EXIT INT TERM
  end=\$((\$(date +%s) + ${DURATION_SECONDS}))
  (
    while [ \$(date +%s) -lt \"\${end}\" ]; do
      : \$((17 * 19))
    done
  ) &
  worker=\$!
  wait \"\${worker}\" || true
"

echo "[cpu-stress] completed ${DURATION_SECONDS}s CPU stress run"
