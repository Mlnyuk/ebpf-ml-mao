같은 사건으로 맞춘 판넬용 이미지

왼쪽: 01-same-incident-logs-1600x600.png
오른쪽: 02-tower-1600x600.png
인쇄용: 같은 이름의 3200x1200.png 사용. 기존 Tower 이미지는 변경하지 않고 함께 넣었다.

권장 캡션
왼쪽: 동일 장애 사건의 애플리케이션 로그 — 저장 기록 재생.
오른쪽: 동일 사건의 저장된 AI 판단과 인용 증거 — 설정 포트와 연결 시도 포트 비교.

정확한 화면 성격
왼쪽은 K9s :screendump에서 저장 파일을 선택해 외부 읽기 전용 뷰어 less로 연 화면이다.
K9s 기본 실시간 Pod 로그 화면이나 10월 29일 당시 촬영한 스크린샷으로 설명하면 안 된다.
실제 연구 기록의 timestamp/message를 발췌해 지금 다시 열어 캡처했고, 그 사실을 화면 안에도 표시했다.
59개 원문 로그 중 첫 6행이다. 전체 raw export와 원본 증거 JSON을 records/에 함께 제공한다.
메시지·시각·Pod·컨테이너·출처 ID를 새로 만들지 않았다. 외부 뷰어의 제목과 출처 안내만 별도로 추가했다.
K9s의 저장 파일 기능 문서: https://k9scli.io/topics/commands/

동일 사건 연결
study: analysis-v3
case_id: 9e4945e7170b4a58
run_id: efc0b3de7271822b1552
Pod: sample-service-6d54574998-wljrj / app
Pod UID: d7dc68b5-d929-429b-b639-39519f1dfa69
로그 증거: ev-56e93b3b171d6a27a4a8
설정 증거: ev-d746a0bf5e594fdc022b
eBPF 증거: ev-a95c551872117dfc1836

설명 멘트
“왼쪽 로그에는 의존성 요청 실패와 HTTP 503이 있지만 목적지 포트는 없습니다.
같은 사건을 조사한 오른쪽 기록에서는 eBPF 연결 시도가 9099번 포트로 향했고,
설정에 선언된 8080번과 다르다는 근거를 확인할 수 있습니다.
eBPF 자체가 연결 성공·실패를 측정한 것은 아닙니다.”

검증
좌우 run_id/case_id/아카이브 해시 일치, Pod UID와 컨테이너 실행 ID 일치 확인.
59개 원문 로그 보존, 6개 표시 메시지와 타임스탬프 원문 일치, 두 해상도 PNG와 ZIP 무결성 확인.
K9s 저장 파일 선택 → 외부 뷰어 → q로 K9s 복귀를 직접 확인했다.
새 LLM 호출, 장애 재주입, 클러스터 변경 없음. 기존 연구 결과와 이전 캡처는 보존했다.

로그 내보내기 재현 (저장소 루트에서 새 출력 경로 사용)
python3 rca/scripts/export_paired_logs.py --archive rca/control-tower/archive.json --run-id efc0b3de7271822b1552 --output /tmp/rca-saved-logs
이 명령은 오프라인 파일 읽기/쓰기만 수행한다. 출력 경로가 존재하면 덮어쓰지 않는다.
K9s에서 열기: 전용 --screen-dump-dir 하위의 현재 cluster/context 폴더에 .ansi 파일을 복사하고,
K9S_EDITOR에 read_saved_logs.sh의 절대 경로를 지정한 뒤 :sd에서 해당 파일을 연다.
