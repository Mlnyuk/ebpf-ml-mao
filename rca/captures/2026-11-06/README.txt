2026-11-06 실제 터미널 캡처

바로 사용할 이미지
- 01-k9s-pod-state-events.png (1920x1080)
  위: rca-lab Pod 상태. 아래: 선택한 Pending Pod의 Describe/FailedScheduling 이벤트.
  캡션: 운영자가 Pod 상태와 스케줄링 이벤트를 확인하는 화면.
- 02-tower-answer-and-evidence.png (2520x1050)
  왼쪽: 저장된 모델의 주장과 인용 ID. 오른쪽: 동일 실행에서 인용한 eBPF 증거.
  캡션: 저장된 RCA 실행의 분석 결과와 인용 증거를 연결해 확인하는 화면.
- 03-tower-retrieval-history.png (1260x1050)
  동일 실행에서 실제로 조회한 6개 자료의 기록. inspect 한 번에 요청한 6개 자료이며 LLM 6회 호출을 뜻하지 않음.

확대용 원본
- 02a-tower-answer.png: 모델 답변 부분
- 02b-tower-ebpf-evidence.png: eBPF 증거 부분
- 04-tower-incident-overview.png: 선택 사건의 저장된 원인 요약, 토큰/비용 및 탐색 화면

내용과 시점
K9s는 2026-11-06의 현재 상태이며, Pending Pod는 컨테이너가 시작되지 않아 애플리케이션 로그를 캡처하지 못했다.
Tower는 2026-10-29에 저장한 포트 불일치 사건을 오프라인으로 열었다. K9s의 현재 Pending 사건을 분석한 결과가 아니다.
Tower 사건: analysis-v3 / 9e4945e7170b4a58
실행: efc0b3de7271822b1552 / selective-ebpf / 반복 0
설정상 목적지 10.233.61.222:8080, 관측된 연결 시도 10.233.61.222:9099, 40회.
eBPF는 연결 시도만 관측했다. TCP 성공·실패, 지연 및 재전송은 측정하지 않았다.
모델의 저장 답변을 그대로 보여 주며 이번 캡처 작업이 답변의 독립적인 정확성 검증을 의미하지 않는다.
화면의 53개 사건 구성/214개 조사 숫자는 독립 장애 수가 아니다.

원본 연결
저장소 rca/control-tower/archive.json의 위 case_id/run_id를 기준으로 조회한다.
인용 ID: eBPF ev-a95c551872117dfc1836, 설정 ev-d746a0bf5e594fdc022b, 로그 ev-56e93b3b171d6a27a4a8.
파일별 SHA-256, 캡처 시각, 원본 해시는 capture-manifest.json에 있다.

촬영 방법
실제 K9s와 tower.py를 Zutty 터미널로 Xvfb 가상 화면에서 실행하고 화면 영역을 PNG로 캡처했다.
나란히/위아래 놓인 창은 같은 실제 데스크톱의 동시 캡처다. 출력 내용을 다시 그리거나 모델 답변을 편집하지 않았다.
K9s는 읽기 전용, Tower는 --offline. 새로운 LLM API 호출 및 클러스터 변경은 수행하지 않았다.
캡처 후 이번 촬영에 사용한 터미널과 Xvfb 프로세스를 종료했다.

확인
모든 PNG를 실제로 열어 확인했고 PNG 파일 검증, 원본 아카이브·실행 코드 해시 일치 및 ZIP 검증을 수행했다.
