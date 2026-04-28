# Implementation Overview Without MAO Perspective

이 문서는 저장소의 디렉터리 구조와 실제 구현 상태를 정리한다. Multi Agent Orchestration 관점의 설계 문서와 역할 분해 설명은 제외하고, 코드가 어떤 입력을 받아 어떤 처리 경로로 결과를 만드는지에 집중한다.

## 1. 디렉터리 구조

```text
.
├── app/ebpf_ml_mao/          # Python MVP 애플리케이션 코드
│   ├── adapters.py           # Tetragon/Prometheus 원천 데이터를 내부 이벤트 모델로 변환
│   ├── api.py                # analyzer HTTP API, 상태/알림/대시보드 엔드포인트
│   ├── cli.py                # phase 실행, 모델/레지스트리/전송/상태 CLI
│   ├── features.py           # 30초 윈도우 분할과 특징 추출
│   ├── live.py               # Tetragon 로그 tail, Prometheus text scrape/parse
│   ├── models.py             # 내부 dataclass 모델
│   ├── normalizer.py         # Phase 1 flat JSONL 정규화
│   ├── pipeline.py           # 학습, 추론, 리포트 생성 파이프라인
│   ├── registry.py           # 모델 레지스트리 로드/저장/활성화/정리
│   ├── report.py             # JSON/Markdown 리포트 출력
│   ├── scoring.py            # baseline/zscore 모델과 이상 점수 계산
│   ├── transport.py          # 리포트 POST, spool, postprocess queue 처리
│   └── ui/                   # analyzer 정적 운영 대시보드
├── deploy/yaml/              # Kubernetes/Tetragon 배포 매니페스트와 단계별 overlay
├── docs/                     # 스펙, 단계별 구현 기록, 운영 문서, 아키텍처 문서
├── samples/                  # 단계별 입력 샘플과 baseline 샘플
├── tests/                    # unittest 기반 회귀 테스트
├── Dockerfile                # 애플리케이션 컨테이너 이미지 정의
├── Makefile                  # 테스트, kustomize render, 이미지 빌드 보조 명령
└── README.md                 # 저장소 개요
```

## 2. 구현의 중심 흐름

핵심 실행 흐름은 `app/ebpf_ml_mao/pipeline.py`에 모여 있다.

1. 입력 로드
   - JSONL 파일은 `loader.load_jsonl()`, JSON 파일은 `loader.load_json()`로 읽는다.
   - live 모드에서는 `live.tail_jsonl()`로 Tetragon 로그의 마지막 N개 라인을 읽고, `live.scrape_prometheus_snapshot()`으로 Prometheus text endpoint를 scrape한다.

2. 입력 표준화
   - Tetragon 이벤트는 `adapters.adapt_tetragon_event()`가 `NormalizedEvent`로 변환한다.
   - Prometheus snapshot은 metric series를 workload/pod/container/node 단위로 묶은 뒤 `NormalizedEvent` 목록으로 변환한다.
   - Phase 1의 단순 JSONL 입력은 `normalizer.normalize_event()`가 같은 내부 모델로 맞춘다.

3. 윈도우와 특징 추출
   - `features.window_events()`는 workload와 30초 bucket 기준으로 이벤트를 묶는다.
   - `features.extract_features()`는 이벤트 수, exec 수, network event 수, unique PID 수, CPU/메모리/네트워크 평균 및 최대값을 계산해 `FeatureWindow`를 만든다.

4. 학습 또는 모델 로드
   - baseline 학습은 `train_baseline_model()`이 baseline feature window들의 평균값을 모델로 저장한다.
   - zscore 학습은 feature별 mean/std를 저장한다.
   - 저장된 모델은 JSON 파일이며 `BaselineModel` schema v2를 사용한다.
   - `registry.py`는 모델 파일 경로, model type, schema version, threshold, tag, active model을 JSON registry로 관리한다.

