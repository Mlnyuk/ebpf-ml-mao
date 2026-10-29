import copy
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from rca.agent import Agent, Provider, validate_result
from rca.collector import event_identity
from rca.common import Settings, epoch, now, redact
from rca.server import Application
from rca.store import Store
from rca.telemetry import Telemetry


def incident():
    return {'namespace': 'rca-lab', 'pod': 'sample-service-abc', 'pod_uid': 'aaa-bbb',
            'container_name': 'app', 'container_id': 'containerd://old', 'node': 'worker-1',
            'time': now(), 'symptom': 'ContainerRestart'}


def pod():
    i = incident()
    return {'metadata': {'name': i['pod'], 'uid': i['pod_uid'], 'creationTimestamp': now()},
            'spec': {'nodeName': 'worker-1', 'containers': [{'name': 'app', 'resources': {'limits': {'memory': '128Mi'}}}]},
            'status': {'phase': 'Running', 'containerStatuses': [{'name': 'app', 'containerID': 'containerd://new',
                'restartCount': 1, 'lastState': {'terminated': {'containerID': 'containerd://old', 'reason': 'OOMKilled'}}}]}}


class FakeKube:
    def __init__(self):
        self.paths = []
        self.value = pod()

    def get(self, path, raw=False):
        self.paths.append(path)
        if '/log?' in path:
            return now() + ' token=abcdef allocation failed\n'
        if '/events?' in path:
            return {'items': []}
        return self.value


class ScriptedProvider:
    """Test-only transport double. Never used by the deployed application."""
    def __init__(self, sequence):
        self.sequence = iter(sequence)
        self.requests = []

    def complete(self, messages, tools, timeout):
        self.requests.append(copy.deepcopy(messages))
        value = next(self.sequence)
        if callable(value):
            value = value(messages)
        return {'model': 'TEST-DOUBLE', 'choices': [{'message': value, 'finish_reason': 'tool_calls'}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 20}}


def call(name, args=None):
    return {'role': 'assistant', 'tool_calls': [{'id': name, 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(args or {})}}]}


def final(eid):
    return {'status': 'completed', 'failure_mechanism': 'memory limit termination', 'root_cause': None,
            'confidence': 'low', 'evidence': [{'evidence_id': eid, 'supports': 'termination state'}],
            'missing_evidence': ['underlying allocation cause'], 'recommended_action': 'inspect allocation'}


