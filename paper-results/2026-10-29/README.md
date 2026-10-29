# Selective Telemetry RCA

이미 발생한 Kubernetes 장애를 외부 LLM이 읽기 전용 도구로 조사하는 MVP다.
이 디렉터리는 상위 저장소의 ML 이상탐지 구현과 독립적이다. 모델 학습,
이상치 분류, 로컬 LLM, GPU, 장애별 RCA 규칙을 사용하지 않는다.

## 빠른 시작: API 키 입력

현재 클러스터에는 배포와 실제 telemetry 연결까지 준비한다. 기존 코드나
manifest에 키를 넣지 않는다. 다음 명령은 숨김 입력을 받고 Kubernetes Secret을 생성한다.
현재 제공자는 **OpenRouter**, 모델은 `z-ai/glm-5.3-flash`다. OpenRouter에서 발급한 키를 입력한다.

```bash
cd /root/Capstone/rca
python3 scripts/rcactl.py set-key
python3 scripts/rcactl.py health
```

Secret 볼륨 갱신 후 `llm_configured: true`가 된다. 보통 1~2분 정도 기다려야
할 수 있다. 서버 재배포는 필요 없다. 키 설치 명령 자체는 유료 API를 호출하지 않는다.
키 설정과 유료 호출 활성화는 별개다. 새 코드/manifest는 `LLM_ENABLED=false`가
기본이므로 키가 있어도 API를 호출하지 않는다. 명시적으로 활성화한 뒤에만 새 장애를
자동 조사한다. 기존 `paused`/`awaiting_api_key` 사건은 일괄 실행하지 않는다.
`health`의 `llm_configured`는 키 존재 여부, `llm_enabled`는 유료 호출 허용 여부다.
Agent 자체가 0 replicas이면 health/CLI도 동작하지 않는다.

유료 동작을 승인한 운영자가 새 코드를 배포한 뒤 활성화하는 명령:

```bash
kubectl -n rca-system set env deployment/rca-agent LLM_ENABLED=true
kubectl -n rca-system scale deployment/rca-agent --replicas=1
```

호출만 차단하고 수집 서버를 유지하려면 `LLM_ENABLED=false`로 변경한다.
완전히 중지하려면 deployment를 0 replicas로 축소한다. 이 문서의 명령은
사용자가 실행해야 하며, 오프라인 평가가 Agent를 자동으로 켜지는 않는다.

```bash
python3 scripts/rcactl.py list
python3 scripts/rcactl.py show INCIDENT_ID
python3 scripts/rcactl.py evidence INCIDENT_ID
python3 scripts/rcactl.py inspect INCIDENT_ID  # 과거 사건 기준 telemetry 검증; LLM 호출 없음
python3 scripts/rcactl.py run INCIDENT_ID
```

`python3 scripts/verify_llm.py`는 `verify_live.py --faults`에서 저장한 실제 장애
최대 3건을 외부 API로 재분석한다(유료 호출). 새 장애는 만들지 않으며 첫 실행 오류에서
중단한다. 결과와 usage는 `artifacts/llm-verification.json`에 저장한다.
이 검사는 연결·도구 호출·출력 프로토콜 검증이며 진단의 의미상 정확도는 별도 검토한다.

호출 비활성화 상태의 새 사건은 `paused`, 활성화했지만 키가 없으면 `awaiting_api_key`다.
둘 다 새 RCA 결과는 `null`이다.
가짜 진단을 생성하지 않는다. 오래된 사건은 Prometheus 보존 기간이나 로그 수명 때문에
증거가 부족할 수 있다. 실제 비용과 진단 정확도는 API 키 연결 후 검증해야 한다.

## 구성과 데이터 흐름

- `rca-system`: worker-3의 Agent 1개, worker-1·3의 eBPF summary DaemonSet.
- `rca-lab`: worker-1의 sample-service, worker-3의 sample-backend.
- 기존 Prometheus/Alertmanager 및 Tetragon을 활용한다.
- Pod 재시작/초기 CrashLoop 상태를 읽는 Incident poller와 Alertmanager webhook.
- LLM이 다섯 도구 중 필요한 것을 선택하고 `submit_rca`로 조사 종료.
- `get_workload_status`, `get_k8s_events`, `get_logs`, `get_metrics`, `get_ebpf_summary`.
- 결과는 종료 메커니즘과 근본 원인을 구분하며, 실제 조회한 evidence ID만 참조 가능하다.
- `confidence`는 모델의 정성 평가이며 보정된 확률이 아니다.

Pod 상태·이벤트·제한된 로그는 사건 발생 시 별도 저장한다. eBPF는 상시 수집하고
10초 단위로 집계해 최근 10분을 보관하며 사건 시 관련 구간을 보존한다.
Prometheus의 과거 시계열은 모델이 요청할 때 조회한다. 저장된 증거를 모두 프롬프트에
넣지는 않는다. 초기 프롬프트에는 Incident만 전달한다.

조회 구간은 호출 시각이 아니라 사건 발생 시각 기준이다. 로그와 eBPF는 Pod UID와
container ID를 대조한다. cAdvisor 시계열도 Pod UID와 container ID가 포함된
`id` 라벨로 제한하므로 다른 재시작 인스턴스의 값을 합치지 않는다.

## 키 없이 검증 / 장애 실험

