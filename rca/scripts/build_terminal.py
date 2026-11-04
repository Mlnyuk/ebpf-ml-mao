#!/usr/bin/env python3
"""Package the existing reviewed saved-run pair for the standalone terminal demo."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_v4.booth import read_viewer, select_demo
from research_v4.terminal import Exhibit

README = '''RCA Terminal Console — 저장 기록 재생

Python 3.9 이상만 필요합니다. pip 설치·인터넷·API 키·클러스터 연결은 필요 없습니다.
이 폴더 전체를 복사하고 터미널에서 실행하세요.

Linux / macOS:
  python3 rca_demo.py
Windows Terminal / PowerShell:
  py -3 rca_demo.py

권장 크기: 110열 × 32행 이상. 글자가 작으면 터미널 글꼴 크기를 조절하세요.
한글이 표시되는 고정폭 글꼴을 사용하세요. Windows 환경은 직접 검증하지 못했습니다.

행사 진행: Enter → Enter → e (원문 확인) → Esc → Enter (비교) → r
Enter 또는 Space: 다음 화면 / 1~4: 화면 바로 이동 / r: 처음으로 / q: 종료
e: eBPF 인용 원문 / s: 설정 인용 원문 / l: 로그 원문
a: 포함 실행의 AI 답변 / b: 제외 실행의 AI 답변 / t: 도구 호출 원문
↑↓ 또는 j/k, PgUp/PgDn: 스크롤 / Esc: 원문 닫기
단축키는 영문 입력 상태에서 사용하세요.

텍스트로 확인하거나 저장할 때:
  python3 rca_demo.py --snapshot 3 --width 110 --height 32

대표 사건: 9e4945e7170b4a58
포함 실행: efc0b3de7271822b1552 / 제외 실행: 6c938d099e296bd28fa6
로그에 목적지가 없지만 eBPF 기록에 연결 시도 주소·포트가 있는 실제 사례입니다.
포트·횟수·AI 판단·인용은 records.json의 원래 저장 기록에서 읽습니다.
현재 eBPF 증거는 연결 시도 요약입니다. 성공·실패, 지연, 재전송은 측정하지 않았습니다.
커널 원시 이벤트 덤프는 이 묶음에 포함하지 않습니다.
장애 발생이나 LLM 호출을 실행하지 않습니다. 운영 클러스터와 통신하지 않습니다.

약 40초 설명:
[1 장애] “실제 장애의 저장 기록입니다. 로그에는 요청 실패가 남지만 연결 목적지는 없습니다.”
[2 조사] “AI가 설정과 관측 자료를 확인했습니다. 설정은 8080번인데 실제 연결 시도는 9099번입니다.”
[3 판단, e] “AI는 이 차이로 포트 불일치를 추정했습니다. 인용한 원문을 직접 확인할 수 있습니다.”
[Esc, Enter → 4 비교] “이 사건에서는 eBPF가 없을 때 목적지를 특정하지 못했습니다.
추가 관측이 원인을 좁힌 사례이며 연결 성공·실패까지 단정하지는 않습니다.”
[r] 다음 관람객에게 처음부터 다시 보여줍니다.
'''


def package(source, output):
    data = select_demo(read_viewer(source))
    Exhibit(data)  # Fail before creating an incomplete bundle.
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(ROOT/'research_v4/terminal.py', output/'rca_demo.py')
    (output/'records.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (output/'README.txt').write_text(README, encoding='utf-8')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())}
    manifest = {'mode': 'offline stored-record replay', 'source_viewer_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'case_id': data['cases'][0]['case_id'], 'primary_run_id': data['demo']['primary_run_id'],
                'baseline_run_id': data['demo']['baseline_run_id'], 'files': hashes,
                'external_requests': False, 'api_calls': 0, 'kernel_raw_export_included': False}
    (output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT.parent/'paper-results/2026-10-29/analysis-v3/viewer/index.html')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package(args.source, args.output)
    print(f'실행: python3 {args.output}/rca_demo.py')
