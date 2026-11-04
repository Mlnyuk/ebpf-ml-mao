#!/usr/bin/env python3
"""Exercise the delivered standalone program in a real Linux pseudo terminal."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import select
import signal
import struct
import subprocess
import sys
import termios
import time


CSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


def plain_screen(data):
    text = data.decode('utf-8')
    text = text.rsplit('\x1b[H', 1)[-1]
    text = re.sub(r'\x1b\[\d+;1H\x1b\[2K', '\n', text)
    return CSI.sub('', text).strip('\n') + '\n'


def exercise(bundle, out):
    out.mkdir(parents=True, exist_ok=False)
    master, slave = os.openpty()
    before = termios.tcgetattr(slave)
    def resize(w, h):
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', h, w, 0, 0))
    resize(110, 32)
    env = dict(os.environ, TERM='xterm-256color', PYTHONIOENCODING='utf-8')
    env.pop('COLUMNS', None); env.pop('LINES', None)
    env.pop('NO_COLOR', None)  # This run explicitly verifies ANSI evidence highlighting.
    proc = subprocess.Popen([sys.executable, str(bundle/'rca_demo.py')], stdin=slave, stdout=slave, stderr=slave, env=env)
    archive = bytearray(); checks = []; frames = []; result = {}
    def capture(name, marker, keys=None):
        if keys is not None:
            os.write(master, keys)
        data = bytearray(); limit = time.monotonic() + 5
        while time.monotonic() < limit:
            if select.select([master], [], [], .08)[0]:
                data.extend(os.read(master, 65536))
            elif marker.encode() in data:
                break
        archive.extend(data)
        assert marker.encode() in data, (name, bytes(data))
        screen = plain_screen(data)
        (out/(name + '.txt')).write_text(screen, encoding='utf-8')
        frames.append(name)
        return screen, bytes(data)
    try:
        initial, _ = capture('01-incident', 'INCIDENT')
        assert '저장 기록 재생' in initial and 'status=503' in initial and '9099' not in initial
        investigation, _ = capture('02-investigation', 'INVESTIGATION', b'\r')
        assert '06  eBPF' in investigation and ':8080' in investigation and ':9099' in investigation
        judgement, _ = capture('03-judgement', 'AI FINDING', b'\r')
        assert '포트(9099)' in judgement
        evidence, ansi = capture('04-cited-evidence', '"destination_port"', b'e')
        assert '"destination_port": 9099' in evidence and 'records.json / runs/0/evidence/5' in evidence
        assert b'\x1b[1;33m' in ansi
        # Split a terminal arrow sequence across two writes, as real terminals can.
        os.write(master, b'\x1b'); time.sleep(.01)
        scrolled, _ = capture('05-evidence-scroll', 'records.json', b'[A')
        assert scrolled != evidence
        capture('06-close-evidence', 'AI FINDING', b'\x1b')
        settings, _ = capture('07-cited-setting', 'declared_dependency', b's')
        assert '8080' in settings
        comparison, _ = capture('08-comparison', 'WITHOUT eBPF', b'\x1b\r')
        assert '원인 판단 보류' in comparison and 'WITH eBPF' in comparison
        reset, _ = capture('09-reset', 'INCIDENT', b'r')
        assert reset == initial
        checks += ['actual Enter flow, exact citation location and highlighted port PASS',
                   'fragmented arrow, Escape, paired comparison and full reset PASS']
        resize(80, 24)
        small, _ = capture('10-resize', 'INCIDENT')
        assert len(small.splitlines()) == 24
        lower, _ = capture('11-small-scroll', '캡처된 로그', b'\x1b[6~')
        assert lower != small
        checks.append('resize to 80x24 and PageDown PASS')
        os.write(master, b'q'); proc.wait(timeout=5)
        tail = b''
        while select.select([master], [], [], .05)[0]:
            tail += os.read(master, 65536)
        archive.extend(tail)
        assert proc.returncode == 0
        assert b'\x1b[?1049l' in tail and b'\x1b[?25h' in tail
        assert termios.tcgetattr(slave) == before
        checks.append('q exit restores cursor, screen and termios PASS')
        # Verify interrupted termination restores the same terminal settings.
        proc = subprocess.Popen([sys.executable, str(bundle/'rca_demo.py')], stdin=slave, stdout=slave, stderr=slave, env=env)
        capture('12-before-interrupt', 'INCIDENT')
        proc.send_signal(signal.SIGINT); proc.wait(timeout=5)
        assert proc.returncode == 0 and termios.tcgetattr(slave) == before
        checks.append('Ctrl-C / SIGINT restores termios PASS')
        result.update(result='PASS', checks=checks, screens=frames,
                      platform='Linux PTY', windows='NOT_TESTED', macos='NOT_TESTED')
    except BaseException as exc:
        result.update(result='FAIL', checks=checks, error=repr(exc)); raise
    finally:
        if proc.poll() is None:
            proc.kill(); proc.wait()
        (out/'session.ansi').write_bytes(archive)
        (out/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        os.close(master); os.close(slave)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path); parser.add_argument('output', type=Path)
    args = parser.parse_args()
    exercise(args.bundle.resolve(), args.output.resolve())