```bash
python3 scripts/rcactl.py traffic       # 30회, 약 1초 간격의 요청; 오류도 출력하고 계속 실행
python3 scripts/rcactl.py preflight     # 모든 telemetry 도구 조회; LLM 호출 없음
python3 scripts/rcactl.py fault crash   # 실험 컨테이너만 exit 42, 자동 재시작
python3 scripts/rcactl.py fault memory  # 128Mi 제한 안에서 메모리 증가 → OOM
python3 scripts/rcactl.py fault cpu     # 500m 제한 안에서 45초 연산
python3 scripts/rcactl.py incident      # 현재 sample-service에 수동 조사 사건 등록
```

fault 명령은 `rca-lab` sample-service의 localhost 전용 fault endpoint만 호출한다.
호스트 네트워크/메모리를 조작하지 않는다. 명령 실행 이력은 로컬
`artifacts/experiments.jsonl`에 기록하며 Agent에는 이 정답 파일을 전달하지 않는다.
CPU는 Prometheus의 기존 detection 계층에 추가한 실험 전용 throttling 알림으로
trigger된다. 알림 규칙은 탐지 조건일 뿐 RCA 판단 규칙은 아니다.

## 기본 비용·실행 제한

- 모델: OpenRouter `z-ai/glm-5.3-flash`, reasoning effort `low`, reasoning 응답 제외.
- API: `https://openrouter.ai/api/v1/chat/completions`; 도구 등 요청 파라미터 지원 provider로 제한.
- 최대 LLM 요청 6회, telemetry 도구 실행 시도 8회.
- 요청별 출력 상한 4,096 tokens, 조사 시간 예산 240초, 요청 timeout 최대 60초.
- 현재 실행 중인 도구의 네트워크 timeout 때문에 전체 종료는 시간 예산을 조금 초과할 수 있다.
- 하루 실행 시도 20회; 실패/재시도도 포함한다. 서버 내부 단일 조사 worker로 직렬 처리한다.
- 요청 본문(메시지 + tool schema 포함) 제한 65,000 characters, 조사 누적 본문 제한 120,000 characters.
  토큰·달러 한도와 동일하지 않으며 다음 API 요청 전에 검사한다.
- 과금은 각 API 응답의 usage를 합산해 추정한다. 캐시 입력을 구분한다.
- OpenRouter가 반환하는 `usage.cost` 합계를 `provider_reported_cost_usd`로 별도 기록한다.
  고정 단가 추정치와 구분하며 크레딧 구매 수수료 등은 포함하지 않는다.
- 응답 누락/실패로 비용을 확정할 수 없으면 `usage_complete: false`, 비용은 `null`이다.
- 예산 초과·잘못된 JSON·허구의 증거 ID는 정상 RCA로 통과하지 않는다.

가격 초기값은 입력 $0.15 / 캐시 입력 $0.03 / 출력 $0.50 per 1M tokens이며
환경변수로 변경 가능하다. 추론 토큰 세부 내역은 제공자의 원본 usage trace에 보존한다.
각 run에는 모델, 프롬프트 버전, 호출 내역, 토큰, 시간, 오류를 저장한다.
모델의 reasoning_content 및 API 키는 실행 기록에 저장하지 않는다.

## 효율 개선 및 재현 평가 (v3)

2026-10-16 연구 실험에서는 집계기와 실험 서비스만 갱신했다. 운영 Agent는 계속
0 replicas다. 실제 모델 평가는 별도 프로세스가 고정 증거를 읽어 제한된 횟수만
호출하며, 운영 incident queue나 자동 조사를 활성화하지 않는다.

- `RCA_CONTEXT_MODE=legacy`: 이전 v2 프롬프트 + 전체 tool 대화 재전송.
- `RCA_CONTEXT_MODE=full`: v3 프롬프트 + 조회한 원본 증거 ledger.
- `RCA_CONTEXT_MODE=compact`: **같은 v3 프롬프트** + 기존 무손실 압축 증거 ledger.
- `RCA_CONTEXT_MODE=compact-v4`(현재 기본): 아래 v4 개선 버전. 과거 v3 실험과 구분한다.
- ledger는 이미 조회한 모든 증거를 ID별 한 번씩 포함한다. 이전 증거가 다음 요청에서도
  재전송되는 점은 동일하며, 서버 측 대화 캐시나 완전한 중복 전송 제거가 아니다.
- 로그의 반복 형식과 숫자 열을 분리하고, 메트릭의 공통 시간 축을 공유한다.
  샘플/로그 행을 삭제하거나 이상 판별 규칙으로 선별하지 않는다. 원본은 계속 저장한다.
- `ALLOW_EBPF=false`는 도구 목록뿐 아니라 실행 단계에서도 eBPF 호출을 차단해 ablation을 지원한다.
- 요청별 본문 크기, 실제 조회 인자, evidence ID, 응답의 provider 식별자, 실제 전송한 요청을 보존한다.

API 없이 같은 데이터·같은 6개 조회·4회 요청을 가정하여 본문 크기와 복원성을 비교:

```bash
python3 scripts/benchmark_context.py --output artifacts/context-benchmark-new.json
```

`context-benchmark.json` 초기 결과: 기존 대비 누적 UTF-8 요청 바이트 19.08% 감소,
같은 v3 프롬프트의 full 대비 compact 11.78% 감소. 3건의 모든 증거가 원본으로 정확히
복원됐다. **이 결과는 모델 토큰 절감·정확도 개선·eBPF 효용의 증명이 아니다.**
실제 LLM의 선택이나 압축 해석 능력은 이 오프라인 고정 조회 실험에 포함되지 않는다.

