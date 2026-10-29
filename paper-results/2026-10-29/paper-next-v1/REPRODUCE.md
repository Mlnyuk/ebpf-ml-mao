# 재현과 독립 검토

패키지의 `rca/` 디렉터리에서 명령을 실행한다. 기본 구현은 Python 표준 라이브러리와 kubectl을 사용한다. 재생 화면에는 외부 JavaScript 라이브러리가 필요하지 않다. 새 API 실행은 재현 검토에 필요하지 않다.

## 기록 재생: API 호출 없음

```bash
python3 scripts/research_next.py serve \
  --source artifacts/paper-next-v1-20261029 \
  --output artifacts/paper-next-v1-20261029/viewer \
  --port 8765
```

`http://127.0.0.1:8765`에서 같은 사건의 방법별 결과·도구 호출·비용·원본 응답·수정 기록을 확인한다. 주장에 연결된 evidence ID를 누르면 증거를 확인할 수 있다. 원본 raw-export/summary-proof/capture 파일 링크는 이 서버를 통해 동작한다. `viewer/index.html`을 직접 열면 내장 기록은 보이지만 외부 원본 링크는 동작하지 않는다. 서버는 localhost에만 바인딩한다.

`--enable-live`를 추가하지 않는다. 해당 옵션은 별도 유료 탐색 실행을 위한 것으로 검토에 필요하지 않다. 완료된 실험에 API를 다시 호출하거나 기존 결과를 덮어쓰지 않는다.

## 독립 사람 채점

`viewer/review.html`을 검토자에게 제공한다. 방식 이름과 run 매핑은 이 화면 데이터에서 제거했으나 문체·증거량에서 방식을 추측할 가능성이 있으므로 완전한 맹검을 보장하지 않는다. 사람 검토용 정답은 화면에 포함되어 있고 Agent API 입력에는 포함되지 않았다. 작성자용 index 화면과 private/review-mapping.json은 맹검 채점 전에 검토자에게 보여주지 않는다.

목적지, 대상, 원인 유형, 시간·컨테이너 혼동, 보류 적절성은 각각 평가하고, 주장별 supported/contradicted/unsupported/unassessable 판정과 근거를 기록한다. 채점자 ID·독립 검토 확인·사유를 입력하고 JSON으로 내보낸다. 미응답 항목은 null/미평가로 유지한다. localStorage의 이전 채점을 덮어쓰지 않으며 export가 실제 제출 파일이다. 이 기능 시험에서 생성한 가상 입력은 실제 채점 결과로 저장하지 않았다.

기존 `scripts/paper_score.py --help`로 JSON 수집 형식을 확인할 수 있다. 다수 검토자가 있으면 합의 전에 각자의 원본 export를 보존하고, 불일치와 합의 절차를 별도 기록한다. 검토자 독립성은 확인 문구만으로 외부 검증된 것이 아니다. K8sGPT의 native 설명과 목적지 기준선의 의미 평가는 report의 별도 범위 및 원자료를 사용해야 하며, 주 비교의 구조화 출력 통과율과 합산하지 않는다.

## 데이터 구조와 무결성

- `protocol.json`, `freeze.json`: 수집 전 계획과 코드/설정 hash.
- `legacy-sha256.json`: 이전 paper-clock-v3 파일의 보존 확인값.
- `agent-cases/`: Agent가 읽는 사건·증거. small/wide 및 robustness는 독립 수집 횟수를 늘리지 않는다.
- `private/truth.json`: 주입 정답과 held-out 관측. Agent 입력과 분리.
- `private/<occurrence>/`: raw-export, summary-proof, 주소 매핑·시계·컨테이너 기록, K8sGPT native output/API 기록.
- `runs-main/`: 고정 실행 순서, 요청·응답·수정·최종 결과와 완료 기록.
- `report/`, `audit/`: 집계, 추적 검증, 비용 회계. 진단 품질은 미평가.
- `offline-summary-benchmark/`: 별도 후속 미세 측정 계획·60개 시간 측정 원본. 온라인 오버헤드가 아님.

번들의 MANIFEST.json으로 포함 파일의 SHA-256을 검증한다. freeze의 경로는 원래 rca 작업 디렉터리 기준이다. 전체 freeze 재검증에는 별도로 보존한 이전 paper-clock-v3 데이터와 K8sGPT 바이너리도 필요하다. K8sGPT 바이너리와 tarball은 패키지 크기를 줄이기 위해 제외했으며, 공식 v0.4.41 release의 Linux x86_64 asset을 다운로드해 checksums.txt와 freeze의 SHA-256에 대조해야 한다. 바이너리/소스 버전은 자동 최신화하지 않는다. 외부 소스의 라이선스는 audit/K8sGPT-LICENSE에 포함했다.

원본 실험 결과 디렉터리는 변경하지 않는다. 분석·시각화 재실행은 존재하지 않는 새 출력 경로를 사용한다. `scripts/audit_next.py`, `scripts/plot_research.py`, `scripts/benchmark_summary.py`는 평가 후 추가한 감사·그림·오프라인 측정 도구이며 고정된 Agent 정책을 수정하지 않는다. 그래프는 matplotlib 3.10.8로 생성했고 의존성 버전은 audit/plot-environment.json에 기록했다.

API 실행 시간은 고정 증거에 대한 controller/LLM 시간이며 수집·전처리를 포함한 온라인 종단 간 지연이 아니다. K8sGPT 시간은 live CLI 작업을 포함한다. prefix cache, 출력 언어/형식 차이와 단일 클러스터의 한계를 함께 보고한다.
