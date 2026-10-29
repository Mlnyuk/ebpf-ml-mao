import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import evaluate_fixed as runner
from rca.context import restore_evidence
from test_rca import incident, final, call


class FixedEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.case = {'mode': 'SECRET_LABEL', 'incident': {'data': incident()},
                     'evidence': [{'evidence_id': 'ev-frozen', 'tool': 'get_workload_status',
                                   'availability': 'available', 'data': {'ready': True}}]}
        self.fixture = self.directory / 'fixture.json'
        self.fixture.write_text(json.dumps({'cases': [self.case]}))
        self.output = self.directory / 'output'
        self.args = ['evaluate_fixed', '--fixture', str(self.fixture), '--output-dir', str(self.output),
                     '--budget-file', str(self.directory / 'budget.json')]

    def tearDown(self):
        self.temp.cleanup()

    def test_same_six_sources_and_lossless_modes(self):
        full, _ = runner.prepare(self.case, 'full')
        packed, messages = runner.prepare(self.case, 'compact')
        self.assertEqual(len(full), 6)
        self.assertEqual(full, [restore_evidence(x, self.case['incident']['data']) for x in packed])
        self.assertNotIn('SECRET_LABEL', json.dumps(messages))

    def test_plan_has_no_credentials_or_calls(self):
        with patch('sys.argv', self.args), contextlib.redirect_stdout(io.StringIO()), \
                patch.object(runner, 'evaluation_key', side_effect=AssertionError('no credentials')):
            runner.main()
        self.assertFalse(self.output.exists())

    def test_single_request_per_arm_and_no_label_in_model_input(self):
        key = self.directory / 'key'
        key.write_text('TEST-ONLY')
        seen = []
        def fake(provider, messages, tools, timeout):
            seen.append(messages)
            provider.budget.reserve()
            return {'model': 'TEST', 'usage': {'prompt_tokens': 200, 'completion_tokens': 10, 'cost': 0.001},
                    'choices': [{'finish_reason': 'tool_calls', 'message': call('submit_rca', final('ev-frozen'))}]}
        with patch('sys.argv', self.args + ['--execute', '--key-file', str(key)]), \
                patch.object(runner.BudgetProvider, 'complete', fake), contextlib.redirect_stdout(io.StringIO()):
            runner.main()
        self.assertEqual(len(seen), 2)
        self.assertNotIn('SECRET_LABEL', json.dumps(seen))
        report = json.loads((self.output / 'results.json').read_text())
        self.assertTrue(report['complete'])
        self.assertEqual(len(report['runs']), 2)
        self.assertNotIn('TEST-ONLY', (self.output / 'results.json').read_text())


if __name__ == '__main__':
    unittest.main()
