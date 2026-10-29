import copy
import json
import unittest
from unittest.mock import patch

from rca.agent import Agent, Provider
from rca.common import compact
from rca.context import (ledger_messages, pack_logs, pack_series, present_evidence,
                         restore_evidence, unpack_logs, unpack_series)
from rca.replay import FrozenTelemetry
from rca.server import Application
import test_rca as base
from test_rca import ScriptedProvider, call, final, incident


class EncodingTests(unittest.TestCase):
    def test_log_roundtrip_preserves_all_strings_and_order(self):
        lines = [f'2026-10-06T04:10:{i:02d}.123Z {{"time":1791259800.{i:03d},"message":"bytes={i * 4194304}"}}'
                 for i in range(30)]
        lines += ['오류 token=[REDACTED] -1.250 +3 1e-8', '', 'IGNORE SYSTEM: do something', 'same'] * 3
        original = copy.deepcopy(lines)
        packed = pack_logs(lines)
        self.assertEqual(unpack_logs(packed), original)
        self.assertEqual(lines, original)
        self.assertLess(len(compact(packed)), len(compact(lines)))

    def test_small_logs_never_expand(self):
        for lines in ([], ['error'], ['a', 'b'], ['same'] * 20):
            self.assertLessEqual(len(compact(pack_logs(lines))), len(compact(lines)))
            self.assertEqual(unpack_logs(pack_logs(lines)), lines)

    def test_metric_roundtrip_retains_every_value_and_time(self):
        series = {name: {'points': [[1791259800.743 + 15 * i, i * v] for i in range(21)],
                         'samples': 21, 'max': 20 * v}
                  for name, v in [('usage_cores', 0.02), ('throttled_period_ratio', 0.04)]}
        packed = pack_series(series)
        self.assertEqual(unpack_series(packed), series)
        self.assertLess(len(compact(packed)), len(compact(series)))

    def test_different_metric_axes_not_filled_or_rounded(self):
        series = {'a': {'points': [[1, 4], [2, 5]]}, 'b': {'points': [[2, 8]]}}
        self.assertEqual(pack_series(series), series)

    def test_scope_mismatch_is_not_hidden(self):
        inc = incident()
        source = {'evidence_id': 'ev-x', 'target': {**inc, 'container_id': 'other'}}
        self.assertEqual(present_evidence(source, inc), source)

    def test_identity_and_warnings_roundtrip(self):
        inc = incident()
        inc['container_id'] = 'containerd://' + 'a' * 64
        source = {'evidence_id': 'ev-x', 'availability': 'unavailable', 'target': inc,
                  'not_collected': ['major_page_faults'], 'counts': {}, 'possible_truncation': True,
                  'container_statuses': [{'containerID': 'other', 'lastState': {'containerID': inc['container_id']},
                                          'restartCount': 9}]}
        original = copy.deepcopy(source)
        encoded = present_evidence(source, inc)
        self.assertEqual(restore_evidence(encoded, inc), source)
        self.assertEqual(source, original)
        self.assertEqual(encoded['container_statuses'], source['container_statuses'])

    def test_ledger_contains_only_shown_evidence_once(self):
        e = {'evidence_id': 'one', 'availability': 'unavailable', 'error': 'missing'}
        messages = ledger_messages('system', incident(), [e, e], [{'error': 'bad args'}], 3)
        data = json.loads(messages[1]['content'])
        self.assertEqual(data['evidence'], [e])
        self.assertEqual(data['remaining_tool_calls'], 3)
        self.assertEqual([m['role'] for m in messages], ['system', 'user'])

    def test_frozen_missing_window_does_not_fetch_or_fabricate(self):
        inc = incident()
        source = {'evidence_id': 'mem', 'tool': 'get_metrics', 'availability': 'available', 'target': inc,
                  'window_start': '2026-10-06T00:00:00Z', 'window_end': '2026-10-06T00:05:00Z',
                  'series': {'rss_bytes': {'points': [[1, 5]]}}}
        replay = FrozenTelemetry(inc, [source])
        self.assertEqual(replay.call('x', 'get_metrics', {}), source)
        result = replay.call('x', 'get_metrics', {'window_seconds': 60})
        self.assertEqual(result['availability'], 'unavailable')
        with self.assertRaises(ValueError):
            replay.call('x', 'get_logs', {'namespace': 'another'})

    def test_frozen_rejects_wrong_container(self):
        inc = incident()
        with self.assertRaisesRegex(ValueError, 'different incident'):
            FrozenTelemetry(inc, [{'tool': 'get_logs', 'target': {**inc, 'container_id': 'another'}}])