고정된 과거 증거를 사용하는 실제 모델 비교 실험 계획(기본은 API 미호출):

```bash
python3 scripts/evaluate_frozen.py
python3 scripts/evaluate_frozen.py --arms full compact compact-no-ebpf --repeats 3 --max-api-calls 60
```

기본 계획은 3개 사건 × full/compact 2개 방식 × 1회 = 6개 조사, 전체 최대 36 API 요청이다.
유료 실행은 승인한 범위에서 `--execute --key-file /보호된/키파일` 또는
`--execute --cluster-key`를 명시해야 한다. 후자는 기존 Secret을 읽어 임시 0600
키 파일로 사용하고 종료 시 제거한다.
키 내용 자체를 인자나 코드에 적지 않는다. 운영 Agent/SQLite를 사용하지 않아 자동 조사를
재개하지 않으며, live telemetry fallback도 없다. 정확한 조회 구간이 저장되어 있지 않으면
unavailable로 반환한다. 응답 오류 시 다음 조사를 중단하고 부분 결과를 보존한다.

실험 순서는 seed로 섞으며 seed는 **실행 순서용**이지 모델 출력 결정성을 보장하지 않는다.
데이터·코드 SHA256, 실제 토큰/비용/시간 및 요청 원문을 별도 결과 디렉터리에 저장한다.
한 번의 paired 실행은 smoke test다. 반복 평가에서 원인·근거의 정확도를 arm을 가린 상태로
별도 채점해야 하며 `completed` 상태를 정답으로 계산하지 않는다. API 호출 횟수 제한은
달러 한도가 아니므로 provider의 실제 요금·키 사용 한도도 실행 전에 확인해야 한다.

### 실제 네트워크 장애 대조 실험

`artifacts/study-20261015/protocol.json`에 새 장애 수집 전 실험 조건을 기록했다.
잘못된 포트 / 잘못된 목적지 IP의 두 종류를 각각 새 Pod에서 3회 발생시키고,
각 사건의 같은 증거로 full / compact / compact-no-ebpf를 비교한다.
원인은 주입 기록으로 별도 보관하며 모델 입력에는 포함하지 않는다.

- 앱 로그는 의도적으로 동일한 `dependency request failed`만 남긴다. **불투명한 로그라는
  eBPF에 유리한 조건**이며 상세 오류 로그가 있는 모든 서비스에 일반화하지 않는다.
- 예상 의존성 IP/포트는 동일한 Pod annotation으로 모든 arm에 제공한다.
- `network-fixture.json`: 실제 수집 데이터, 주입 기록, 부하 결과, 집계기 자원 측정.
- `network-heldout-v3/`: 수집 전 고정한 v3 정책의 세 가지 arm, 요청 원문과 usage.
- `development-v3/`: 이전 OOM/crash/CPU 개발 데이터. 새로운 검증 데이터와 혼합하지 않는다.
- `network-fixed-v3/`: 별도 **탐색적 대조군**. 제한된 증거 6개를 한 번에 전달한다.
  raw 전체 덤프가 아니며 작은 사건에서는 이 방식이 더 저렴할 수 있다.
- `summary.json`, `runs.csv`: arm별 실제 토큰·비용·시간과 사건별 차이.
- `review-packet.json`: arm 이름을 숨긴 사람 검토 자료. 누락된 eBPF 등으로 arm을
  추측할 수 있으므로 완벽한 맹검은 아니다. 대응표는 `review-mapping-private.json`에 분리.
- `assistant-review.json`: 구현자의 예비 검토일 뿐 독립된 사람 평가가 아니다.

모든 유료 실험은 동일한 `budget.json`을 사용해 총 100 API 시도 / 보수적 $1 예산을
공유한다. 요청 전에 UTF-8 크기로 비용을 넉넉히 예약하고 알려진 실제 비용으로 정산한다.
응답/비용이 없으면 예약액을 유지한다. 토크나이저나 제공자의 청구 상한 보장은 아니며,
제공자 단가 상한과 고정 routing(`z-ai/fp8`, fallback 금지)도 적용한다.
예산 파일에는 프로세스 간 잠금이 없으므로 **공유 예산 runner를 동시에 실행하면 안 된다.**

아래는 결과 재집계만 수행하며 API를 호출하지 않는다.

```bash
python3 scripts/summarize_study.py --study artifacts/study-20261015
```

실험 데이터 수집은 `scripts/capture_network_study.py`, 개별 평가 계획은
`scripts/evaluate_frozen.py`, 고정 6개 증거 대조군은 `scripts/evaluate_fixed.py`다.
수집 스크립트는 실제 lab 장애와 재배포를 포함하므로 단순 조회 도구가 아니다.
정확도는 `completed` 비율이 아니라 **증거가 뒷받침하는 목적지 불일치 식별**과
**근거/인과관계의 오류**를 구분해서 평가한다. 2개 장애 종류 × 3회는 제한된 pilot이며
통계적 유의성·일반적 Kubernetes 정확도·신뢰도 보정을 입증하지 않는다.

2026-10-16 완료 결과(각 방식 6건, 조사 전체 입력+출력 토큰 평균):

| 방식 | 토큰/건 | 목적지 불일치 식별* |
|---|---:|---:|
| 선택 조회, 원본 형식, eBPF 포함 | 13,335 | 6/6 |
| 선택 조회, 무손실 압축, eBPF 포함 | 9,948 | 6/6 |
| 선택 조회, 무손실 압축, eBPF 제외 | 11,140 | 0/6 |
| 고정 6개 요약, 원본 형식, 1회 호출 | 6,973 | 6/6 |
| 고정 6개 요약, 무손실 압축, 1회 호출 | 6,343 | 6/6 |

