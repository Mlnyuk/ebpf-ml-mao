"""Package a reviewed pair of actual archived runs; no API or cluster access."""
import copy
import hashlib
import json
import re
from pathlib import Path
from .viewer import render_html

PRIMARY = 'efc0b3de7271822b1552'
BASELINE = '6c938d099e296bd28fa6'


def read_viewer(path):
    match = re.search(r'<script id="dataset" type="application/json">(.*?)</script>', path.read_text(), re.S)
    if not match:
        raise ValueError('Existing viewer has no embedded dataset')
    return json.loads(match[1])


def select_demo(dataset, primary=PRIMARY, baseline=BASELINE):
    run = next((r for r in dataset['runs'] if r['run_id'] == primary), None)
    if not run or not run.get('answer'):
        raise ValueError('Representative saved run/answer missing; no example substituted')
    case = next(c for c in dataset['cases'] if c['case_id'] == run['case_id'])
    evidence = {e['evidence_id']: e for e in run['evidence']}
    log = next((e for e in evidence.values() if e['tool'] == 'get_logs'), {})
    network = next((e for e in evidence.values() if e['tool'] == 'get_ebpf_summary'), {})
    status = next((e for e in evidence.values() if e['tool'] == 'get_workload_status'), {})
    if not log.get('lines') or not network.get('network', {}).get('tcp_connect_attempts'):
        raise ValueError('Actual log or connection-attempt evidence missing')
    declaration = json.loads(status.get('data', {}).get('declared_dependency', '{}'))
    if not declaration.get('expected_port') or not status.get('data', {}).get('expected_destination_source'):
        raise ValueError('Recorded dependency declaration or address mapping source missing')
    # This is an explicitly curated exhibit, not an automated diagnosis/evaluation.
    # Index 2 is the original inference citing BOTH declaration and eBPF summary.
    claim_index = 2
    claim = run['answer']['claims'][claim_index]
    if set(claim['evidence_ids']) != {status['evidence_id'], network['evidence_id']}:
        raise ValueError('Selected claim no longer cites the expected recorded evidence')
    if any(eid not in evidence for c in run['answer']['claims'] for eid in c['evidence_ids']):
        raise ValueError('Unresolvable citation in representative run')
    log_index = next((i for i, line in enumerate(log['lines']) if 'status=503' in line), None)
    if log_index is None:
        raise ValueError('Saved failure log not found')
    for line in log['lines']:
        if re.search(r'(?:\d{1,3}\.){3}\d{1,3}|https?://|\b(?:destination|port)\s*[:=]', line):
            raise ValueError('This exhibit requires captured logs without destination details')
    pair = next((r for r in dataset['runs'] if r['run_id'] == baseline), None)
    if pair:
        if pair['case_id'] != run['case_id'] or pair['repeat'] != run['repeat']:
            raise ValueError('Comparison must use the same case and repeat')
        if run['arm'] != 'selective-ebpf' or pair['arm'] != 'selective-no-ebpf':
            raise ValueError('Comparison must hold selective policy fixed')
        # Compare actual source records, not just matching labels.
        expected = {k: v for k, v in evidence.items() if v['tool'] != 'get_ebpf_summary'}
        actual = {e['evidence_id']: e for e in pair['evidence']}
        if expected != actual:
            raise ValueError('Non-eBPF source records differ between selected runs')
        def model(r):
            return {t['payload']['model'] for t in r['trace'] if t['type'] == 'request'}
        if model(run) != model(pair):
            raise ValueError('Comparison model differs')
    data = {'mode': 'replay', 'dataset_hash': dataset['dataset_hash'], 'offline_only': True,
            'cases': [copy.deepcopy(case)], 'runs': copy.deepcopy([run] + ([pair] if pair else [])),
            'demo': {'primary_run_id': primary, 'baseline_run_id': pair['run_id'] if pair else None,
                     'claim_index': claim_index, 'log_evidence_id': log['evidence_id'], 'log_line_index': log_index,
                     'selection_reason': '목적지가 없는 실패 로그와 선언 포트와 다른 연결 시도가 있는 실제 사례. ' + ('같은 사건·선택 조회·반복 번호의 eBPF 포함/제외 실행을 비교합니다.' if pair else '대응하는 eBPF 제외 실행이 없어 자료의 정보 차이만 보여줍니다.'),
                     'scope': '선정한 저장 사례의 설명용 재생. 전체 정확도나 eBPF 효과의 통계적 입증이 아님.'}}
    data['cases'][0]['source_links'] = {}  # raw-export files are NOT silently linked to a lab server
    return data


def package(source, output):
    data = select_demo(read_viewer(source))
    output.mkdir(parents=True, exist_ok=False)
    (output / 'viewer').mkdir()
    html = render_html(data)
    policy = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'"
    html = html.replace('<title>', '<meta http-equiv="Content-Security-Policy" content="' + policy + '"><title>', 1)
    (output / 'viewer/index.html').write_text(html)
    (output / 'START.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta http-equiv="refresh" content="0;url=viewer/index.html?demo=1">
<title>Kubernetes RCA 시연 시작</title><a href="viewer/index.html?demo=1">저장된 조사 기록 시연 시작</a></html>''')
    (output / 'manifest.json').write_text(json.dumps({
        'source_viewer': source.name, 'source_viewer_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'case_id': data['cases'][0]['case_id'], **data['demo'],
        'mode': 'offline stored-record replay', 'external_requests': False,
        'kernel_raw_export_included': False,
        'evidence': 'Exact evidence objects supplied to the saved AI runs, including eBPF summary; not raw kernel events.',
        'viewer_sha256': hashlib.sha256((output / 'viewer/index.html').read_bytes()).hexdigest()
    }, ensure_ascii=False, indent=2))
    return data
