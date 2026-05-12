#!/usr/bin/env bash
set -euo pipefail

NS="${NS:-ebpf-obs}"
ANALYZER_DEPLOY="${ANALYZER_DEPLOY:-ebpf-ml-mao-analyzer}"
ANALYZER_DATA_DIR="${ANALYZER_DATA_DIR:-/var/lib/ebpf-ml-mao}"
OLDER_THAN_DAYS="${OLDER_THAN_DAYS:-1}"
DRY_RUN="${DRY_RUN:-true}"
CANDIDATE_LIST_LIMIT="${CANDIDATE_LIST_LIMIT:-200}"

log() {
  echo "[analyzer-prune] $*"
}

warn() {
  echo "[analyzer-prune][WARN] $*" >&2
}

first_analyzer_pod() {
  kubectl get pod -n "${NS}" -l "app=${ANALYZER_DEPLOY}" -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.phase}{"\n"}{end}' 2>/dev/null \
    | awk '$2 == "Running" {print $1; exit}'
}

if ! [[ "${OLDER_THAN_DAYS}" =~ ^[0-9]+$ ]]; then
  echo "OLDER_THAN_DAYS must be a non-negative integer" >&2
  exit 2
fi

if [[ "${DRY_RUN}" != "true" && "${DRY_RUN}" != "false" ]]; then
  echo "DRY_RUN must be true or false" >&2
  exit 2
fi

log "namespace: ${NS}"
log "analyzer deployment: ${ANALYZER_DEPLOY}"
log "data dir: ${ANALYZER_DATA_DIR}"
log "target directories: ingest reports spool postprocess-queue queue"
log "age threshold: files older than ${OLDER_THAN_DAYS} day(s)"
log "dry run: ${DRY_RUN}"
log "dry-run candidate list limit: ${CANDIDATE_LIST_LIMIT}"
warn "This command targets generated runtime/experiment data only. It never touches registry or models."
warn "If DRY_RUN=false, this may delete collected experiment/runtime data."

pod="$(first_analyzer_pod)"
if [[ -z "${pod}" ]]; then
  warn "no analyzer pod found; nothing to prune"
  exit 0
fi

kubectl exec -n "${NS}" "${pod}" -- /bin/sh -c "
  set -eu
  base='${ANALYZER_DATA_DIR}'
  older='${OLDER_THAN_DAYS}'
  dry_run='${DRY_RUN}'
  limit='${CANDIDATE_LIST_LIMIT}'
  for name in ingest reports spool postprocess-queue queue; do
    dir=\"\${base}/\${name}\"
    echo \"--- \${dir} ---\"
    if [ ! -d \"\${dir}\" ]; then
      echo \"missing; skipped\"
      continue
    fi
    count=\$(find \"\${dir}\" -type f -mtime +\"\${older}\" 2>/dev/null | wc -l | tr -d ' ')
    echo \"candidate files: \${count}\"
    if [ \"\${dry_run}\" = \"true\" ]; then
      echo \"showing up to \${limit} candidate file(s)\"
      find \"\${dir}\" -type f -mtime +\"\${older}\" -print 2>/dev/null | sed 's/^/DRY-RUN /' | head -n \"\${limit}\"
    else
      echo \"DELETING candidate files under \${dir}\"
      find \"\${dir}\" -type f -mtime +\"\${older}\" -print -delete 2>/dev/null
    fi
  done
"