\* 구현자의 예비 검토로, **답변 전체의 정확도 100%라는 뜻이 아니다.** 원인을 식별한
답에도 readiness/저샘플 메트릭으로 다른 원인을 배제하거나 오래된 DNS를 추정하는 문제가
남았다. `assistant-review.json`에 개별 오류를 보존했다. 독립 평가 전 확정 정확도로 쓰지 않는다.

선택 조회 full→compact는 누적 토큰 25.4% 감소했지만 조회 계획도 달라져 순수 압축
기여로 분해할 수 없다. 동일한 고정 6개 증거를 사용하는 일괄 방식은 입력 토큰 약 10.0%,
입력+출력 약 9.0% 감소했다. **작은 bounded evidence에서는 일괄 압축이 선택 압축보다
총 토큰 36.2% 적었다.** 선택 조회 자체의 비용 우위는 이번 실험에서 입증되지 않았다.
원본 선택 대비 압축 선택의 평균 응답 시간도 28.4→32.7초로 증가했으므로 지연 개선으로
표현하지 않는다. API 캐시/시간 변동이 있어 비용·지연을 토큰과 별도로 해석한다.

집계기 PID 측정은 부하 중 CPU 1.72~2.89 millicores, RSS 25.3MiB였다.
부하는 30초당 30/40/60건으로 작으며, 집계 전 export JSON 대비 eBPF 응답 바이트는
99.75~99.87% 줄었다. 이는 **기존 exporter 이후 집계기의 footprint와 lossy 요약 비율**이며
전체 eBPF 오버헤드, 대규모 처리 성능 또는 raw 대비 LLM 토큰 절감률이 아니다.
개발 검증까지 합계 36개 조사 / 76 API 요청 / 제공자 보고 $0.05019681로 종료했다.
운영 Agent는 0 replicas, 실험 서비스 HTTP 200 복구를 확인했다.

## v4 구현 및 비용 없는 개발 검증

기존 `legacy`/`full`/`compact`의 프롬프트·인코딩·출력 필드는 유지하며,
새 기본 `compact-v4`와 동일 정책의 비압축 대조군 `full-v4`를 추가했다.
기존 `study-20261015` 데이터·실험 결과는 수정하지 않는다. 이제 이 데이터는
v4 개선에 사용한 **개발 데이터**이며 v4의 독립 검증/held-out 자료로 부르면 안 된다.

- `indexed-template-columns-v2`: 번갈아 나타나는 로그 형식도 공유한다. `order`는
  template 인덱스이며, 각 template이 다시 나올 때 그 template의 다음 행을 사용한다.
  타임스탬프/숫자는 문자열 그대로 보존한다. 순서·행 삭제·반올림·의미 기반 필터링 없음.
  기존 v1/raw 표현이 더 작으면 그대로 사용한다.
- 조회가 끝난 단일 스냅샷 도구(status/events/logs)의 schema는 이후 요청에서 제외한다.
  증거 자체는 모두 유지하고, 메트릭/eBPF의 다른 window 조회는 계속 허용한다.
  추가 조회 여부와 도구 선택은 LLM이 결정한다. 자동 전체 수집이나 장애별 판단 규칙 없음.
- 독립적인 유용한 조회를 같은 응답에 묶도록 지시한다. 호출 횟수 감소는 아직 실측하지 않았다.
- 누적 context 예산에 걸릴 때, 이미 증거가 있다면 **증거 삭제 없이** 최종 제출 도구만
  제공하는 요청이 예산에 들어가는지 먼저 검사한다. 그래도 넘으면 호출하지 않는다.
- v4 출력은 `root_cause_status: observed|hypothesis|undetermined`와 인용별
  `claim_type: observation|inference`를 추가한다. 원인 미확정은 `root_cause=null`,
  confidence는 high 금지. 이는 **형식·일관성 검증이지 의미상 진실성 검증이 아니다.**
  Ready/저샘플 사용량/entry probe로 과도한 결론을 내리지 않도록 지시했으나 실제 개선은
  별도 모델 평가가 필요하다. 기존 결과 소비자는 새 필드를 허용해야 한다.

같은 6개 조회·4회 요청으로 비교한 누적 UTF-8 요청 바이트:

| 개발 데이터 | v3 compact | v4 compact | 감소 |
|---|---:|---:|---:|
| 네트워크 6건 | 274,413 | 221,111 | 19.42% |
| OOM/Crash/CPU 3건 | 100,045 | 98,794 | 1.25% |

모든 증거의 원문 복원이 일치했다. 이 값은 **토큰/비용/정확도 개선률이 아니다.**
모델 선택 없이 고정한 계획이므로 실제 호출 수나 진단 품질도 측정하지 않는다.
초기 긴 지시문에서는 작은 3건의 본문이 5.87% 증가했다. 그 중간 결과도 보존하고,
지시문을 축약한 최종 결과와 구분했다. eBPF collector/probe에는 변경이 없으며,
인코딩은 조회 시 Agent에서 수행한다. 새 Agent CPU/RSS의 실측 비교는 아직 없다.

