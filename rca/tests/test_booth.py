import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from research_v4.booth import read_viewer, select_demo, package, PRIMARY, BASELINE
from research_v4.viewer import render_html

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent/'paper-results/2026-10-29/analysis-v3/viewer/index.html'


class BoothTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = read_viewer(SOURCE)

    def test_pair_preserves_actual_runs_and_source(self):
        before = copy.deepcopy(self.original)
        data = select_demo(self.original)
        self.assertEqual(self.original, before)
        for run in data['runs']:
            self.assertEqual(run, next(r for r in before['runs'] if r['run_id']==run['run_id']))
        self.assertEqual(data['runs'][0]['case_id'], data['runs'][1]['case_id'])
        self.assertEqual(data['runs'][1]['answer']['status'], 'inconclusive')

    def test_selected_claim_cites_actual_declaration_and_attempts(self):
        data = select_demo(self.original); run = data['runs'][0]
        lookup = {e['evidence_id']:e for e in run['evidence']}
        cited = [lookup[x] for x in run['answer']['claims'][data['demo']['claim_index']]['evidence_ids']]
        self.assertEqual({e['tool'] for e in cited}, {'get_workload_status','get_ebpf_summary'})
        port = next(e for e in cited if e['tool']=='get_ebpf_summary')['network']['tcp_connect_attempts'][0]['destination_port']
        declared = json.loads(next(e for e in cited if e['tool']=='get_workload_status')['data']['declared_dependency'])
        self.assertNotEqual(port, declared['expected_port'])
        log = lookup[data['demo']['log_evidence_id']]
        self.assertIn('status=503', log['lines'][data['demo']['log_line_index']])
        self.assertNotIn(str(port), '\n'.join(log['lines']))

    def test_actual_selection_order_matches_saved_retrievals(self):
        run = select_demo(self.original)['runs'][0]
        response = next(t['response'] for t in run['trace'] if t['type']=='response')
        sources = json.loads(response['choices'][0]['message']['tool_calls'][0]['function']['arguments'])['sources']
        self.assertEqual(sources, [r['source'] for r in run['retrievals']])

    def test_missing_pair_is_explicit_fallback(self):
        data = select_demo(self.original, baseline='not-present')
        self.assertIsNone(data['demo']['baseline_run_id'])
        self.assertEqual(len(data['runs']),1)
        self.assertIn('정보 차이만',data['demo']['selection_reason'])

    def test_missing_log_does_not_get_example_data(self):
        data = copy.deepcopy(self.original)
        run = next(r for r in data['runs'] if r['run_id']==PRIMARY)
        run['evidence'] = [e for e in run['evidence'] if e['tool']!='get_logs']
        with self.assertRaisesRegex(ValueError,'missing'):select_demo(data)

    def test_wrong_case_pair_rejected(self):
        data = copy.deepcopy(self.original)
        next(r for r in data['runs'] if r['run_id']==BASELINE)['case_id']='other'
        with self.assertRaisesRegex(ValueError,'same case'):select_demo(data)

    def test_portable_build_is_network_free_and_does_not_overwrite(self):
        before=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temp, patch('urllib.request.urlopen',side_effect=AssertionError('network forbidden')):
            out=Path(temp)/'demo';package(SOURCE,out)
            html=(out/'viewer/index.html').read_text()
            self.assertIn("connect-src 'none'",html)
            self.assertNotIn('__DATA__',html)
            self.assertIn('window.RCABooth',html)
            self.assertEqual(read_viewer(out/'viewer/index.html')['runs'],select_demo(self.original)['runs'])
            with self.assertRaises(FileExistsError):package(SOURCE,out)
        self.assertEqual(before,hashlib.sha256(SOURCE.read_bytes()).hexdigest())

    def test_log_html_is_data_not_executable_markup(self):
        data=select_demo(self.original)
        data['runs'][0]['evidence'][0]['untrusted']='</script><script>window.pwned=true</script>'
        html=render_html(data)
        self.assertNotIn('</script><script>window.pwned=true',html)
        self.assertIn('\\u003c/script\\u003e',html)


if __name__=='__main__':unittest.main()
