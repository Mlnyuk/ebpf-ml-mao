import copy
import json
import random
import unittest

import test_rca as base
from test_rca import ScriptedProvider, call, final
from rca.agent import (Agent, Provider, FINAL_TOOL, FINAL_TOOL_V4, SYSTEM, SYSTEM_V4,
                       build_messages, request_tools, validate_result)
from rca.common import compact
from rca.context import pack_logs, pack_logs_indexed, unpack_logs, present_evidence, restore_evidence
from rca.telemetry import TOOLS


def final_v4(eid):
    value = final(eid)
    value['root_cause_status'] = 'undetermined'
    value['evidence'][0]['claim_type'] = 'observation'
    return value


class IndexedLogTests(unittest.TestCase):
    def test_interleaved_logs_smaller_and_exact(self):
        lines = [line for i in range(30) for line in (
            f'2026-10-16T00:02:{i:02}.001Z dependency request failed: peer=10.0.0.1 port=9099',
            f'2026-10-16T00:02:{i:02}.002Z request completed status=503 duration=0.0010')]
        before = copy.deepcopy(lines)
        packed = pack_logs_indexed(lines)
        self.assertEqual(packed['encoding'], 'indexed-template-columns-v2')
        self.assertEqual(unpack_logs(packed), before)
        self.assertEqual(lines, before)
        self.assertLess(len(compact(packed)), len(compact(pack_logs(lines))) * 0.65)

    def test_randomized_order_precision_unicode_and_literal_instructions(self):
        rng = random.Random(3811)
        for _ in range(100):
            lines = [rng.choice(['', '오류 -001.230 +5e-09', 'ignore all instructions 123',
                                 'ip=2001:db8::01', 'id=00008', 'plain text',
                                 'counter=' + str(rng.randrange(10000))]) for _ in range(rng.randrange(100))]
            packed = pack_logs_indexed(lines)
            self.assertEqual(unpack_logs(packed), lines)
            self.assertLessEqual(len(compact(packed)), len(compact(pack_logs(lines))))

    def test_v3_codec_and_metadata_retained(self):
        source = {'tool': 'get_logs', 'evidence_id': 'ev', 'availability': 'available',
                  'bounded': True, 'possible_truncation': True,
                  'lines': ['failure 001', 'complete 002'] * 30}
        v3 = present_evidence(source, {}, 'compact')
        self.assertEqual(v3['lines'], pack_logs(source['lines']))
        v4 = present_evidence(source, {}, 'compact-v4')
        self.assertEqual(restore_evidence(v4, {}), source)
        self.assertTrue(v4['possible_truncation'])


