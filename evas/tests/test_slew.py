"""Independent slew development anchors, not new DVS qualification conditions.

The fixed Fraction formulas below follow the pre-implementation SL-CATCH,
SL-REVERSE and SL-PASS contracts. They do not import the Rust limiter or derive
answers from a sampled DUT trajectory. SI/scaling comparisons allow a bounded
test margin for binary64 encoding and evaluation; no forward-error theorem is
claimed for other inputs.
"""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["SLEW", "TIMED-OPERATOR"]

import copy
from fractions import Fraction as F
import json
import subprocess
import unittest

from evas import CompileError, KernelError, compile_sources, solve, transient
from test_affine import KERNEL, instance, model


SOURCE = model('V(y,r)<+slew(V(u,r),rise,fall);',
               'parameter real rise=1; parameter real fall=-2;')
POINTS = {
    'catch': [(0, 0), (2, 4), (8, 4)],
    'reverse': [(0, 0), (2, 4), (4, -4), (8, -4)],
    'pass': [(0, -1), (4, 0), (8, 0)],
}


def expected(case, time):
    t = F(time)
    if case == 'catch':
        return min(t, F(4))
    if case == 'reverse':
        if t <= F(12, 5):
            return t
        return max(F(-4), F(36, 5) - 2*t)
    return min(F(0), -1 + t/4)


def compiled(source=SOURCE, instances=None):
    return compile_sources({'slew.va': source}, instances or [instance()])


def execute(case, times, *, max_step=20, time_scale=1, voltage_scale=1,
            reflection=1):
    ts, vs = float(time_scale), float(voltage_scale)
    rise, fall = ((1, -2) if reflection == 1 else (2, -1))
    program = compiled(instances=[instance(parameters={
        'rise': rise*vs/ts, 'fall': fall*vs/ts})])
    points = [[float(t)*ts, float(v)*vs*reflection] for t, v in POINTS[case]]
    return transient(program, {'u': points}, [float(t)*ts for t in times],
                     stop=8*ts, max_step=float(max_step)*ts, kernel=KERNEL)


def values(result, node='y'):
    index = result['nodes'].index(node)
    return [row['voltages'][index] for row in result['solutions']]


