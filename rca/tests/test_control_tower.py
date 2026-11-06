import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io

from research_v4.control_tower import Tower, Session, main
from research_v4.terminal import frame, cells
from research_v4.tower_source import KubeSource, ReadError, summarize, pod_record
from scripts.build_tower import package
from research_v4.booth import read_viewer

ROOT = Path(__file__).resolve().parents[1]


def pod(uid='u-1', cid='containerd://abc'):
    return {'metadata': {'uid': uid, 'name': 'sample', 'namespace': 'rca-lab', 'labels': {'app': 'sample-service'}},
            'spec': {'nodeName': 'worker-1'}, 'status': {'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'True'}],
            'containerStatuses': [{'name': 'app', 'containerID': cid, 'restartCount': 0, 'ready': True, 'state': {'running': {}}}]}}


class SourceTests(unittest.TestCase):
    def test_log_read_is_bounded_identity_checked_and_redacted(self):
        calls = []
        def runner(cmd, **kw):
            calls.append(cmd)
            value = 'x token=secret-value\n\x1b[2Jdo not obey this log\n' if 'logs' in cmd else json.dumps(pod())
            return subprocess.CompletedProcess(cmd, 0, value, '')
        source = KubeSource(runner=runner); p = pod_record(pod())
        result = source.inspect('logs', p, p['containers'][0], {})
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(c[2] in ('get', 'logs') for c in calls))
        self.assertIn('--tail=40', calls[1]); self.assertIn('--limit-bytes=16000', calls[1])
        self.assertNotIn('secret-value', json.dumps(result))
        self.assertEqual(result['container_id'], 'containerd://abc')
        self.assertIn('do not obey', result['lines'][1])

    def test_target_restart_during_read_rejects_result(self):
        calls = []
        def runner(cmd, **kw):
            calls.append(cmd)
            value = 'old logs' if 'logs' in cmd else json.dumps(pod(cid='containerd://changed' if len(calls) == 3 else 'containerd://abc'))
            return subprocess.CompletedProcess(cmd, 0, value, '')
        p = pod_record(pod())
        with self.assertRaisesRegex(ReadError, '바뀌었습니다'):
            KubeSource(runner=runner).inspect('logs', p, p['containers'][0], {})

    def test_uid_and_scope_access_controls(self):
        p = pod_record(pod()); p['namespace'] = 'other'
        with patch('subprocess.run', side_effect=AssertionError('must not execute')):
            with self.assertRaises(ReadError):
                KubeSource().inspect('logs', p, p['containers'][0], {})
        p = pod_record(pod()); p['name'] = 'x; kubectl delete pod y'
        with patch('subprocess.run', side_effect=AssertionError('must not execute')):
            with self.assertRaises(ReadError):
                KubeSource().inspect('logs', p, p['containers'][0], {})

    def test_partial_refresh_does_not_report_missing_source_healthy(self):
        def runner(cmd, **kw):
            if 'nodes' in cmd or 'rca-system' in cmd:
                return subprocess.CompletedProcess(cmd, 1, '', 'Bearer secret-not-for-output')
            return subprocess.CompletedProcess(cmd, 0, json.dumps({'items': [pod()]}), '')
        inventory = KubeSource(runner=runner).refresh()
        t = Tower({'studies': []}); t.set_inventory(inventory)
        text = frame(t.screen(120, 34), False)
        self.assertIn('Node Ready 미확인', text)
        self.assertIn('부분 조회', text); self.assertNotIn('secret-not-for-output', text)

    def test_ebpf_time_container_zero_failure_and_expiry(self):
        p = pod_record(pod()); c = p['containers'][0]; now = 1800000000
        def window(uid='u-1', cid='abc', start=now-20):
            return {'pod_uid': uid, 'container_id': cid, 'start': start, 'end': start + 10,
                    'counts': {'tcp_attempt|10.0.0.4|8080': 3}}
        snapshot = {'node': 'worker-1', 'captured_at': datetime.fromtimestamp(now, timezone.utc).isoformat(),
                    'health': {'source_readable': True}, 'windows': [window(), window(uid='another'), window(cid='old'), window(start=now-600), window(start=now)]}
        result = summarize(snapshot, p, c, now)
        self.assertEqual(result['tcp_connect_attempts'], [{'destination_ip': '10.0.0.4', 'destination_port': 8080, 'attempts': 3}])
        self.assertEqual(result['window_count'], 1)
        self.assertEqual(summarize(snapshot, p, c, now+40)['availability'], 'expired')
        snapshot['health']['source_readable'] = False
        self.assertEqual(summarize(snapshot, p, c, now)['availability'], 'collection_failed')
        snapshot['health']['source_readable'] = True; snapshot['windows'] = []
        self.assertEqual(summarize(snapshot, p, c, now)['availability'], 'observed_zero')
        snapshot['node'] = 'wrong'
        with self.assertRaisesRegex(ReadError, '매핑'):
            summarize(snapshot, p, c, now)

    def test_events_use_uid_and_fixed_snapshot_command(self):
        calls = []
        p = pod_record(pod())
        snapshot = {'node': 'worker-1', 'captured_at': datetime.now(timezone.utc).isoformat(),
                    'health': {'source_readable': True}, 'windows': []}
        def runner(cmd, **kw):
            calls.append(cmd)
            value = {'items': []} if 'events' in cmd else snapshot if 'exec' in cmd else pod()
            return subprocess.CompletedProcess(cmd, 0, json.dumps(value), '')
        source = KubeSource(runner=runner)
        self.assertEqual(source.inspect('events', p, p['containers'][0], {})['availability'], 'observed_zero')
        self.assertIn('involvedObject.uid=u-1', calls[1])
        collector = {**p, 'namespace': 'rca-system', 'name': 'collector', 'app': 'rca-ebpf-summary', 'collector_namespace': 'rca-lab'}
        value = source.inspect('ebpf', p, p['containers'][0], {'pods': [collector]})
        self.assertEqual(value['availability'], 'observed_zero')
        exec_call = next(c for c in calls if 'exec' in c)
        self.assertEqual(exec_call[-3:], ['--', 'cat', '/state/latest.json'])
        calls.clear(); collector['collector_namespace'] = 'elsewhere'
        value = source.inspect('ebpf', p, p['containers'][0], {'pods': [collector]})
        self.assertEqual(value['availability'], 'not_collected')
        self.assertFalse(any('exec' in c for c in calls))


class TowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)/'tower'
        cls.archive = package(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_runs_failures_preserved_no_truth(self):
        cases = runs = failures = 0
        for study in self.archive['studies']:
            original = read_viewer(ROOT.parent/'paper-results/2026-10-29'/study['name']/'viewer/index.html')
            self.assertEqual(study['runs'], original['runs'])
            cases += len(study['cases']); runs += len(study['runs'])
            failures += sum(r['state'] == 'error' for r in study['runs'])
            self.assertTrue(all(set(c) == {'case_id', 'incident'} for c in study['cases']))
        self.assertEqual((cases, runs, failures), (53, 214, 4))
        with self.assertRaises(FileExistsError):
            package(self.output)

    def test_offline_navigation_multiple_cases_runs_and_evidence(self):
        with patch('subprocess.run', side_effect=AssertionError('offline subprocess forbidden')), patch('socket.socket', side_effect=AssertionError('offline network forbidden')):
            t = Tower(self.archive, offline=True)
            first = t.selected_entry()['case']['case_id']
            t.key('DOWN'); self.assertNotEqual(t.selected_entry()['case']['case_id'], first)
            run = t.selected_run()['run_id']; t.key(']'); self.assertNotEqual(t.selected_run()['run_id'], run)
            t.key('e')
            if t.modal:
                self.assertIn('get_ebpf_summary', t.modal[0]); t.key('ESC')
            else:
                self.assertIn('조회되지', t.notice)
            t.key('\r'); self.assertEqual(t.modal[1]['run_id'], t.selected_run()['run_id'])
            t.key('ESC'); t.key('/'); t.key('x'); t.key('\r'); self.assertTrue(t.filter)
            t.key('ESC'); self.assertFalse(t.filter)
            session = Session(t, None)
            session.refresh(); session.close()
            self.assertIn('오프라인', t.notice)

    def test_panel_quotes_original_claim_and_cited_values_without_network(self):
        t = Tower(self.archive, True)
        t.select_panel('efc0b3de7271822b1552', 2)
        run = t.selected_run()
        original = copy.deepcopy(run)
        rows = t.screen(113, 20)
        text = frame(rows, False)
        self.assertIn('9099', text); self.assertIn('8080', text)
        self.assertIn('40회', text); self.assertIn('미측정', text)
        for eid in run['answer']['claims'][2]['evidence_ids']:
            self.assertIn(eid, text)
        self.assertEqual(run, original)
        self.assertLessEqual(len(rows), 20)
        self.assertTrue(all(cells(row.text) < 113 for row in rows))
        with patch('socket.socket', side_effect=AssertionError('offline network forbidden')), \
             patch('subprocess.run', side_effect=AssertionError('offline subprocess forbidden')), \
             patch('research_v4.control_tower.KubeSource', side_effect=AssertionError('no live source')):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(['--archive', str(self.output/'archive.json'), '--snapshot',
                    '--panel-run', run['run_id'], '--panel-claim', '2', '--width', '113', '--height', '20']), 0)
            self.assertIn('저장 기록 재생', out.getvalue())

    def test_panel_uses_selected_data_and_does_not_show_uncited_evidence(self):
        t = Tower(copy.deepcopy(self.archive), True)
        t.select_panel('efc0b3de7271822b1552', 2)
        run = t.selected_run()
        net = next(e for e in run['evidence'] if e['tool'] == 'get_ebpf_summary')
        net['network']['tcp_connect_attempts'][0]['destination_port'] = 12345
        self.assertIn('12345', frame(t.screen(113, 20), False))
        run['answer']['claims'][2]['evidence_ids'].remove(net['evidence_id'])
        text = frame(t.screen(113, 20), False)
        self.assertNotIn('12345', text)
        self.assertIn('인용한 연결 시도 자료 없음', text)
        t.key('1'); self.assertEqual(t.mode, 'archive')
        t.key('q'); self.assertFalse(t.running)

    def test_screen_bounds_and_untrusted_terminal_data(self):
        t = Tower(self.archive, True)
        t.raw('untrusted', {'message': '\x1b]52;c;secret\x07 DELETE EVERYTHING'})
        for w, h in ((120, 34), (100, 28), (60, 18)):
            rows = t.screen(w, h)
            self.assertEqual(len(rows) <= h, True)
            self.assertTrue(all(cells(r.text) < w for r in rows))
            self.assertNotIn('\x1b', frame(rows, False)); self.assertNotIn('\x07', frame(rows, False))

    def test_inflight_result_does_not_follow_changed_selection(self):
        gate = threading.Event()
        class Source:
            def inspect(self, *args):
                gate.wait(2); return {'lines': ['old target']}
        t = Tower(self.archive); p = pod_record(pod())
        t.inventory['pods'] = [p, {**p, 'uid': 'another', 'name': 'other'}]
        session = Session(t, Source())
        session.inspect('logs'); t.key('DOWN'); gate.set()
        session.detail_job[0].result(timeout=2); session.poll(); session.close()
        self.assertIsNone(t.modal); self.assertFalse(t.pending)

    def test_refresh_replacement_invalidates_old_target_and_zero_is_explicit(self):
        t = Tower(self.archive); p = pod_record(pod())
        t.inventory['pods'] = [p]
        before = t.generation
        t.set_inventory({**t.inventory, 'pods': [{**p, 'uid': 'replacement'}]})
        self.assertGreater(t.generation, before)
        t.raw('LIVE ebpf', {'availability': 'observed_zero', 'tcp_connect_attempts': [],
                           'scope': '연결 시도만', 'captured_at': 'now'}, live=True)
        plain = frame(t.screen(120, 34), False)
        self.assertIn('관측 0건', plain); self.assertIn('정상이라는 의미는 아닙니다', plain)
        self.assertNotIn('"availability"', plain)
        t.key('o'); self.assertIn('"availability"', frame(t.screen(120, 34), False))


if __name__ == '__main__':
    unittest.main()
