import unittest
from research.clock_capture import bracket,translate_epoch

class ClockTests(unittest.TestCase):
    def test_slow_node_to_prometheus_bounds(self):
        node=bracket(95,100,100.4);prom=bracket(101,100.9,101.2)
        mapped=translate_epoch(120,node,prom)
        self.assertLessEqual(mapped['bounds'][0],125)
        self.assertGreaterEqual(mapped['bounds'][1],125)
        self.assertGreater(mapped['uncertainty_seconds'],0)
    def test_identical_zero_uncertainty_clocks(self):
        clock=bracket(100,100,100)
        self.assertEqual(translate_epoch(120,clock,clock),{'midpoint':120,'bounds':[120,120],'uncertainty_seconds':0})
    def test_clock_step_refused(self):
        with self.assertRaises(ValueError):bracket(100,101,100)

if __name__=='__main__':unittest.main()
