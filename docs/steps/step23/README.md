# Step 23

Step 23 범위는 `Dashboard Rewrite — Per-Workload Anomaly View`입니다.

기존 Step 15 대시보드는 운영 지표(ingest/queue/spool backlog) 위주였고, ML 이상 탐지 신호가
화면에서 잘 드러나지 않았습니다. 구체적 한계:

1. **anomaly score 미표시**: verdict가 binary(normal/anomalous)로만 보이고 실제 score(0~1)는 안 보임.
2. **workload 구분 없음**: `latest_verdict`가 클러스터 전체 마지막 리포트 하나만 표시 → fault-target과 다른 workload를 구분 못 함.
3. **시계열 없음**: 현재 카운트만 보이고 score 추세/spike 시점이 안 보임.
4. **feature breakdown 없음**: 어떤 feature가 튀어서 anomalous가 됐는지 알 수 없음.

> 참고: `_filter_target_events` fallback(`return filtered or events`)은 이미 commit `2e7af71`
> "Keep Step 16 target filter strict"에서 `return filtered`로 수정 완료. Step 23은 표현 계층만 다룹니다.

## 변경 내용

### Backend (`app/ebpf_ml_mao/api.py`)

- **ingest index 확장**: `store_ingest_payload` / `rebuild_ingest_index`가 리포트에서 `score`,
  `workload`, `window_start/end`, `features`(feature_window.values), `received_at`를 추출해 인덱싱.
  `_index_item` 헬퍼로 두 경로 통합. 누락 필드는 None/"unknown"으로 graceful 처리.
- **per-workload 집계**: `_save_workflow_summary`가 `workloads` 맵 생성. 각 workload마다
  `latest_verdict`, `latest_score`, `detection_rate`, `anomalous_count`, `top_feature`,
  `recent_scores`(최근 N=40 윈도우 score/verdict 시계열) 제공.
- **시간순 latest**: `latest_verdict`를 dict 삽입 순서(`items[-1]`)가 아니라
  `(received_at, window_start)` 시간순 정렬 마지막으로 계산.
- **`/v1/scores` 엔드포인트 추가**: workload별 최근 score 시계열 반환. `/v1/dashboard`의
  `workflow.workloads`에도 동일 데이터 포함.

### Frontend (`app/ebpf_ml_mao/ui/`)

- **workload anomaly 카드 (메인)**: workload마다 카드 1개. 현재 verdict pill, 큰 anomaly score,
  최근 score SVG sparkline(0.45 임계선 점선 표시), top feature chip, detection rate, 노드 표시.
  anomalous workload를 상단에 정렬.
- **ops-strip (보조)**: ingest/queue/spool/alerts/active-model을 작은 chip으로 축소.
- alert feed / registry / queue·spool health 패널은 하단 보조 영역으로 유지.

## Added / Changed

- `app/ebpf_ml_mao/api.py`: `_index_item`, `_summarize_workloads`, `_top_feature`, `_item_sort_key`,
  `/v1/scores` 추가. `_save_workflow_summary`에 `workloads` 추가.
- `app/ebpf_ml_mao/ui/dashboard.html`: workload 그리드 + ops-strip 구조로 재작성.
- `app/ebpf_ml_mao/ui/dashboard.js`: `renderWorkloads`, `sparkline`, `workloadCard` 추가.
- `app/ebpf_ml_mao/ui/dashboard.css`: workload-card / spark / ops-chip 스타일 추가.
- `tests/test_step23_dashboard.py`: index/aggregation/endpoint/UI 검증 5개 테스트.
- `docs/steps/step23/README.md`: 본 문서.

## API

```bash
# workload별 최근 score 시계열
curl http://localhost:8080/v1/scores

# /v1/dashboard 에도 workflow.workloads 포함
curl http://localhost:8080/v1/dashboard | jq '.workflow.workloads'
```

`/v1/scores` 응답 예:

```json
{
  "component": "analyzer",
  "timestamp": 1779778084,
  "workloads": {
    "fault-target": {
      "sample_count": 5,
      "anomalous_count": 3,
      "detection_rate": 0.6,
      "latest_verdict": "anomalous",
      "latest_score": 0.55,
      "top_feature": {"name": "exec_count", "value": 7.0},
      "recent_scores": [{"score": 0.01, "verdict": "normal", "window_start": 1000.0}, ...]
    }
  }
}
```

## 호환성

- 기존 `/v1/dashboard`, `/v1/alerts`, `/v1/workflow` 응답 필드는 모두 유지(추가만 함).
- 기존 인덱스(`index.json`)는 `repair=True` 경로에서 `rebuild_ingest_index`로 재구성되며
  새 필드가 자동 채워집니다.

## Limitations

- sparkline 임계선은 UI 상수 0.45로 고정. 모델 threshold를 동적으로 받아오려면
  `/v1/dashboard`에 active model threshold를 노출하는 후속 작업 필요.
- 헤드리스 브라우저가 없는 환경이라 자동 스크린샷 검증은 못 함. 엔드포인트 응답,
  HTML/JS/CSS 정합성, JS 문법(node --check)으로 검증.