5. 이상 점수 산출
   - `BaselineScorer.score()`가 feature window와 모델을 비교한다.
   - `baseline` 모델은 feature별 기준값 대비 상대 거리의 평균을 점수화한다.
   - `zscore` 모델은 feature별 표준점수 평균을 점수화한다.
   - `verdict_for_score()`는 score가 threshold 이상이면 `anomalous`, 아니면 `normal`로 판정한다.

6. 리포트 생성
   - 단일 리포트는 `AnalysisReport`, 배치 리포트는 `BatchAnalysisReport`로 표현된다.
   - `report.py`가 `report.json`, `report.md`, `report-index.json`, `report-index.md`, 개별 batch report 파일을 생성한다.

## 3. Phase별 실행 기능

`cli.py`는 아래 명령을 제공한다.

| 명령 | 역할 |
| --- | --- |
| `phase1` | flat JSONL baseline/input을 정규화해 단일 분석 리포트 생성 |
| `phase2` | Tetragon JSONL + Prometheus JSON snapshot을 사용해 단일 분석 리포트 생성 |
| `phase3` | Tetragon live log tail + Prometheus scrape 결과로 단일 리포트 생성 |
| `phase4` | 파일 입력 기반 batch 리포트 생성 |
| `phase5` | 저장된 모델 또는 registry active model을 로드해 batch 추론 실행 |
| `train-model` | baseline 또는 zscore 모델 학습 및 선택적으로 registry 등록/활성화 |
| `show-model` | 모델 파일 schema/type/feature/threshold 정보 출력 |
| `migrate-model` | 모델 JSON을 최신 schema로 마이그레이션 |

운영 보조 명령으로 registry 관리, 리포트 전송, spool drain/prune/status, ingest/workflow/dashboard/alerts 상태 조회도 제공한다.

## 4. 데이터 모델

주요 내부 모델은 `models.py`의 dataclass로 정의되어 있다.

- `NormalizedEvent`: 표준 이벤트 단위. timestamp, source, event_type, node, workload, pod, container, pid, CPU, memory, network connection, metadata를 담는다.
- `FeatureWindow`: 특정 workload의 시간 구간과 계산된 feature dictionary를 담는다.
- `AnalysisReport`: score, verdict, confidence, feature window, 리포트 보조 요약 결과를 담는다.
- `BatchAnalysisReport`: 여러 `AnalysisReport`를 묶는다.
- `DashboardSnapshot`: analyzer 상태 API/UI에서 사용하는 registry, ingest, workflow, queue, spool, alert 상태 묶음이다.

## 5. Analyzer API와 UI

`api.py`는 Python 표준 라이브러리의 `ThreadingHTTPServer` 기반으로 구현되어 있다. 외부 framework 없이 동작한다.

주요 GET 경로:

- `/healthz`: analyzer 기본 health check
- `/readyz`: dashboard 상태가 critical이면 503, 아니면 200
- `/v1/status`, `/v1/dashboard`: registry, ingest, workflow, queue, spool, alerts를 합친 상태 snapshot
- `/v1/alerts`: alert 중심 응답
- `/v1/workflow`: ingest된 리포트들의 workflow summary
- `/v1/queue`, `/v1/spool`: queue/spool 상태
- `/ui`: 정적 HTML 대시보드
- `/assets/dashboard.css`, `/assets/dashboard.js`: UI asset

주요 POST 경로:

- `/v1/reports`: collector가 보낸 분석 리포트를 ingest directory에 저장하고 중복을 digest로 판별한다.

인증은 `shared_token`이 설정된 경우 `Authorization: Bearer <token>` 헤더를 확인하는 방식이다.

UI는 `app/ebpf_ml_mao/ui/`에 있는 정적 파일로 구성된다. `dashboard.js`가 analyzer API를 호출해 상태 pill, 주요 counter, alert feed, registry/workflow/queue/spool health 정보를 표시하고 15초마다 새로고침한다.

## 6. 전송, Spool, Queue

`transport.py`는 collector와 analyzer 사이의 파일/HTTP 전송을 담당한다.

