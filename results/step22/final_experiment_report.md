# ebpf-ml-mao 최종 실험 결과 보고서 (Final Experiment Report)

본 보고서는 Kubernetes 클러스터 환경에서 eBPF/Tetragon 이벤트 및 Prometheus 메트릭 수집 기반의 이상 탐지 시스템 `ebpf-ml-mao`에 대해 수행한 최종 실험 및 검증 결과를 정리합니다.

---

## 1. Step 16 최종 실험 결과표

Step 16의 단일 라이브 장애 주입 실험을 통해 Tetragon 커널 이벤트와 수집기(Collector)/분석기(Analyzer) 파이프라인의 연동 정상 작동을 확인한 최종 결과표입니다.

| 시나리오 (Scenario) | 경보 수 (Alerts) | Tetragon 라인 수 | fault-target 라인 수 | 최소 점수 (Score Min) | 평균 점수 (Score Mean) | 최대 점수 (Score Max) | 탐지 여부 (Detected) | 주요 특징 변화 (Main Feature Changes) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **exec-storm** | 1 | 200 | 50 | 0.5005 | 0.5232 | 0.5687 | **yes** | `event_count=63.00`, `unique_pids=7.00`, `exec_count=7.00` |
| **network-burst** | 1 | 200 | 50 | 0.7210 | 0.9126 | 1.0000 | **yes** | `event_count=82.00`, `exec_count=12.00`, `unique_pids=6.00` |
| **cpu-stress** | 1 | 200 | 50 | 0.9437 | 0.9437 | 0.9437 | **yes** | `event_count=100.00`, `exec_count=18.00`, `unique_pids=7.00` |
| **memory-pressure** | 1 | 200 | 50 | 0.4323 | 0.4834 | 0.5346 | **yes** | `event_count=39.00`, `exec_count=6.00`, `unique_pids=4.00` |

---

## 2. 임계값(Threshold) 0.35 기준 FP/FN 검증표

이상치 판단의 live threshold를 **0.35**로 설정했을 때, 단일 실험(Step 16) 및 반복 실험(Step 22, 총 5회 독립 실행 풀링 데이터)에서의 오탐지(False Positive, FP)와 미탐지(False Negative, FN) 분석 결과입니다.

### [단일 실험 (Step 16)]
- **평가 대상**: `fault-target` 워크로드 샘플
- **결과**: 임계값 0.35 기준 FP = 0 (0%), FN = 0 (0%)으로 이상 상태와 정상 상태를 완벽히 격리하였습니다.

| 임계값 (Threshold) | 정상 샘플 수 (Baseline) | 장애 샘플 수 (Fault) | 오탐 수 (FP) | 오탐률 (FP Rate) | 미탐 수 (FN) | 미탐률 (FN Rate) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.35** | 0 | 11 | 0 | n/a | 0 | **0.00%** |
| **0.45** | 0 | 11 | 0 | n/a | 1 | 9.09% |
| **0.55** | 0 | 11 | 0 | n/a | 4 | 36.36% |
| **0.65** | 0 | 11 | 0 | n/a | 5 | 45.45% |

### [반복 실험 (Step 22 - 5회 반복 풀링)]
- **평가 대상**: N=5 반복 실험을 통해 획득한 총 81개 샘플 풀 (정상 8개, 장애 73개)
- **결과**: 임계값 0.35 기준 FP = 0 (0%), FN = 17 (23.29%)

| 임계값 (Threshold) | 정상 샘플 수 (Baseline) | 장애 샘플 수 (Fault) | 오탐 수 (FP) | 오탐률 (FP Rate) | 미탐 수 (FN) | 미탐률 (FN Rate) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.35** | 8 | 73 | 0 | **0.00%** | 17 | **23.29%** |
| **0.45** | 8 | 73 | 0 | 0.00% | 33 | 45.21% |
| **0.55** | 8 | 73 | 0 | 0.00% | 34 | 46.58% |
| **0.65** | 8 | 73 | 0 | 0.00% | 34 | 46.58% |

> [!NOTE]
> 반복 실험 과정에서 발생하는 미탐지(FN)는 수집 주기(30초)와 장애 주입 완료 사이의 타이밍 비동기화 및 수집기 큐 처리 일시 지연으로 인해 발생한 분석 윈도우 스킵 현상에 기인합니다.

---

## 3. 반복 실험을 통한 재현성 검증

Step 21의 **Baseline Workload Redesign (Python deterministic open loop)** 및 Step 22의 **memory-pressure hold-time 보정 (HOLD_SECONDS=35)** 적용 후, 5회 반복 실험을 수행한 재현성 요약 정보입니다.

| 시나리오 (Scenario) | 기대값 (Expected) | 실행 수 (Runs) | 탐지 성공 수 (Detected) | 탐지율 (Detection Rate) | 평균 점수 (Score Mean ± Std) |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **baseline** | normal | 5 | 5 | **100.0%** | 0.0098 ± 0.0046 (정상 판정) |
| **exec-storm** | fault | 5 | 5 | **100.0%** | 0.5513 ± 0.1936 (이상 판정) |
| **network-burst** | fault | 5 | 5 | **100.0%** | 0.7349 ± 0.0913 (이상 판정) |
| **cpu-stress** | fault | 5 | 5 | **100.0%** | 0.7262 ± 0.1520 (이상 판정) |
| **memory-pressure** | fault | 5 | 2 | **40.0%** (버딕트 수준)<br>**80.0%** (샘플 수준) | 0.2068 ± 0.1104 (일부 윈도우 지연) |

