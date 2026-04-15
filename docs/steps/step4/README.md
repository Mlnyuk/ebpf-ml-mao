# Step 4

Step 4 범위는 `다중 workload / 다중 window 처리`입니다.

이번 단계에서는 기존 pipeline이 첫 번째 window 하나만 대표로 반환하던 구조를 바꿔, workload와 시간 버킷별로 여러 report를 생성하도록 확장했습니다.

## Added

- `app/ebpf_ml_mao/models.py`
  - `BatchAnalysisReport` 추가
- `app/ebpf_ml_mao/report.py`
  - batch index JSON/Markdown 출력 추가
- `app/ebpf_ml_mao/pipeline.py`
  - `build_batch_report(...)` 추가
  - `run_phase4(...)` 추가
- `app/ebpf_ml_mao/cli.py`
  - `phase4` subcommand 추가
- `samples/step4/`
  - 다중 workload / 다중 window 샘플 입력 추가

## Phase 4 Flow

```text
raw input
  -> adapters
  -> NormalizedEvent list
  -> workload + 30s window grouping
  -> feature extraction per window
  -> anomaly scoring per window
  -> multiple reports
  -> batch index + per-report outputs
```

## Run

저장소 루트에서 실행:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao phase4 \
  --baseline-tetragon samples/step2/baseline_tetragon.jsonl \
  --baseline-prometheus samples/step2/baseline_prometheus.json \
  --input-tetragon samples/step4/input_tetragon.jsonl \
  --input-prometheus samples/step4/input_prometheus.json \
  --output-dir docs/steps/step4/output
```

## Output

- `docs/steps/step4/output/report-index.json`
- `docs/steps/step4/output/report-index.md`
- `docs/steps/step4/output/reports/report-01.json`
- `docs/steps/step4/output/reports/report-01.md`
- `docs/steps/step4/output/reports/report-02.json`
- `docs/steps/step4/output/reports/report-02.md`
- `docs/steps/step4/output/reports/report-03.json`
- `docs/steps/step4/output/reports/report-03.md`

현재 샘플 기준 기대 결과:

- report count: `3`
- workload: `checkout`, `checkout`, `payment`
- verdict mix: `normal`, `anomalous`, `anomalous`

## Verification

```bash
python3 -m unittest discover -s tests -v
```

Step 4에서 추가 검증한 항목:

- 여러 workload와 여러 time window가 각각 별도 report로 분리됨
- batch index 파일이 생성됨
- per-report JSON/Markdown 파일이 생성됨

## Limits

- report 정렬은 현재 `workload + window_start` 기준
- batch summary는 최소 메타데이터만 포함
- cross-window 상관분석은 아직 없음
- top-N 우선순위 정렬은 아직 없음