class RCATests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.s = Settings()
        self.s.llm_enabled = True
        self.s.context_mode = 'legacy'
        self.s.database = self.temp.name + '/db.sqlite3'
        self.s.api_key_file = self.temp.name + '/missing-key'
        self.store = Store(self.s.database)
        self.kube = FakeKube()
        self.tools = Telemetry(self.kube, self.store, self.s)
        self.iid, _ = self.store.add(incident(), 'first')
        self.tools.capture(self.iid, pod())

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_incident_dedup(self):
        other, created = self.store.add(incident(), 'first')
        self.assertEqual(other, self.iid)
        self.assertFalse(created)

    def test_missing_key_never_calls_provider(self):
        agent = Agent(self.store, self.tools, self.s)
        with patch.object(Provider, 'complete', side_effect=AssertionError('must not call')):
            result = agent.run(self.iid)
        self.assertEqual(result['state'], 'awaiting_api_key')
        self.assertIsNone(result['result'])

    def test_model_selects_tool_then_final_with_actual_evidence_id(self):
        def submit(messages):
            result = json.loads(messages[-1]['content'])
            return call('submit_rca', final(result['evidence_id']))
        provider = ScriptedProvider([call('get_workload_status'), submit])
        result = Agent(self.store, self.tools, self.s, provider).run(self.iid)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['result']['execution']['input_tokens'], 200)
        self.assertAlmostEqual(result['result']['execution']['estimated_cost_usd'], 0.00005)
        self.assertEqual(len(provider.requests[0]), 2)
        self.assertNotIn('OOMKilled', provider.requests[0][-1]['content'])

    def test_hallucinated_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'evidence'):
            validate_result(final('invented'), [])

    def test_no_data_cannot_support_completed_result(self):
        with self.assertRaisesRegex(ValueError, 'available'):
            validate_result(final('ev-1'), [{'evidence_id': 'ev-1', 'availability': 'unavailable'}])

    def test_budget_exhaustion_is_inconclusive(self):
        self.s.max_requests = 2
        result = Agent(self.store, self.tools, self.s, ScriptedProvider([
            call('get_workload_status'), call('get_logs')])).run(self.iid)
        self.assertEqual(result['result']['status'], 'inconclusive')
        self.assertEqual(result['result']['execution']['tool_calls'], 1)

    def test_repeat_query_is_not_executed_again(self):
        self.s.max_requests = 3
        provider = ScriptedProvider([call('get_workload_status'), call('get_workload_status'), call('submit_rca', final('bad'))])
        with patch.object(self.tools, 'call', wraps=self.tools.call) as method:
            Agent(self.store, self.tools, self.s, provider).run(self.iid)
            self.assertEqual(method.call_count, 1)

    def test_daily_limit_counts_retries(self):
        self.assertTrue(self.store.claim(self.iid, 1))
        self.store.update(self.iid, 'error')
        with self.assertRaisesRegex(ValueError, 'daily'):
            self.store.claim(self.iid, 1)

    def test_query_scope_cannot_be_changed(self):
        with self.assertRaises(ValueError):
            self.tools.call(self.iid, 'get_logs', {'namespace': 'kube-system'})
        with self.assertRaises(ValueError):
            self.tools.call(self.iid, 'get_metrics', {'window_seconds': 100000})
        with self.assertRaises(ValueError):
            self.tools.call(self.iid, 'exec', {})

    def test_logs_use_previous_container_and_redact(self):
        evidence = self.tools.call(self.iid, 'get_logs', {})
        self.assertTrue(evidence['previous'])
        self.assertIn('previous=true', self.kube.paths[-1])
        self.assertNotIn('abcdef', json.dumps(evidence))

    def test_changed_uid_refuses_live_logs(self):
        other, _ = self.store.add(incident(), 'second')
        self.kube.value['metadata']['uid'] = 'replacement'
        evidence = self.tools.call(other, 'get_logs', {})
        self.assertEqual(evidence['availability'], 'unavailable')

    def test_event_identity_exact_uid_and_container(self):
        event = {'time': now(), 'process_exec': {'process': {'pod': {
            'namespace': 'rca-lab', 'uid': 'uid-1', 'container': {'id': 'containerd://123'}}}}}
        self.assertEqual(event_identity(event, 'rca-lab')[:3], ('uid-1', 'containerd://123', 'process_exec'))
        self.assertIsNone(event_identity(event, 'other'))

    def test_window_retry_idempotent_and_other_container_excluded(self):
        t = epoch(self.store.get(self.iid)['data']['time'])
        payload = {'node': 'worker-1', 'health': {'source_readable': True}, 'windows': [
            {'pod_uid': 'aaa-bbb', 'container_id': 'containerd://old', 'start': t-10, 'end': t,
             'counts': {'process_exec': 3}},
            {'pod_uid': 'aaa-bbb', 'container_id': 'containerd://new', 'start': t-10, 'end': t,
             'counts': {'process_exec': 100}}]}
        self.store.ingest(payload)
        self.store.ingest(payload)
        self.tools.freeze_ebpf(self.iid)
        result = self.tools.call(self.iid, 'get_ebpf_summary', {})
        self.assertEqual(result['counts']['process_exec'], 3)
        self.assertIn('scheduler_latency', result['not_collected'])

    def test_missing_ebpf_is_not_normal(self):
        result = self.tools.call(self.iid, 'get_ebpf_summary', {})
        self.assertEqual(result['availability'], 'unavailable')
        self.assertEqual(result['counts'], {})

    def test_prometheus_uid_filter_and_missing_data(self):
        with patch('rca.telemetry.request', return_value={'status': 'success', 'data': {'result': []}}) as req:
            result = self.tools.call(self.iid, 'get_metrics', {'metric': 'memory'})
            self.assertIn('podaaa', req.call_args[0][0])
            self.assertEqual(result['availability'], 'unavailable')

    def test_preflight_can_capture_without_enqueue(self):
        app = Application(self.s, self.kube)
        result = app.incident({'pod': 'sample-service-abc'}, enqueue=False)
        self.assertTrue(app.queue.empty())
        self.assertEqual(result['state'], 'awaiting_api_key')
        app.store.db.close()

    def test_redaction(self):
        self.assertNotIn('sensitive', json.dumps(redact({'api_key': 'sensitive', 'log': 'Bearer sensitive token=sensitive'})))

    def test_real_http_provider_tool_protocol(self):
        received = []
        class FakeHTTP(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.append(body)
                if len(received) == 1:
                    message = call('get_workload_status')
                else:
                    eid = json.loads(body['messages'][-1]['content'])['evidence_id']
                    message = call('submit_rca', final(eid))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'choices': [{'message': message, 'finish_reason': 'tool_calls'}],
                                            'usage': {'prompt_tokens': 100, 'completion_tokens': 20}}).encode())
        http = ThreadingHTTPServer(('127.0.0.1', 0), FakeHTTP)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            self.s.api_url = 'http://127.0.0.1:' + str(http.server_port)
            self.s.api_key_file = self.temp.name + '/test-key'
            Path(self.s.api_key_file).write_text('test-only-not-a-real-key')
            result = Agent(self.store, self.tools, self.s).run(self.iid)
            self.assertEqual(result['state'], 'completed')
            self.assertEqual(received[0]['model'], 'z-ai/glm-5.3-flash')
            self.assertEqual(received[0]['reasoning'], {'effort': 'low', 'exclude': True})
            self.assertEqual(received[0]['provider'], {'require_parameters': True})
            self.assertNotIn('thinking', received[0])
            self.assertEqual(received[1]['messages'][-1]['tool_call_id'], 'get_workload_status')
        finally:
            http.shutdown()
            http.server_close()

    def test_zai_request_is_separate_from_openrouter(self):
        self.s.provider = 'zai'
        with patch('rca.agent.secret', return_value='test-key'), patch('rca.agent.request') as req:
            Provider(self.s).complete([], [], 5)
        body = req.call_args.args[2]
        self.assertEqual(body['thinking'], {'type': 'enabled', 'clear_thinking': True})
        self.assertNotIn('provider', body)

    def test_provider_reported_cost(self):
        def submit(messages):
            return call('submit_rca', final(json.loads(messages[-1]['content'])['evidence_id']))
        provider = ScriptedProvider([call('get_workload_status'), submit])
        original = provider.complete
        def complete(*args):
            response = original(*args)
            response['usage']['cost'] = 0.0000123
            return response
        provider.complete = complete
        result = Agent(self.store, self.tools, self.s, provider).run(self.iid)
        self.assertAlmostEqual(result['result']['execution']['provider_reported_cost_usd'], 0.0000246)


if __name__ == '__main__':
    unittest.main()
