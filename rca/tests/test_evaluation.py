import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rca.common import now
from test_rca import call, final, incident


spec = importlib.util.spec_from_file_location('frozen_eval', Path(__file__).resolve().parents[1] / 'scripts/evaluate_frozen.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.fixture = self.directory / 'fixture.json'
        self.inc = incident()
        self.fixture.write_text(json.dumps({'cases': [{'mode': 'PRIVATE_GROUND_TRUTH_LABEL',
            'incident': {'data': self.inc}, 'evidence': [{'evidence_id': 'ev-frozen', 'tool': 'get_workload_status',
                'availability': 'available', 'observed_at': now(), 'data': {'pod_uid': self.inc['pod_uid']}}]}]}))

    def tearDown(self):
        self.temp.cleanup()

    def test_call_budget_reserves_before_request(self):
        budget = runner.CallBudget(2)
        budget.reserve()
        budget.reserve()
        with self.assertRaisesRegex(ValueError, 'budget'):
            budget.reserve()
        self.assertEqual(budget.attempts, 2)

    def test_cost_reservation_settlement_and_persistence(self):
        path = self.directory / 'budget.json'
        budget = runner.CallBudget(10, 0.1, path)
        budget.reserve(0.06)
        with self.assertRaisesRegex(ValueError, 'cost budget'):
            budget.reserve(0.05)
        self.assertEqual(budget.attempts, 1)
        budget.settle(0.06, {'cost': 0.01})
        restored = runner.CallBudget(10, 0.1, path)
        self.assertAlmostEqual(restored.accounted_usd, 0.01)
        with self.assertRaisesRegex(ValueError, 'limits'):
            runner.CallBudget(11, 0.1, path)

    def test_unknown_cost_retains_reservation_and_excess_stops(self):
        budget = runner.CallBudget(10, 0.1)
        budget.reserve(0.02)
        for usage in ({}, {'cost': None}, {'cost': True}, {'cost': -1}):
            budget.settle(0.02, usage)
            self.assertAlmostEqual(budget.accounted_usd, 0.02)
        with self.assertRaisesRegex(ValueError, 'exceeded'):
            budget.settle(0.02, {'cost': 0.03})
        self.assertAlmostEqual(budget.accounted_usd, 0.03)

    def test_default_is_plan_only_even_with_key_file_argument(self):
        output = io.StringIO()
        with patch('sys.argv', ['evaluate_frozen', '--fixture', str(self.fixture), '--key-file', '/must-not-read']), \
                patch.object(runner.BudgetProvider, 'complete', side_effect=AssertionError('no API allowed')), \
                patch('rca.agent.secret', side_effect=AssertionError('no credential read')), contextlib.redirect_stdout(output):
            runner.main()
        self.assertIn('PLAN ONLY', output.getvalue())
        self.assertNotIn('PRIVATE_GROUND_TRUTH_LABEL', output.getvalue())

    def test_paired_runner_isolated_and_no_label_leakage(self):
        key = self.directory / 'test-key'
        key.write_text('TEST-ONLY-SECRET')
        destination = self.directory / 'results'
        messages_seen = []
        def fake_complete(provider, messages, tools, timeout):
            provider.budget.reserve()
            messages_seen.append(messages)
            ledger = json.loads(messages[-1]['content'])
            answer = call('submit_rca', final('ev-frozen')) if ledger['evidence'] else call('get_workload_status')
            return {'model': 'TEST-DOUBLE', 'choices': [{'message': answer, 'finish_reason': 'tool_calls'}],
                    'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'cost': 0.0001}}
        args = ['evaluate_frozen', '--fixture', str(self.fixture), '--execute', '--key-file', str(key),
                '--output-dir', str(destination)]
        with patch('sys.argv', args), patch.object(runner.BudgetProvider, 'complete', fake_complete), \
                contextlib.redirect_stdout(io.StringIO()):
            runner.main()
        report = json.loads((destination / 'results.json').read_text())
        self.assertTrue(report['complete'])
        self.assertEqual(report['api_attempts'], 4)
        self.assertEqual(len(report['runs']), 2)
        self.assertEqual(len(list(destination.glob('*-requests.json'))), 2)
        self.assertNotIn('PRIVATE_GROUND_TRUTH_LABEL', json.dumps(messages_seen))
        for path in destination.glob('*.json'):
            self.assertNotIn('TEST-ONLY-SECRET', path.read_text())

    def test_failure_stops_further_runs_and_preserves_partial_report(self):
        key = self.directory / 'test-key'
        key.write_text('TEST-ONLY')
        destination = self.directory / 'failed-results'
        args = ['evaluate_frozen', '--fixture', str(self.fixture), '--execute', '--key-file', str(key),
                '--output-dir', str(destination)]
        with patch('sys.argv', args), \
                patch.object(runner.BudgetProvider, 'complete', side_effect=ValueError('test transport failure')) as provider, \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'stopped'):
                runner.main()
        self.assertEqual(provider.call_count, 1)
        report = json.loads((destination / 'results.json').read_text())
        self.assertFalse(report['complete'])
        self.assertEqual(len(report['runs']), 1)
        self.assertIn('test transport failure', report['runs'][0]['incident']['result']['execution']['error'])

    def test_v4_arms_use_new_schema_and_enforce_ebpf_ablation(self):
        key = self.directory / 'v4-test-key'
        key.write_text('TEST-ONLY')
        destination = self.directory / 'v4-results'
        seen = []
        def fake_complete(provider, messages, tools, timeout):
            provider.budget.reserve()
            names = [t['function']['name'] for t in tools]
            self.assertEqual('get_ebpf_summary' in names, provider.settings.allow_ebpf)
            schema = next(t['function']['parameters'] for t in tools if t['function']['name'] == 'submit_rca')
            self.assertIn('root_cause_status', schema['required'])
            ledger = json.loads(messages[1]['content'])
            value = final('ev-frozen')
            value['root_cause_status'] = 'undetermined'
            value['evidence'][0]['claim_type'] = 'observation'
            answer = call('submit_rca', value) if ledger['evidence'] else call('get_workload_status')
            seen.append(messages)
            return {'model': 'TEST-DOUBLE', 'choices': [{'message': answer, 'finish_reason': 'tool_calls'}],
                    'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'cost': 0.0001}}
        args = ['evaluate_frozen', '--fixture', str(self.fixture), '--execute', '--key-file', str(key),
                '--arms', 'full-v4', 'compact-v4', 'compact-v4-no-ebpf', '--output-dir', str(destination)]
        with patch('sys.argv', args), patch.object(runner.BudgetProvider, 'complete', fake_complete), \
                contextlib.redirect_stdout(io.StringIO()):
            runner.main()
        report = json.loads((destination / 'results.json').read_text())
        self.assertTrue(report['complete'])
        self.assertEqual(report['api_attempts'], 6)
        self.assertNotIn('PRIVATE_GROUND_TRUTH_LABEL', json.dumps(seen))
        for run in report['runs']:
            self.assertEqual(run['incident']['result']['execution']['prompt_version'], 'rca-v4')


if __name__ == '__main__':
    unittest.main()
