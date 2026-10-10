"""A whole-response demand guides work; original voltage acceptance still decides."""
GUARDS = ['CROSS', 'TRANSITION', 'DYNAMICS', 'COMPOSE', 'DEV:precision-chain']

import math
import unittest
from test_continuous_dynamics import rows
from test_root_recovery import request_for, observe, details
from test_sample_edge_filter import ramp_filter


def chain_request(*, delay=0, gain=1, budget=1e-10, times=None, extra=''):
    request = request_for(
        '@(initial_step) q=0; '
        '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3)) q=V(u,r); '
        f'V(e,r)<+transition(q,{delay},0.5,0.5); '
        f"V(y,r)<+laplace_nd({gain}*V(e,r),'{{1}},'{{1,0.25}});" + extra,
        'real q; electrical e;', budget=budget,
        times=times or [0, 1, 1.75, 2.5, 3])
    request['transient']['max_step'] = 1
    return request


class FilterBudget(unittest.TestCase):
    def test_sample_and_time_share_output_budget_without_query_dependence(self):
        sparse = [0, 1, 1.75, 2.5, 3]
        dense = sorted(set(sparse+[1.4142, 1.41423, math.sqrt(2)-1e-12,
                                   math.sqrt(2)+1e-12, 1.55, 1.6, 2]))
        for delay in (0, 0.125):
            for gain in (1, -2):
                for budget in (1e-10, 2.01e-6):
                    with self.subTest(delay=delay, gain=gain, budget=budget):
                        outputs = []
                        for times in (sparse, dense):
                            result, error, report = observe(chain_request(
                                delay=delay, gain=gain, budget=budget, times=times))
                            self.assertIsNone(error)
                            for t, row in zip(times, rows(result)):
                                expected = gain*math.sqrt(2)*ramp_filter(
                                    t, start=math.sqrt(2)+delay)
                                self.assertLessEqual(abs(row['y']-expected), budget)
                            demand = details(report, 'filter_root_budget')
                            self.assertEqual(len(demand), 1)
                            d = demand[0]
                            self.assertGreater(d['sample_sensitivity'], 0)
                            self.assertGreater(d['edge_sensitivity'], 0)
                            self.assertEqual(d['consumer'], 'dut:e' if gain == 1 else 'y')
                            self.assertGreater(d['target_width'], 0)
                            trials = details(report, 'root_refinement')
                            self.assertEqual(trials[-1]['stop'], 'target_reached')
                            self.assertLessEqual(trials[-1]['width_after'], d['target_width'])
                            outputs.append((result, report))
                        self.assertEqual(outputs[0][0]['transient']['events'],
                                         outputs[1][0]['transient']['events'])
                        self.assertEqual(outputs[0][0]['solutions'],
                                         [outputs[1][0]['solutions'][dense.index(t)] for t in sparse])
                        self.assertEqual(details(outputs[0][1], 'root_refinement'),
                                         details(outputs[1][1], 'root_refinement'))

    def test_impossible_budget_is_still_rejected_with_bounded_work(self):
        result, error, report = observe(chain_request(budget=1e-30))
        self.assertIsNone(result)
        self.assertIn(error['kind'], ('event_accuracy', 'waveform_accuracy'))
        self.assertLessEqual(report['counters'].get('root_refinement_iterations', 0), 256)

    def test_whole_response_demand_can_precede_a_local_failure(self):
        # On the baseline the event and first deadline pass with zero root
        # iterations. Both uncertainty contributions exceed this loose budget
        # after a gain of -2, so planning must not wait for that local failure.
        result, error, report = observe(chain_request(gain=-2, budget=1e-3))
        self.assertIsNone(error)
        demand = details(report, 'filter_root_budget')[0]
        self.assertGreater(demand['predicted_error_bound'], demand['budget'])
        self.assertGreater(report['counters']['root_refinement_iterations'], 0)
        self.assertEqual(details(report, 'root_refinement')[-1]['stop'], 'target_reached')

    def test_input_feedthrough_and_additional_history_keep_full_recovery(self):
        for suffix in ('+V(u,r)', "+laplace_nd(V(u,r),'{1},'{1,1})"):
            # Compile the different consumers through the public path.
            request = request_for(
                '@(initial_step) q=0; '
                '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3)) q=V(u,r); '
                'V(e,r)<+transition(q,0,0.5,0.5); '
                "V(y,r)<+laplace_nd(V(e,r),'{1},'{1,0.25})"+suffix+';',
                'real q; electrical e;', budget=1e-10)
            result, error, report = observe(request)
            self.assertIsNone(error)
            self.assertFalse(details(report, 'filter_root_budget'))
            self.assertTrue(all(t['target_width'] is None
                                for t in details(report, 'root_refinement')))

    def test_later_write_does_not_use_single_event_budget(self):
        result, error, report = observe(chain_request(
            extra='@(timer(2.5,0,1e-12)) q=2;'))
        self.assertIsNone(error)
        self.assertFalse(details(report, 'filter_root_budget'))
        self.assertTrue(all(t['target_width'] is None
                            for t in details(report, 'root_refinement')))


if __name__ == '__main__':
    unittest.main()
