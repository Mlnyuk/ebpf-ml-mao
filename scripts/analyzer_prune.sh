#!/usr/bin/env bash
set -euo pipefail

NS="${NS:-ebpf-obs}"
ANALYZER_DEPLOY="${ANALYZER_DEPLOY:-ebpf-ml-mao-analyzer}"
ANALYZER_DATA_DIR="${ANALYZER_DATA_DIR:-/var/lib/ebpf-ml-mao}"
OLDER_THAN_DAYS="${OLDER_THAN_DAYS:-1}"
DRY_RUN="${DRY_RUN:-true}"
CANDIDATE_LIST_LIMIT="${CANDIDATE_LIST_LIMIT:-200}"
MAX_FILES_PER_DIR="${MAX_FILES_PER_DIR:-0}"
PRINT_DELETED="${PRINT_DELETED:-false}"

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

if ! [[ "${MAX_FILES_PER_DIR}" =~ ^[0-9]+$ ]]; then
  echo "MAX_FILES_PER_DIR must be a non-negative integer" >&2
  exit 2
fi

if [[ "${PRINT_DELETED}" != "true" && "${PRINT_DELETED}" != "false" ]]; then
  echo "PRINT_DELETED must be true or false" >&2
  exit 2
fi

log "namespace: ${NS}"
log "analyzer deployment: ${ANALYZER_DEPLOY}"
log "data dir: ${ANALYZER_DATA_DIR}"
log "target directories: ingest reports spool postprocess-queue queue"
log "age threshold: files older than ${OLDER_THAN_DAYS} day(s)"
log "max files per directory: ${MAX_FILES_PER_DIR} (0 disables count-based pruning)"
log "dry run: ${DRY_RUN}"
log "dry-run candidate list limit: ${CANDIDATE_LIST_LIMIT}"
log "print deleted files: ${PRINT_DELETED}"
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
  max_files='${MAX_FILES_PER_DIR}'
  print_deleted='${PRINT_DELETED}'
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
      if [ \"\${print_deleted}\" = \"true\" ]; then
        find \"\${dir}\" -type f -mtime +\"\${older}\" -print -delete 2>/dev/null
      else
        find \"\${dir}\" -type f -mtime +\"\${older}\" -delete 2>/dev/null
      fi
    fi

    if [ \"\${max_files}\" -gt 0 ]; then
      total=\$(find \"\${dir}\" -type f 2>/dev/null | wc -l | tr -d ' ')
      echo \"total files after age pass: \${total}\"
      if [ \"\${total}\" -gt \"\${max_files}\" ]; then
        remove_count=\$((total - max_files))
        echo \"count-based prune candidates: \${remove_count}\"
        if [ \"\${dry_run}\" = \"true\" ]; then
          find \"\${dir}\" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | head -n \"\${remove_count}\" | cut -d' ' -f2- | sed 's/^/DRY-RUN count-prune /' | head -n \"\${limit}\"
        else
          find \"\${dir}\" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | head -n \"\${remove_count}\" | cut -d' ' -f2- | xargs -r rm -f
        fi
      fi
    fi
  done
"
