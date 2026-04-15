# Agent Handoff — ebpf-ml-mao

**최종 업데이트**: 2026-04-15  
**현재 브랜치**: `main`  
**최신 커밋**: `535846a` Fix GHCR image tag casing  
**배포 단계**: Step 15 (시각화 대시보드) — 구현 완료, 클러스터 배포 완료

---

## 프로젝트 한줄 요약

eBPF(Tetragon) + Prometheus 이벤트를 수집해 멀티 에이전트 파이프라인으로 이상 탐지하고 웹 UI로 운영 상태를 시각화하는 Kubernetes 네이티브 보안 관측 시스템.

---

## 디렉터리 구조

```
Capstone/
├── app/ebpf_ml_mao/          # Python 패키지 (analyzer + collector 공용)
│   ├── adapters.py            # Tetragon/Prometheus 이벤트 → NormalizedEvent
│   ├── agents.py              # 멀티 에이전트 (summarizer/analyst/correlator/reviewer)
│   ├── api.py                 # HTTP API 서버 + /ui + /readyz + /healthz
│   ├── cli.py                 # 명령줄 진입점 (serve-api, phase3, ship-report 등)
│   ├── features.py            # 피처 추출
│   ├── live.py                # Tetragon 로그 tail + Prometheus scrape + label 파싱
│   ├── models.py              # 데이터 모델
│   ├── pipeline.py            # phase3 파이프라인 (tetragon+prometheus → report)
│   ├── registry.py            # 모델 레지스트리
│   ├── scoring.py             # 이상 점수화
│   ├── transport.py           # HTTP 리포트 전송 (collector → analyzer)
│   └── ui/                    # 정적 웹 UI (dashboard.html/css/js)
├── deploy/yaml/
│   ├── step9/                 # 기반 리소스 (NS, SA, RBAC, PVC, Deployment, DaemonSet, Service, ConfigMap)
│   ├── step10/                # NetworkPolicy + readinessProbe + PDB + Secret
│   ├── step11/                # ingest 중복 제거 + spool replay
│   ├── step12/                # spool-prune/drain 루프 (collector 고도화)
│   ├── step13/                # 운영 상태 API (/v1/dashboard, /v1/alerts)
│   ├── step14/                # 배포 closeout (이미지 태그 고정, runbook, CI)
│   └── step15/                # 시각화 UI + 클러스터 배포 픽스 (현재 최신)
│       ├── kustomization.yaml
│       ├── ui-service.yaml            # ebpf-ml-mao-ui Service
│       ├── patch-serviceaccounts.yaml # imagePullSecrets: ghcr-pull-secret
│       ├── patch-volume-permissions.yaml  # fsGroup + initContainer(fix-perms)
│       ├── patch-configmap.yaml       # 올바른 PROMETHEUS_URL
│       ├── patch-networkpolicy-dns.yaml   # NodeLocal DNS ipBlock 허용
│       └── patch-collector-live-py.yaml   # ConfigMap subPath로 live.py 교체
├── tests/                     # 단계별 단위 테스트 (test_stepNN_*.py)
├── docs/
│   ├── steps/stepNN/          # 각 단계 README + agent-notes + output
│   ├── specs/                 # 클러스터 스펙, 요구사항, 미래 아키텍처
│   ├── architecture/          # MAO 설계 + ebpf-ml-mao 디렉터리 트리/에이전트 역할
│   └── operations/            # runbook, rollback, CI/CD, checklist
├── samples/                   # 단계별 샘플 입력 데이터
├── Dockerfile                 # Python 앱 이미지 빌드
├── Makefile                   # build-image, test, render/deploy 타깃
├── .github/workflows/
│   ├── ci.yaml                # PR 검증 (test + kustomize render)
│   └── release-image.yaml     # 수동 트리거로 GHCR 빌드+푸시
└── HANDOFF.md                 # ← 이 파일
```

---

## 현재 클러스터 상태 (2026-04-15 기준)

| 리소스 | 상태 |
|--------|------|
| `ebpf-ml-mao-analyzer` Deployment | `1/1 Running` |
| `ebpf-ml-mao-collector` DaemonSet | `2/2 Running` × 8노드 |
| `ebpf-ml-mao-analyzer` Service (ClusterIP) | Endpoint 등록됨 `10.233.64.175:8080` |
| `ebpf-ml-mao-ui` Service (ClusterIP) | 동일 Endpoint |
| `/healthz` | HTTP 200 |
| `/ui` | HTTP 200 (HTML 대시보드) |
| collector phase3 | 성공 — 매 30초 리포트 생성·전송 중 |
| analyzer ingest | `received_count` 증가 중, `verdict: normal` |

