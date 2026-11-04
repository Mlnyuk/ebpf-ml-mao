#!/usr/bin/env python3
"""Offline RCA terminal exhibit. Python standard library only; no live execution."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import sys
import time
import unicodedata

COLORS = {'plain': '37', 'muted': '90', 'title': '1;36', 'good': '36',
          'warn': '1;33', 'selected': '30;46'}
TITLES = {'get_workload_status': '서비스 설정', 'get_k8s_events': 'Kubernetes 이벤트',
          'get_logs': '애플리케이션 로그', 'metrics_cpu': 'CPU 표본',
          'metrics_memory': '메모리 표본', 'get_ebpf_summary': 'eBPF 연결 시도'}


def safe(text):
    """Stored telemetry cannot emit terminal controls, OSC links or bidi controls."""
    return ''.join(('\\u%04x' % ord(c)) if unicodedata.category(c).startswith('C') else c
                   for c in str(text))


def cells(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in 'WF'
               else 1 for c in text)


def clip(text, width):
    result = ''; used = 0
    for c in text:
        n = cells(c)
        if used + n > width:
            break
        result += c; used += n
    return result


def wrap(text, width):
    text = safe(text)
    result = []; part = ''; used = 0
    for c in text:
        n = cells(c)
        if used + n > width:
            result.append(part); part = ''; used = 0
        part += c; used += n
    return result + [part]


@dataclass
class Row:
    text: str
    tone: str = 'plain'


def panel(title, rows, width):
    inner = width - 4
    heading = '─ ' + safe(title) + ' '
    result = [Row('┌' + clip(heading, width - 2) + '─' * max(0, width - 2 - cells(heading)) + '┐', 'good')]
    for row in rows:
        if isinstance(row, str):
            row = Row(row)
        for part in wrap(row.text, inner):
            result.append(Row('│ ' + part + ' ' * (inner - cells(part)) + ' │', row.tone))
    result.append(Row('└' + '─' * (width - 2) + '┘', 'muted'))
    return result


def source_key(e):
    if e.get('source_key'):
        return e['source_key']
    if e['tool'] == 'get_metrics':
        return 'metrics_memory' if 'working_set_bytes' in e.get('series', {}) else 'metrics_cpu'
    return e['tool']


class Exhibit:
    def __init__(self, data):
        self.data = data
        cfg = data['demo']
        self.run = next(r for r in data['runs'] if r['run_id'] == cfg['primary_run_id'])
        self.baseline = next((r for r in data['runs'] if r['run_id'] == cfg.get('baseline_run_id')), None)
        self.incident = next(c['incident'] for c in data['cases'] if c['case_id'] == self.run['case_id'])
        self.evidence = {e['evidence_id']: e for e in self.run['evidence']}
        self.sources = {source_key(e): e for e in self.run['evidence']}
        self.log = self.evidence[cfg['log_evidence_id']]
        self.net = self.sources['get_ebpf_summary']
        self.settings = self.sources['get_workload_status']
        self.declared = json.loads(self.settings['data']['declared_dependency'])
        self.attempts = self.net['network']['tcp_connect_attempts']
        self.claim = self.run['answer']['claims'][cfg['claim_index']]
        if not self.log['lines'] or not self.attempts or not self.declared.get('expected_port'):
            raise ValueError('시연에 필요한 실제 로그·설정·연결 시도 기록이 없습니다.')
        if any(i not in self.evidence for i in self.claim['evidence_ids']):
            raise ValueError('AI 판단의 인용 원문을 찾을 수 없습니다.')
        if {self.settings['evidence_id'], self.net['evidence_id']} != set(self.claim['evidence_ids']):
            raise ValueError('선정된 판단의 인용 구성이 달라졌습니다.')
        if self.baseline and (self.baseline['case_id'] != self.run['case_id'] or
                              self.baseline['repeat'] != self.run['repeat']):
            raise ValueError('같은 사건·반복의 비교 기록이 아닙니다.')
        self.failures = sum('status=503' in line for line in self.log['lines'])
        self.stage = 0; self.scroll = 0; self.raw = None; self.raw_scroll = 0
        self.raw_seek = ''; self.running = True

    def fact(self, e):
        if not e or e.get('availability') != 'available':
            return '자료 미확보 · 정상 여부 미확인'
        k = source_key(e)
        if k == 'get_workload_status':
            return f"{self.declared['expected_ip']}:{self.declared['expected_port']} 선언"
        if k == 'get_k8s_events':
            return f"{len(e.get('events', []))}개 이벤트 · 요청 결과와 별개"
        if k == 'get_logs':
            return f'{self.failures}줄의 오류 응답 로그 · 목적지 없음'
        if k == 'get_ebpf_summary':
            return f"{sum(a['attempts'] for a in self.attempts)}회 연결 시도 · 결과 미측정"
        s = e.get('series', {}).get('usage_cores', e.get('series', {}).get('working_set_bytes', {}))
        count = s.get('samples', len(s.get('points', [])))
        return f'{count}개 표본 · 표본 사이 상태 미확인'

    def ports(self):
        result = [Row(f"설정상 목적지    {self.declared['expected_ip']}:{self.declared['expected_port']}", 'good')]
        result += [Row(f"실제 연결 시도   {a['destination_ip']}:{a['destination_port']}    {a['attempts']}회", 'warn')
                   for a in self.attempts]
        result.append(Row('관측 범위: 연결 시도만. 성공·실패, 지연, 재전송은 미측정.', 'muted'))
        return result

    def body(self, width):
        out = []
        def add(title, rows):
            out.extend(panel(title, rows, width)); out.append(Row(''))
        if self.stage == 0:
            add('INCIDENT / 장애 상황', [Row('서비스 요청이 실패했습니다. 어디에서 문제가 생겼을까요?', 'warn'),
                f"대상  {self.incident['pod']} / {self.incident['container_name']}",
                '이 로그만으로는 연결하려던 주소와 포트를 알 수 없습니다.'])
            lines = self.log['lines']
            start = self.data['demo']['log_line_index']
            logs = [Row('UTC            MESSAGE', 'muted')]
            for line in lines[start:start + 4]:
                stamp, _, payload = line.partition(' ')
                try:
                    message = json.loads(payload)['message']
                except (ValueError, KeyError, TypeError):
                    message = payload or line
                logs.append(Row(stamp[11:23] + '   ' + str(message)))
            logs.append(Row('[l] 시각·메시지를 발췌했습니다. 로그 원문 전체 열기', 'good'))
            add('APPLICATION LOG / 실제 저장 로그', logs)
            add('조사의 출발점', [f'캡처된 로그 {len(lines)}줄 중 오류 응답 로그 {self.failures}줄.',
                '전체 요청 수나 오류율을 뜻하지 않습니다.',
                Row('Enter → AI가 실제로 조회한 자료 보기', 'good')])
        elif self.stage == 1:
            rows = []
            for i, r in enumerate(self.run['retrievals'], 1):
                name = TITLES.get(r['source'], r['source'])
                rows.append(Row(f"{i:02d}  {name}" + ' ' * max(1, 22 - cells(name)) + self.fact(self.sources.get(r['source'])),
                                'warn' if r['source'] == 'get_ebpf_summary' else 'plain'))
            add('INVESTIGATION / 실제 조회 순서', rows)
            out.append(Row('  저장된 묶음 조회의 순서입니다. 단계별 새 LLM 호출이 아닙니다.', 'muted')); out.append(Row(''))
            add('DESTINATION / 로그에 없던 단서', self.ports())
            out.append(Row('  Enter → AI 판단     t → 저장된 도구 호출 원문', 'good'))
        elif self.stage == 2:
            add('EVIDENCE / 설정과 관측', self.ports())
            add('AI FINDING / 저장된 AI 판단', [Row(self.claim['text'], 'warn'),
                Row('이 문장은 저장된 AI의 추정입니다. 연결 결과와 설정 변경의 출처는 미확인입니다.', 'muted')])
            add('CITATIONS / 관람객이 직접 확인', [Row('[e] eBPF 연결 시도 원문    [s] 서비스 설정 원문', 'good'),
                '실제로 인용한 원문의 해당 부분이 열립니다. Esc로 돌아옵니다.',
                Row('Enter → 같은 사건의 eBPF 포함·제외 결과 비교', 'good')])
        else:
            if self.baseline:
                answer = self.baseline.get('answer') or {}
                unknown = next((s for s in answer.get('unknowns', []) if '목적지' in s),
                               next(iter(answer.get('unknowns', [])), '저장된 미확인 설명이 없습니다.'))
                label = '원인 판단 보류' if answer.get('status') == 'inconclusive' else '저장된 답변 확인'
                add('WITHOUT eBPF / 같은 사건', [Row(label, 'muted'), unknown,
                    Row('[b] 제외 실행의 AI 답변 전체', 'good')])
                add('WITH eBPF / 같은 사건', [Row(self.claim['text'], 'warn'),
                    Row('[a] 포함 실행의 AI 답변 전체', 'good')])
                out.extend(Row(s, 'muted') for s in wrap('  동일 사건·선택 조회·반복 번호의 한 사례입니다. 전체 성능을 입증하는 비교는 아닙니다.', width))
            else:
                add('LOG / eBPF 정보 비교', ['같은 사건의 제외 실행이 없어 자료의 정보 차이만 보여줍니다.',
                    '로그: 연결 목적지 없음', *self.ports()])
            out.append(Row(''))
            out.append(Row('  r 또는 Enter → 처음으로 / 다음 관람객', 'good'))
        return out

    def open_raw(self, key):
        items = {'e': ('eBPF 연결 시도 · AI 인용 원문', self.net, '"destination_port"'),
                 's': ('서비스 설정 · AI 인용 원문', self.settings, '"declared_dependency"'),
                 'l': ('애플리케이션 로그 · 저장 원문', self.log, '"lines"'),
                 'a': ('eBPF 포함 · 저장된 AI 답변', self.run['answer'], '"claims"'),
                 't': ('저장된 도구 호출', {'retrievals': self.run['retrievals'], 'trace': self.run['trace']}, '"retrievals"')}
        if self.baseline:
            items['b'] = ('eBPF 제외 · 저장된 AI 답변', self.baseline['answer'], '"unknowns"')
        if key not in items:
            return
        title, obj, needle = items[key]
        if key in 'esl':
            index = self.run['evidence'].index(obj)
            source = f"records.json / runs/{self.data['runs'].index(self.run)}/evidence/{index}"
        else:
            chosen = self.baseline if key == 'b' else self.run
            source = f"records.json / runs/{self.data['runs'].index(chosen)}/" + ('trace + retrievals' if key == 't' else 'answer')
        self.raw = {'title': title, 'object': obj, 'source': source, 'needle': needle}
        self.raw_seek = needle; self.raw_scroll = 0

    def raw_rows(self, width):
        result = []
        for i, line in enumerate(json.dumps(self.raw['object'], ensure_ascii=False, indent=2).splitlines(), 1):
            highlighted = self.raw['needle'] in line
            for j, part in enumerate(wrap(line, max(1, width - 8))):
                prefix = f'{i:4}  ' if j == 0 else '      '
                result.append(Row(prefix + part, 'warn' if highlighted else 'plain'))
        if self.raw_seek:
            self.raw_scroll = max(0, next((i for i, row in enumerate(result) if row.tone == 'warn'), 0) - 3)
            self.raw_seek = ''
        return result

    def key(self, key, page=12):
        if key == 'q' or key == '\x03':
            self.running = False; return
        if key == 'r':
            self.stage = 0; self.scroll = 0; self.raw = None; self.raw_scroll = 0; return
        if self.raw:
            if key in ('ESC', '\r', '\n'):
                self.raw = None
            elif key in ('j', 'DOWN', 'k', 'UP', 'PGDN', 'PGUP'):
                delta = {'j': 1, 'DOWN': 1, 'k': -1, 'UP': -1, 'PGDN': page, 'PGUP': -page}[key]
                self.raw_scroll = max(0, self.raw_scroll + delta)
            return
        if key in ('e', 's', 'l', 'a', 'b', 't'):
            self.open_raw(key)
        elif key in (' ', '\r', '\n', 'RIGHT'):
            self.stage = (self.stage + 1) % 4; self.scroll = 0
        elif key in ('LEFT', '\x7f', '\b'):
            self.stage = max(0, self.stage - 1); self.scroll = 0
        elif key in ('1', '2', '3', '4'):
            self.stage = int(key) - 1; self.scroll = 0
        elif key in ('j', 'DOWN', 'k', 'UP', 'PGDN', 'PGUP'):
            delta = {'j': 1, 'DOWN': 1, 'k': -1, 'UP': -1, 'PGDN': page, 'PGUP': -page}[key]
            self.scroll = max(0, self.scroll + delta)

    def screen(self, width, height):
        width = max(0, width - 1)  # avoid terminal autowrap at the last column
        if width < 71 or height < 20:
            return [Row(clip(s, width), 'warn') for s in ['RCA / 저장 기록 재생', '터미널을 72열 × 20행 이상으로 넓혀 주세요.',
                                           '권장: 110열 × 32행 / q: 종료']][:height]
        rows = [Row(' RCA / TERMINAL CONSOLE    저장 기록 재생    OFFLINE · 새 API 호출 0', 'title'),
                Row(f" {self.incident['namespace']} / {self.incident['node']} / {self.incident['container_name']}"
                    f"    {self.incident['time'][:19]} UTC", 'muted')]
        if self.raw:
            rows += [Row(' ' + self.raw['title'], 'selected'), Row(' ' + self.raw['source'], 'muted')]
            content = self.raw_rows(width); offset = self.raw_scroll
        else:
            names = ['1 장애', '2 조사', '3 판단·근거', '4 비교']
            rows += [Row(' ' + '    '.join('[' + n + ']' if i == self.stage else n for i, n in enumerate(names)), 'good'),
                     Row('─' * width, 'muted')]
            content = self.body(width); offset = self.scroll
        available = height - len(rows) - 3
        offset = min(offset, max(0, len(content) - available))
        if self.raw:
            self.raw_scroll = offset
        else:
            self.scroll = offset
        rows += content[offset:offset + available]
        rows += [Row('')] * (height - 3 - len(rows))
        position = f' {offset + 1}–{min(offset + available, len(content))}/{len(content)}행'
        rows.append(Row('─' * max(0, width - cells(position)) + position, 'muted'))
        rows.append(Row(' Esc 돌아가기   ↑↓/j k 스크롤   PgUp/PgDn   r 처음으로   q 종료' if self.raw else
                        ' Enter 다음   1–4 이동   e 관측 원문   s 설정 원문   r 처음으로   q 종료', 'good'))
        rows.append(Row(' 원본은 records.json에 보존됩니다.' if self.raw else
                        ' ↑↓/j k 스크롤   l 로그   a/b AI 답변   t 도구 호출   연결 결과 미측정', 'muted'))
        return [Row(clip(safe(row.text), width), row.tone) for row in rows]


def frame(rows, color=True):
    if not color:
        return '\n'.join(row.text for row in rows)
    return '\n'.join('\x1b[' + COLORS[row.tone] + 'm' + row.text + '\x1b[0m' for row in rows)


@contextmanager
def terminal():
    """Restore both screen and input mode even on Ctrl-C or rendering failure."""
    restore = None
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.windll.kernel32
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetConsoleMode.restype = wintypes.BOOL
        kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.SetConsoleMode.restype = wintypes.BOOL
        handle = kernel.GetStdHandle(-11); old = ctypes.c_ulong()
        if not kernel.GetConsoleMode(handle, ctypes.byref(old)) or not kernel.SetConsoleMode(handle, old.value | 4):
            raise OSError('Windows Terminal에서 실행해 주세요.')
        restore = lambda: kernel.SetConsoleMode(handle, old.value)
    else:
        import termios
        import tty
        fd = sys.stdin.fileno(); old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        restore = lambda: termios.tcsetattr(fd, termios.TCSADRAIN, old)
    try:
        sys.stdout.write('\x1b[?1049h\x1b[?25l'); sys.stdout.flush()
        yield
    finally:
        try:
            sys.stdout.write('\x1b[0m\x1b[?25h\x1b[?1049l'); sys.stdout.flush()
        finally:
            if restore:
                restore()


class Keyboard:
    def __init__(self):
        self.pending = b''

    def read(self):
        if os.name == 'nt':
            import msvcrt
            if not msvcrt.kbhit():
                time.sleep(.05); return None
            char = msvcrt.getwch()
            if char in ('\x00', '\xe0'):
                return {'H': 'UP', 'P': 'DOWN', 'K': 'LEFT', 'M': 'RIGHT', 'I': 'PGUP', 'Q': 'PGDN'}.get(msvcrt.getwch())
            return 'ESC' if char == '\x1b' else char.lower()
        import select
        if not self.pending:
            if not select.select([sys.stdin], [], [], .2)[0]:
                return None
            self.pending = os.read(sys.stdin.fileno(), 64)
            if not self.pending:
                return 'q'
        sequences = {b'\x1b[A': 'UP', b'\x1b[B': 'DOWN', b'\x1b[C': 'RIGHT', b'\x1b[D': 'LEFT',
                     b'\x1b[5~': 'PGUP', b'\x1b[6~': 'PGDN'}
        if self.pending.startswith(b'\x1b'):
            # Arrow escape sequences may arrive in separate reads.
            while any(s.startswith(self.pending) and s != self.pending for s in sequences):
                if not select.select([sys.stdin], [], [], .04)[0]:
                    break
                more = os.read(sys.stdin.fileno(), 64)
                if not more:
                    break
                self.pending += more
            for seq, name in sequences.items():
                if self.pending.startswith(seq):
                    self.pending = self.pending[len(seq):]; return name
            self.pending = self.pending[1:]; return 'ESC'
        char, self.pending = self.pending[:1], self.pending[1:]
        return char.decode('ascii', errors='ignore').lower() or None


def main(argv=None):
    p = argparse.ArgumentParser(description='인터넷·API 없이 실행하는 실제 RCA 저장 기록 시연')
    p.add_argument('--data', type=Path, default=Path(__file__).with_name('records.json'))
    p.add_argument('--snapshot', type=int, choices=range(1, 5), help='해당 화면을 텍스트로 출력하고 종료')
    p.add_argument('--width', type=int, default=110, help='snapshot 열 수')
    p.add_argument('--height', type=int, default=32, help='snapshot 행 수')
    p.add_argument('--no-color', action='store_true')
    args = p.parse_args(argv)
    try:
        show = Exhibit(json.loads(args.data.read_text(encoding='utf-8')))
    except (OSError, ValueError, KeyError, IndexError, TypeError, StopIteration) as exc:
        print('저장 기록을 열 수 없습니다. 예시로 대체하지 않습니다: ' + safe(exc), file=sys.stderr)
        return 2
    if args.snapshot:
        show.stage = args.snapshot - 1
        print(frame(show.screen(max(1, args.width), max(1, args.height)), color=False)); return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print('대화형 터미널에서 실행해 주세요. 텍스트 확인: --snapshot 1', file=sys.stderr); return 2
    color = not args.no_color and 'NO_COLOR' not in os.environ
    keyboard = Keyboard(); last = None
    try:
        with terminal():
            while show.running:
                size = shutil.get_terminal_size((110, 32))
                output = frame(show.screen(size.columns, size.lines), color)
                if output != last:
                    # Position each row separately; independent of ONLCR terminal setting.
                    painted = ''.join(f'\x1b[{i};1H\x1b[2K' + line for i, line in enumerate(output.split('\n'), 1))
                    sys.stdout.write('\x1b[H' + painted + '\x1b[J'); sys.stdout.flush(); last = output
                key = keyboard.read()
                if key:
                    show.key(key, max(1, size.lines - 10))
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        print('터미널 오류: ' + safe(exc), file=sys.stderr); return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
