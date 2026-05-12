#!/usr/bin/env bash
set -euo pipefail

NS="${NS:-ebpf-obs}"
ANALYZER_DEPLOY="${ANALYZER_DEPLOY:-ebpf-ml-mao-analyzer}"
TEST_NS="${TEST_NS:-ebpf-obs-test}"
ANALYZER_DATA_DIR="${ANALYZER_DATA_DIR:-/var/lib/ebpf-ml-mao}"
COLLECTOR_DS="${COLLECTOR_DS:-ebpf-ml-mao-collector}"
UI_SERVICE="${UI_SERVICE:-ebpf-ml-mao-ui}"
FAULT_DEPLOY="${FAULT_DEPLOY:-fault-target}"
STRICT="${STRICT:-true}"

failures=0

log() {
  echo "[step16-preflight] $*"
}

warn() {
  echo "[step16-preflight][WARN] $*" >&2
}

fail_or_warn() {
  local message="$1"
  if [[ "${STRICT}" == "true" ]]; then
    echo "[step16-preflight][FAIL] ${message}" >&2
    failures=$((failures + 1))
  else
    warn "${message}"
  fi
}

actionable_next_steps() {
  cat <<EOF

Actionable next commands:
- kubectl scale deploy -n ${NS} ${ANALYZER_DEPLOY} --replicas=1
- kubectl delete hpa -n ${NS} <hpa-name>
- bash scripts/analyzer_storage_check.sh
- DRY_RUN=true bash scripts/analyzer_prune.sh
- kubectl apply -k deploy/yaml/step18
EOF
}

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is not available" >&2
  exit 127
fi

if [[ "${STRICT}" != "true" && "${STRICT}" != "false" ]]; then
  echo "STRICT must be true or false" >&2
  exit 2
fi

log "namespace: ${NS}"
log "strict mode: ${STRICT}"

if ! kubectl get deploy -n "${NS}" "${ANALYZER_DEPLOY}" >/dev/null 2>&1; then
  echo "analyzer deployment not found: ${NS}/${ANALYZER_DEPLOY}" >&2
  actionable_next_steps
  exit 1
fi

desired="$(kubectl get deploy -n "${NS}" "${ANALYZER_DEPLOY}" -o jsonpath='{.spec.replicas}')"
ready="$(kubectl get deploy -n "${NS}" "${ANALYZER_DEPLOY}" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || true)"
ready="${ready:-0}"
log "analyzer desired replicas: ${desired:-unknown}"
log "analyzer ready replicas: ${ready}"

if [[ "${ready}" == "0" ]]; then
  failures=$((failures + 1))
  echo "[step16-preflight][FAIL] analyzer has no ready replicas" >&2
fi

if [[ "${desired:-0}" =~ ^[0-9]+$ ]] && (( desired > 1 )); then
  fail_or_warn "analyzer desired replicas > 1; current file-based state should be single-writer"
fi

hpa_targets="$(kubectl get hpa -n "${NS}" -o jsonpath='{range .items[?(@.spec.scaleTargetRef.name=="'"${ANALYZER_DEPLOY}"'")]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)"
if [[ -n "${hpa_targets}" ]]; then
  fail_or_warn "HPA targets analyzer deployment: ${hpa_targets//$'\n'/, }"
fi

if kubectl get ds -n "${NS}" "${COLLECTOR_DS}" >/dev/null 2>&1; then
  log "collector DaemonSet exists: ${COLLECTOR_DS}"
else
  warn "collector DaemonSet not found: ${COLLECTOR_DS}"
fi

if kubectl get svc -n "${NS}" "${UI_SERVICE}" >/dev/null 2>&1; then
  log "UI service exists: ${UI_SERVICE}"
else
  failures=$((failures + 1))
  echo "[step16-preflight][FAIL] UI service not found: ${UI_SERVICE}" >&2
fi

if kubectl get deploy -n "${TEST_NS}" "${FAULT_DEPLOY}" >/dev/null 2>&1; then
  log "fault target deployment exists: ${TEST_NS}/${FAULT_DEPLOY}"
else
  warn "fault target deployment not found; apply Step 16/18 before live scenarios"
fi

pod="$(kubectl get pod -n "${NS}" -l "app=${ANALYZER_DEPLOY}" -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.phase}{"\n"}{end}' 2>/dev/null | awk '$2 == "Running" {print $1; exit}')"
if [[ -n "${pod}" ]]; then
  log "checking analyzer data dir free space on pod ${pod}"
  kubectl exec -n "${NS}" "${pod}" -- /bin/sh -c "df -h '${ANALYZER_DATA_DIR}' 2>/dev/null || df -h" || warn "unable to check analyzer data dir space"
else
  warn "no analyzer pod found for storage check"
fi

if (( failures > 0 )); then
  actionable_next_steps
  exit 1
fi

log "preflight completed"
actionable_next_steps
