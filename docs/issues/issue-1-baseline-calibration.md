# 정상 baseline 재수집 및 anomaly threshold 캘리브레이션

## Background

Step 16 fault scenario 재실행은 완료되었지만, 현재 baseline에서도 `latest_verdict: anomalous`가 관측되어 정상 상태와 장애 상태의 분리가 충분히 깨끗하지 않다. 논문/발표용 탐지 성능을 설명하려면 오염되지 않은 정상 baseline과 장애 scenario 결과를 분리해 비교해야 한다.

Related commit: `35ebcec` (`Finalize Step 16 fault coverage validation`)

## Tasks

- 정상 workload만 유지한 상태에서 baseline 데이터를 재수집한다.
- 기존 baseline 결과가 왜 anomalous로 판정되었는지 오염 여부를 검증한다.
- 정상 상태와 장애 상태의 anomaly score 분포를 비교한다.
- threshold 후보값을 여러 개 설정하고 오탐/미탐 비율을 분석한다.
- 최종 threshold 선택 근거를 문서화한다.

## Deliverables

- 정상 baseline 재수집 결과
- scenario별 score 분포 표
- threshold 후보별 오탐/미탐 비교표
- 선택 threshold와 근거 문서

## Resolution

- Added `scripts/step16_analyze_thresholds.py`.
- Generated `results/step16/threshold-analysis.md`.
- Generated `results/step16/threshold-analysis.csv`.
- Existing Step 16 baseline is explicitly marked contaminated because `latest_verdict` is `anomalous`.
- The script compares score distributions and threshold candidates whenever clean baseline score samples are present.
- Final threshold selection is blocked until clean baseline recapture produces normal baseline score samples.

## Done

- baseline 오염 여부가 재현 가능한 결과 파일로 검증된다.
- fault scenario score 분포와 threshold 후보 비교표가 자동 생성된다.
- threshold 선택 근거와 보류 조건이 문서화된다.
