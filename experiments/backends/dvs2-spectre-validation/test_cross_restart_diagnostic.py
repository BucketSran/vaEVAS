"""Calibrate decomposition measurements against hand-written trajectories."""
import unittest

import cross_restart_diagnostic as diagnostic


class RestartMeasurements(unittest.TestCase):
    def setUp(self):
        self.case = dict(family='timer-large', tau=.75, stop=1.25, maxstep=.5)
        # Slopes +1 to .75, then -1; .5 crossings at .5 and 1.
        self.rows = [dict(time=t,z=z,count=n) for t,z,n in
                     [(0,0,0),(.5,.5,1),(.75,.75,11),(1,.5,12),(1.25,.25,12)]]

    def test_exact_control_and_distinct_faults(self):
        result = diagnostic.measure(self.rows,self.case)
        self.assertTrue(result['meets_diagnostic_targets'])
        self.assertEqual(result['expected_cross_s'],[.5,1.])
        self.assertEqual(result['max_error_with_observed_timer_v'],0)
        wrong_history = [dict(r,z=r['z']+(.01 if r['time']>.75 else 0)) for r in self.rows]
        missed_return = [dict(r,count=11 if r['time']>=1 else r['count']) for r in self.rows]
        for rows in [wrong_history,missed_return]:
            self.assertFalse(diagnostic.measure(rows,self.case)['meets_diagnostic_targets'])

    def test_execution_delay_separate_from_history_error(self):
        # Timer executes at .8 instead of .75. Exact subsequent integral crosses
        # .5 at 1.1; anchoring to that observed timer removes the voltage error.
        rows=[dict(time=t,z=z,count=n) for t,z,n in
              [(0,0,0),(.5,.5,1),(.8,.8,11),(1.1,.5,12),(1.25,.35,12)]]
        result=diagnostic.measure(rows,self.case)
        self.assertAlmostEqual(result['timer_delay_s'],.05)
        self.assertAlmostEqual(result['max_voltage_error_v'],.1)
        self.assertLess(result['max_error_with_observed_timer_v'],1e-15)
        self.assertFalse(result['meets_diagnostic_targets'])

    def test_original_model_has_no_triangle_oracle(self):
        rows=[dict(time=0,z=0,count=0),dict(time=.5,z=.5,count=1),dict(time=1,z=1,count=2)]
        result=diagnostic.measure(rows,dict(family='original',stop=1,maxstep=.5))
        self.assertEqual(result['status'],'observed_without_unique_event_oracle')
        self.assertNotIn('meets_diagnostic_targets',result)

    def test_sparse_outputs_use_event_log_and_check_it_against_counter(self):
        rows=[self.rows[0],self.rows[1],self.rows[-1]]
        trace=[dict(time=.5,kind='cross'),dict(time=.75,kind='timer'),dict(time=1.,kind='cross')]
        result=diagnostic.measure(rows,dict(self.case,maxstep=1),trace)
        self.assertEqual(result['cross_count'],2)
        self.assertEqual(result['max_cross_time_error_s'],0)
        with self.assertRaisesRegex(ValueError,'counter.*event log'):
            diagnostic.measure(rows,dict(self.case,maxstep=1),trace[:-1])


if __name__=='__main__': unittest.main()