```bash
python3 scripts/benchmark_context.py --fixture artifacts/study-20261015/network-fixture.json \
  --arms compact full-v4 compact-v4 --output artifacts/v4-development/new-network-check.json
python3 scripts/evaluate_frozen.py --arms full-v4 compact-v4 compact-v4-no-ebpf
```

첫 명령은 로컬 본문 크기 비교, 두 번째는 **계획 출력만** 한다. 유료 실행은 `--execute`와
키 경로를 명시해야 한다. 이번 v4 구현에서는 실제 외부 모델 호출을 하지 않았다.
결과는 `artifacts/v4-development/*-fixed-plan-final.json`, 새 테스트는 `tests/test_v4.py`다.

중지 상태를 유지한 Agent 코드 준비:

```bash
python3 scripts/stage_agent.py                 # 로컬 계획만, 클러스터 접근 없음
python3 scripts/stage_agent.py --execute       # 중지 상태에서만 코드 준비
```

이 스크립트는 별도 immutable ConfigMap에 코드 버전을 보관하고 Agent의 마운트만
변경한다. `replicas=0`을 전제하며 `LLM_ENABLED=false`로 유지한다. resourceVersion을
검사하므로 동시 운영자 변경을 덮어쓰지 않는다. 기존 ConfigMap은 삭제하지 않는다.
Collector/실험 서비스 재시작, Secret 읽기, 새 probe 로드, GPU 변경은 하지 않는다.
이는 **코드 준비**이지 실행 중 v4의 실환경 검증이나 자동 조사 재개가 아니다.
범용 `rcactl.py deploy`는 이 제한적 코드 준비 명령과 달리 전체 구성에 적용하므로 주의한다.

## 새 v4 검증: 최초 중단 기록 (이후 재개 결과는 아래)

`artifacts/v4-validation/protocol.json`을 새 수집 전에 작성했다. 포트/IP 오류 ×
불투명/목적지 포함 로그 × 두 부하 조건으로 **새 Pod 8개의 사건**을 수집했다.
처음에는 수집 스크립트의 반복문 변수 충돌로 저장 전 중단했다. 실패 파일을 보존하고
수집 코드만 수정한 후 `confirmed/`에 8건을 다시 수집했다. RCA 정책은 변경하지 않았다.

v3 선택 / v4 선택 / v4 eBPF 제외 / v4 압축 일괄의 32개 조사를 계획했으나,
첫 사건의 일괄 방식에서 모델 답변이 v4의 원인 미확정·null·신뢰도 일관성 검증에
실패했다. **사전 규칙대로 4개 조사에서 중단했고 재시도하지 않았다.** 3개는 유효 출력,
1개는 출력 계약 오류다. 오류 시 대체한 inconclusive 결과를 모델의 적절한 판단 유보로
세면 안 된다. 원래 잘못된 함수 인자는 보존되지 않아 어떤 값 조합이었는지 복원할 수 없다.

첫 한 사건에서 v3/v4 선택 조회의 총 토큰은 12,138/10,176이었지만,
제공자 비용은 $0.00147827/$0.0019338로 v4가 높았다. 캐시 입력은 5,184/0,
출력 토큰은 799/1,164로 달랐다. **한 사건으로 절감·정확도 개선을 결론 내릴 수 없다.**
v4에도 관측 구간 과장·과도한 자원 원인 배제 등의 근거 문제가 남았다.

- `confirmed/network-fixture.json`: 새 사건 8건, 이후 평가용으로 보존.
- `confirmed/evaluation/results.json`: 성공과 실패를 포함한 부분 평가.
- `confirmed/summary.json`, `runs.csv`: 불완전 평가임을 명시한 집계.
- `confirmed/assistant-review.json`: 구현자 예비 검토; 독립 평가가 아니다.
- `confirmed/review-packet.json`: arm 이름과 버전 전용 출력 필드를 가린 검토 자료.
- `confirmed/verification.json`: 중단 이유·복구 상태·비용 기록.

총 10 API 시도, 제공자 보고 비용 $0.005957로 종료했다. Agent는 0 replicas이고
실험 서비스의 `/work` HTTP 200 및 backend 200 복구를 확인했다.
오버헤드 ON/OFF 실험은 이번 단계에서 수행하지 않았다.

이 시점의 기록과 파일은 보존했다. 아래의 재개에서도 실패를 지우거나 같은 조사를
성공할 때까지 재실행하지 않았다.

## v4 검증 완료: 32개 조사, 기존 실패 포함

사용자 승인 후 출력 계약 실패만 기록하고 진행하도록 실행 중단 정책을 변경했다.
`continuation-evaluation/`에서 21건을 추가 실행한 뒤, eBPF 제외 방식이 사건당 6회
호출 안에 유효한 출력을 제출하지 못해 누적 25건에서 중단했다. 다시 승인받아
`final-evaluation/`에서 **남은 7건만** 실행했다. 사건당 호출 제한, 원래 실행 순서,
RCA 코드·모델·프롬프트·데이터·전역 100회/$1 한도는 변경하지 않았다.

최종 **32건 / API 90회 / 반환된 usage 비용 $0.05598982**다. 오류가 난 조사 비용도
포함한다. 마지막 7건의 실제 실행은 **5분 28초**, 추가 비용은 **$0.01185552**였다.
32건은 모두 시도했다는 뜻이며, 29건은 출력 계약 통과, 3건은 실행 실패다.