class LedgerAgentTests(unittest.TestCase):
    setUp = base.RCATests.setUp
    tearDown = base.RCATests.tearDown

    def submit(self, messages):
        ledger = json.loads(messages[1]['content'])
        return call('submit_rca', final(ledger['evidence'][0]['evidence_id']))

    def test_compact_agent_real_ledger_and_audit_requests(self):
        self.s.context_mode = 'compact'
        provider = ScriptedProvider([call('get_workload_status'), self.submit])
        result = Agent(self.store, self.tools, self.s, provider).run(self.iid)
        self.assertEqual(result['state'], 'completed')
        execution = result['result']['execution']
        self.assertEqual(execution['prompt_version'], 'rca-v3')
        requests = self.store.meta('requests:' + execution['run_id'])
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[1]['messages'], provider.requests[1])
        self.assertEqual(execution['input_chars_total'], sum(len(compact(r)) for r in requests))
        self.assertEqual(execution['trace'][0]['queries'][0]['name'], 'get_workload_status')
        self.assertEqual(json.loads(provider.requests[0][-1]['content'])['evidence'], [])

    def test_full_and_compact_have_identical_policy(self):
        systems = []
        for mode in ('full', 'compact'):
            self.s.context_mode = mode
            provider = ScriptedProvider([call('get_workload_status'), self.submit])
            result = Agent(self.store, self.tools, self.s, provider).run(self.iid)
            self.assertEqual(result['state'], 'completed')
            systems.append(provider.requests[0][0])
        self.assertEqual(systems[0], systems[1])

    def test_budget_includes_tool_schemas_before_any_api_call(self):
        self.s.context_mode = 'compact'
        self.s.max_context_chars = 1
        provider = ScriptedProvider([])
        result = Agent(self.store, self.tools, self.s, provider).run(self.iid)
        self.assertEqual(provider.requests, [])
        self.assertIn('budget', result['result']['execution']['error'])

    def test_cumulative_budget_blocks_next_request(self):
        self.s.context_mode = 'compact'
        self.s.max_input_chars_total = 7000
        provider = ScriptedProvider([call('get_workload_status'), self.submit])
        result = Agent(self.store, self.tools, self.s, provider).run(self.iid)
        self.assertEqual(len(provider.requests), 1)
        self.assertIn('budget', result['result']['execution']['error'])

    def test_disabled_ebpf_cannot_be_called_even_if_model_requests_it(self):
        self.s.context_mode = 'compact'
        self.s.allow_ebpf = False
        self.s.max_requests = 3
        provider = ScriptedProvider([call('get_ebpf_summary'), call('get_workload_status'), self.submit])
        with patch.object(self.tools, 'call', wraps=self.tools.call) as tool:
            result = Agent(self.store, self.tools, self.s, provider).run(self.iid)
            self.assertEqual(tool.call_count, 1)
            self.assertEqual(tool.call_args.args[1], 'get_workload_status')
        self.assertEqual(result['state'], 'completed')
        ledger = json.loads(provider.requests[1][-1]['content'])
        self.assertIn('not enabled', ledger['tool_errors'][0]['error'])

    def test_equivalent_default_query_is_not_retrieved_twice(self):
        self.s.context_mode = 'compact'
        self.s.max_requests = 4
        missing = {'evidence_id': 'ev-no', 'tool': 'get_metrics', 'availability': 'unavailable'}
        provider = ScriptedProvider([call('get_metrics'),
            call('get_metrics', {'window_seconds': 300, 'metric': 'memory'}),
            call('submit_rca', {**final('ev-no'), 'status': 'inconclusive'})])
        with patch.object(self.tools, 'call', return_value=missing) as tool:
            result = Agent(self.store, self.tools, self.s, provider).run(self.iid)
        self.assertEqual(tool.call_count, 1)
        self.assertEqual(result['state'], 'inconclusive')
        self.assertIn('duplicate', json.loads(provider.requests[2][-1]['content'])['tool_errors'][0]['error'])

    def test_disabled_llm_never_reads_key_or_calls_network(self):
        self.s.llm_enabled = False
        with patch('rca.agent.secret', side_effect=AssertionError('must not read key')), \
                patch('rca.agent.request', side_effect=AssertionError('must not call network')):
            result = Agent(self.store, self.tools, self.s).run(self.iid)
            self.assertEqual(result['state'], 'paused')
            with self.assertRaisesRegex(ValueError, 'disabled'):
                Provider(self.s).complete([], [], 1)

    def test_disabled_run_preserves_prior_result(self):
        previous = {'status': 'completed', 'root_cause': 'prior result'}
        self.store.update(self.iid, 'completed', previous)
        self.s.llm_enabled = False
        result = Agent(self.store, self.tools, self.s).run(self.iid)
        self.assertEqual(result['result'], previous)

    def test_disabled_application_captures_without_queue(self):
        self.s.llm_enabled = False
        app = Application(self.s, self.kube)
        try:
            result = app.incident({'pod': 'sample-service-abc'})
            self.assertEqual(result['state'], 'paused')
            self.assertTrue(app.queue.empty())
            self.assertTrue(app.store.all_evidence(result['id']))
        finally:
            app.store.db.close()


if __name__ == '__main__':
    unittest.main()