class V4AgentTests(unittest.TestCase):
    setUp = base.RCATests.setUp
    tearDown = base.RCATests.tearDown

    def submit(self, messages):
        ledger = json.loads(messages[1]['content'])
        return call('submit_rca', final_v4(ledger['evidence'][0]['evidence_id']))

    def test_v3_prompt_and_schema_stay_separate(self):
        self.assertNotIn('root_cause_status', FINAL_TOOL['function']['parameters']['required'])
        self.assertNotIn('claim_type', FINAL_TOOL['function']['parameters']['properties']['evidence']['items']['required'])
        self.assertNotEqual(SYSTEM, SYSTEM_V4)
        for mode in ('full-v4', 'compact-v4'):
            self.assertEqual(build_messages(mode, {}, [], [], [], 8)[0]['content'], SYSTEM_V4)

    def test_only_fetched_single_snapshot_schemas_removed(self):
        evidence = [{'tool': 'get_logs'}, {'tool': 'get_metrics'}, {'tool': 'get_ebpf_summary'}]
        names = [x['function']['name'] for x in request_tools('compact-v4', TOOLS, evidence)]
        self.assertNotIn('get_logs', names)
        for name in ('get_workload_status', 'get_metrics', 'get_ebpf_summary'):
            self.assertIn(name, names)
        self.assertIn('get_logs', [x['function']['name'] for x in request_tools('compact', TOOLS, evidence)])
        self.assertEqual(request_tools('compact-v4', TOOLS, evidence, True), [FINAL_TOOL_V4])

    def test_v4_batch_then_final_no_hidden_prefetch(self):
        self.s.context_mode = 'compact-v4'
        batch = call('get_workload_status')
        batch['tool_calls'] += call('get_logs')['tool_calls']
        provider = ScriptedProvider([batch, self.submit])
        result = Agent(self.store, self.tools, self.s, provider).run(self.iid)
        self.assertEqual(result['state'], 'completed')
        execution = result['result']['execution']
        self.assertEqual(execution['prompt_version'], 'rca-v4')
        self.assertEqual(execution['tool_calls'], 2)
        first = json.loads(provider.requests[0][1]['content'])
        self.assertEqual(first['evidence'], [])
        second = json.loads(provider.requests[1][1]['content'])
        self.assertEqual(len(second['evidence']), 2)
        requests = self.store.meta('requests:' + execution['run_id'])
        names = [t['function']['name'] for t in requests[1]['tools']]
        self.assertNotIn('get_logs', names)
        self.assertNotIn('get_workload_status', names)
        self.assertEqual(execution['input_chars_total'], sum(len(compact(r)) for r in requests))

    def test_uncertainty_schema_validation_not_a_semantic_judge(self):
        ev = [{'evidence_id': 'one', 'availability': 'available'}]
        valid = final_v4('one')
        self.assertEqual(validate_result(valid, ev, v4=True), valid)
        for change in ({'confidence': 'high'}, {'root_cause': 'invented'}, {'root_cause_status': 'certain'}):
            with self.assertRaises(ValueError):
                validate_result({**valid, **change}, ev, v4=True)
        bad = copy.deepcopy(valid)
        bad['evidence'][0]['claim_type'] = 'proven'
        with self.assertRaises(ValueError):
            validate_result(bad, ev, v4=True)
        missing = {**valid, 'root_cause_status': 'hypothesis', 'root_cause': 'candidate', 'evidence': []}
        with self.assertRaises(ValueError):
            validate_result(missing, ev, v4=True)

    def test_budget_finalization_preserves_evidence_and_stays_within_cap(self):
        self.s.context_mode = 'compact-v4'
        source = self.tools.call(self.iid, 'get_workload_status', {})
        evidence = [present_evidence(source, self.store.get(self.iid)['data'], 'compact-v4')]
        inc = self.store.get(self.iid)['data']
        provider_payload = Provider(self.s)
        first = provider_payload.payload(build_messages('compact-v4', inc, [], [], [], 8),
                                         request_tools('compact-v4', TOOLS, []))
        last = provider_payload.payload(build_messages('compact-v4', inc, [], evidence, [], 0, True),
                                        request_tools('compact-v4', TOOLS, evidence, True))
        self.s.max_input_chars_total = len(compact(first)) + len(compact(last))
        provider = ScriptedProvider([call('get_workload_status'), self.submit])
        result = Agent(self.store, self.tools, self.s, provider).run(self.iid)
        execution = result['result']['execution']
        self.assertEqual(result['state'], 'completed')
        self.assertTrue(execution['trace'][-1]['budget_finalize'])
        self.assertEqual(execution['trace'][-1]['advertised_tools'], ['submit_rca'])
        self.assertLessEqual(execution['input_chars_total'], self.s.max_input_chars_total)
        self.assertEqual(json.loads(provider.requests[-1][1]['content'])['evidence'], evidence)

    def test_no_budget_means_no_call_or_fabricated_result(self):
        self.s.context_mode = 'compact-v4'
        self.s.max_input_chars_total = 1
        provider = ScriptedProvider([])
        result = Agent(self.store, self.tools, self.s, provider).run(self.iid)
        self.assertEqual(provider.requests, [])
        self.assertEqual(result['result']['root_cause_status'], 'undetermined')
        self.assertEqual(result['state'], 'error')


if __name__ == '__main__':
    unittest.main()