| 방식 | 목적지·포트 특정(예비 검토) | 실행 실패 | 평균 총 토큰 | 전체 호출 수 |
|---|---:|---:|---:|---:|
| v3 선택 조회 | 8/8 | 0 | 10,752 | 22 |
| v4 선택 조회 | 8/8 | 0 | 12,048 | 28 |
| v4, eBPF 제외 | 4/8 | 1 | 13,992 | 32 |
| v4 압축 일괄 조회 | 6/8 | 2 | 5,040 | 8 |

이는 **구현자의 비독립·비블라인드 목적지 특정 예비 채점**이며, 일반적인 RCA 정확도나
모든 문장의 사실성을 뜻하지 않는다. 형식 오류 대체 결과는 모델의 판단 유보로 세지 않는다.
평균 토큰은 실패를 포함한 각 방식 8건의 모든 반환 호출을 합산한 값이다.

- 목적지가 없는 로그 4건: v4+eBPF는 4/4, eBPF 제외는 0/4 특정했다.
- 목적지가 있는 로그 4건: eBPF를 제외해도 4/4 특정했다. eBPF의 가치는 로그 정보량에
  따라 달라지는 추가 증거이지 항상 필요한 입력이라는 결론이 아니다.
- **v4는 v3보다 총 토큰이 12.05% 증가했다.** 이번 실험은 저토큰 개선 성공이 아니다.
  압축 일괄 방식은 가장 적은 토큰을 썼지만 출력 계약 오류가 2건 있었다.
- eBPF 제외 case 6의 반환 응답에는 JSON null 대신 문자열 `"null"`이 4번 반복됐다.
  v4 case 7도 같은 오류가 한 번 나타나고 추가 조회 후 유효 출력에 도달했다.
  fixed case 2는 undetermined 상태에 원인 설명 문자열을 함께 제출했다.
  첫 fixed case 0의 원본 잘못된 인자는 보존되지 않아 동일 원인으로 단정하지 않는다.
- 8개 사건은 두 알려진 장애 유형의 반복 사례다. 통계적 우월성·비열등성이나
  전체 장애군 정확도를 주장할 수 없다. **오버헤드 ON/OFF 비교는 아직 수행하지 않았다.**

최종 자료는 모두 `artifacts/v4-validation/confirmed/` 아래에 있다.

- `final-evaluation/combined-results.json`: 최초 25건과 마지막 7건을 합친 결과.
- `final-evaluation/verification.json`: 원본·코드·데이터 해시, 순서, 중복 없음, 호출 예산 검증.
- `final-summary/summary.json`, `runs.csv`: 조건별 토큰·비용·실패 및 예비 목적지 특정 집계.
- `endpoint-review.json`: 목적지 특정만 채점한 예비 검토. 문장별 근거 충실성은 별도다.
- `final-summary/review-packet.json`: 독립 검토자에게 전달할 arm 이름 마스킹 자료.

운영 Agent는 확인 시점에도 **0 replicas / LLM_ENABLED=false**다. 평가 프로세스는
종료했고, 별도의 자동 재실행은 등록하지 않았다. 다음 개선은 null/가설 상태의 출력
계약 호환성과 불필요한 추가 조회를 우선 검토하되, 이번 데이터는 이후 개발 데이터로
취급하고 변경 효과는 별도의 새 평가에서 확인해야 한다.

## 논문 평가용 별도 구현 (2026-10-29)

`research/`는 운영 Agent와 분리한 평가 구현이다. 기존 8개 사건·32개 조사 및 실패 기록은
개발·회귀 자료로 보존하며 새 결과와 합산하지 않는다. 운영 Agent를 켜거나 정기 실행을
등록하지 않는다. 아래 파일의 상태를 읽어 완료 여부를 확인한다. 실행 명령을 다시 호출해
실패한 조사를 성공할 때까지 반복하는 용도로 사용하지 않는다.

현재 새 평가 캡슐은 `artifacts/paper-clock-v3-20261029/`다.

- `protocol.json`, `freeze.json`, `capture-freeze.json`: 수집 전 고정한 계획과 코드 해시.
- `analysis-freeze.json`: 유료 조사 전 고정한 추가 감사·패키징 코드 해시.
- `clock-source-preflight.json`: 같은 노드 시계 구간, 원본 재집계, Prometheus 시각 변환 오차 확인.
- `agent-cases/`: Agent에 제공 가능한 사건·증거만 포함한다.
- `private/truth.json`, `private/ground-truth-table.csv`: 평가 전용 정답. 후자는 보고서 단계에 생성된다.
- `private/<case>/raw-export.json`, `summary-proof.json`, `clocks.json`: 원본 바이트·파일 위치,
  이벤트 해시, 포함/제외 근거, 시계 구간. 원본 → 요약 → evidence ID → 주장 추적에 사용한다.
- `runs-all/*.jsonl`: 호출 전 요청과 호출 후 공개 응답을 즉시 보존한다. 키와 비공개 추론은 저장하지 않는다.
- `runs-all/completion.json`: `complete: true`일 때만 계획한 조사가 모두 종료된 것이다.
  출력 오류도 결과이며, 종료 자체가 진단 성공을 뜻하지 않는다.
- `report/`, `paid-accounting.json`, `overhead.json`, `paper-status.html`, `delivery-status.json`:
  실행 종료 후 만드는 결과와 한계. 파일이 없으면 그 산출물이 아직 생성되지 않은 것이다.

