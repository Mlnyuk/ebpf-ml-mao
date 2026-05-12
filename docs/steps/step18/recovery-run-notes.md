# Step 18 Recovery Run Notes

Run date: 2026-04-28 UTC

## Recovery Commands Used

```bash
python3 -m unittest discover -s tests -v
kubectl kustomize deploy/yaml/step18
kubectl apply -k deploy/yaml/step18
kubectl get hpa -n ebpf-obs
kubectl describe hpa -n ebpf-obs
kubectl get deploy -n ebpf-obs ebpf-ml-mao-analyzer
bash scripts/analyzer_storage_check.sh
DRY_RUN=true OLDER_THAN_DAYS=1 bash scripts/analyzer_prune.sh
DRY_RUN=false OLDER_THAN_DAYS=1 bash scripts/analyzer_prune.sh
kubectl delete hpa -n ebpf-obs ebpf-ml-mao-analyzer
bash scripts/step16_preflight.sh
kubectl port-forward -n ebpf-obs svc/ebpf-ml-mao-ui 8080:8080
bash scripts/step16_collect_results.sh
python3 scripts/step16_generate_report.py
```

## Storage Before

- PVC: `2.0G`
- Used: `1.3G`
- Available: `615M`
- Analyzer replicas: `1`
- HPA: present, targeting analyzer, patched to `minReplicas=1`, `maxReplicas=1`
- `registry`: `16K`
- `models`: missing
- `reports`: missing
- `ingest`: `1.1G`, `67402 files`
- `spool`: missing
- `postprocess-queue`: `208M`, `52288 files`
- `queue`: missing

## Prune Action

Dry-run was executed first with:

```bash
DRY_RUN=true OLDER_THAN_DAYS=1 bash scripts/analyzer_prune.sh
```

Dry-run candidate summary:

- `ingest`: `67402` candidate files
- `postprocess-queue`: `52288` candidate files
- `reports`, `spool`, `queue`: missing or no candidates
- `registry` and `models`: not targeted

Because the dry-run only targeted generated runtime directories, destructive prune was then executed with:

```bash
DRY_RUN=false OLDER_THAN_DAYS=1 bash scripts/analyzer_prune.sh
```

Pruned:

- generated files under `/var/lib/ebpf-ml-mao/ingest`
- generated files under `/var/lib/ebpf-ml-mao/postprocess-queue`

Not pruned:

- `/var/lib/ebpf-ml-mao/registry`
- `/var/lib/ebpf-ml-mao/models`

## Storage After Prune

- PVC: `2.0G`
- Used: `52M`
- Available: `1.9G`
- Analyzer replicas: `1`
- HPA: still present at first, targeting analyzer
- `registry`: `16K`
- `models`: missing
- `reports`: missing
- `ingest`: `3.4M`, `51 files`
- `spool`: missing
- `postprocess-queue`: `3.2M`, `43 files`
- `queue`: missing

Strict preflight still failed while the HPA object existed because `STRICT=true` treats any analyzer-targeting HPA as unsafe for the current file-based single-writer design. The analyzer HPA was deleted in the live experiment environment.

## Preflight After HPA Removal

Preflight passed after deleting the analyzer HPA:

- analyzer desired replicas: `1`
- analyzer ready replicas: `1`
- UI service: present
- collector DaemonSet: present
- fault target Deployment: present
- PVC available space: `1.9G`
- HPA: no analyzer HPA present

## Step 16/17 Rerun Status

Port-forward to `svc/ebpf-ml-mao-ui` succeeded and `/healthz` returned `ok`.

All four scenarios completed:

- `exec-storm`: `status=ok`
- `network-burst`: `status=ok`
- `cpu-stress`: `status=ok`
- `memory-pressure`: `status=ok`

API snapshots were collected for all scenarios:

- dashboard JSON
- alerts JSON
- workflow JSON

Logs were collected for all scenarios:

- analyzer logs
- collector logs

`kubectl top pod -n ebpf-obs-test` was collected for CPU and memory scenarios, but reported `0m` CPU and `0Mi` memory for the `fault-target` pod at the sample time.

Generated report:

```text
results/step16/experiment-report.md
```

## Anomaly Evidence

No anomalous verdict was observed in the collected dashboard, alerts, workflow, or generated report.

The generated report shows:

- each scenario snapshot status: `complete`
- each scenario alert count: `1`
- `anomalous`: `no`
- `score`: `no` in API snapshot JSON
- latest workflow/dashboard verdict: `normal`

Collector logs do contain normal report scoring output, for example `score: 0.4083` and summaries ending in `Final verdict is normal`. This confirms that report generation/scoring output was present in logs, but it is not evidence of anomaly detection success.

## Storage After Validation

- PVC: `2.0G`
- Used: `53M`
- Available: `1.9G`
- Analyzer replicas: `1`
- HPA: not present
- `registry`: `16K`
- `models`: missing
- `reports`: missing
- `ingest`: `4.2M`, `231 files`
- `spool`: missing
- `postprocess-queue`: `3.9M`, `223 files`
- `queue`: missing

## Limitations

- This recovery run did not modify eBPF programs.
- This recovery run did not add advanced ML.
- This recovery run does not make the analyzer production-HA.
- No anomaly detection success is claimed because the collected evidence remained `normal`.
- The fault-target pod metrics sampled by `kubectl top` were `0m` CPU and `0Mi` memory, so metric scrape timing and workload-to-metric mapping need further calibration.
