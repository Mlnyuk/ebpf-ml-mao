# paper-next-v1 — 새 독립 사건 평가

새 독립 수집 20건, 각 사건의 작은/주변 포함 증거는 종속 비교 조건이다. LLM 반복은 사건·방식·증거 조건당 1회. 기록된 조사 88건, 최종 실패 0건.

**진단 품질은 독립 사람 채점 전 미평가다. 아래 수치는 실패를 포함한 실제 사용량이며, 정확도 유지나 우월성을 입증하지 않는다.**

| 조건 | 증거 규모 | 방식 | 조사 | 평균 토큰 | 총 비용 USD | 평균 초 | 수정 호출 | 실패 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| collection_missing | surrounding_3_workloads | batch | 1 | 17274.0 | 0.003035 | 37.9 | 0 | 0 |
| collection_missing | surrounding_3_workloads | selective | 1 | 17398.0 | 0.003151 | 45.9 | 0 | 0 |
| collection_missing | target_only | batch | 1 | 4027.0 | 0.000959 | 31.5 | 0 | 0 |
| collection_missing | target_only | selective | 1 | 5343.0 | 0.001266 | 44.8 | 0 | 0 |
| historical_contamination | surrounding_3_workloads | batch | 1 | 22279.0 | 0.003921 | 45.2 | 0 | 0 |
| historical_contamination | surrounding_3_workloads | selective | 1 | 23331.0 | 0.004084 | 62.2 | 0 | 0 |
| historical_contamination | target_only | batch | 1 | 8838.0 | 0.001748 | 32.7 | 0 | 0 |
| historical_contamination | target_only | selective | 1 | 10116.0 | 0.002035 | 46.9 | 0 | 0 |
| original | surrounding_3_workloads | batch | 20 | 19767.7 | 0.066572 | 38.6 | 1 | 0 |
| original | surrounding_3_workloads | selective | 20 | 9453.3 | 0.036691 | 43.7 | 1 | 0 |
| original | target_only | batch | 20 | 5534.0 | 0.023285 | 32.8 | 0 | 0 |
| original | target_only | selective | 20 | 7222.2 | 0.030602 | 42.4 | 2 | 0 |

단순 목적지 기준선은 정상 목적지에서 발생하는 애플리케이션 오류나 비핵심 보조 통신의 서비스 영향까지 판단하지 않는다. 이는 해당 기준선의 정의된 범위이며 일반 RCA 정확도와 같은 지표로 합산하지 않는다.

K8sGPT 원본은 private/<occurrence>/k8sgpt-native.json에 보존한다. analyzer 범위 밖과 범위 내 미감지를 구분해야 하며 사람 채점 없이 오진/적절한 보류를 자동 확정하지 않는다.

공유 클러스터 온라인 Tetragon·정책·추가 요약기·서비스 영향의 인과적 오버헤드는 미측정이다.