실제 독립 수집은 포트 오류·목적지 오류·정상 각각 2회로 총 6회다. 과거 사건 혼입·eBPF
수집 누락·전체 증거 부족 3건은 동일 원본에서 만든 **종속 변형**이다. 네 주 비교군은
압축 일괄/eBPF 제외·포함, 선택 조회/eBPF 제외·포함이다. 같은 원본, 모델·제공자,
출력 계약, 1회 수정 정책을 적용한다. 압축·중복 방지·종료 안내를 각각 제거한 3개
추가 비교군도 둔다. 사건별 각 2회 LLM 반복으로 주 비교 72건, 추가 비교 54건이다.
반복 실행을 독립 장애 발생으로 세지 않는다. 6건의 작은 파일럿이므로 통계적 우월성을
주장하지 않는다. 단순 목적지 불일치 기준선은 오프라인 비교용이며 Agent 판단에 넣지 않는다.

출력은 확정 원인·잠정 가설·미확인 정보를 분리하고 원자적 주장마다 조회한 evidence ID를
요구한다. 원문, JSON fence 제거 여부, 수정 요청/응답, 최종 실패를 보존한다.
현재 고정 endpoint의 구조화 출력 강제 지원은 검증되지 않았다. 메타데이터의
`response_format` 표기만으로 strict JSON Schema 보장을 주장하지 않으며, 별도 strict
요청이 HTTP 404로 실패한 기록도 남겼다. 따라서 모든 비교군에 동일한 도구 스키마와
로컬 검증을 적용하고 형식 통과율을 따로 보고한다.

목적지, 대상, 원인 유형, 주장별 근거 충실성, 시간·컨테이너 혼동, 판단 보류는 별도로
채점한다. `report/independent-review-packet.json`은 방식 이름을 가린 자료지만 증거
구성으로 방식이 추정될 수 있어 완전한 맹검이라고 부르지 않는다. 실제 독립 검토자
2인의 채점 전에는 진단 품질이 `NOT_PERFORMED`다. 정답과 방식 매핑은 `private/`에
분리하며, 이는 논리적 분리이지 적대적 프로세스에 대한 OS 보안 경계는 아니다.

```bash
# 보존된 실행의 특정 주장 역추적; 실제 run ID로 바꾼다.
python3 scripts/paper_trace.py --study artifacts/paper-clock-v3-20261029 --run-id RUN_ID --claim 0
# 실제 독립 검토자가 작성한 JSON만 입력한다. 빈 파일로 결과를 만들지 않는다.
python3 scripts/paper_score.py --study artifacts/paper-clock-v3-20261029 --ratings ratings.json --output human-review-v1
```

Tetragon 증거는 연결 **시도**의 주소·포트·횟수뿐이다. 정상 목적지는 실험의 선언된
의존성 계약과 Service/EndpointSlice 스냅샷에서 얻으며 Service VIP와 실제 Pod 주소를
구분한다. 미조회, 관측 0건, 수집 실패를 구분하고 연결 성공·실패나 DNS 원인을 추정하지
않는다. 원본 export 재구성 일치는 커널/export 이전 손실이 없다는 뜻이 아니다.

전체 입력·출력·수정 호출 토큰은 제공자 usage에서 집계한다. 새 증거·반복 증거의
기여는 UTF-8 바이트 기준 보조 지표이며 정확한 부분별 토큰으로 바꿔 부르지 않는다.
독립 품질 채점이 없으면 토큰 감소와 품질 유지가 함께 입증됐다고 결론 내리지 않는다.
Tetragon 기본·관측 정책·온라인 요약기 추가 비용은 공유 클러스터에서 안전한 ON/OFF
대조가 없어 `NOT_MEASURED`다. 오프라인 요약 재생 CPU/RSS 측정과 구별한다.

보존한 실패 배치는 다음과 같다.

- `artifacts/paper-v1-20261029/`: 회전한 Tetragon 파일 누락을 발견해 모델 평가 전에 중단.
- `artifacts/paper-v1-capture-v2-20261029/`: 파일 회전 처리는 수정했으나 서로 다른 호스트
  시계로 구간을 정한 문제를 발견해 평가 중단. 25개 종료 결과와 1개 중단 결과를 보존했다.
  `operator-abort.json`, `validity-warning.html`을 함께 읽어야 한다.
- 현재 clock-v3는 동일 worker-1 시계로 양쪽 경계를 측정하고 Prometheus 시각 변환
  불확실성을 기록한다. 앞선 실패 배치의 사용 예산을 이월하며 결과를 새 배치에 합치지 않는다.

## 저장과 권한

- SQLite WAL: worker-3의 `/var/lib/selective-rca/rca.sqlite3`.
- 단일 노드 로컬 저장소이며 고가용성/백업 서비스가 아니다. 재배포해도 데이터를 유지한다.
- Agent ServiceAccount는 `rca-lab`의 pods/pods-log/events에 get/list만 가능하다.
- Agent에는 exec, Secret 조회, Pod 변경 권한이 없다.
- eBPF 요약기는 기존 Tetragon export 경로만 읽기 전용 마운트한다. 새 BPF program을 로드하지 않는다.
- API는 ClusterIP이며 bearer token 인증을 사용한다. CLI는 kubectl exec로 내부 호출한다.
- 기본 redaction은 흔한 token/password/Bearer 패턴만 제거한다. 완전한 개인정보 탐지기가 아니다.
  따라서 초기 허용 범위는 직접 만든 `rca-lab` 데이터로 제한한다.
- 실험용 Pod는 requests/limits와 namespace quota를 가진다.

## 기존 환경에 맞춘 배포

```bash
python3 scripts/rcactl.py deploy
```

