#!/usr/bin/env python3
"""Small operator console: current cluster + incident archive, no paid actions."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
from pathlib import Path
import shutil
import sys
import time

try:
    from .terminal import Row, cells, clip, frame, panel, safe, terminal, Keyboard, wrap
    from .tower_source import KubeSource, ReadError, redact
except ImportError:
    from terminal import Row, cells, clip, frame, panel, safe, terminal, Keyboard, wrap
    from tower_source import KubeSource, ReadError, redact

STATE = {'accepted': '출력 완료', 'error': '실행 실패', 'resolved': '원인 제시',
         'inconclusive': '판단 보류', 'no_fault_supported': '장애 근거 없음'}


def fit(text, width):
    text = safe(text)
    if cells(text) > width:
        text = clip(text, width - 1) + '…'
    return text + ' ' * max(0, width - cells(text))


def columns(left, right, width):
    half = (width - 2) // 2
    return [Row(fit(left[i].text if i < len(left) else '', half) + '  ' +
                fit(right[i].text if i < len(right) else '', width - half - 2),
                left[i].tone if i < len(left) and left[i].tone == 'selected' else
                right[i].tone if i < len(right) else 'plain')
            for i in range(max(len(left), len(right)))]


class Tower:
    def __init__(self, archive, offline=False):
        self.archive = archive; self.offline = offline; self.mode = 'archive' if offline else 'live'
        self.inventory = {'nodes': [], 'pods': [], 'system': [], 'sources': {}, 'observed_at': None}
        self.cases = []
        for study in archive.get('studies', []):
            for case in study['cases']:
                runs = [r for r in study['runs'] if r['case_id'] == case['case_id']]
                runs.sort(key=lambda r: (r['arm'] not in ('selective', 'selective-ebpf'), r['repeat'], r['arm'], r['run_id']))
                self.cases.append({'study': study['name'], 'case': case, 'runs': runs})
        self.cases.sort(key=lambda c: (c['case']['incident']['time'], c['study'], c['case']['case_id']), reverse=True)
        self.selected = 0; self.run_index = 0; self.container_index = 0
        self.filter = ''; self.searching = False; self.modal = None; self.modal_scroll = 0
        self.modal_live = False; self.modal_technical = False
        self.seek = ''; self.notice = ''; self.running = True; self.generation = 0
        self.pending = False; self.refreshing = False
        self.panel_claim = None

    def select_panel(self, run_id, claim_index):
        """Focus an existing archived claim for a short, read-only exhibit view."""
        for i, entry in enumerate(self.cases):
            for j, run in enumerate(entry['runs']):
                if run['run_id'] == run_id:
                    claims = (run.get('answer') or {}).get('claims', [])
                    if not 0 <= claim_index < len(claims):
                        raise ValueError('저장된 주장 번호를 찾을 수 없습니다.')
                    self.selected = i; self.run_index = j; self.panel_claim = claim_index
                    self.offline = True; self.mode = 'archive'
                    return
        raise ValueError('저장된 실행 ID를 찾을 수 없습니다.')

    def panel_screen(self, width, height):
        """Quote a stored claim and only its cited, retrieved destination evidence."""
        width = max(0, width - 1)
        if width < 90 or height < 17:
            return [Row('판넬 보기: 91열 × 17행 이상으로 넓혀 주세요.', 'warn')][:height]
        run = self.selected_run(); entry = self.selected_entry()
        claim = run['answer']['claims'][self.panel_claim]
        evidence = {e['evidence_id']: e for e in run['evidence']}
        cited = [evidence[i] for i in claim['evidence_ids'] if i in evidence]
        settings = next((e for e in cited if e['tool'] == 'get_workload_status'), None)
        net = next((e for e in cited if e['tool'] == 'get_ebpf_summary'), None)
        incident = entry['case']['incident']
        out = [Row(' RCA CONTROL TOWER  |  저장 기록 재생  |  새 API 호출 없음', 'title'),
               Row(' ' + incident['time'][:19].replace('T', ' ') + ' UTC  /  ' + incident['pod'], 'muted'),
               Row('─' * width, 'muted'),
               Row(' AI 주장 · 저장된 문장 인용 / ' + str(claim['kind']), 'good')]
        out += [Row(' ' + s, 'warn') for s in wrap(claim['text'], width - 2)]
        out.append(Row(''))
        left = [Row('인용한 설정 자료 없음', 'warn')]
        if settings and settings.get('availability') == 'available':
            try:
                declared = settings['data']['declared_dependency']
                declared = json.loads(declared) if isinstance(declared, str) else declared
                left = [Row(f"{declared['expected_ip']} : {declared['expected_port']}", 'warn'),
                        '출처: 선언된 의존성 · Service 주소 매핑', settings['evidence_id']]
            except (KeyError, ValueError, TypeError):
                left = [Row('설정상 목적지 해석 불가 · 원문 확인 필요', 'warn')]
        elif settings:
            left = [Row('설정 자료: ' + str(settings.get('availability', '미확인')), 'warn')]
        right = [Row('인용한 연결 시도 자료 없음', 'warn')]
        if net and net.get('availability') == 'available':
            attempts = net.get('network', {}).get('tcp_connect_attempts', [])
            right = [Row(f"{a['destination_ip']} : {a['destination_port']}  /  {a['attempts']}회", 'warn')
                     for a in attempts]
            if not attempts:
                right = [Row('관측된 연결 시도 0건 · 정상 판정 아님', 'warn')]
            right += ['출처: Tetragon 연결 시도 요약', net['evidence_id']]
        elif net:
            right = [Row('연결 시도 자료: ' + str(net.get('availability', '미확인')), 'warn')]
        half = (width - 2) // 2
        out += columns(panel('설정상 목적지 / 인용 증거', left, half),
                       panel('관측된 연결 시도 / 인용 증거', right, width - half - 2), width)
        names = {'get_workload_status': '설정', 'get_k8s_events': '이벤트', 'get_logs': '로그',
                 'metrics_cpu': 'CPU', 'metrics_memory': '메모리', 'get_ebpf_summary': 'eBPF'}
        order = ' → '.join(names.get(r['source'], r['source']) for r in run['retrievals'] if r.get('executed'))
        out += [Row(''), *[Row(' 조회 기록: ' + s, 'good') for s in wrap(order, width - 13)]]
        for line in (' 연결 성공·실패, 지연, 재전송: 미측정. 저장된 AI 주장은 독립 검증 결과가 아닙니다.',
                     ' [q] 종료  ·  원문은 일반 보기의 Enter / e / s / t에서 확인'):
            out += [Row(s, 'muted') for s in wrap(line, width)]
        if len(out) > height:
            return [Row('자료를 생략하지 않도록 터미널 높이를 늘려 주세요.', 'warn'),
                    Row(f'필요 {len(out)}행 / 현재 {height}행', 'muted')]
        return [Row(clip(safe(r.text), width), r.tone) for r in out]

    def entries(self):
        items = self.cases if self.mode == 'archive' else self.inventory['pods']
        if not self.filter:
            return items
        return [x for x in items if self.filter.lower() in json.dumps(
            {'study': x['study'], **x['case']['incident']} if self.mode == 'archive' else x, ensure_ascii=False).lower()]

    def selected_entry(self):
        entries = self.entries(); self.selected = min(self.selected, max(0, len(entries) - 1))
        return entries[self.selected] if entries else None

    def selected_run(self):
        entry = self.selected_entry()
        return entry['runs'][self.run_index % len(entry['runs'])] if entry and entry['runs'] else None

    def set_inventory(self, inventory):
        entry = self.selected_entry() if self.mode == 'live' else None
        self.inventory = inventory
        if entry:
            self.selected = next((i for i, p in enumerate(self.entries()) if p['uid'] == entry['uid']), 0)
            new = self.selected_entry()
            if not new or new['uid'] != entry['uid'] or new['containers'] != entry['containers']:
                self.generation += 1

    def raw(self, title, value, needle='', live=False):
        self.modal = (title, value, needle); self.modal_scroll = 0; self.seek = needle
        self.modal_live = live; self.modal_technical = False

    def archive_action(self, key):
        run = self.selected_run()
        if not run:
            self.notice = '저장된 실행이 없습니다.'; return
        if key in ('\r', '\n', 'a'):
            self.raw('저장된 AI 답변 · 현재 장애의 판단이 아님', {'run_id': run['run_id'], 'state': run['state'],
                      'answer': run['answer'], 'error': run['error']}); return
        if key == 't':
            self.raw('실제 도구 호출 기록', {'retrievals': run['retrievals'], 'trace': run['trace']}); return
        tool = {'l': 'get_logs', 'v': 'get_k8s_events', 'e': 'get_ebpf_summary', 's': 'get_workload_status'}.get(key)
        items = [e for e in run['evidence'] if e['tool'] == tool]
        if not items:
            self.notice = '이 실행에서는 해당 증거가 조회되지 않았습니다.'; return
        self.raw('해당 실행에서 조회한 증거 · ' + tool, items[0] if len(items) == 1 else {'evidence': items},
                 '"destination_port"' if key == 'e' else '"declared_dependency"' if key == 's' else '')

    def key(self, key, page=12):
        if self.panel_claim is not None:
            if key in ('q', '\x03'):
                self.running = False
            return
        if self.searching:
            if key in ('ESC', '\r', '\n'):
                self.searching = False
            elif key in ('\x7f', '\b'):
                self.filter = self.filter[:-1]
            elif len(key) == 1 and key.isprintable():
                self.filter = (self.filter + key)[:80]
            self.selected = 0; self.run_index = 0; self.generation += 1; return
        if key in ('q', '\x03'):
            self.running = False; return
        if self.modal:
            if key in ('ESC', '\r', '\n'):
                self.modal = None; self.generation += 1
            elif key == 'o' and self.modal_live:
                self.modal_technical = not self.modal_technical; self.modal_scroll = 0; self.seek = ''
            elif key in ('j', 'DOWN', 'k', 'UP', 'PGDN', 'PGUP'):
                self.modal_scroll = max(0, self.modal_scroll + {'j': 1, 'DOWN': 1, 'k': -1, 'UP': -1, 'PGDN': page, 'PGUP': -page}[key])
            return
        if key in ('1', '2'):
            self.mode = 'live' if key == '1' else 'archive'; self.selected = 0; self.run_index = 0
            self.filter = ''; self.notice = ''; self.generation += 1
        elif key == '/':
            self.searching = True; self.generation += 1
        elif key == 'ESC':
            self.filter = ''; self.selected = 0; self.generation += 1
        elif key in ('j', 'DOWN', 'k', 'UP', 'PGDN', 'PGUP'):
            self.selected = max(0, min(len(self.entries()) - 1, self.selected +
                {'j': 1, 'DOWN': 1, 'k': -1, 'UP': -1, 'PGDN': page, 'PGUP': -page}[key]))
            self.run_index = 0; self.container_index = 0; self.generation += 1; self.notice = ''
        elif key in ('[', ']') and self.mode == 'archive':
            self.run_index += 1 if key == ']' else -1; self.notice = ''
        elif key == 'c' and self.mode == 'live':
            self.container_index += 1; self.generation += 1
        elif key == 'r':
            return 'refresh'
        elif self.mode == 'archive' and key in ('\r', '\n', 'a', 't', 'l', 'v', 'e', 's'):
            self.archive_action(key)
        elif self.mode == 'live' and key in ('\r', '\n'):
            if self.selected_entry():
                self.raw('현재 Pod 상태 · 마지막 조회 시각 ' + str(self.inventory['observed_at']), self.selected_entry())
        elif self.mode == 'live' and key in ('l', 'v', 'e'):
            return {'l': 'logs', 'v': 'events', 'e': 'ebpf'}[key]

    def system_text(self):
        agent = next((s for s in self.inventory['system'] if s['name'] == 'rca-agent'), None)
        collector = next((s for s in self.inventory['system'] if s['name'] == 'rca-ebpf-summary'), None)
        a = '상태 미확인' if agent is None else '중지' if agent['desired'] == 0 else f"{agent['ready']}/{agent['desired']} Ready"
        c = '상태 미확인' if collector is None else f"{collector['ready']}/{collector['desired']} Ready"
        return 'RCA Agent: ' + a, 'eBPF 요약기: ' + c

    def live_body(self, width, height):
        half = (width - 2) // 2; other = width - half - 2
        nodes = self.inventory['nodes']; entries = self.entries()
        nrows = [Row(fit(n['name'], 16) + fit('Ready' if n['ready'] == 'True' else 'NotReady' if n['ready'] == 'False' else 'Unknown', 11)
                     + n['cpu'] + ' CPU', 'plain' if n['ready'] == 'True' else 'warn') for n in nodes[:8]]
        if not nodes:
            nrows = [Row('조회 전 / 실패 · 상태 미확인', 'warn')]
        if len(nodes) > 8:
            nrows.append(Row(f'외 {len(nodes) - 8}개 노드 (상단 합계에 포함)', 'muted'))
        left = panel('NODES / 할당 가능 CPU', nrows, half)
        available = max(2, height - len(left) - 3)
        start = min(max(0, self.selected - available + 1), max(0, len(entries) - available))
        rows = []
        for i in range(start, min(len(entries), start + available)):
            p = entries[i]
            rows.append(Row(('› ' if i == self.selected else '  ') + fit(p['name'], max(12, half - 21)) +
                            ' ' + fit(p['phase'], 11), 'selected' if i == self.selected else 'plain'))
        left += [Row('')] + panel(f'PODS {len(entries)} / ↑↓ 선택', rows or [Row('표시할 Pod 없음 · 조회 상태 확인', 'muted')], half)
        pod = self.selected_entry()
        detail = []
        if pod:
            cs = pod['containers']; c = cs[self.container_index % len(cs)] if cs else None
            detail = [Row(pod['name'], 'title'), pod['namespace'] + ' / ' + pod['node'],
                      f"Ready: {pod['ready']}  누적 재시작: {pod['restarts']}",
                      Row('Ready는 요청 성공을 보장하지 않습니다.', 'muted')]
            if c:
                detail += ['', '컨테이너: ' + c['name'] + '  [c 변경]',
                           Row('[l] 최근 로그   [v] Pod 이벤트', 'good'),
                           Row('[e] 이 컨테이너의 eBPF 연결 시도', 'good')]
            else:
                detail.append(Row('컨테이너 실행 정보 없음', 'warn'))
        else:
            detail = ['선택할 Pod가 없습니다. r로 갱신하세요.']
        right = panel('SELECTED POD', detail, other) + [Row('')]
        right += panel('RCA / TELEMETRY', [*self.system_text(),
            Row('콘솔 AI 실행: 잠금', 'warn'),
            '이 콘솔은 상태·증거를 읽기만 합니다.',
            Row('Collector Ready와 자료 수집 성공은 별개입니다.', 'muted')], other)
        failed = [k for k, v in self.inventory['sources'].items() if v['state'] != 'available']
        if failed:
            right += [Row('조회 실패: ' + ', '.join(failed), 'warn')]
        return columns(left, right, width)[:height]

    def archive_body(self, width, height):
        half = (width - 2) // 2; other = width - half - 2
        entries = self.entries(); run = self.selected_run(); entry = self.selected_entry()
        available = max(1, height - 4)
        start = min(max(0, self.selected - available + 1), max(0, len(entries) - available))
        rows = []
        for i in range(start, min(len(entries), start + available)):
            item = entries[i]; incident = item['case']['incident']; runs = item['runs']
            selected = runs[0] if runs else {}; cause = (selected.get('answer') or {}).get('cause_type', '실패')
            rows.append(Row(('›' if i == self.selected else ' ') + incident['time'][11:19] + ' ' +
                            fit(cause, max(12, half - 24)) + f" {len(runs):2}실행", 'selected' if i == self.selected else 'plain'))
        left = panel(f'INCIDENTS {len(entries)} / ↑↓ 선택', rows or ['일치하는 사건 없음'], half)
        if not run:
            return columns(left, panel('DETAIL', ['저장된 실행 없음'], other), width)
        answer = run.get('answer') or {}
        info = [entry['study'] + ' / ' + entry['case']['incident']['time'][:19],
                Row(run['arm'] + f" · 반복 {run['repeat']}", 'good'),
                '실행: ' + STATE.get(run['state'], run['state']) + ' / 판단: ' + STATE.get(answer.get('status'), '미출력'),
                Row('출력 완료는 원인의 정확도나 서비스 복구를 뜻하지 않음.', 'muted')]
        right = panel('SELECTED INCIDENT', info, other)
        cause = answer.get('confirmed_cause') or (' / '.join(answer.get('unknowns', []))) or str(run.get('error') or '저장된 원인 없음')
        # Summary preview; complete unmodified answer is always available with Enter.
        preview = wrap(cause, other - 4)[:4]
        right += [Row('')] + panel('AI 판단 / 저장된 답변', [*preview, Row('[Enter] 답변 전체 · [ / ] 실행 전환', 'good')], other)
        cost = '비용 미확정' if run.get('cost_usd') is None else f"${run['cost_usd']:.6f}"
        right += [Row('')] + panel('EVIDENCE / 원문', [Row('[e] eBPF  [s] 설정  [l] 로그  [v] 이벤트', 'good'),
            f"{len(run['evidence'])}개 조회 증거 · {run.get('total_tokens', '?')} tokens · {cost}",
            Row('선택한 실행의 자료만 표시 · 새 과금 없음', 'muted')], other)
        return columns(left, right, width)[:height]

    def live_detail(self, title, value, width):
        states = {'available': '관측 자료 있음', 'observed_zero': '일치하는 관측 0건', 'expired': '기간 만료 / 시계 확인 필요',
                  'collection_failed': '원본 수집 실패', 'query_failed': '조회 실패', 'not_collected': '수집 범위 밖 / 범위 미확인'}
        rows = [Row(title, 'title'), Row('상태: ' + states.get(value.get('availability'), '미확인'), 'warn'),
                Row('조회: ' + str(value.get('read_at', '완료하지 못함')), 'muted'), Row('')]
        rows += [Row(s, 'muted') for s in wrap(value.get('scope', ''), width)]
        if value.get('error'):
            rows += [Row(s, 'warn') for s in wrap(value['error'], width)]
        if value.get('availability') == 'observed_zero':
            rows += [Row('조회한 범위에 일치하는 기록이 없습니다. 정상이라는 의미는 아닙니다.', 'warn')]
        rows.append(Row(''))
        for line in value.get('lines', []):
            timestamp, _, payload = line.partition(' ')
            try:
                message = json.loads(payload).get('message')
            except (ValueError, AttributeError):
                message = None
            rows += [Row(s) for s in wrap(timestamp + ' ' + str(message) if message is not None else line, width)]
        for e in value.get('events', []):
            rows += [Row(str(e['time']) + '  ' + str(e['reason']), 'good')]
            rows += [Row(s) for s in wrap(e.get('message') or '', width)]
        if 'tcp_connect_attempts' in value:
            rows.append(Row('DESTINATION                         ATTEMPTS', 'good'))
            rows += [Row(fit(f"{e['destination_ip']}:{e['destination_port']}", 35) + str(e['attempts']))
                     for e in value['tcp_connect_attempts']]
            rows += [Row(''), Row('요약기 시각: ' + str(value.get('captured_at')), 'muted'),
                     Row('연결 성공·실패 / 지연 / 재전송: 미측정', 'warn')]
        rows += [Row(''), Row('[o] 기술 상세 · 수집 식별자와 원문 데이터', 'good')]
        return rows

    def screen(self, width, height):
        if self.panel_claim is not None:
            return self.panel_screen(width, height)
        width = max(0, width - 1)
        if width < 89 or height < 26:
            return [Row(clip(s, width), 'warn') for s in ['RCA CONTROL TOWER', '90열 × 26행 이상으로 넓혀 주세요.',
                                                        '권장 120열 × 34행 / q 종료']][:height]
        mode = 'OFFLINE / 저장 사건' if self.offline else 'LIVE / 읽기 전용' if self.mode == 'live' else 'ARCHIVE / 저장 사건'
        rows = [Row(' RCA CONTROL TOWER   ' + mode + '   AI 신규 호출 OFF', 'title')]
        if self.mode == 'live':
            nodes = self.inventory['nodes']; pods = self.inventory['pods']
            n = f"{sum(x['ready'] == 'True' for x in nodes)}/{len(nodes)}" if self.inventory['sources'].get('nodes', {}).get('state') == 'available' else '미확인'
            pod_ok = any(k.startswith('pods:') and v['state'] == 'available' for k, v in self.inventory['sources'].items())
            p = f"{sum(x['ready'] == 'True' for x in pods)}/{len(pods)}" if pod_ok else '미확인'
            if pod_ok and any(k.startswith('pods:') and v['state'] != 'available' for k, v in self.inventory['sources'].items()):
                p += ' (부분 조회)'
            rows.append(Row(f" Node Ready {n}   RCA Pod Ready {p}   조회 {self.inventory['observed_at'] or '아직 없음'}", 'muted'))
        else:
            total = sum(len(c['runs']) for c in self.cases)
            failed = sum(r['state'] == 'error' for c in self.cases for r in c['runs'])
            rows.append(Row(f' 저장 사건 구성 {len(self.cases)}개 / 조사 {total}건 / 실행 실패 {failed}건 · 독립 장애 수가 아님', 'muted'))
        rows += [Row(' [1] 클러스터    [2] 사건 보관함    / 검색: ' + self.filter + ('▏' if self.searching else ''), 'good'),
                 Row('─' * width, 'muted')]
        available = height - 8
        if self.modal:
            title, obj, needle = self.modal
            if self.modal_live and not self.modal_technical:
                content = self.live_detail(title, obj, width); self.seek = ''
            else:
                content = [Row(title, 'title')]
                for line in json.dumps(obj, ensure_ascii=False, indent=2).splitlines():
                    content += [Row(t, 'warn' if needle and needle in line else 'plain') for t in wrap(line, width)]
            if self.seek:
                self.modal_scroll = max(0, next((i for i, r in enumerate(content) if r.tone == 'warn'), 0) - 3); self.seek = ''
            self.modal_scroll = min(self.modal_scroll, max(0, len(content) - available))
            body = content[self.modal_scroll:self.modal_scroll + available]
        elif self.mode == 'live':
            body = self.live_body(width, available)
        else:
            body = self.archive_body(width, available)
        rows += body[:available]; rows += [Row('')] * (height - 4 - len(rows))
        message = ('조회 중… ' if self.pending else '') + ('상태 갱신 중… ' if self.refreshing else '') + self.notice
        rows += [Row('─' * width, 'muted'), Row(' ' + message, 'warn'),
                 Row(' Esc 닫기  ↑↓/j k 스크롤  PgUp/PgDn  o 기술 상세  q 종료' if self.modal else
                     ' ↑↓ 선택  Enter 상세  l 로그  v 이벤트  e eBPF  r 갱신  / 검색  q 종료', 'good'),
                 Row(' 현재 Ready/NotReady는 Kubernetes 상태입니다. 장애 원인 판단은 아닙니다.' if self.mode == 'live' else
                     ' 과거 사건과 현재 상태를 분리합니다. 독립 수집·변형·반복을 사건 수로 합산하지 마세요.', 'muted')]
        return [Row(clip(safe(r.text), width), r.tone) for r in rows[:height]]


class Session:
    def __init__(self, tower, source):
        self.tower = tower; self.source = source
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.refresh_job = None; self.detail_job = None; self.last_refresh = 0

    def refresh(self):
        if self.source is None:
            self.tower.notice = '오프라인: 클러스터 연결 없이 저장 사건만 사용합니다.'; return
        if self.refresh_job:
            return
        self.tower.refreshing = True; self.last_refresh = time.monotonic()
        self.refresh_job = self.pool.submit(self.source.refresh)

    def inspect(self, kind):
        if self.source is None:
            self.tower.notice = '오프라인에서는 현재 자료를 조회하지 않습니다.'; return
        if self.detail_job:
            self.tower.notice = '현재 조회가 끝난 뒤 다시 시도하세요.'; return
        pod = self.tower.selected_entry()
        if not pod or not pod['containers']:
            self.tower.notice = '조회 가능한 Pod/컨테이너가 없습니다.'; return
        c = pod['containers'][self.tower.container_index % len(pod['containers'])]
        self.tower.pending = True
        job = self.pool.submit(self.source.inspect, kind, pod, c, self.tower.inventory)
        self.detail_job = (job, self.tower.generation, f"LIVE {kind} / {pod['name']} / {c['name']}")

    def poll(self):
        if self.refresh_job and self.refresh_job.done():
            try:
                self.tower.set_inventory(self.refresh_job.result())
            except Exception as e:
                self.tower.notice = '상태 갱신 실패: ' + type(e).__name__
                self.tower.inventory['sources'] = {'refresh': {'state': 'failed'}}
            self.tower.refreshing = False; self.refresh_job = None
        if self.detail_job and self.detail_job[0].done():
            job, generation, title = self.detail_job
            try:
                value = job.result()
            except Exception as e:
                value = {'availability': 'query_failed', 'error': str(e) if isinstance(e, ReadError) else type(e).__name__,
                         'scope': '조회 실패는 정상 상태의 근거가 아닙니다.'}
            if generation == self.tower.generation:
                self.tower.raw(title, value, '"destination_port"', live=True)
            self.detail_job = None; self.tower.pending = False

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='클러스터에 연결하지 않고 사건 보관함만 열기')
    parser.add_argument('--panel-run', help='지정 실행의 판넬용 확대 보기 (항상 오프라인)')
    parser.add_argument('--panel-claim', type=int, default=0, help='확대할 저장 주장 번호 (0부터)')
    parser.add_argument('--archive', type=Path, default=Path(__file__).with_name('archive.json'))
    parser.add_argument('--context', help='현재 context 대신 사용할 kubectl context')
    parser.add_argument('--interval', type=int, default=15, help='실행 중 상태 갱신 간격, 최소 5초')
    parser.add_argument('--snapshot', action='store_true', help='한 번 조회해 현재 화면을 텍스트로 출력')
    parser.add_argument('--width', type=int, default=120); parser.add_argument('--height', type=int, default=34)
    args = parser.parse_args(argv)
    try:
        archive = json.loads(args.archive.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        print('사건 보관함을 열 수 없습니다. archive.json을 확인하세요.', file=sys.stderr); return 2
    tower = Tower(archive, args.offline or bool(args.panel_run))
    if args.panel_run:
        try:
            tower.select_panel(args.panel_run, args.panel_claim)
        except ValueError as e:
            print(str(e), file=sys.stderr); return 2
    source = None if tower.offline else KubeSource(context=args.context)
    if args.snapshot:
        if source:
            tower.set_inventory(source.refresh())
        print(frame(tower.screen(args.width, args.height), False)); return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print('터미널에서 실행하거나 --snapshot을 사용하세요.', file=sys.stderr); return 2
    session = Session(tower, source); keyboard = Keyboard(); previous = None
    try:
        with terminal():
            if source:
                session.refresh()
            while tower.running:
                session.poll()
                if tower.mode == 'live' and source and time.monotonic() - session.last_refresh >= max(5, args.interval):
                    session.refresh()
                size = shutil.get_terminal_size((120, 34))
                output = frame(tower.screen(size.columns, size.lines))
                if output != previous:
                    sys.stdout.write('\x1b[H' + ''.join(f'\x1b[{i};1H\x1b[2K' + line for i, line in enumerate(output.split('\n'), 1)) + '\x1b[J')
                    sys.stdout.flush(); previous = output
                key = keyboard.read()
                if key:
                    action = tower.key(key, max(1, size.lines - 10))
                    if action == 'refresh':
                        session.refresh()
                    elif action:
                        session.inspect(action)
    except KeyboardInterrupt:
        pass
    finally:
        session.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
