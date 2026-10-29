import copy
import hashlib
import json
import unittest
from pathlib import Path

from scripts.continue_v4_validation import failure_kind, validate_prefix


class ContinuationTests(unittest.TestCase):
    def test_contract_failure_continues_only_after_received_response(self):
        e = {'error': 'undetermined cause requires null root_cause and non-high confidence'}
        answers = [{'choices': [{'finish_reason': 'tool_calls'}]}]
        self.assertEqual(failure_kind(e, answers), 'model_output_validation')
        self.assertEqual(failure_kind(e, []), 'unknown_execution_error')
        self.assertEqual(failure_kind(e, answers, True), 'transport_or_provider_budget')

    def test_unknown_and_budgets_stop(self):
        answers = [{'choices': [{'finish_reason': 'tool_calls'}]}]
        for message in ['global evaluation API-call budget exhausted', 'model output token limit reached',
                        'model did not submit a valid RCA within budget']:
            self.assertEqual(failure_kind({'error': message}, answers), 'budget')
        for message in ['RemoteError', 'TimeoutError', 'HTTP 502', 'unexpected internal failure']:
            self.assertEqual(failure_kind({'error': message}, answers), 'unknown_execution_error')
        self.assertIsNone(failure_kind({'error': None}, answers))

    def test_output_truncation_is_not_schema_only_failure(self):
        self.assertEqual(failure_kind({'error': 'fixed arm failed to submit one complete RCA'},
                                     [{'choices': [{'finish_reason': 'length'}]}]), 'unknown_execution_error')

    def test_original_prefix_is_not_rescheduled(self):
        root = Path(__file__).resolve().parents[1] / 'artifacts/v4-validation/confirmed'
        previous = json.loads((root / 'evaluation/results.json').read_text())
        freeze = json.loads((root / 'freeze.json').read_text())
        raw = (root / 'network-fixture.json').read_bytes()
        budget = {'maximum': 100, 'maximum_usd': 1.0, 'attempts': previous['api_attempts'],
                  'accounted_usd': previous['conservative_accounted_usd']}
        remaining = validate_prefix(previous, raw, freeze, budget)
        self.assertEqual(len(remaining), 28)
        self.assertTrue(all(r['case'] > 0 for r in remaining))
        for mutation in ('order', 'budget', 'fixture'):
            changed, changed_budget, changed_raw = copy.deepcopy(previous), dict(budget), raw
            if mutation == 'order':
                changed['runs'][0], changed['runs'][1] = changed['runs'][1], changed['runs'][0]
            elif mutation == 'budget':
                changed_budget['attempts'] = 0
            else:
                changed_raw = raw + b' '
            with self.assertRaises(ValueError):
                validate_prefix(changed, changed_raw, freeze, changed_budget)


if __name__ == '__main__':
    unittest.main()
