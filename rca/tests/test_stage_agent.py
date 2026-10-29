import copy
import contextlib
import io
import unittest
from unittest.mock import patch
from scripts import stage_agent


class StageAgentTests(unittest.TestCase):
    def deployment(self):
        return {'metadata': {'resourceVersion': '123'}, 'spec': {'replicas': 0, 'template': {'spec': {
            'containers': [{'name': 'agent', 'env': [{'name': 'KEEP', 'value': 'x'},
                {'name': 'LLM_ENABLED', 'valueFrom': {'secretKeyRef': {'name': 'old', 'key': 'x'}}}]}],
            'volumes': [{'name': 'code', 'configMap': {'name': 'rca-code'}}]}}}}

    def test_patch_preserves_others_and_never_scales_or_enables(self):
        deployment = self.deployment()
        before = copy.deepcopy(deployment)
        operations = stage_agent.build_patch(deployment, 'versioned-code')
        self.assertEqual(deployment, before)
        self.assertEqual([x['op'] for x in operations[:2]], ['test', 'test'])
        env = operations[2]['value']
        self.assertIn({'name': 'KEEP', 'value': 'x'}, env)
        self.assertIn({'name': 'LLM_ENABLED', 'value': 'false'}, env)
        self.assertFalse(any('valueFrom' in e for e in env if e['name'] == 'LLM_ENABLED'))
        self.assertFalse(any(x['op'] != 'test' and x['path'] == '/spec/replicas' for x in operations))

    def test_running_or_terminating_agent_refused(self):
        for location in ('spec', 'status'):
            deployment = self.deployment()
            deployment.setdefault(location, {})['replicas'] = 1
            with self.assertRaises(ValueError):
                stage_agent.build_patch(deployment, 'code')

    def test_plan_only_makes_no_cluster_call(self):
        with patch('sys.argv', ['stage_agent']), contextlib.redirect_stdout(io.StringIO()), \
                patch.object(stage_agent, 'kubectl', side_effect=AssertionError('no cluster')):
            stage_agent.main()


if __name__ == '__main__':
    unittest.main()
