import ast
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from rca import lab
from rca.common import Settings
from rca.agent import SYSTEM_V4, Provider
from scripts.evaluate_fixed import prepare
from scripts.run_v4_validation import fixed_run
from test_rca import incident, final, call


class ValidationTests(unittest.TestCase):
    def test_capture_schedule_variable_is_not_shadowed_by_evidence_loops(self):
        source = Path(__file__).resolve().parents[1] / 'scripts/capture_network_study.py'
        tree = ast.parse(source.read_text())
        outer = next(n for n in ast.walk(tree) if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == 'trial_spec')
        assigned = [n for statement in outer.body for n in ast.walk(statement)
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == 'trial_spec']
        self.assertEqual(assigned, [])

    def case(self):
        return {'incident': {'data': incident()}, 'evidence': [
            {'tool': 'get_workload_status', 'availability': 'available', 'evidence_id': 'ev-test'}]}

    def test_v4_fixed_uses_same_prompt_and_schema(self):
        case = self.case()
        _, messages = prepare(case, 'compact-v4')
        self.assertEqual(messages[0]['content'], SYSTEM_V4)
        value = final('ev-test')
        value['root_cause_status'] = 'undetermined'
        value['evidence'][0]['claim_type'] = 'observation'
        class Fake(Provider):
            def complete(self, messages, tools, timeout):
                return {'choices': [{'finish_reason': 'tool_calls', 'message': call('submit_rca', value)}],
                        'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'cost': 0.001}}
        settings = Settings()
        with tempfile.TemporaryDirectory() as directory:
            result = fixed_run(case, settings, Fake(settings), Path(directory))
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['result']['execution']['llm_responses'], 1)

    def test_fixed_invalid_output_preserves_returned_usage(self):
        class Fake(Provider):
            def complete(self, messages, tools, timeout):
                return {'choices': [{'finish_reason': 'length', 'message': {}}],
                        'usage': {'prompt_tokens': 20, 'completion_tokens': 30, 'cost': 0.002}}
        settings = Settings()
        with tempfile.TemporaryDirectory() as directory:
            result = fixed_run(self.case(), settings, Fake(settings), Path(directory))
        self.assertEqual(result['state'], 'error')
        self.assertEqual(result['result']['execution']['provider_reported_cost_usd'], 0.002)

    def test_real_handler_log_condition_does_not_reveal_injection_label(self):
        for detail in ('opaque', 'endpoint'):
            handler = lab.Handler.__new__(lab.Handler)
            handler.path = '/work'
            handler.wfile = io.BytesIO()
            handler.send_response = lambda status: None
            handler.end_headers = lambda: None
            messages = []
            with patch.dict('os.environ', {'BACKEND_URL': 'http://sample-backend:8080', 'LOG_DETAIL': detail}), \
                    patch.object(lab, 'routing_fault', 'network_port'), \
                    patch.object(lab, 'routing_fault_until', time.monotonic() + 60), \
                    patch.object(lab.subprocess, 'run'), \
                    patch.object(lab.urllib.request, 'urlopen', side_effect=OSError('test')), \
                    patch.object(lab, 'log', side_effect=messages.append):
                handler.do_GET()
            self.assertEqual('target=http://sample-backend:9099' in messages[0], detail == 'endpoint')
            self.assertNotIn('network_port', json.dumps(messages))
            self.assertEqual(json.loads(handler.wfile.getvalue())['error'], 'dependency request failed')


if __name__ == '__main__':
    unittest.main()
