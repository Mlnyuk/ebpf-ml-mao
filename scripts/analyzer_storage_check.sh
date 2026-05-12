#!/usr/bin/env bash
set -euo pipefail

NS="${NS:-ebpf-obs}"
ANALYZER_DEPLOY="${ANALYZER_DEPLOY:-ebpf-ml-mao-analyzer}"
ANALYZER_DATA_DIR="${ANALYZER_DATA_DIR:-/var/lib/ebpf-ml-mao}"

log() {
  echo "[analyzer-storage-check] $*"
}

warn() {
  echo "[analyzer-storage-check][WARN] $*" >&2
}

deployment_replicas() {
  kubectl get deploy -n "${NS}" "${ANALYZER_DEPLOY}" -o jsonpath='{.spec.replicas}' 2>/dev/null || true
}

first_analyzer_pod() {
  kubectl get pod -n "${NS}" -l "app=${ANALYZER_DEPLOY}" -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.phase}{"\n"}{end}' 2>/dev/null \
    | awk '$2 == "Running" {print $1; exit}'
}

hpa_targets() {
  kubectl get hpa -n "${NS}" -o jsonpath='{range .items[?(@.spec.scaleTargetRef.name=="'"${ANALYZER_DEPLOY}"'")]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true
}

log "namespace: ${NS}"
log "analyzer deployment: ${ANALYZER_DEPLOY}"
log "analyzer data dir: ${ANALYZER_DATA_DIR}"

echo
log "analyzer pods"
kubectl get pod -n "${NS}" -l "app=${ANALYZER_DEPLOY}" -o wide || true

echo
log "PVCs"
kubectl get pvc -n "${NS}" || true

echo
log "HPAs"
kubectl get hpa -n "${NS}" || true

replicas="$(deployment_replicas)"
echo
log "analyzer deployment replicas: ${replicas:-unknown}"
if [[ "${replicas:-0}" =~ ^[0-9]+$ ]] && (( replicas > 1 )); then
  warn "analyzer replicas are greater than 1; file-based registry/ingest/queue should be treated as single-writer"
fi

targets="$(hpa_targets)"
if [[ -n "${targets}" ]]; then
  warn "HPA targets analyzer deployment: ${targets//$'\n'/, }"
fi

pod="$(first_analyzer_pod)"
if [[ -z "${pod}" ]]; then
  warn "no analyzer pod found; skipping in-pod storage checks"
  exit 0
fi

echo
log "using analyzer pod: ${pod}"
log "disk usage"
kubectl exec -n "${NS}" "${pod}" -- /bin/sh -c "df -h '${ANALYZER_DATA_DIR}' 2>/dev/null || df -h" || true

echo
log "directory usage"
kubectl exec -n "${NS}" "${pod}" -- /bin/sh -c "
  set -eu
  base='${ANALYZER_DATA_DIR}'
  for name in registry models reports ingest spool postprocess-queue queue; do
    dir=\"\${base}/\${name}\"
    if [ -e \"\${dir}\" ]; then
      du -sh \"\${dir}\" 2>/dev/null || true
    else
      echo \"missing \${dir}\"
    fi
  done
" || true

echo
log "file counts"
kubectl exec -n "${NS}" "${pod}" -- /bin/sh -c "
  set -eu
  base='${ANALYZER_DATA_DIR}'
  for name in ingest reports spool postprocess-queue queue; do
    dir=\"\${base}/\${name}\"
    if [ -d \"\${dir}\" ]; then
      count=\$(find \"\${dir}\" -type f 2>/dev/null | wc -l | tr -d ' ')
      echo \"\${dir}: \${count} files\"
    else
      echo \"missing \${dir}\"
    fi
  done
" || true
