# paper-clock-v3 원자료 재분석

독립 수집 6건, 종속 변형 3건, 사건·방식당 LLM 2회. 총 126개 실행이며 최종 실패 4건을 포함한다.

원본 response usage 재계산: 229 API 요청, 918,109 tokens, $0.18570969. 기존 중단 배치 비용과 합산하지 않았다.

**사람의 진단 품질 채점은 미평가다. 형식 통과율을 정확도로 해석하지 않는다.**

## 주 비교군 — 독립 수집만

| 방식 | 조사 수 | 평균 토큰 | 비용 합계 USD | 평균 초 | 수정 호출 | 최종 실패 |
|---|---:|---:|---:|---:|---:|---:|
| batch-ebpf | 12 | 5757.0 | 0.014368 | 29.8 | 0 | 0 |
| batch-no-ebpf | 12 | 6473.1 | 0.016601 | 37.9 | 2 | 0 |
| selective-ebpf | 12 | 6792.9 | 0.016276 | 36.3 | 0 | 0 |
| selective-no-ebpf | 12 | 6521.0 | 0.016721 | 39.3 | 0 | 0 |

## 구성요소 제거 실험 — 독립 수집만

| 방식 | 조사 수 | 평균 토큰 | 비용 합계 USD | 평균 초 | 수정 호출 | 최종 실패 |
|---|---:|---:|---:|---:|---:|---:|
| selective-ebpf-no-compression | 12 | 8224.8 | 0.018989 | 36.8 | 0 | 0 |
| selective-ebpf-no-dedup | 12 | 6739.4 | 0.015485 | 33.4 | 0 | 0 |
| selective-ebpf-no-stop-guidance | 12 | 6904.0 | 0.017992 | 39.9 | 0 | 0 |

## 실패 및 조회 분석

- `129e255992675f308766` / batch-ebpf / historical_contamination: `output_invalid_after_repair:claim needs actually retrieved evidence IDs`. 관측된 형식 문제: validation_errors 참조.
  실제 제공된 중첩 증거 ID를 최상위 ID만 인정하는 검증기가 거부함: ev-2a72021b33ea566c3965, ev-e3aeffbc2756c8e82c2c. 이는 과거 사건을 올바르게 해석했다는 판정이 아니며, 기존 실패 결과도 변경하지 않는다.
- `28ef0f63a77e3a9052be` / selective-ebpf-no-dedup / insufficient_evidence: `output_invalid_after_repair:invalid string`. 관측된 형식 문제: $.hypotheses[0]:expected string, got dict.
- `b6fae56d4f15ea72d522` / selective-ebpf-no-stop-guidance / historical_contamination: `output_invalid_after_repair:claim needs actually retrieved evidence IDs`. 관측된 형식 문제: validation_errors 참조.
  실제 제공된 중첩 증거 ID를 최상위 ID만 인정하는 검증기가 거부함: ev-2a72021b33ea566c3965. 이는 과거 사건을 올바르게 해석했다는 판정이 아니며, 기존 실패 결과도 변경하지 않는다.
- `c9d0db75b9027f963f7f` / selective-no-ebpf / historical_contamination: `output_invalid_after_repair:claim needs actually retrieved evidence IDs`. 관측된 형식 문제: validation_errors 참조.
  실제 제공된 중첩 증거 ID를 최상위 ID만 인정하는 검증기가 거부함: ev-2a72021b33ea566c3965. 이는 과거 사건을 올바르게 해석했다는 판정이 아니며, 기존 실패 결과도 변경하지 않는다.

중복 조회 요청 4회, 실제 중복 실행 4회. 인용되지 않은 증거 128개는 불필요 조회의 확정 판정이 아니다.
재조회 도구는 고정 스냅샷을 반환하므로 실제 중복 실행에서는 새 관측이 추가되지 않는다. 미인용 증거는 대안 배제나 맥락 확인에 쓰였을 수 있어 동일하게 취급하지 않는다.

## 해석 범위

종속 변형은 methods.csv에서 별도로 집계한다. incidents.csv와 paired-incident-deltas.csv는 동일 사건 반복을 평균한 뒤 비교한다. 여섯 독립 수집에서 통계적 우월성이나 일반 RCA 정확도를 주장하지 않는다.

선택 조회와 eBPF에 불리한 차이도 그대로 남긴다. 원자료·프로토콜·실패를 수정하지 않았다. 온라인 오버헤드는 미측정이며 진단 품질과 비용의 결합 평가는 독립 채점 이후에만 가능하다.

## 후속 연구를 결정한 관측

- eBPF 포함 선택 조회는 일괄 대비 평균 토큰 17.99% 증가했다. 작은 증거 집합에서 선택 조회의 비용 우위는 관측되지 않았다.
- 압축을 제거하면 평균 토큰이 21.08% 증가했다. 압축 버전은 비압축 버전 대비 17.41% 적었지만 진단 품질 유지는 미평가다.
- 중복 방지 제거는 평균 6739.4 tokens로 기본 6792.9보다 낮았다. 이 표본에서 중복 방지의 전체 토큰 절감 주장은 지지되지 않는다.
- 종료 안내 제거는 평균 6904.0 tokens였다. 단일 요인 제거 결과이며 작은 반복 표본의 변동을 일반적 효과로 해석하지 않는다.
- 다음 버전은 새 독립 발생, 주변 telemetry 증가, 애플리케이션 오류와 비핵심 보조 통신, 중첩 인용 등록 수정에 집중한다. 이전 결과를 성공으로 교체하지 않는다.
