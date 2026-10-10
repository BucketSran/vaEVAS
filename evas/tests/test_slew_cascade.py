"""Issue #66 C3: independent fixed two-stage slew contracts."""

GUARDS = ["SLEW", "COMPOSE"]

from fractions import Fraction as F
import math
import unittest

from evas import KernelError, Instance
from test_continuous_dynamics import compile_model, run, rows


BODY = 'V(h,r)<+slew(V(u,r),0.5,-0.5); V(y,r)<+slew(V(h,r),0.25,-0.25);'


def answer(case, t):
    t = F(t)
    if case == 'ramp':
        return t/2, t/4
    if case == 'catch':
        return min(t/2, F(4)), min(t/4, F(4))
    # u=2t to t=2, then 12-4t to t=4, then -4.
    # Inner reversal occurs at 8/3; outer at 32/9. These are physical
    # intersections, independent of the simulator's rounded breakpoints.
    return (t/2 if t <= F(8, 3) else max(F(-4), F(8, 3)-t/2),
            t/4 if t <= F(32, 9) else max(F(-4), F(16, 9)-t/4))


class SlewCascadeContracts(unittest.TestCase):
    def test_defined_ramp_catchup_reversal_and_query_invariance(self):
        cases = [('ramp', [[0, 0], [4, 4]], 4),
                 ('catch', [[0, 0], [4, 4], [20, 4]], 20),
                 ('reverse', [[0, 0], [2, 4], [4, -4], [24, -4]], 24)]
        program = compile_model(BODY, 'electrical h;')
        for case, points, stop in cases:
            sparse = [0, 1, 2, 3, 4, stop] if stop > 4 else [0, 1, 2, 3, 4]
            dense = sorted(set(sparse + [k/8 for k in range(8*stop+1)]))
            if case == 'reverse':
                dense = sorted(set(dense + [math.nextafter(float(t), direction)
                    for t in [F(8, 3), F(32, 9), F(40, 3), F(208, 9)]
                    for direction in [-math.inf, math.inf]]))
            baseline = None
            for times, step in [(sparse, stop), (dense, 0.125)]:
                with self.subTest(case=case, dense=times is dense):
                    result = run(program, {'u': points}, times, stop=stop,
                                 max_step=step, vabstol=1e-10, reltol=0)
                    actual = rows(result)
                    for t, row in zip(times, actual):
                        h, y = answer(case, t)
                        self.assertLessEqual(abs(F(row['dut:h'])-h), F(1e-10))
                        self.assertLessEqual(abs(F(row['y'])-y), F(1e-10))
                    selected = [actual[times.index(t)] for t in sparse]
                    if baseline is None:
                        baseline = selected
                    else:
                        self.assertEqual(selected, baseline)

    def test_nested_spelling_and_contribution_order(self):
        bodies = [BODY, ';'.join(BODY.split(';')[-2::-1])+';',
                  'V(y,r)<+slew(slew(V(u,r),0.5,-0.5),0.25,-0.25);']
        for body in bodies:
            result = run(compile_model(body, 'electrical h;' if 'V(h' in body else ''),
                         {'u': [[0, 0], [4, 4]]}, [0, 1, 2, 4],
                         vabstol=1e-10, reltol=0)
            self.assertEqual([r['y'] for r in rows(result)], [0, .25, .5, 1])

    def test_instances_nonzero_initials_asymmetric_rates_and_units(self):
        body = ('V(h,r)<+slew(V(u,r),rate,-2*rate); '
                'V(y,r)<+slew(V(h,r),rate/2,-rate/2);')
        # Start at 3 V; ramp to 7 then hold. First stage catches at 4,
        # second at 8 in normalized time. Reflected input uses the negative
        # rates, so the inner stage catches at 2 and the outer still at 8.
        for scale in [1, 2**-20]:
            declarations = f'electrical h; parameter real rate={1/scale:.17g};'
            a = Instance('a','m',dict(u='u',y='aout',r='0'))
            b = Instance('b','m',dict(u='v',y='bout',r='0'))
            for instances in [[a,b],[b,a]]:
                program = compile_model(body, declarations, instances=instances)
                times = [t*scale for t in [0,1,2,3,4,6,8,10]]
                result = run(program, {'u': [[0,3],[2*scale,7],[10*scale,7]],
                                      'v': [[0,-3],[2*scale,-7],[10*scale,-7]]}, times,
                             vabstol=1e-10,reltol=0)
                for t,row in zip([0,1,2,3,4,6,8,10],rows(result)):
                    self.assertEqual(row['a:h'],3+min(t,4))
                    self.assertEqual(row['aout'],3+min(t/2,4))
                    self.assertEqual(row['b:h'],-3-min(2*t,4))
                    self.assertEqual(row['bout'],-3-min(t/2,4))

    def test_projected_input_error_is_carried_through_both_stages(self):
        # The exact binary64 sum .1+.2 differs from its rounded point.
        # Passing that point through two histories cannot erase its error.
        body = BODY.replace('V(u,r),0.5', '0.1*V(u,r)+0.2*V(u,r),0.5').replace('V(y,r)<+', 'V(y,r)<+1073741824*')
        program = compile_model(body,'electrical h;')
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            run(program, {'u':[[0,1],[4,1]]},[0,1,4],vabstol=1e-9,reltol=0)
        result = run(program, {'u':[[0,1],[4,1]]},[0,1,4],vabstol=1e-6,reltol=0)
        for row in rows(result):
            self.assertLessEqual(abs(F(row['y'])-1073741824*(F(.1)+F(.2))),F(1e-6))

    def test_asymmetric_reversal_preserves_fractional_intersections(self):
        body = 'V(h,r)<+slew(V(u,r),1,-2); V(y,r)<+slew(V(h,r),0.5,-1);'
        roots = [F(12,5),F(72,25),F(28,5),F(208,25)]
        times = sorted(set([k/8 for k in range(81)] +
            [math.nextafter(float(t), d) for t in roots for d in [-math.inf, math.inf]]))
        result = run(compile_model(body,'electrical h;'),
                     {'u':[[0,3],[2,7],[4,-1],[10,-1]]},times,
                     vabstol=1e-10,reltol=0)
        for time,row in zip(times,rows(result)):
            t = F(time)
            h = 3+(t if t <= F(12,5) else max(F(-4),F(36,5)-2*t))
            y = 3+(t/2 if t <= F(72,25) else max(F(-4),F(108,25)-t))
            self.assertLessEqual(abs(F(row['dut:h'])-h),F(1e-10))
            self.assertLessEqual(abs(F(row['y'])-y),F(1e-10))

    def test_direct_gain_cannot_hide_cascade_rounding(self):
        program = compile_model(BODY.replace('V(y,r)<+', 'V(y,r)<+1073741824*'), 'electrical h;')
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            run(program, {'u': [[0, 0], [2, 4], [4, -4], [24, -4]]}, [0, 4, 24],
                stop=24, vabstol=1e-9, reltol=0)
        result = run(program, {'u': [[0, 0], [2, 4], [4, -4], [24, -4]]}, [0, 4, 24],
                     stop=24, vabstol=1e-5, reltol=0)
        self.assertLessEqual(abs(F(rows(result)[1]['y'])-F(7*1073741824, 9)), F(1e-5))

    def test_deeper_nonunit_mixed_and_feedback_inputs_stay_rejected(self):
        for body in [
            'V(y,r)<+slew(slew(slew(V(u,r),1,-1),0.5,-0.5),0.25,-0.25);',
            BODY.replace('slew(V(h,r)', 'slew(2*V(h,r)'),
            BODY.replace('slew(V(h,r)', 'slew(V(h,r)+0*V(y,r)'),
            BODY.replace('slew(V(u,r),0.5,-0.5)', 'absdelay(V(u,r),0.5)'),
            BODY.replace('slew(V(u,r)', 'slew(V(y,r)'),
        ]:
            with self.subTest(body=body), self.assertRaisesRegex(KernelError, 'unsupported_operator'):
                run(compile_model(body, 'electrical h;' if 'V(h' in body else ''), {'u': [[0, 0], [4, 4]]}, [0, 4])


if __name__ == '__main__':
    unittest.main()
