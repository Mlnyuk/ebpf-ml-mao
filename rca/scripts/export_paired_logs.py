#!/usr/bin/env python3
"""Export one archived run's real log evidence for an explicitly labelled replay.

No Kubernetes or LLM connection. The original lines are exported unchanged;
the separate presentation excerpt displays timestamp and message fields only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def export(archive_path, run_id, output):
    archive = json.loads(archive_path.read_text())
    study, run = next((s, r) for s in archive['studies'] for r in s['runs'] if r['run_id'] == run_id)
    incident = next(c['incident'] for c in study['cases'] if c['case_id'] == run['case_id'])
    log = next(e for e in run['evidence'] if e['tool'] == 'get_logs' and e['availability'] == 'available')
    for key in ('pod', 'pod_uid', 'container_name', 'container_id'):
        if log['target'][key] != incident[key]:
            raise ValueError('Log evidence target does not match the selected incident: ' + key)
    raw = '\n'.join(log['lines']) + '\n'
    selected = []
    for index, line in enumerate(log['lines'][:6]):
        timestamp, payload = line.split(' ', 1)
        message = json.loads(payload)['message']
        if re.search(r'[\x00-\x1f\x7f]', message):
            raise ValueError('Terminal control characters in the selected message')
        selected.append({'source_line_1based': index + 1, 'timestamp': timestamp, 'message': message})
    if len(selected) != 6:
        raise ValueError('Six original log lines are required for this excerpt')
    title = [
        'K9s에서 연 저장 로그  |  외부 뷰어: less',
        '저장된 장애 로그 재생  |  ' + incident['time'][:10] + '  |  실시간 아님',
        incident['namespace'] + ' / ' + incident['pod'] + ' / ' + incident['container_name'],
        '출처: Kubernetes container logs  |  ' + log['evidence_id'],
        '', 'UTC 시각' + ' ' * 13 + '애플리케이션 메시지', '─' * 87,
    ]
    rows = title + [x['timestamp'][11:-1] + '   ' + x['message'] for x in selected]
    rows += ['', f"저장된 {len(log['lines'])}줄 중 1–6행 · timestamp/message 필드 발췌",
             '같은 조사 실행: ' + run_id]
    text = '\n'.join(rows) + '\n'
    colored = []
    for i, row in enumerate(rows):
        color = '1;36' if i in (0, 1, 5) else '1;33' if 7 <= i < 13 else '37'
        colored.append('\x1b[' + color + 'm' + row + '\x1b[0m')
    ansi = '\n'.join(colored) + '\n'
    output.mkdir(parents=True, exist_ok=False)
    (output/'sample-service-20261029.raw.log').write_text(raw)
    (output/'excerpt.txt').write_text(text)
    (output/'REPLAY_2026-10-29_sample-service.ansi').write_text(ansi)
    (output/'log-evidence.json').write_text(json.dumps(log, ensure_ascii=False, indent=2) + '\n')
    metadata = {'study': study['name'], 'case_id': run['case_id'], 'run_id': run_id,
                'incident': incident, 'log_evidence_id': log['evidence_id'],
                'source_archive_sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                'raw_export_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                'shown_fields': ['timestamp (date is in header)', 'message'],
                'excerpt': selected, 'original_line_count': len(log['lines']),
                'bounded': log.get('bounded'), 'possible_truncation': log.get('possible_truncation'),
                'mode': 'archived evidence opened now, not a contemporaneous K9s screenshot',
                'new_api_calls': 0, 'cluster_mutations': 0}
    (output/'provenance.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    assert (output/'sample-service-20261029.raw.log').read_text().splitlines() == log['lines']
    assert re.sub(r'\x1b\[[0-9;]*m', '', ansi) == text
    return metadata


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = export(a.archive, a.run_id, a.output)
    print(result['run_id'], result['log_evidence_id'], result['original_line_count'])
