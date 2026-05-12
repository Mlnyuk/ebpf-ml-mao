# Step 17

Step 17 범위는 Step 16 live fault scenario validation 결과를 오프라인으로 집계하고 Markdown 리포트로 정리하는 것입니다.

Step 16은 실제 Kubernetes workload에 fault scenario를 주입하는 단계이고, Step 17은 그때 수집된 dashboard, alerts, workflow, analyzer log, collector log, `kubectl top` 결과를 `results/step16/experiment-report.md`로 변환합니다. live cluster가 없거나 port-forward가 실패한 경우에도, 현재 존재하는 결과 파일만으로 partial report를 만들 수 있습니다.

## Commands

Step 16 workload와 analyzer UI port-forward가 준비된 상태에서 결과를 수집합니다.

```bash
bash scripts/step16_collect_results.sh
```

수집된 결과를 Markdown report로 변환합니다.

```bash
python3 scripts/step16_generate_report.py
```

## Scenarios Covered

- `exec-storm`: 반복 `kubectl exec`로 process execution activity를 만든다.
- `network-burst`: pod 내부에서 Kubernetes service endpoint로 반복 network request를 만든다.
- `cpu-stress`: 약 30초 동안 bounded CPU busy loop를 만든다.
- `memory-pressure`: 임시 파일 생성/삭제로 안전한 memory/file pressure를 만든다.

## Interpretation

성공적인 scenario execution은 fault-target pod에 의도한 행위가 주입되었음을 뜻합니다. 이후 dashboard/workflow가 갱신되면 collector와 analyzer가 적어도 일부 runtime 결과를 수집하고 API로 노출했다는 의미입니다.

alert 또는 anomaly 변화가 보이면 fault scenario가 현재 feature/scoring 설정에서 anomaly signal로 관측되었다고 해석할 수 있습니다. 반대로 anomaly가 나오지 않아도 pipeline 실패를 의미하지는 않습니다. threshold, baseline, scrape interval, Tetragon policy coverage, Prometheus metric coverage, workload label mapping을 조정해야 할 수 있습니다.

## Limitations

- Step 17은 advanced ML을 추가하지 않습니다.
- Step 17은 eBPF program을 직접 수정하지 않습니다.
- Step 17은 analyzer를 production-HA 구조로 바꾸지 않습니다.
- analyzer는 여전히 ReadWriteOnce PVC와 파일 기반 registry/ingest/postprocess queue를 사용하는 단일 writer 성격을 가집니다.

## Korean Summary

Step 17은 Step 16에서 수집된 실험 결과를 자동으로 집계하여 Markdown 리포트로 변환한다. 이를 통해 장애 주입 시나리오별 관측 결과, alert 변화, anomaly signal 여부를 재현 가능한 형태로 정리할 수 있다.
