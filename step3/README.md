# Step 3

Step 3 범위는 `live ingestion 연결`입니다.

이번 단계에서는 Step 2의 raw adapter를 재사용하면서 입력 경로만 실시간 방식으로 바꿨습니다.

- Prometheus: 실제 HTTP scrape
- Tetragon: 실제 JSONL 로그 파일 tail

## Added

- `app/ebpf_ml_mao/live.py`
  - Tetragon log tail reader
  - Prometheus HTTP scraper
  - Prometheus text exposition parser
- `app/ebpf_ml_mao/pipeline.py`
  - `run_phase3(...)` 추가
- `app/ebpf_ml_mao/cli.py`
  - `phase3` subcommand 추가
- `samples/step3/`
  - live ingestion 테스트용 Tetragon log / Prometheus metrics 샘플

## Phase 3 Flow

```text
Tetragon log file tail + Prometheus HTTP scrape
  -> source adapters
  -> NormalizedEvent list
  -> 30s window feature extraction
  -> baseline anomaly scoring
  -> multi-agent summaries
  -> JSON/Markdown report
```

## Design Choice

Tetragon 수집 경로는 gRPC 대신 `파일 tail`을 선택했습니다.

이유:

- 현재 저장소에 이미 `exportFilename` 기반 문맥이 있음
- 테스트에서 로컬 재현이 쉬움
- Step 4 이전까지는 gRPC client 의존성을 늘릴 필요가 없음

## Run

저장소 루트에서 실행:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao phase3 \
  --baseline-tetragon samples/step2/baseline_tetragon.jsonl \
  --baseline-prometheus samples/step2/baseline_prometheus.json \
  --tetragon-log samples/step3/tetragon-live.log \
  --prometheus-url http://127.0.0.1:9090/metrics \
  --output-dir step3/output
```

## Verification

```bash
python3 -m unittest discover -s tests -v
```

Step 3에서 추가 검증한 항목:

- Tetragon log tail이 마지막 N줄만 읽음
- Prometheus text exposition을 HTTP로 scrape해서 파싱함
- live ingestion 입력이 기존 pipeline에 연결됨

## Limits

- Tetragon 파일 offset 저장은 아직 없음
- log rotation 대응은 아직 없음
- Prometheus scrape는 현재 단일 endpoint만 지원
- 다중 workload 리포트는 아직 대표 window 1개만 반환