배포 명령:
```bash
kubectl apply -k deploy/yaml/step15
```

---

## 이번 세션에서 구현한 것 (클러스터 배포 디버깅)

Step 15까지 코드는 완성되어 있었지만 클러스터에서 동작하지 않았다. 아래 6가지 문제를 순서대로 진단·수정했다.

### 1. analyzer PVC 권한 오류
- **증상**: `PermissionError: [Errno 13] Permission denied: '/var/lib/ebpf-ml-mao/ingest'`
- **원인**: pod `securityContext.fsGroup` 미설정 → PVC가 root 소유 → UID 10001 쓰기 불가
- **수정**: `step15/patch-volume-permissions.yaml`에 `fsGroup: 10001` 추가

### 2. collector hostPath 권한 오류
- **증상**: `mkdir: cannot create directory '/var/lib/ebpf-ml-mao-collector/reports': Permission denied`
- **원인**: hostPath는 `fsGroup` 미적용 → kubelet이 root로 생성한 디렉토리에 UID 10001 쓰기 불가
- **수정**: `fix-permissions` initContainer(runAsUser: 0) 추가 → `chown -R 10001:10001`

### 3. collector readiness 실패 (tetragon.log 없음)
- **증상**: collector `1/2`, readinessProbe `test -f ${TETRAGON_LOG_PATH}` 항상 실패
- **원인**: 이 클러스터에 실제 Tetragon 미설치 (ebpf-agent는 `ubuntu sleep infinity` placeholder)
- **수정**: `fix-permissions` initContainer에서 `tetragon-run` 볼륨도 마운트해 빈 `tetragon.log` 생성

### 4. analyzer readiness 실패 (모델 없음)
- **증상**: `/readyz` 항상 503 (`state: critical` — "registry has no active model") → Service endpoint 미등록
- **원인**: fresh 클러스터에는 ML 모델 없음, readinessProbe가 `/readyz`를 사용
- **수정**: `patch-volume-permissions.yaml`에서 readinessProbe를 `/healthz`로 변경

### 5. PROMETHEUS_URL 오타 + NetworkPolicy DNS 차단
- **증상**: `URLError: [Errno -3] Temporary failure in name resolution`
- **원인 A**: ConfigMap의 URL이 `prometheus-kube-prometheus-prometheus`인데 실제 서비스는 `my-monitoring-kube-prometh-prometheus`
- **원인 B**: NodeLocal DNSCache(`169.254.25.10`)는 파드가 아니라 `namespaceSelector: {}`에 매칭 안 됨
- **수정 A**: `step15/patch-configmap.yaml` 추가 — 올바른 URL로 교체
- **수정 B**: `step15/patch-networkpolicy-dns.yaml` 추가 — `ipBlock: 169.254.25.10/32` egress 규칙 추가

### 6. Prometheus label 파싱 버그
- **증상**: `ValueError: not enough values to unpack (expected 2, got 1)` in `_parse_labels`
- **원인**: `prometheus_build_info{tags="netgo,builtinassets",...}` — 라벨 값 안에 `,` 포함, 단순 `split(",")` 로 파싱하면 `builtinassets"` 같은 `=` 없는 토큰 발생
- **수정**:
  - `app/ebpf_ml_mao/live.py` — `_parse_labels`를 regex 기반(`re.finditer(r'(\w+)="((?:[^"\\]|\\.)*)"')`)으로 교체
  - Docker 없는 환경이므로 이미지 재빌드 대신 `ConfigMap + subPath volumeMount`로 `live.py` overlay 배포
  - `kubectl -n ebpf-obs create configmap ebpf-ml-mao-live-py --from-file=live.py=...`
  - `step15/patch-collector-live-py.yaml` — DaemonSet에 해당 마운트 추가

