#!/usr/bin/env bash
# Inject low-rate exec activity into fault-target so the analyzer produces
# scoring windows for the target workload during the baseline period.
# Without this warmup, fault-target is mostly idle and the baseline contains
# zero per-sample scores, which prevents quantitative FP rate measurement.
set -euo pipefail

NAMESPACE="${NAMESPACE:-ebpf-obs-test}"
DURATION="${WARMUP_DURATION:-${DURATION:-60}}"
INTERVAL="${WARMUP_INTERVAL:-${INTERVAL:-5}}"

log() {
  echo "[warmup-baseline] $*"
}

pod="$(
  kubectl get pod -n "${NAMESPACE}" \
    -l app=fault-target \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
)"
if [[ -z "${pod}" ]]; then
  log "fault-target pod not found in namespace ${NAMESPACE}; skipping warmup"
  exit 0
fi

log "starting low-rate exec activity on ${pod} for ${DURATION}s (interval=${INTERVAL}s)"
end_ts=$(( $(date +%s) + DURATION ))
ticks=0
while [[ $(date +%s) -lt ${end_ts} ]]; do
  kubectl exec -n "${NAMESPACE}" "${pod}" -- sh -c 'ls / >/dev/null 2>&1' >/dev/null 2>&1 || true
  ticks=$(( ticks + 1 ))
  sleep "${INTERVAL}"
done
log "warmup complete after ${ticks} ticks"
