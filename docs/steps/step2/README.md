# Step 2

Step 2 범위는 `실제 입력 어댑터 연결`입니다.

이번 단계에서는 Phase 1의 내부 파이프라인은 그대로 두고, 아래 두 입력 소스를 붙였습니다.

- Tetragon raw JSONL event
- Prometheus metric snapshot JSON

## Added

- `app/ebpf_ml_mao/adapters.py`
  - Tetragon raw event -> `NormalizedEvent`
  - Prometheus snapshot -> `NormalizedEvent`
- `app/ebpf_ml_mao/pipeline.py`
  - `run_phase2(...)` 추가
  - 기존 점수화/리포트 경로는 재사용
- `app/ebpf_ml_mao/cli.py`
  - `phase1`, `phase2` subcommand 분리
- `samples/step2/`
  - baseline/input raw sample 추가

## Phase 2 Flow

```text
Tetragon JSONL + Prometheus snapshot JSON
  -> source adapters
  -> NormalizedEvent list
  -> 30s window feature extraction
  -> baseline anomaly scoring
  -> multi-agent summaries
  -> JSON/Markdown report
```

## Adapter Notes

### Tetragon

추출 필드:

- `time`
- `type`
- `process.pid`
- `process.node_name`
- `process.pod.name`
- `process.pod.workload`
- `process.pod.container.name`

Tetragon 이벤트에는 CPU/메모리 같은 metric 값이 없으므로 해당 필드는 `0`으로 두고, Prometheus snapshot이 이를 채우는 구조로 뒀습니다.

### Prometheus

입력 포맷은 간단한 snapshot JSON입니다.

지원 metric:

- `container_cpu_usage_percent`
- `container_memory_working_set_bytes`
- `container_network_connections`

동일 workload/pod/container/node 라벨을 기준으로 한 개의 metric event로 합칩니다.

## Run

저장소 루트에서 실행:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao phase2 \
  --baseline-tetragon samples/step2/baseline_tetragon.jsonl \
  --baseline-prometheus samples/step2/baseline_prometheus.json \
  --input-tetragon samples/step2/input_tetragon.jsonl \
  --input-prometheus samples/step2/input_prometheus.json \
  --output-dir docs/steps/step2/output
```

## Output

- `docs/steps/step2/output/report.json`
- `docs/steps/step2/output/report.md`

현재 샘플 기준으로 anomalous 판정이 나와야 정상입니다.

## Verification

```bash
python3 -m unittest discover -s tests -v
```

Step 2에서 추가 검증한 항목:

- Tetragon nested field 파싱
- Prometheus snapshot 집계
- mixed source 입력이 기존 anomaly pipeline에 연결됨

## Limits

- 실시간 Tetragon gRPC/stream 구독은 아직 없음
- 실제 Prometheus HTTP scrape는 아직 없음
- metric 이름 매핑은 현재 샘플 기준 최소 집합만 지원
- 다중 workload 동시 리포트는 아직 한 윈도우만 대표로 반환