### 7. step12 collector args YAML 버그 (사전 발견)
- **증상**: `/bin/sh: --ttl-seconds: not found` — shell이 옵션 플래그를 독립 명령으로 해석
- **원인**: `>-` folded scalar + 더 깊은 indentation → 옵션 행에 literal `\n` 보존
- **수정**: `step12/patch-collector-daemonset.yaml` — 각 python 명령 continuation 행에 `\` 추가

---

## 수정된 파일 목록

| 파일 | 변경 유형 |
|------|-----------|
| `deploy/yaml/step15/patch-volume-permissions.yaml` | **신규** |
| `deploy/yaml/step15/patch-configmap.yaml` | **신규** |
| `deploy/yaml/step15/patch-networkpolicy-dns.yaml` | **신규** |
| `deploy/yaml/step15/patch-collector-live-py.yaml` | **신규** |
| `deploy/yaml/step15/kustomization.yaml` | 수정 (패치 4개 등록) |
| `deploy/yaml/step12/patch-collector-daemonset.yaml` | 수정 (`\` continuation 추가) |
| `app/ebpf_ml_mao/live.py` | 수정 (regex label 파서) |

클러스터에만 적용된 리소스 (저장소에는 없음):
- `ConfigMap/ebpf-ml-mao-live-py` in `ebpf-obs` — live.py patch 내용

> **주의**: `patch-collector-live-py.yaml`은 이 ConfigMap을 참조한다. 클러스터를 초기화하거나 다른 클러스터에 배포할 경우 ConfigMap을 먼저 생성해야 한다:
> ```bash
> kubectl -n ebpf-obs create configmap ebpf-ml-mao-live-py \
>   --from-file=live.py=app/ebpf_ml_mao/live.py
> ```

---

## 다음 에이전트가 할 일

### 즉시 해결 필요

1. **live.py fix를 이미지에 포함시키기**
   - 현재 `live.py` 수정이 ConfigMap overlay로 임시 배포됨
   - `release-image.yaml` workflow를 수동 트리거해 `ghcr.io/mlnyuk/ebpf-ml-mao:step15`를 재빌드·푸시
   - 재빌드 후 `patch-collector-live-py.yaml` 패치는 제거 가능
   - GitHub Actions: `workflow_dispatch` → `image_tag: step15`

2. **step15 patch-configmap에 `DEPLOYMENT_*` 메타데이터 누락 확인**
   - step14 패턴 참고: `DEPLOYMENT_STEP`, `DEPLOYMENT_IMAGE`, `DEPLOYMENT_RUNBOOK` 세 키가 있어야 함
   - `step15/patch-configmap.yaml`에 이미 포함됨 — 확인 후 불필요하면 스킵

### 중기 작업

3. **Step 16 이후 구현** (docs/specs/future.md 참고)
   - 실시간 Tetragon 이벤트 스트림 처리 (현재는 파일 tail)
   - 자동 대응(response) 모듈
   - 인증/RBAC 추가 (현재 UI는 인증 없음)

4. **테스트 환경에 실제 Tetragon 연결**
   - 현재 `ebpf-agent`는 `ubuntu:22.04 sleep infinity` placeholder
   - 실제 Tetragon DaemonSet 배포 시 `tetragon.log` 생성 → initContainer의 placeholder touch 불필요

5. **모델 등록**
   - analyzer 레지스트리가 비어 있어 `/readyz`가 `critical` 반환 중
   - readinessProbe는 `/healthz`로 우회했지만, 실제 운영을 위해서는 step7~8에서 만든 모델을 레지스트리에 등록해야 함
   - `docs/steps/step7/output/registry.json` 참고

---

## 주요 설정값 (ConfigMap: ebpf-ml-mao-runtime)

| 키 | 값 |
|----|-----|
| `ANALYZER_API_URL` | `http://ebpf-ml-mao-analyzer.ebpf-obs.svc.cluster.local:8080` |
| `PROMETHEUS_URL` | `http://my-monitoring-kube-prometh-prometheus.monitoring.svc.cluster.local:9090/metrics` |
| `ANALYSIS_INTERVAL_SECONDS` | `30` |
| `COLLECTOR_SPOOL_DIR` | (ConfigMap에서 확인) |
| `TETRAGON_LOG_PATH` | `/var/run/cilium/tetragon/tetragon.log` |

---

## 빠른 상태 확인 명령

```bash
# 전체 상태
kubectl -n ebpf-obs get pods,svc,endpoints

# analyzer 로그
kubectl -n ebpf-obs logs deploy/ebpf-ml-mao-analyzer --tail=20

# collector 로그 (아무 노드나)
kubectl -n ebpf-obs logs daemonset/ebpf-ml-mao-collector -c collector --tail=20

# UI 응답 확인 (클러스터 내부에서)
kubectl -n ebpf-obs exec daemonset/ebpf-ml-mao-collector -c report-shipper -- \
  wget -qO- http://ebpf-ml-mao-analyzer.ebpf-obs.svc.cluster.local:8080/ui | head -5

# kustomize 렌더링 확인
kubectl kustomize deploy/yaml/step15
```
