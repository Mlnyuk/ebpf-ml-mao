from collections import Counter
import unittest

from rca.collector import event_counts, merge_counts, network_summary


class NetworkEvidenceTests(unittest.TestCase):
    def test_existing_probe_retains_peer_but_never_invents_success(self):
        event = {'process_kprobe': {'function_name': 'tcp_connect', 'args': [{'sock_arg': {
            'daddr': '10.2.3.4', 'dport': 9099, 'state': 'TCP_SYN_SENT'}}]}}
        counts = event_counts(event, 'kprobe:tcp_connect')
        self.assertEqual(counts['tcp_attempt|10.2.3.4|9099'], 1)
        view = network_summary(counts)
        self.assertEqual(view['tcp_connect_attempts'][0]['destination_port'], 9099)
        self.assertIn('connect_result', view['not_measured'])
        self.assertIn('NOT connection success', view['semantics'])

    def test_cardinality_bound_counts_omissions(self):
        counts = Counter()
        for i in range(100):
            merge_counts(counts, {'tcp_attempt|10.0.0.1|' + str(i): 1})
        self.assertEqual(len(counts), 17)
        summary = network_summary(counts)
        self.assertEqual(len(summary['tcp_connect_attempts']), 8)
        self.assertEqual(summary['omitted_destination_attempts'], 92)

    def test_invalid_or_uncollected_destination_is_not_a_healthy_result(self):
        counts = event_counts({'process_kprobe': {'function_name': 'tcp_connect', 'args': [
            {'sock_arg': {'daddr': 'injected instructions', 'dport': 42}}]}}, 'kprobe:tcp_connect')
        self.assertEqual(counts, {'kprobe:tcp_connect': 1})
        self.assertEqual(network_summary(counts)['tcp_connect_attempts'], [])


if __name__ == '__main__':
    unittest.main()