- `post_report()`는 리포트를 `/v1/reports`로 직접 POST한다.
- `ship_report()`는 POST 실패 시 리포트를 spool directory에 JSON envelope로 저장한다.
- `drain_spool()`은 spool에 남은 항목을 다시 전송하고 성공 시 파일을 삭제한다.
- `spool_status()`와 `queue_status()`는 pending/failed/expired/quarantined 상태를 집계한다.
- `prune_spool()`과 `prune_queue()`는 만료 항목을 제거하고 깨진 JSON은 quarantine directory로 이동한다.
- analyzer는 새 리포트를 저장할 때 postprocess queue 항목도 생성한다.

이 구조 때문에 네트워크 장애가 있어도 collector가 리포트를 즉시 잃지 않고, 나중에 drain으로 재전송할 수 있다.

## 7. Kubernetes 배포 구성

배포 파일은 `deploy/yaml/` 아래 단계별 overlay로 관리된다.

- `step9`: 기본 runtime layout. collector는 DaemonSet, analyzer는 Deployment로 분리된다.
- `step10`: Secret, NetworkPolicy, PDB, collector/analyzer patch가 추가된다.
- `step11`~`step14`: live collector, API/transport, 운영 상태 산출, validation 산출물이 확장된다.
- `step15`: analyzer UI Service, HPA, ServiceAccount image pull secret, live.py ConfigMap generator가 추가된다.

런타임 경로는 대체로 다음과 같다.

- Tetragon log: `/var/run/cilium/tetragon/tetragon.log`
- Registry: `/var/lib/ebpf-ml-mao/registry/registry.json`
- Model dir: `/var/lib/ebpf-ml-mao/models`
- Report/ingest dir: `/var/lib/ebpf-ml-mao/reports`
- Collector scratch/spool: `/var/lib/ebpf-ml-mao-collector`

Step 15 기준 UI 접근 Service는 `ebpf-ml-mao-ui`이고, cluster 내부 경로는 `http://ebpf-ml-mao-ui.ebpf-obs.svc.cluster.local:8080/ui`로 문서화되어 있다.

## 8. 테스트와 검증

테스트는 `tests/` 아래 `unittest` 기반으로 구성되어 있다. 범위는 다음을 포함한다.

- 입력 어댑터와 정규화
- batch report 생성
- 모델 학습, schema migration, registry 조작
- transport retry/spool/queue 처리
- analyzer API 상태 응답
- Kubernetes manifest render 산출물
- Step 15 UI asset route

기본 검증 명령은 다음과 같다.

```bash
python3 -m unittest discover -s tests -v
kubectl kustomize deploy/yaml/step15
```

## 9. 현재 구현상 특징

- 외부 Python web framework 없이 표준 라이브러리 중심으로 구현되어 배포 이미지가 단순하다.
- 모델은 경량 JSON artifact이며, active model 선택은 registry JSON으로 해결한다.
- baseline/zscore는 운영 실험용 MVP 모델로 구현되어 있고, 복잡한 ML runtime 의존성은 없다.
- collector가 직접 analyzer API로 전송하고, 실패 시 로컬 spool에 보관하는 방식이다.
- analyzer는 파일 기반 registry/ingest/queue를 사용하므로 현재 형태에서는 단일 writer 성격이 강하다.
- UI는 server-side rendering 없이 analyzer API를 읽는 정적 dashboard다.

## 10. 한계와 후속 개선 지점

- 파일 기반 registry/ingest/queue는 단순하지만 analyzer replica를 적극적으로 늘리는 구조에는 적합하지 않다.
- baseline/zscore 점수는 설명 가능하고 가볍지만 실제 운영 이상 탐지 정확도는 더 많은 데이터와 검증이 필요하다.
- postprocess queue는 생성과 상태 집계 중심이며, 별도 worker 처리 루프는 아직 제한적이다.
- API 인증은 shared token 수준이므로 운영 공개 환경에서는 ingress, network policy, secret 관리, RBAC를 함께 설계해야 한다.
- backlog 기반 autoscaling은 아직 구현되어 있지 않고, Step 15 HPA는 CPU/메모리 metric에 의존한다.
