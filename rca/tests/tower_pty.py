#!/usr/bin/env python3
"""Interact with the packaged control tower in a real PTY; live is explicit."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import termios
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.terminal_pty import plain_screen


def run(bundle, output, live=False):
    output.mkdir(parents=True, exist_ok=False)
    master, slave = os.openpty(); before = termios.tcgetattr(slave)
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 34, 120, 0, 0))
    env = dict(os.environ, TERM='xterm-256color', PYTHONIOENCODING='utf-8')
    env.pop('LINES', None); env.pop('COLUMNS', None)
    proc = subprocess.Popen([sys.executable, str(bundle/'tower.py')] + ([] if live else ['--offline']),
                            stdin=slave, stdout=slave, stderr=slave, env=env)
    result = {'mode': 'actual cluster UI' if live else 'offline archive UI', 'checks': []}; raw = bytearray()
    def capture(name, marker, keys=None):
        if keys:
            os.write(master, keys)
        data = bytearray(); deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if select.select([master], [], [], .1)[0]:
                data.extend(os.read(master, 65536))
            elif marker.encode() in data:
                break
        raw.extend(data)
        assert marker.encode() in data, (name, plain_screen(data))
        text = plain_screen(data)
        (output/(name+'.txt')).write_text(text, encoding='utf-8')
        return text
    try:
        if live:
            initial = capture('01-live', 'RCA Agent: 중지')
            assert 'LIVE / 읽기 전용' in initial and '요약기: 2/2 Ready' in initial
            capture('02-pod-selection', 'SELECTED POD', b'\x1b[B')
            logs = capture('03-live-logs', 'LIVE logs', b'l')
            assert '상태:' in logs and '조회:' in logs
            technical = capture('04-log-details', '"availability"', b'o')
            assert '"pod_uid"' in technical
            capture('05-back-to-live', 'SELECTED POD', b'\x1b')
            ebpf = capture('06-live-ebpf', 'LIVE ebpf', b'e')
            assert '상태:' in ebpf and ('미측정' in ebpf or '실패' in ebpf or '기간 만료' in ebpf)
            capture('07-back-to-live', 'SELECTED POD', b'\x1b')
            initial_archive = capture('08-archive', 'INCIDENTS 53', b'2')
            result['checks'].append('actual inventory, Pod selection, live logs, raw toggle and eBPF inspection PASS')
        else:
            initial_archive = capture('01-archive', 'INCIDENTS 53')
            assert 'OFFLINE' in initial_archive
        selected = capture('09-next-case', 'INCIDENTS 53', b'\x1b[B')
        assert selected != initial_archive
        other = capture('10-other-run', 'INCIDENTS 53', b']')
        assert other != selected
        answer = capture('11-answer', '"run_id"', b'\r')
        assert '"answer"' in answer and '현재 장애의 판단이 아님' in answer
        capture('12-close', 'INCIDENTS 53', b'\x1b')
        capture('13-search', 'INCIDENTS 0', b'/doesnotexist\r')
        reset = capture('14-clear-search', 'INCIDENTS 53', b'\x1b')
        assert 'SELECTED INCIDENT' in reset
        os.write(master, b'q'); proc.wait(timeout=12)
        tail = bytearray()
        while select.select([master], [], [], .05)[0]:
            tail.extend(os.read(master, 65536))
        raw.extend(tail)
        assert proc.returncode == 0 and termios.tcgetattr(slave) == before
        assert b'\x1b[?1049l' in tail
        result['checks'].append('multi-case selection, run switching, original answer, search/reset and terminal restoration PASS')
        result.update(result='PASS', new_paid_api_calls=0)
    except BaseException as e:
        result.update(result='FAIL', error=repr(e)); raise
    finally:
        if proc.poll() is None:
            proc.kill(); proc.wait()
        (output/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        (output/'session.ansi').write_bytes(raw)
        os.close(master); os.close(slave)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('bundle', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--live', action='store_true'); a = p.parse_args(); run(a.bundle.resolve(), a.output.resolve(), a.live)
