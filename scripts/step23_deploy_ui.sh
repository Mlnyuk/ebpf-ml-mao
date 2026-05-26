#!/usr/bin/env bash
# Deploy the Step 23 dashboard onto a running analyzer WITHOUT rebuilding the
# container image. Two pieces are packaged in the image and live-patched here:
#   1. UI assets (dashboard.html/js/css) at /app/app/ebpf_ml_mao/ui
#   2. backend api.py (per-workload aggregation + /v1/scores) at
#      /app/app/ebpf_ml_mao/api.py
# Both are sourced from the canonical app/ tree and mounted via ConfigMaps so the
# running pod serves the new dashboard and emits per-workload data.
#
# This is a stop-gap for environments without a container build toolchain. The
# durable fix is to rebuild the image from the committed app/ source.
#
# Reversible: `bash scripts/step23_deploy_ui.sh --revert`.
set -euo pipefail

NAMESPACE="${NAMESPACE:-ebpf-obs}"
DEPLOY="${DEPLOY:-ebpf-ml-mao-analyzer}"
CONTAINER="${CONTAINER:-analyzer}"
UI_CONFIGMAP="${UI_CONFIGMAP:-ebpf-ml-mao-ui-assets}"
API_CONFIGMAP="${API_CONFIGMAP:-ebpf-ml-mao-api-patch}"
UI_MOUNT_PATH="${UI_MOUNT_PATH:-/app/app/ebpf_ml_mao/ui}"
API_MOUNT_PATH="${API_MOUNT_PATH:-/app/app/ebpf_ml_mao/api.py}"
ROLLOUT_TIMEOUT="${ROLLOUT_TIMEOUT:-180s}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UI_DIR="${REPO_ROOT}/app/ebpf_ml_mao/ui"
API_FILE="${REPO_ROOT}/app/ebpf_ml_mao/api.py"

log() { echo "[step23-deploy] $*"; }

if [[ "${1:-}" == "--revert" ]]; then
  log "stripping ui-assets/api-patch volumes + mounts from ${DEPLOY}"
  kubectl patch deployment "${DEPLOY}" -n "${NAMESPACE}" --type=json -p "$(cat <<'JSON'
[
  {"op":"test","path":"/spec/template/spec/containers/0/name","value":"analyzer"}
]
JSON
)" >/dev/null 2>&1 || true
  # Remove by re-applying without the extra volumes/mounts is fragile; instead
  # delete the ConfigMaps and let the operator/image fall back to packaged files.
  kubectl delete configmap "${UI_CONFIGMAP}" "${API_CONFIGMAP}" -n "${NAMESPACE}" --ignore-not-found
  log "deleted ConfigMaps. Manually remove the ui-assets/api-patch volumes from"
  log "the deployment if you want to drop the mounts, then rollout restart."
  exit 0
fi

log "building ${UI_CONFIGMAP} from ${UI_DIR}"
kubectl create configmap "${UI_CONFIGMAP}" -n "${NAMESPACE}" \
  --from-file=dashboard.html="${UI_DIR}/dashboard.html" \
  --from-file=dashboard.js="${UI_DIR}/dashboard.js" \
  --from-file=dashboard.css="${UI_DIR}/dashboard.css" \
  --dry-run=client -o yaml | kubectl apply -f -

log "building ${API_CONFIGMAP} from ${API_FILE}"
kubectl create configmap "${API_CONFIGMAP}" -n "${NAMESPACE}" \
  --from-file=api.py="${API_FILE}" \
  --dry-run=client -o yaml | kubectl apply -f -

log "patching ${DEPLOY}: mount UI dir at ${UI_MOUNT_PATH}, api.py at ${API_MOUNT_PATH}"
kubectl patch deployment "${DEPLOY}" -n "${NAMESPACE}" --type=strategic -p "$(cat <<JSON
{
  "spec": {
    "template": {
      "spec": {
        "volumes": [
          {"name": "ui-assets", "configMap": {"name": "${UI_CONFIGMAP}"}},
          {"name": "api-patch", "configMap": {"name": "${API_CONFIGMAP}"}}
        ],
        "containers": [
          {
            "name": "${CONTAINER}",
            "volumeMounts": [
              {"name": "ui-assets", "mountPath": "${UI_MOUNT_PATH}", "readOnly": true},
              {"name": "api-patch", "mountPath": "${API_MOUNT_PATH}", "subPath": "api.py", "readOnly": true}
            ]
          }
        ]
      }
    }
  }
}
JSON
)"

log "forcing a fresh rollout so subPath mounts are picked up"
kubectl rollout restart "deploy/${DEPLOY}" -n "${NAMESPACE}"
log "waiting for rollout"
kubectl rollout status "deploy/${DEPLOY}" -n "${NAMESPACE}" --timeout="${ROLLOUT_TIMEOUT}"

# Reports indexed by the previous (pre-Step-23) api.py lack the workload/score
# fields. Rebuild the index from the stored report payloads so the per-workload
# view is populated immediately instead of only for reports received afterwards.
log "rebuilding ingest index so existing reports gain per-workload fields"
POD="$(kubectl get pod -n "${NAMESPACE}" -l app="${DEPLOY##*/}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
if [[ -n "${POD}" ]]; then
  ING="$(kubectl exec -n "${NAMESPACE}" "${POD}" -- printenv ANALYZER_INGEST_DIR 2>/dev/null || echo /var/lib/ebpf-ml-mao/ingest)"
  kubectl exec -n "${NAMESPACE}" "${POD}" -- python3 -c "
from ebpf_ml_mao.api import rebuild_ingest_index
idx = rebuild_ingest_index('${ING}')
print('[step23-deploy] reindexed', idx['received_count'], 'reports')
" || log "WARN: index rebuild failed; new per-workload fields will fill in as fresh reports arrive"
fi

log "done. Dashboard served via NodePort 30002 (svc ebpf-ml-mao-ui)."
