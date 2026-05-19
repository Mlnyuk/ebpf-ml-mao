#!/usr/bin/env bash
set -euo pipefail

RESULT_DIR="${RESULT_DIR:-results/step16}"
API_BASE="${API_BASE:-http://localhost:8080}"
NAMESPACE="${NAMESPACE:-ebpf-obs-test}"
SETTLE_SECONDS="${SETTLE_SECONDS:-35}"
CURL_MAX_TIME_SECONDS="${CURL_MAX_TIME_SECONDS:-10}"

mkdir -p "${RESULT_DIR}"

log() {
  echo "[step16-collect] $*"
}

write_json_error() {
  local path="$1"
  local message="$2"
  printf '{\n  "status": "error",\n  "error": "%s"\n}\n' "${message//\"/\\\"}" > "${path}"
}

collect_endpoint() {
  local endpoint="$1"
  local path="$2"
  if curl -fsS --max-time "${CURL_MAX_TIME_SECONDS}" "${API_BASE}${endpoint}" -o "${path}"; then
    log "wrote ${path}"
  else
    write_json_error "${path}" "failed to collect ${API_BASE}${endpoint}; check port-forward and analyzer readiness"
    log "failed to collect ${endpoint}; wrote error JSON to ${path}"
  fi
}

collect_logs() {
  local scenario="$1"
  if kubectl logs -n ebpf-obs deploy/ebpf-ml-mao-analyzer --all-containers --tail=200 > "${RESULT_DIR}/${scenario}-analyzer.log" 2>&1; then
    log "wrote ${scenario}-analyzer.log"
  else
    log "failed to collect analyzer logs; see ${scenario}-analyzer.log"
  fi

  if kubectl logs -n ebpf-obs ds/ebpf-ml-mao-collector --all-containers --tail=300 > "${RESULT_DIR}/${scenario}-collector.log" 2>&1; then
    log "wrote ${scenario}-collector.log"
  else
    log "failed to collect collector logs; see ${scenario}-collector.log"
  fi
}

collect_top() {
  local scenario="$1"
  if kubectl top pod -n "${NAMESPACE}" > "${RESULT_DIR}/${scenario}-kubectl-top.txt" 2>&1; then
    log "wrote ${scenario}-kubectl-top.txt"
  else
    log "kubectl top unavailable for ${scenario}; wrote command output to ${scenario}-kubectl-top.txt"
  fi
}

collect_tetragon_tail() {
  local scenario="$1"
  local target_node
  local collector_pod

  target_node="$(kubectl get pod -n "${NAMESPACE}" -l app=fault-target -o jsonpath='{.items[0].spec.nodeName}' 2>/dev/null || true)"
  if [[ -z "${target_node}" ]]; then
    write_json_error "${RESULT_DIR}/${scenario}-tetragon-tail.jsonl" "fault-target pod not found; cannot choose node-local collector"
    log "fault-target pod not found; wrote error JSON to ${scenario}-tetragon-tail.jsonl"
    return
  fi

  collector_pod="$(
    kubectl get pod -n ebpf-obs \
      -l app=ebpf-ml-mao-collector \
      --field-selector "spec.nodeName=${target_node}" \
      -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
  )"
  if [[ -z "${collector_pod}" ]]; then
    write_json_error "${RESULT_DIR}/${scenario}-tetragon-tail.jsonl" "collector pod not found on ${target_node}; cannot inspect Tetragon tail"
    log "collector pod not found on ${target_node}; wrote error JSON to ${scenario}-tetragon-tail.jsonl"
    return
  fi

  if kubectl exec -n ebpf-obs "${collector_pod}" -c collector -- /bin/sh -c 'tail -n "${TETRAGON_TAIL_LINES:-200}" "${TETRAGON_LOG_PATH}"' > "${RESULT_DIR}/${scenario}-tetragon-tail.jsonl" 2>&1; then
    log "wrote ${scenario}-tetragon-tail.jsonl"
  else
    log "failed to collect Tetragon tail; see ${scenario}-tetragon-tail.jsonl"
  fi

  if kubectl exec -n ebpf-obs "${collector_pod}" -c collector -- /bin/sh -c 'grep -F "fault-target" "${TETRAGON_LOG_PATH}" | tail -n "${TETRAGON_TARGET_TAIL_LINES:-50}" || true' > "${RESULT_DIR}/${scenario}-tetragon-fault-target.jsonl" 2>&1; then
    log "wrote ${scenario}-tetragon-fault-target.jsonl"
  else
    log "failed to collect fault-target Tetragon events; see ${scenario}-tetragon-fault-target.jsonl"
  fi
}

collect_snapshot() {
  local prefix="$1"
  collect_endpoint "/v1/dashboard" "${RESULT_DIR}/${prefix}-dashboard.json"
  collect_endpoint "/v1/alerts" "${RESULT_DIR}/${prefix}-alerts.json"
  collect_endpoint "/v1/workflow" "${RESULT_DIR}/${prefix}-workflow.json"
  collect_tetragon_tail "${prefix}"
}

run_scenario() {
  local name="$1"
  local script="$2"
  local status_file="${RESULT_DIR}/${name}-scenario-status.txt"

  log "starting scenario: ${name}"
  if bash "${script}" > "${RESULT_DIR}/${name}-scenario.log" 2>&1; then
    echo "status=ok" > "${status_file}"
    log "scenario completed: ${name}"
  else
    local code="$?"
    {
      echo "status=failed"
      echo "exit_code=${code}"
      echo "script=${script}"
    } > "${status_file}"
    log "scenario failed: ${name}; continuing so partial results are preserved"
  fi

  log "waiting ${SETTLE_SECONDS}s for collector/analyzer update"
  sleep "${SETTLE_SECONDS}"
  collect_snapshot "${name}"
  collect_logs "${name}"
  collect_top "${name}"
}

log "collecting baseline snapshots from ${API_BASE}"
collect_snapshot "baseline"
collect_logs "baseline"

run_scenario "exec-storm" "scripts/fault-scenarios/exec-storm.sh"
run_scenario "network-burst" "scripts/fault-scenarios/network-burst.sh"
run_scenario "cpu-stress" "scripts/fault-scenarios/cpu-stress.sh"
run_scenario "memory-pressure" "scripts/fault-scenarios/memory-pressure.sh"

log "result collection complete: ${RESULT_DIR}"
