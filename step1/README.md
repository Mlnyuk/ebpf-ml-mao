# Step 1

Step 1 범위는 `이벤트 수집과 내부 스키마 확정`입니다.

이번 구현에서는 라이브 클러스터 연동 대신 오프라인 샘플 데이터를 사용해 아래 파이프라인을 먼저 고정했습니다.

```text
JSONL sample input
  -> normalize
  -> 30s window feature extraction
  -> baseline anomaly scoring
  -> multi-agent summaries
  -> JSON/Markdown report
```

## Implemented

- `app/ebpf_ml_mao/loader.py`
  - JSONL 샘플 이벤트 로더
- `app/ebpf_ml_mao/normalizer.py`
  - Tetragon/Prometheus 스타일 입력을 공통 스키마로 변환
- `app/ebpf_ml_mao/features.py`
  - 30초 윈도우 묶기 및 feature 추출
- `app/ebpf_ml_mao/scoring.py`
  - benign baseline 대비 거리 기반 anomaly score 계산
- `app/ebpf_ml_mao/agents.py`
  - `summarizer`, `analyst`, `correlator`, `reviewer` 요약 생성
- `app/ebpf_ml_mao/report.py`
  - JSON/Markdown 리포트 생성
- `app/ebpf_ml_mao/cli.py`
  - Phase 1 실행용 CLI

## Sample Data

- `samples/benign.jsonl`
- `samples/anomalous.jsonl`

두 파일 모두 동일 workload(`checkout`)를 기준으로 만들었고, anomalous 샘플에는 CPU 급등, 연결 증가, 반복 exec 이벤트를 넣었습니다.

## Run

저장소 루트에서 실행:

```bash
PYTHONPATH=app python3 -m ebpf_ml_mao phase1 \
  --baseline samples/benign.jsonl \
  --input samples/anomalous.jsonl \
  --output-dir step1/output
```

## Output

- `step1/output/report.json`
- `step1/output/report.md`

현재 샘플 기준 결과:

- verdict: `anomalous`
- score: `1.0`
- confidence: `1.0`

## Verification

```bash
python3 -m unittest discover -s tests -v
```

검증된 항목:

- 정규화 필수 필드 채움
- anomalous 샘플이 anomaly로 판정됨
- JSON/Markdown 리포트 생성됨

## Limits

- 실제 Tetragon stream 구독은 아직 없음
- Prometheus scrape 연동은 아직 없음
- 모델은 통계 기반 baseline scorer로 단순화됨
- 학습/추론 분리 저장은 아직 없음

## Next Step

- Tetragon raw event adapter 추가
- Prometheus metric snapshot adapter 추가
- workload/window별 복수 리포트 지원
- baseline 학습 결과 저장 및 재사용