Python 표준 라이브러리만 사용한다. 배포 script는 코드 ConfigMap과 checksum을 적용한다.
Dockerfile은 별도 이미지 빌드용이며, 현재 클러스터 manifest는 두 워커에 캐시된
Python 3.12 기반 `ebpf-ml-mao` 이미지의 digest를 **실행 환경으로만** 사용한다.
command/PYTHONPATH를 지정해 이 디렉터리의 코드만 실행하며, 이미지의 기존 ML entrypoint는
실행하지 않는다. worker-1의 외부 이미지 다운로드 경로가 막혀 있어 선택한 방식이다.
향후 네트워크 복구 후 Dockerfile로 전용 이미지를 만들어 manifest의 image를 바꿀 수 있다.

worker-1은 노드→Pod HTTP readiness와 Prometheus→kubelet 직접 접근에서 타임아웃이 있었다.
서비스 간 통신은 별도로 검증하고, sample-service readiness는 컨테이너 localhost에서 검사한다.
metrics는 기존 Prometheus가 Kubernetes API server proxy를 경유해 두 워커에서 수집한다.
이는 호스트 네트워크 문제 자체를 수리한 것은 아니다.

`monitoring.yaml`은 다음을 추가한다.

- 두 워커의 cAdvisor scrape (15초, `rca-lab` 라벨만 보존).
- 기존 Prometheus SA에 `nodes/proxy` GET 권한을 두 node resourceNames로 제한해 부여.
  이 권한은 일반 metrics 권한보다 강하며 Agent에는 부여하지 않는다.
- 기존 Prometheus의 `additionalScrapeConfigs`를 새 Secret에 연결.
  이미 다른 설정이 있으면 덮어쓰지 않고 중단한다.
- `rca-lab`의 CPU throttling PrometheusRule과 인증된 AlertmanagerConfig.

기존 GPU node/배포 설정, 다른 namespace의 workload, Longhorn 볼륨은 수정하지 않는다.
기존 모니터링 operator의 실행 위치는 클러스터 설정에 따른다.

## 현재 eBPF 범위와 연구 한계

현재 제공하는 커널 증거는 Tetragon이 export한 process exec/exit 및 등록된 kprobe
개수와 **TCP connect 시도의 목적지 IP·포트별 집계**다. 기존 entry probe가 관찰한
주소이므로 성공/실패, errno, RTT는 알 수 없으며 Service VIP가 포함될 수 있다.
새 kernel probe는 추가하지 않았다. scheduler 지연, major page fault, TCP retransmission은
아직 구현되지 않았고, 응답의 `not_collected`에 명시한다.
export 이전 손실은 정량화하지 못한다. 파서 오류, 전송 대기 버퍼 손실, heartbeat는 기록한다.
10초 bucket 경계 때문에 요청 구간 바깥 최대 10초의 이벤트가 포함될 수 있다.
재시작/로그 회전 시 export 전체가 보존되지 않으면 수집 공백이 생길 수 있다.
수집 안 됨/샘플 없음은 정상이라는 근거로 사용할 수 없다.

목적지는 10초 bucket별 최대 16개, 응답은 상위 8개이며 누락 수를 별도로 표시한다.
raw 이벤트를 LLM에 보내지 않으며 이 집계는 정보가 제거되는 요약이다. 이후 증거의
로그/시간축 형식을 바꾸는 **무손실 압축**과 혼동하지 않는다.
Agent가 꺼져도 `/state/latest.json`에 최대 500개 bucket, 최근 10분의 bounded snapshot을
보관한다. 5초 주기 원자적 교체, 8Mi 메모리 볼륨을 사용하며 전송 실패는 backoff한다.
집계기의 PID CPU/RSS 측정은 기존 Tetragon이나 커널 probe 비용을 포함하지 않는다.
이 값만으로 전체 eBPF 오버헤드 또는 서비스 성능 저하율을 주장할 수 없다.

제한된 실제 장애 대조 실험까지 수행하는 MVP이며, 더 다양한 서비스와 장애, 독립 평가,
Tetragon ON/OFF 성능 대조, 신뢰도 보정, scheduler/TCP retransmission 수집은 후속 작업이다.

## 개발 검증

```bash
cd /root/Capstone/rca
python3 -m unittest discover -s tests -v
python3 scripts/verify_live.py                # 실제 연결 검증, API 키 없어야 실행
python3 scripts/verify_live.py --faults       # 실험 서비스에 세 장애를 순차 주입하며 검증
```

테스트는 실제 외부 API 대신 테스트 전용 HTTP 서버/응답을 사용한다.
키 없음, multi-turn tool protocol, 호출 예산, 중복 조회, evidence 검증,
Pod 교체, previous logs, redaction, container-scoped eBPF, daily budget를 검증한다.
이를 실제 모델의 원인 분석 정확도 검증과 혼동하지 않는다.
실제 환경 검증 결과는 `artifacts/live-verification.json`에 저장된다.

현재 공식 API 기준:
[OpenRouter API](https://openrouter.ai/docs/api/reference/overview),
[GLM-5.3-Flash 모델·가격](https://openrouter.ai/z-ai/glm-5.3-flash),
[Reasoning 설정](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens),
[Usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting).

제공자를 바꿀 때는 해당 제공자의 키만 사용한다. 다른 제공자 주소로 잘못 전송한 키는
원래 제공자 콘솔에서 폐기·재발급하고 `set-key`로 교체하는 것을 권장한다.
