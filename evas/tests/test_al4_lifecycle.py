"""Bounded AL-4 compositions, with independent piecewise answers."""

GUARDS = ["DYNAMICS", "CROSS", "TRANSITION", "COMPOSE"]

import math
import unittest

from test_continuous_dynamics import compile_model, run, rows, assert_close


class BoundedLifecycleContracts(unittest.TestCase):
    def test_changed_flow_replaces_old_root_at_independent_exact_crossing(self):
        # z'=1 before .25 and 2 afterwards: z=.75 at .5, not .75.
        program = compile_model(
            '@(initial_step) begin q=1; n=0; end '
            '@(timer(0.25,0,1e-12)) q=2; '
            '@(cross(V(z,r)-0.75,1,1e-10,1e-10)) n=n+1; '
            'V(z,r)<+idt(q,0); V(y,r)<+n;',
            'real q; integer n; electrical z;')
        anchors = [0,.125,.25,.375,.5,.625,.75,.875,1]
        baseline = None
        for times in [anchors, sorted(set(anchors+[i/64 for i in range(65)]))]:
            result = run(program, times=times, stop=1, max_step=1,
                         vabstol=1e-8, reltol=0)
            events = result['transient']['events']
            self.assertEqual(len(events), 2)
            self.assertAlmostEqual(events[0]['time'], .25, delta=1e-12)
            self.assertAlmostEqual(events[1]['time'], .5, delta=1e-10)
            if baseline is not None:
                self.assertEqual(events, baseline)
            baseline = events
            for t, row in zip(times, rows(result)):
                assert_close(self, row['dut:z'], t if t<=.25 else 2*t-.25, delta=1e-8)
                assert_close(self, row['y'], int(t>=.5), delta=1e-8)

    def test_interrupted_edge_keeps_integral_and_nonzero_filter_continuation(self):
        # q changes 0->1 at .25 then 1->0 at .5. The unit-time ramp
        # reaches .25 at interruption, returns to 0 at .75 and stays there.
        # Independent x'=1, x(0)=3; f'+f=u with f(0)=2 and u=2+t.
        # Thus f=1+t+exp(-t), also across the input corner at .75.
        program = compile_model(
            '@(initial_step) begin q=0; n=0; end '
            '@(timer(0.25,0,1e-12)) q=1; '
            '@(timer(0.5,0,1e-12)) q=0; '
            '@(timer(0.875,0,1e-12)) n=n+1; '
            'V(y,r)<+transition(q,0,1,1); V(x,r)<+idt(1,3); '
            "V(f,r)<+laplace_nd(V(u,r),'{1},'{1,1}); V(count,r)<+n;",
            'real q; integer n; electrical x,f,count;')
        anchors = [0,.125,.25,.375,.5,.625,.75,.8125,.875,1]
        baseline = None
        for times in [anchors, sorted(set(anchors+[i/64 for i in range(65)]))]:
            result = run(program, {'u':[[0,2],[.75,2.75],[1,2.75]]}, times,
                         stop=1, max_step=1, vabstol=1e-8, reltol=0)
            events = result['transient']['events']
            self.assertEqual([event['time'] for event in events], [.25,.5,.875])
            if baseline is not None:
                self.assertEqual(events, baseline)
            baseline = events
            corner = 1.75+math.exp(-.75)
            for t, row in zip(times, rows(result)):
                edge = 0 if t<=.25 else t-.25 if t<=.5 else max(0,.75-t)
                f = 1+t+math.exp(-t) if t<=.75 else 2.75+(corner-2.75)*math.exp(-(t-.75))
                assert_close(self, row['y'], edge, delta=1e-8)
                assert_close(self, row['dut:x'], 3+t, delta=1e-8)
                assert_close(self, row['dut:f'], f, delta=1e-8)
                assert_close(self, row['dut:count'], int(t>=.875), delta=1e-8)


if __name__ == '__main__':
    unittest.main()
