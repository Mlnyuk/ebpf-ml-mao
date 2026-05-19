#!/usr/bin/env bash
# Run step16_collect_results.sh N times, each into its own result directory,
# producing independent samples for statistical analysis. Between runs the
# analyzer runtime history is pruned so each baseline starts clean. This
# script manages its own analyzer port-forward; any caller-side port-forward
# on 8080 is killed at start.
#
# Usage:
#   bash scripts/step16_repeat_experiments.sh [N] [BASE_DIR]
set -euo pipefail

N="${1:-${REPEAT_N:-5}}"
BASE_DIR="${2:-${BASE_DIR:-results/step20}}"
WARMUP_BASELINE="${WARMUP_BASELINE:-true}"
WARMUP_DURATION="${WARMUP_DURATION:-60}"
ANALYZER_RESTART_TIMEOUT="${ANALYZER_RESTART_TIMEOUT:-180s}"
PORT_FORWARD_PORT="${PORT_FORWARD_PORT:-8080}"
PORT_FORWARD_READY_TIMEOUT="${PORT_FORWARD_READY_TIMEOUT:-30}"

log() {
  echo "[repeat] $*"
}

mkdir -p "${BASE_DIR}"

PF_PID=""
PF_LOG="${BASE_DIR}/port-forward.log"

stop_port_forward() {
  if [[ -n "${PF_PID}" ]] && kill -0 "${PF_PID}" 2>/dev/null; then
    kill "${PF_PID}" 2>/dev/null || true
    wait "${PF_PID}" 2>/dev/null || true
  fi
  PF_PID=""
  # belt-and-suspenders: kill any stray port-forward on the target port
  pkill -f "kubectl port-forward -n ebpf-obs svc/ebpf-ml-mao-analyzer ${PORT_FORWARD_PORT}:" 2>/dev/null || true
  sleep 1
}

start_port_forward() {
  stop_port_forward
  log "starting analyzer port-forward on :${PORT_FORWARD_PORT}"
  kubectl port-forward -n ebpf-obs svc/ebpf-ml-mao-analyzer "${PORT_FORWARD_PORT}:8080" \
    >>"${PF_LOG}" 2>&1 &
  PF_PID=$!

  # wait until the analyzer responds
  local ready_end=$(( $(date +%s) + PORT_FORWARD_READY_TIMEOUT ))
  while [[ $(date +%s) -lt ${ready_end} ]]; do
    if curl -fsS --max-time 2 "http://localhost:${PORT_FORWARD_PORT}/v1/dashboard" >/dev/null 2>&1; then
      log "port-forward ready (pid=${PF_PID})"
      return 0
    fi
    sleep 1
  done
  log "WARN: port-forward did not become ready within ${PORT_FORWARD_READY_TIMEOUT}s"
  return 1
}

trap stop_port_forward EXIT

for i in $(seq 1 "${N}"); do
  run_dir="$(printf '%s/run_%02d' "${BASE_DIR}" "${i}")"
  log "=== run ${i}/${N} → ${run_dir} ==="

  # 1. prune runtime history so the analyzer baseline starts clean
  log "pruning analyzer runtime history"
  DRY_RUN=false PRUNE_ALL=true bash scripts/analyzer_prune.sh >"${BASE_DIR}/prune_${i}.log" 2>&1 || true

  log "restarting analyzer for clean state"
  kubectl rollout restart deploy/ebpf-ml-mao-analyzer -n ebpf-obs >/dev/null
  kubectl rollout status deploy/ebpf-ml-mao-analyzer -n ebpf-obs --timeout="${ANALYZER_RESTART_TIMEOUT}"

  # (re)start port-forward against the new pod
  start_port_forward || true

  # 2. run the standard collection script into the per-run directory
  log "starting step16 collection"
  WARMUP_BASELINE="${WARMUP_BASELINE}" \
  WARMUP_DURATION="${WARMUP_DURATION}" \
  RESULT_DIR="${run_dir}" \
  API_BASE="http://localhost:${PORT_FORWARD_PORT}" \
    bash scripts/step16_collect_results.sh

  # 3. per-run analysis
  log "running per-run analysis"
  RESULT_DIR="${run_dir}" python3 scripts/step16_generate_report.py >/dev/null
  RESULT_DIR="${run_dir}" python3 scripts/step16_analyze_thresholds.py >/dev/null
  RESULT_DIR="${run_dir}" python3 scripts/step16_generate_paper_tables.py >/dev/null

  log "run ${i} complete"
done

stop_port_forward
log "all ${N} runs complete → ${BASE_DIR}"
log "next: python3 scripts/step16_aggregate_repeated.py ${BASE_DIR}"