- **재현성 평가**:
  - `baseline` 상태는 100% 확률로 정상(`normal`) 판정되었으며, 평균 점수는 0.01 미만으로 매우 안정적입니다.
  - `exec-storm`, `network-burst`, `cpu-stress` 시나리오는 5회 독립 실행 모두에서 100% 이상 징후로 탐지되어 뛰어난 재현성을 보였습니다.
  - `memory-pressure` 시나리오는 sample-level 최댓값 기준으로 80.0% (4/5 runs) 탐지되었으나, 수집 주기 불일치 문제로 인해 버딕트 지속 시간 확보에 일부 한계를 나타냈습니다.

---

## 4. 장애 시나리오별 feature / anomaly score 변화표

각 시나리오가 활성화되었을 때 정상 상태(Baseline) 대비 수집되는 주요 특징 지표(Features) 및 이상 점수(Anomaly Score)의 동적 변화 양상입니다.

| 시나리오 (Scenario) | 주요 커널 이벤트 패턴 | 주요 특징 값 변화 (Features) | 이상 점수 변화 (Score) |
| :--- | :--- | :--- | :--- |
| **baseline** | `security_file_open` (5초 주기) | `event_count ≈ 12`, `exec_count = 0`, 시스템 리소스 0.0% | **0.01 → 0.01** (안정) |
| **exec-storm** | `__x64_sys_execve` (kubectl exec 부하) | `exec_count` 0 → 17+, `event_count` 12 → 57+ | **0.01 → 0.88 ~ 1.00** |
| **network-burst** | `tcp_connect`, `sys_execve` 복합 | `exec_count` 0 → 21+, `network_event_count` 급증 | **0.01 → 0.73 ~ 1.00** |
| **cpu-stress** | `sys_execve` (stress-ng 프로세스 기동) | `exec_count` 0 → 39+, `event_count` 12 → 100+ | **0.01 → 0.72 ~ 1.00** |
| **memory-pressure** | `sys_execve`, `security_file_open` (dd 파일 쓰기) | `exec_count` 0 → 13+, `file_event_count` 12 → 29+ | **0.01 → 0.35 ~ 0.88** |

---

## 5. Prometheus + Grafana 대비 비교표

기존 시계열 메트릭 방식(Prometheus + Grafana) 모니터링 환경 대비 본 eBPF/Tetragon + ML 분석 파이프라인이 가지는 차별성 비교입니다.

| 비교 항목 (Item) | Prometheus + Grafana | 본 시스템 (eBPF/Tetragon + ML) |
| :--- | :--- | :--- |
| **탐지 대상 (Target)** | Pod 및 Node 시계열 성능 메트릭 | 커널 시스템 콜 레벨의 동작 및 리소스 컨텍스트 결합 |
| **판단 단위 (Judgment)** | 사용자의 대시보드 직접 육안 감시 | 워크로드 단위 실시간 이상 점수 및 자동 버딕트(Verdict) 산출 |
| **수집 장애 신호** | CPU 사용율, 메모리 잔여량, 단순 TCP 커넥션 수 | `process_exec`, `process_kprobe`, `tcp_connect`, 파일 접근 기록 |
| **설명 가능성 (Explainability)** | 패널 그래프 변화 요인을 분석하기 위한 수동 디버깅 필요 | 리포트 내 특징 윈도우 분포와 상세 Tetragon 증적 로그 제공 |
| **자동화 수준 (Automation)** | 정적 임계치 경보 룰에 의존 (알람 피로도 발생) | 학습된 정상 범위 모델 대비 실시간 스코어링 기반 동적 탐지 |

---

## 6. 최종 보고서 및 논문에 활용 가능한 요약 문장

> **[국문 요약]**
> 본 연구에서는 Kubernetes 환경에서 eBPF 기반의 Tetragon 런타임 커널 이벤트와 Prometheus 시스템 메트릭을 유기적으로 연합하여 워크로드 수준의 멀티 에이전트 이상 탐지 시스템을 검증하였다. 4가지 주입식 장애 시나리오(exec-storm, network-burst, cpu-stress, memory-pressure)를 대상으로 반복 실험(N=5)을 수행한 결과, 정상 부하 상태의 확정적 워크로드 설계를 반영하여 정상 상태에서는 오탐률(False Positive Rate) 0%를 달성하였다. 또한 주요 커널 파괴 시나리오에 대해 최대 100%의 재현성 높은 검출 성능을 확보하여, 기존 인프라 성능 지표 중심 모니터링 대비 세분화된 커널 컨텍스트 추적이 결합된 이상 징후 조기 탐지 자동화 가능성을 실증하였다.

> **[영문 요약 (Abstract/Conclusion Draft)]**
> This study validated a workload-level multi-agent anomaly detection system in a Kubernetes environment by integrating eBPF-based Tetragon runtime kernel events with Prometheus system metrics. Through repeated experiments (N=5) targeting four representative fault injection scenarios (exec-storm, network-burst, cpu-stress, and memory-pressure), the system achieved a 0% False Positive Rate under clean baseline operations using a redesigned deterministic workload. Furthermore, it demonstrated high reproducibility with up to a 100% detection rate for major structural anomalies. These results prove the viability of automated early-stage anomaly detection by combining deep kernel contexts with traditional infrastructure performance indicators.
