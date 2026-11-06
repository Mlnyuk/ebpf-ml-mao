#!/usr/bin/env python3
"""Build portable operator console, preserving all archived runs and failures."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_v4.booth import read_viewer
from scripts.package_next import check_bytes

README = '''RCA CONTROL TOWER

현재 클러스터와 저장 사건을 한 화면에서 선택하는 터미널 관제 프로그램입니다.
Python 3.9 이상. 라이브 연결에는 기존 kubectl과 kubeconfig가 필요합니다.
운영 Agent를 시작하거나 설정을 바꾸지 않습니다. 새 LLM 호출도 하지 않습니다.

실행 (이 폴더에서):
  python3 tower.py
오프라인 (kubectl/인터넷/API 키 없이):
  python3 tower.py --offline
한 번 조회해 텍스트로 출력:
  python3 tower.py --snapshot
Windows Terminal에서는 python3 대신 py -3를 사용합니다. Windows/macOS 실기 검증은 미실시입니다.

권장 크기: 120열 × 34행. 한글을 표시하는 고정폭 글꼴을 사용하세요.

1: 현재 클러스터 / 2: 저장 사건 보관함
↑↓ 또는 j/k: Pod·사건 선택 / Enter: 상세 원문
l: 로그 / v: 이벤트 / e: eBPF 연결 시도 / s: 저장된 설정 증거
c: 현재 Pod의 컨테이너 변경
[: 이전 저장 실행 / ]: 다음 저장 실행 / t: 저장된 도구 호출
/: 검색 (영문 입력) / Esc: 원문 닫기 또는 검색 해제
r: 현재 상태 갱신 / q: 종료
원문 창에서는 ↑↓·PgUp·PgDn으로 스크롤합니다. 라이브 조회는 o로 기술 상세를 펼칩니다.

실시간 범위:
- 노드 상태, rca-lab·rca-system Pod, RCA Agent·요약기 상태를 15초마다 읽습니다.
- l/v/e를 누를 때만 선택 Pod/컨테이너의 로그·이벤트·요약기를 조회합니다.
- Pod UID와 컨테이너 실행 ID를 조회 전후 확인합니다.
- e는 실행 중인 기존 요약기의 /state/latest.json을 cat으로 읽는 고정 명령입니다.
  새 수집기/정책을 시작하지 않습니다. 연결 시도와 성공·실패를 구분합니다.
- 수집기 Ready는 원본 수집 성공을 뜻하지 않습니다. 자료 없음·수집 실패·기간 만료를 구분합니다.
- 비동기 조회 중 대상을 바꾸면 이전 대상의 결과를 현재 대상으로 표시하지 않습니다.
- 실행 중에만 갱신합니다. 서비스·자동 재실행을 등록하지 않습니다.
  종료 시 진행 중인 읽기 요청이 끝날 때까지 최대 수 초 기다릴 수 있습니다.

보관함 범위:
analysis-v3와 paper-next-v1의 실제 53개 사건 구성, 214개 실행을 보존합니다.
이는 독립 장애 53회라는 뜻이 아닙니다. 종속 변형·LLM 반복이 포함되어 있습니다.
실행 실패 4건도 포함됩니다. 출력 완료를 원인 정확도나 서비스 복구로 표시하지 않습니다.
현재 클러스터 자료와 과거 조사 결과를 자동으로 연결하지 않습니다.
정답표는 포함하지 않습니다. archive.json의 기존 실행/증거/실패를 그대로 사용합니다.
새 유료 AI 조사는 비활성화 상태이며 이 콘솔에서 활성화할 수 없습니다.

판넬용 확대 보기 (항상 저장 기록 재생, API·클러스터 접속 없음):
  python3 tower.py --panel-run efc0b3de7271822b1552 --panel-claim 2
91열 × 17행 이상, 1600×600 캡처에서는 큰 글꼴 사용. q 종료.
지정한 기존 주장의 문장과 인용한 설정·연결 시도 증거만 표시합니다.
'''


def package(output):
    archive = {'mode': 'archive', 'studies': []}; hashes = {}
    for name in ('analysis-v3', 'paper-next-v1'):
        source = ROOT.parent/'paper-results/2026-10-29'/name/'viewer/index.html'
        data = read_viewer(source)
        cases = [{'case_id': c['case_id'], 'incident': c['incident']} for c in data['cases']]
        archive['studies'].append({'name': name, 'cases': cases, 'runs': data['runs']})
        hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    raw = json.dumps(archive, ensure_ascii=False, separators=(',', ':'))
    check_bytes(raw.encode(), 'archive.json')
    output.mkdir(parents=True, exist_ok=False)
    for src, dst in [('control_tower.py', 'tower.py'), ('tower_source.py', 'tower_source.py'), ('terminal.py', 'terminal.py')]:
        shutil.copyfile(ROOT/'research_v4'/src, output/dst)
    (output/'archive.json').write_text(raw, encoding='utf-8')
    (output/'README.txt').write_text(README, encoding='utf-8')
    manifest = {'version': 'control-tower-panel-20261106', 'source_sha256': hashes,
                'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()},
                'live_access': 'read-only nodes, scoped pods, logs, events and existing collector snapshot',
                'paid_actions': False, 'mutations': False,
                'archive_cases': sum(len(s['cases']) for s in archive['studies']),
                'archive_runs': sum(len(s['runs']) for s in archive['studies'])}
    (output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    return archive


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); package(args.output)
    print('python3 ' + str(args.output/'tower.py'))
