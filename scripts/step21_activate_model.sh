#!/usr/bin/env bash
# Copy a freshly-trained baseline model into the analyzer PVC and activate it
# in the registry. Defaults match scripts/step21_train_baseline.py output.
#
# Usage:
#   bash scripts/step21_activate_model.sh [MODEL_JSON] [MODEL_ID]
set -euo pipefail

MODEL_JSON="${1:-${MODEL_JSON:-results/step21/baseline-v4.json}}"
MODEL_ID="${2:-${MODEL_ID:-baseline-v4-01}}"
THRESHOLD="${THRESHOLD:-0.45}"
TAG="${TAG:-step21}"

log() { echo "[step21-activate-model] $*"; }

if [[ ! -f "${MODEL_JSON}" ]]; then
  log "model file not found: ${MODEL_JSON}"
  exit 1
fi

analyzer_pod="$(
  kubectl get pod -n ebpf-obs \
    -l app=ebpf-ml-mao-analyzer \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
)"
if [[ -z "${analyzer_pod}" ]]; then
  log "analyzer pod not found"
  exit 1
fi

remote_path="/var/lib/ebpf-ml-mao/registry/models/$(basename "${MODEL_JSON}")"
log "copying ${MODEL_JSON} -> ${analyzer_pod}:${remote_path}"
kubectl cp "${MODEL_JSON}" "ebpf-obs/${analyzer_pod}:${remote_path}"

log "updating registry.json (activate ${MODEL_ID})"
kubectl exec -n ebpf-obs "${analyzer_pod}" -- cat /var/lib/ebpf-ml-mao/registry/registry.json | \
  MODEL_ID="${MODEL_ID}" MODEL_PATH="${remote_path}" THRESHOLD="${THRESHOLD}" TAG="${TAG}" \
  python3 -c '
import datetime, json, os, sys

reg = json.loads(sys.stdin.read())
model_id = os.environ["MODEL_ID"]
entry = {
    "id": model_id,
    "path": os.environ["MODEL_PATH"],
    "model_type": "baseline",
    "schema_version": "v2",
    "threshold": float(os.environ["THRESHOLD"]),
    "feature_count": 20,
    "created_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
    "tags": ["prod", os.environ["TAG"]],
}
ids = {m["id"] for m in reg.get("models", [])}
if model_id not in ids:
    reg.setdefault("models", []).append(entry)
reg["active_model_id"] = model_id
print(json.dumps(reg, indent=2))
' | kubectl exec -i -n ebpf-obs "${analyzer_pod}" -- sh -c 'cat > /var/lib/ebpf-ml-mao/registry/registry.json'

log "active model is now ${MODEL_ID}; restart analyzer to pick up: kubectl rollout restart deploy/ebpf-ml-mao-analyzer -n ebpf-obs"
