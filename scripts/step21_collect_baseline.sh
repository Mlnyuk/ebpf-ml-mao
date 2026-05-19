#!/usr/bin/env bash
# Collect fault-target baseline data (file_open events only) from the new
# Step 21 python workload so we can train a fresh baseline model.
#
# Usage:
#   bash scripts/step21_collect_baseline.sh [WAIT_SECONDS] [OUT_DIR]
set -euo pipefail

WAIT_SECONDS="${1:-${WAIT_SECONDS:-180}}"
OUT_DIR="${2:-${OUT_DIR:-results/step21/baseline_collect}}"

log() { echo "[step21-collect-baseline] $*"; }

mkdir -p "${OUT_DIR}"

log "waiting ${WAIT_SECONDS}s for fault-target events to accumulate"
sleep "${WAIT_SECONDS}"

analyzer_pod="$(
  kubectl get pod -n ebpf-obs \
    -l app=ebpf-ml-mao-analyzer \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
)"
if [[ -z "${analyzer_pod}" ]]; then
  log "analyzer pod not found"
  exit 1
fi

out_jsonl="${OUT_DIR}/fault-target-baseline.jsonl"
kubectl exec -n ebpf-obs "${analyzer_pod}" -- sh -c '
  find /var/lib/ebpf-ml-mao/ingest -name "*-report.json" 2>/dev/null | \
  while IFS= read -r f; do
    if grep -q fault-target "$f" 2>/dev/null; then cat "$f"; fi
  done
' 2>/dev/null | python3 "$(dirname "$0")/step16_extract_fault_target_scores.py" > "${out_jsonl}"

count="$(wc -l <"${out_jsonl}" | awk '{print $1}')"
log "wrote ${out_jsonl} (${count} windows)"
