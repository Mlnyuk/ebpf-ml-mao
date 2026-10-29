import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.finish_v4_validation import preflight


class FinishTests(unittest.TestCase):
    def setUp(self):
        self.study = Path(__file__).resolve().parents[1] / 'artifacts/v4-validation/confirmed'
        self.read_text = Path.read_text
        self.prior = json.loads((self.study / 'continuation-evaluation/combined-results.json').read_text())

    def read_checkpoint(self, path, *args, **kwargs):
        if path == self.study / 'budget.json':
            return json.dumps({'maximum': 100, 'maximum_usd': 1.0,
                              'attempts': self.prior['api_attempts'],
                              'accounted_usd': self.prior['conservative_accounted_usd']})
        return self.read_text(path, *args, **kwargs)

    def test_only_seven_not_prior_failed_runs(self):
        with patch.object(Path, 'read_text', lambda path, *a, **kw: self.read_checkpoint(path, *a, **kw)):
            prior, fixture, budget, schedule = preflight(self.study)
        self.assertEqual(len(schedule), 7)
        self.assertEqual(schedule[0], {'case': 6, 'arm': 'compact-v4', 'repeat': 0})
        self.assertNotIn({'case': 6, 'arm': 'compact-v4-no-ebpf', 'repeat': 0}, schedule)
        self.assertEqual(budget['attempts'], 71)
        self.assertEqual(len(prior['runs']), 25)

    def test_budget_cannot_be_reset(self):
        def read(path, *args, **kwargs):
            value = self.read_checkpoint(path, *args, **kwargs)
            if path == self.study / 'budget.json':
                budget = json.loads(value)
                budget['attempts'] = 0
                return json.dumps(budget)
            return value
        with patch.object(Path, 'read_text', read), self.assertRaisesRegex(ValueError, 'Budget changed'):
            preflight(self.study)


if __name__ == '__main__':
    unittest.main()