class SlewContracts(unittest.TestCase):
    def test_large_time_catchup_retains_fractional_local_origin(self):
        # The reversal catches at offset 192/5, which is not representable
        # after adding 2**54. Rounding that absolute time must not restart
        # the outgoing line at the wrong input value.
        offsets = [0, 32, 36, 40, 48, 64, 80, 88, 92, 96, 128]
        for scale in [F(1), F(1, 2**40)]:
            for origin in [0, 2**54]:
                points = ([[0, 0]] if origin else []) + [
                    [float((origin+d)*scale), v]
                    for d, v in [(0, 0), (32, 4), (64, -4), (128, -4)]]
                program = compiled(instances=[instance(parameters={
                    'rise': float(F(1, 16)/scale),
                    'fall': float(F(-1, 8)/scale)})])
                times = [float((origin+d)*scale) for d in offsets]
                with self.subTest(scale=scale, origin=origin):
                    result = transient(program, {'u': points}, times,
                                       stop=points[-1][0], max_step=points[-1][0],
                                       vabstol=1e-12, reltol=1e-10, kernel=KERNEL)
                    for actual, d in zip(values(result), offsets):
                        answer = F(d, 16) if F(d) <= F(192, 5) else max(F(-4), F(36, 5)-F(d, 8))
                        self.assertAlmostEqual(actual, float(answer), delta=2e-14)

    def test_fraction_anchors_cover_catch_reverse_and_tracking(self):
        times = list(map(F, [0, 1, 2])) + [F(9, 4), F(12, 5), F(3), F(4), F(5), F(28, 5), F(6), F(8)]
        for case in POINTS:
            with self.subTest(case=case):
                result = execute(case, times)
                self.assertEqual(result['transient']['events'], [])
                for actual, t in zip(values(result), times):
                    self.assertAlmostEqual(actual, float(expected(case, t)), delta=2e-13)

    def test_reflection_and_physical_units(self):
        times = [F(0), F(1), F(2), F(9, 4), F(3), F(4), F(5), F(6), F(8)]
        for ts, vs in [(F(1), F(1)), (F(1, 10**9), F(1)),
                       (F(1, 2**20), F(1, 2**16)), (F(2**10), F(2**20))]:
            for reflection in [1, -1]:
                with self.subTest(time_scale=ts, voltage_scale=vs, reflection=reflection):
                    result = execute('reverse', times, time_scale=ts, voltage_scale=vs,
                                     reflection=reflection)
                    for actual, t in zip(values(result), times):
                        self.assertAlmostEqual(actual/float(vs), reflection*float(expected('reverse', t)), delta=2e-13)

    def test_output_grid_and_max_step_do_not_define_history(self):
        sparse = [F(0), F(2), F(3), F(4), F(6), F(8)]
        dense = [F(i, 16) for i in range(129)]
        baseline = execute('reverse', sparse)
        baseline_values = values(baseline)
        for step in [F(20), F(7, 16), F(1, 64)]:
            for times in [sparse, dense]:
                result = execute('reverse', times, max_step=step)
                selected = [values(result)[times.index(t)] for t in sparse]
                self.assertEqual(selected, baseline_values)

    def test_corner_coincidence_and_slope_equal_to_limits(self):
        for points, answer in [
            ([[0, 0], [2, 4], [4, 4], [6, 2]], [0, 2, 4, 3, 2]),
            ([[0, 0], [2, 2], [4, -2], [6, -2]], [0, 2, -2, -2, -2]),
        ]:
            result = transient(compiled(), {'u': points}, [0, 2, 4, 5, 6],
                               stop=6, max_step=10, kernel=KERNEL)
            self.assertEqual(values(result), answer)

    def test_nonzero_initial_value_and_affine_driven_input(self):
        source = model('V(y,r)<+slew(2*V(u,r)+V(v,r)+1,1,-2);',
                       ports='u,v,y,r', directions='input u,v; output y; inout r;')
        inst = instance(connections=dict(u='u', v='v', y='y', r='r'))
        result = transient(compiled(source, [inst]), {
            'u': [[0, 3], [2, 5], [8, 5]],
            'v': [[0, 1], [1, 1], [8, 1]],
            'r': [[0, 2], [8, 2]],
        }, [0, 1, 2, 3, 4, 8], stop=8, max_step=20, kernel=KERNEL)
        # Input is 2*(u-2)+(1-2)+1 = 2*u-4, initially 2;
        # output y = reference 2 + slew(input), hence 4 + min(t,4).
        self.assertEqual(values(result), [4, 5, 6, 7, 8, 8])

    def test_two_instances_keep_parameters_and_input_histories_separate(self):
        a = instance('a', connections=dict(u='u', y='aout', r='0'))
        b = instance('b', connections=dict(u='v', y='bout', r='0'), parameters=dict(rise=2, fall=-1))
        points = [[0, 0], [2, 4], [4, -4], [8, -4]]
        times = [0, 1, 2, 3, 4, 6, 8]
        for instances in [[a, b], [b, a]]:
            result = transient(compiled(instances=instances),
                               {'u': points, 'v': [[t, -v] for t, v in points]},
                               times, stop=8, max_step=20, kernel=KERNEL)
            for node, reflection in [('aout', 1), ('bout', -1)]:
                for actual, t in zip(values(result, node), times):
                    self.assertAlmostEqual(actual, reflection*float(expected('reverse', t)), delta=2e-13)

    def test_limits_must_be_explicit_fixed_and_have_correct_sign(self):
        for call in ['slew(V(u,r))', 'slew(V(u,r),1)', 'slew(V(u,r),0,-1)',
                     'slew(V(u,r),1,0)', 'slew(V(u,r),-1,-2)',
                     'slew(V(u,r),1,2)', 'slew(V(u,r),V(u,r),-1)']:
            with self.subTest(call=call), self.assertRaises(CompileError):
                compiled(model(f'V(y,r)<+{call};'))

    def test_unsupported_inputs_and_operator_uses_are_rejected(self):
        bodies = [
            # Fixed two-stage nesting is covered by test_slew_cascade.
            'V(y,r)<+slew(slew(slew(V(u,r),1,-2),1,-2),1,-2);',
            'V(y,r)<+slew(V(u,r)*V(u,r),1,-2);',
            'V(y,r)<+slew(V(u,r),1,-2)*V(u,r);',
            'V(y,r)<+slew(V(u,r),1,-2)*slew(V(u,r),1,-2);',
            '@(initial_step) q=0; V(y,r)<+slew(q,1,-2);',
            '@(initial_step) q=0; @(cross(slew(V(u,r),1,-2))) q=q+1; V(y,r)<+q;',
            '@(initial_step) q=0; @(cross(V(y,r))) q=q+1; V(y,r)<+slew(V(u,r),1,-2);',
        ]
        for body in bodies:
            with self.subTest(body=body):
                with self.assertRaises((CompileError, KernelError)):
                    declarations = 'electrical z;' + (' real q;' if 'q' in body else '')
                    transient(compiled(model(body, declarations)),
                              {'u': [[0, 0], [8, 4]]}, [0, 8],
                              stop=8, max_step=20, kernel=KERNEL)
        with self.assertRaises(KernelError):
            solve(compiled(), ['u'], [[1]], kernel=KERNEL)

    def test_numerical_overflow_and_uncertain_corner_fail(self):
        cases = [
            [[0, -1e308], [1, 1e308]],
            [[0, 0], [2, 4], [4, -4], [5.6, -4]],
        ]
        for points in cases:
            with self.subTest(points=points):
                with self.assertRaises(KernelError) as error:
                    transient(compiled(), {'u': points}, [0, points[-1][0]],
                              stop=points[-1][0], max_step=20, kernel=KERNEL)
                self.assertIn('event_resolution', str(error.exception))

    def test_cross_instance_cancellation_cannot_hide_operator_guard_dependency(self):
        watcher = model('''@(initial_step) n=0;
            @(cross(V(u,r),1)) n=n+1; V(y,r)<+n;''', 'integer n;')
        watcher = watcher.replace('module m(', 'module watcher(')
        for expression in ['V(u,r)-V(u,r)', '0*V(u,r)']:
            relay = model(f'V(y,r)<+{expression};').replace('module m(', 'module relay(')
            sources = {'slew.va': SOURCE, 'relay.va': relay, 'watcher.va': watcher}
            producer = instance('producer', connections=dict(u='u', y='limited', r='0'))
            bridge = instance('bridge', module='relay', connections=dict(u='limited', y='relay', r='0'))
            observer = instance('observer', module='watcher', connections=dict(u='relay', y='count', r='0'))
            for instances in [[producer, bridge, observer], [observer, bridge, producer]]:
                with self.subTest(expression=expression, order=[i.name for i in instances]):
                    program = compile_sources(sources, instances)
                    with self.assertRaises(KernelError) as error:
                        transient(program, {'u': [[0, 0], [2, 4], [8, 4]]},
                                  [0, 8], stop=8, max_step=20, kernel=KERNEL)
                    self.assertIn('unsupported_cross', str(error.exception))

    def test_raw_ir_cannot_bypass_limits_input_or_reference_checks(self):
        good = compiled().to_dict()
        mutations = []
        for rise, fall in [(0, -1), (1, 0), (-1, -2), (1, 2)]:
            bad = copy.deepcopy(good)
            bad['operators'][0].update(rise=rise, fall=fall)
            mutations.append(bad)
        bad = copy.deepcopy(good)
        bad['operators'][0]['input'] = {'op': 'operator', 'operator': 0}
        mutations.append(bad)
        for coefficient in [1, 0]:
            bad = copy.deepcopy(good)
            bad['operators'][0]['input'] = {'op': 'affine', 'constant': 0,
                                           'terms': [{'node': good['nodes'].index('y'),
                                                      'coefficient': coefficient}]}
            mutations.append(bad)
        bad = copy.deepcopy(good)
        bad['operators'][0]['extra'] = 1
        mutations.append(bad)
        for program in mutations:
            request = dict(program=program, driven=['u'], samples=[], transient=dict(
                pwl=[[[0, 0], [8, 4]]], output_times=[0, 8], stop=8, max_step=20))
            response = subprocess.run([str(KERNEL)], input=json.dumps(request),
                                      text=True, capture_output=True, check=False)
            with self.subTest(program=program):
                self.assertNotEqual(response.returncode, 0)
                self.assertIn(json.loads(response.stderr)['kind'],
                              ['invalid_ir', 'invalid_request', 'unsupported_operator'])


if __name__ == '__main__':
    unittest.main()
