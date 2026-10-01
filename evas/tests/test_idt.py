"""First restricted integral: independent rational answers fixed before implementation.

These are development cases, not additional conditions in the original matrix.
The oracle integrates the source polyline by exact rational trapezoid areas;
it does not use the kernel's history or output sampling grid.
"""
import copy
from fractions import Fraction as F
import json
import subprocess
import unittest

from evas import CompileError, KernelError, compile_sources, solve, transient
from evas.ir import SCHEMA_VERSION
from test_affine import KERNEL, instance, model


POINTS = [(0, 0), (2, 4), (5, -2), (8, -2)]


def integral(points, time, ic=0):
    """Exact area of the ORIGINAL binary64 source up to a binary64 time."""
    t, result = F(time), F(ic)
    for (s, a), (e, b) in zip(points, points[1:]):
        s, a, e, b = map(F, (s, a, e, b))
        if t <= s:
            break
        end = min(t, e)
        u_end = a + (b-a)*(end-s)/(e-s)
        result += (a+u_end)*(end-s)/2
    return result


def compiled(body='V(y,r)<+idt(V(u,r),3);', declarations='', instances=None):
    return compile_sources({'idt.va': model(body, declarations)}, instances or [instance()])


def execute(program=None, points=POINTS, times=None, step=20, **tolerances):
    return transient(program or compiled(), {'u': points},
                     times or [0, 1, 2, 3, 4, 5, 6, 8], stop=points[-1][0],
                     max_step=step, kernel=KERNEL, **tolerances)


def values(result, node='y'):
    index = result['nodes'].index(node)
    return [row['voltages'][index] for row in result['solutions']]


class IdtContracts(unittest.TestCase):
    def test_fixed_analytic_anchors_and_rational_oracle_agree(self):
        # Check the independent oracle before comparing any DUT result.
        for t in range(9):
            expected = (3+t*t if t <= 2 else
                        7+4*(t-2)-(t-2)**2 if t <= 5 else 10-2*(t-5))
            self.assertEqual(integral(POINTS, t, 3), expected)
        cases = [([(0, 3), (4, 3)], -2, lambda t: -2+3*t),
                 ([(0, -2), (4, 10)], 5, lambda t: 5-2*t+F(3, 2)*t*t),
                 ([(0, 2), (4, -2)], -1, lambda t: -1+2*t-t*t/2)]
        for points, ic, answer in cases:
            times = [0, .5, 1, 2, 3, 4]
            result = execute(compiled(f'V(y,r)<+idt(V(u,r),{ic});'), points, times)
            for t, actual in zip(times, values(result)):
                self.assertEqual(integral(points, t, ic), answer(F(t)))
                self.assertEqual(F(actual), answer(F(t)))

    def test_multisegment_nonzero_ic_and_callsite_isolation(self):
        # Both calls contribute to the SAME branch; there is no target-key slot.
        pieces = ['V(y,r)<+idt(V(u,r),3);', 'V(y,r)<+idt(-2*V(u,r)+1,-4);']
        for body in [''.join(pieces), ''.join(pieces[::-1]),
                     'V(y,r)<+idt(V(u,r),3)+idt(-2*V(u,r)+1,-4);']:
            program = compiled(body)
            self.assertEqual(len(program.operators), 2)
            result = execute(program)
            for t, actual in zip(result['transient']['times'], values(result)):
                self.assertEqual(F(actual), -1-integral(POINTS, t)+F(t))

    def test_constant_input_and_zero_initial_condition(self):
        result = execute(compiled('V(y,r)<+idt(2,0);'))
        self.assertEqual(values(result), [2*t for t in result['transient']['times']])

    def test_level_reset_holds_ic_and_releases_from_reset_time(self):
        body = """
          @(initial_step) reset=1;
          @(timer(1,1,1e-15)) reset=1-reset;
          V(y,r)<+idt(V(u,r),0.25,reset);
        """
        program = compiled(body, 'real reset;')
        times = [0, 1, 1.5, 2, 3, 3.5, 4, 5]
        expected = [0.25, 0.25, 1.25, 0.25, 0.25, 1.25, 0.25, 0.25]
        for step in [10, 0.125]:
            result = execute(program, [[0, 2], [5, 2]], times, step)
            self.assertEqual(values(result), expected)
            self.assertEqual(
                [(event['time'], event['after']) for event in result['transient']['events']],
                [(1.0, [0.0]), (2.0, [1.0]), (3.0, [0.0]), (4.0, [1.0]), (5.0, [0.0])],
            )

    def test_large_finite_ic_survives_reset_release(self):
        # Zero input gives the independent answer IC at every time. Prefix
        # subtraction must not first add two large copies of the same IC.
        for ic in [1e308, -1e308]:
            with self.subTest(ic=ic):
                body = f"""
                  @(initial_step) reset=1;
                  @(timer(1,0,1e-15)) reset=0;
                  V(y,r)<+idt(0,{ic},reset);
                """
                result = execute(compiled(body, 'real reset;'),
                                 [(0, 0), (3, 0)], [0, .5, 1, 2, 3])
                self.assertEqual(values(result), [ic] * 5)

    def test_reset_idt_and_transition_share_event_state(self):
        body = """
          @(initial_step) flag=0;
          @(timer(1,1,1e-15)) flag=1-flag;
          V(y,r)<+idt(V(u,r),0.25,flag);
          V(q,r)<+transition(flag,0,0.25,0.25);
        """
        source = model(body, 'real flag;', ports='u,y,q,r', directions='input u; output y,q; inout r;')
        program = compile_sources({'idt.va': source}, [instance(connections=dict(u='u', y='y', q='q', r='r'))])
        times = [0, 1, 1.125, 1.25, 2, 2.125, 2.25]
        result = transient(program, {'u': [[0, 1], [3, 1]], 'r': [[0, 0], [3, 0]]},
                           times, stop=3, max_step=10, kernel=KERNEL)
        self.assertEqual(values(result, 'y'), [0.25, 0.25, 0.25, 0.25, 0.25, 0.375, 0.5])
        self.assertEqual(values(result, 'q'), [0, 0, 0.5, 1, 1, 0.5, 0])

    def test_reset_feedback_is_rejected_instead_of_selecting_a_trial_history(self):
        # At t=1, the unreset integral is 1 and IC is 0. q=y has no fixed
        # point; q=1-y has two. Numerical stability cannot select a history.
        cases = [
            ('no_solution', 'q=V(y,r);', ''),
            ('two_solutions', 'q=1-V(y,r);', ''),
            ('relay', 'q=V(z,r);', 'V(z,r)<+V(y,r);'),
            ('cancelled_relay', 'q=V(z,r)-V(z,r);', 'V(z,r)<+V(y,r);'),
            ('zero_relay', 'q=0*V(z,r);', 'V(z,r)<+V(y,r);'),
            ('local_state_relay', 'a=V(y,r); q=a;', ''),
        ]
        for name, assignments, relay in cases:
            body = ('@(initial_step) begin q=0; a=0; end '
                    f'@(timer(1,0,1e-12)) begin {assignments} end '
                    'V(y,r)<+idt(1,0,q);' + relay)
            with self.subTest(case=name), self.assertRaisesRegex(KernelError, 'unsupported_operator'):
                execute(compiled(body, 'real q,a;' + (' electrical z;' if relay else '')),
                        [[0,0],[2,0]], [0,.5,1,1.5,2], 2)

    def test_reset_feedback_across_instances_and_fixed_drive_boundary(self):
        producer = model("""@(initial_step) q=0;
            @(timer(1,0,1e-12)) q=V(p,r);
            V(y,r)<+idt(1,0,q);""", 'real q;', ports='u,p,y,r',
            directions='input u,p; output y; inout r;')
        relay = model('V(y,r)<+V(u,r);').replace('module m(', 'module relay(')
        for sample in ['feedback', 'u']:
            instances = [instance('integrator', connections=dict(u='u', p=sample, y='z', r='0')),
                         instance('relay', module='relay', connections=dict(u='z', y='feedback', r='0'))]
            for order in [instances, instances[::-1]]:
                program = compile_sources({'producer.va': producer, 'relay.va': relay}, order)
                with self.subTest(sample=sample, order=[i.name for i in order]):
                    if sample == 'feedback':
                        with self.assertRaisesRegex(KernelError, 'unsupported_operator'):
                            execute(program, [(0, 1), (2, 1)], [0, .5, 1, 1.5, 2])
                    else:
                        result = execute(program, [(0, 1), (2, 1)], [0, .5, 1, 1.5, 2])
                        self.assertEqual(values(result, 'z'), [0, .5, 0, 0, 0])

    def test_raw_ir_reset_feedback_is_rejected(self):
        good = compiled('''@(initial_step) q=0;
            @(timer(1,0,1e-12)) q=0;
            V(y,r)<+idt(1,0,q);''', 'real q;').to_dict()
        good['events'][0]['body'][0]['rhs'] = {
            'op': 'affine', 'constant': 0,
            'terms': [{'node': good['nodes'].index('y'), 'coefficient': 1}],
        }
        request = dict(program=good, driven=['u'], samples=[],
                       transient=dict(pwl=[[[0,0],[2,0]]], output_times=[0,1,2],
                                      stop=2, max_step=2))
        result = subprocess.run([str(KERNEL)], input=json.dumps(request), text=True,
                                capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unsupported_operator', result.stderr)

    def test_post_reset_sampling_without_feedback_remains_supported(self):
        body = '''@(initial_step) begin flag=0; held=0; end
            @(timer(1,0,1e-12)) begin flag=1; held=V(z,r); end
            V(z,r)<+idt(1,0,flag); V(y,r)<+held;'''
        result = execute(compiled(body, 'integer flag; real held; electrical z;'),
                         [[0,0],[2,0]], [0,.5,1,1.5,2], 2)
        self.assertEqual(values(result), [0,0,0,0,0])
        self.assertEqual(values(result, 'dut:z'), [0,.5,0,0,0])

    def test_reset_expression_is_certified_from_original_structure(self):
        body = """
          @(initial_step) q=1;
          @(timer(2,0,.001)) q=0;
          V(y,r)<+idt(V(u,r),0.25,1e16*q+q-1e16*q);
        """
        program = compiled(body, 'integer q;')
        result = execute(program, [[0, 1], [3, 1]], [0, 1, 2, 3], 3)
        self.assertEqual(values(result), [0.25, 0.25, 0.25, 1.25])

    def test_inexact_nested_reset_coefficient_is_rejected(self):
        body = """
          @(initial_step) q=1;
          @(timer(2,0,.001)) q=0;
          V(y,r)<+idt(V(u,r),0.25,(0.1*q)*0.1-0.010000000000000002*q);
        """
        with self.assertRaisesRegex(KernelError, 'unsupported_operator'):
            execute(compiled(body, 'integer q;'), [[0, 1], [3, 1]], [0, 1, 2, 3], 3)

    def test_raw_reset_expression_uses_structural_state_bounds(self):
        good = compiled().to_dict()
        good['states'] = [dict(instance='dut', name='q', kind='integer', initial=1)]
        good['events'] = [{
            'trigger': {'kind': 'timer', 'start': 2, 'period': 0, 'time_tolerance': .001, 'enabled': True},
            'body': [{'kind': 'assign', 'state': 0, 'rhs': {'op': 'affine', 'constant': 0, 'terms': []}}],
            'origin': {'source': 'raw.va', 'line': 1, 'column': 1, 'instance': 'dut'},
        }]
        q = {'op': 'state', 'state': 0}
        product = {'op': 'multiply', 'left': {'op': 'affine', 'constant': 1e16, 'terms': []}, 'right': q}
        good['operators'][0]['ic'] = .25
        good['operators'][0]['reset'] = {'op': 'add', 'left': {'op': 'add', 'left': product, 'right': q},
                                         'right': {'op': 'multiply', 'left': {'op': 'affine', 'constant': -1e16, 'terms': []},
                                                   'right': q}}
        request = dict(program=good, driven=['u'], samples=[],
                       transient=dict(pwl=[[[0, 1], [3, 1]]], output_times=[0, 1, 2, 3],
                                      stop=3, max_step=3))
        response = subprocess.run([str(KERNEL)], input=json.dumps(request), text=True,
                                  capture_output=True, check=False)
        self.assertEqual(response.returncode, 0, response.stderr)
        result = json.loads(response.stdout)
        y = result['nodes'].index('y')
        self.assertEqual([row['voltages'][y] for row in result['solutions']], [0.25, 0.25, 0.25, 1.25])

    def test_raw_inexact_nested_reset_coefficient_is_rejected(self):
        good = compiled().to_dict()
        good['states'] = [dict(instance='dut', name='q', kind='integer', initial=1)]
        good['events'] = [{
            'trigger': {'kind': 'timer', 'start': 2, 'period': 0, 'time_tolerance': .001, 'enabled': True},
            'body': [{'kind': 'assign', 'state': 0, 'rhs': {'op': 'affine', 'constant': 0, 'terms': []}}],
            'origin': {'source': 'raw.va', 'line': 1, 'column': 1, 'instance': 'dut'},
        }]
        q = {'op': 'state', 'state': 0}
        left = {'op': 'multiply',
                'left': {'op': 'multiply', 'left': {'op': 'affine', 'constant': 0.1, 'terms': []}, 'right': q},
                'right': {'op': 'affine', 'constant': 0.1, 'terms': []}}
        right = {'op': 'multiply', 'left': {'op': 'affine', 'constant': -0.010000000000000002, 'terms': []},
                 'right': q}
        good['operators'][0]['ic'] = .25
        good['operators'][0]['reset'] = {'op': 'add', 'left': left, 'right': right}
        request = dict(program=good, driven=['u'], samples=[],
                       transient=dict(pwl=[[[0, 1], [3, 1]]], output_times=[0, 1, 2, 3],
                                      stop=3, max_step=3))
        response = subprocess.run([str(KERNEL)], input=json.dumps(request), text=True,
                                  capture_output=True, check=False)
        self.assertNotEqual(response.returncode, 0, response.stdout)
        self.assertIn('unsupported_operator', response.stderr)

    def test_output_grid_and_max_step_do_not_accumulate_history(self):
        sparse = [0, 1, 2, 3, 4, 5, 6, 8]
        dense = [i/16 for i in range(129)]
        baseline = values(execute(times=sparse, vabstol=1e-12, reltol=0))
        for times in [sparse, dense]:
            for step in [20, .375, 1/64]:
                result = execute(times=times, step=step, vabstol=1e-12, reltol=0)
                self.assertEqual([values(result)[times.index(t)] for t in sparse], baseline)
                for t, actual in zip(times, values(result)):
                    self.assertLessEqual(abs(F(actual)-integral(POINTS, t, 3)), F(1e-12))

    def test_instances_parameters_reference_and_order_are_isolated(self):
        source = model('V(y,r)<+idt(g*V(u,r)+1,ic);',
                       'parameter real g=2; parameter real ic=3;')
        a = instance('a', connections=dict(u='u', y='ya', r='r'))
        b = instance('b', connections=dict(u='v', y='yb', r='r'), parameters=dict(g=-1, ic=7))
        for order in [[a, b], [b, a]]:
            program = compile_sources({'idt.va': source}, order)
            result = transient(program, {'u': [[0, 2], [4, 6]], 'v': [[0, 0], [4, -4]],
                                         'r': [[0, 2], [4, 2]]},
                               [0, 1, 2, 4], stop=4, max_step=4, kernel=KERNEL)
            for t, ya, yb in zip([0, 1, 2, 4], values(result, 'ya'), values(result, 'yb')):
                self.assertEqual(ya, 5+t+t*t)
                self.assertEqual(yb, 9+3*t+t*t/2)

    def test_same_timestamp_changed_source_recomputes_integral(self):
        program = compiled('V(y,r)<+idt(V(u,r),1);')
        # The API supplies a complete immutable trajectory per request. A new
        # trial at identical observation times must bind the corrected source.
        for points, expected in [([[0, 0], [2, 2]], [1, 1.5, 3]),
                                 ([[0, 0], [2, 4]], [1, 2, 5]),
                                 ([[0, 0], [2, 2]], [1, 1.5, 3])]:
            self.assertEqual(values(execute(program, points, [0, 1, 2])), expected)

    def test_explicit_finite_constant_ic_and_arity(self):
        for call in ['idt(V(u,r))', 'idt(V(u,r),0,0,1e-9)',
                     'idt(V(u,r),V(u,r))', 'idt(V(u,r),q)', 'idt(V(u,r),1e999)',
                     'idt(V(u,r),1e308*10)', 'idt(V(u,r),0,V(u,r))',
                     'idt(V(u,r),0,idt(V(u,r),0))']:
            with self.subTest(call=call), self.assertRaises(CompileError):
                compiled('@(initial_step) q=0; V(y,r)<+'+call+';', 'real q;')

    def test_structural_rejections_survive_zero_and_cancellation(self):
        inputs = ['V(z,r)', 'V(z,r)-V(z,r)', '0*V(z,r)', 'V(z,z)',
                  '1e-200*(1e-200*V(z,r))', 'q-q', '0*q',
                  'idt(V(u,r),0)', 'absdelay(V(u,r),1)', 'V(u,r)*V(u,r)', 'pow(V(u,r),2)']
        for expr in inputs:
            body = f'@(initial_step) q=0; V(z,r)<+V(u,r); V(y,r)<+idt({expr},0);'
            with self.subTest(expr=expr), self.assertRaises((CompileError, KernelError)):
                execute(compiled(body, 'electrical z; real q;'))
        for body in ['V(y,r)<+idt(V(y,r),0);',
                     'V(y,r)<+idt(V(u,r),0)*V(u,r);',
                     'V(y,r)<+idt(V(u,r),0)*idt(V(u,r),0);',
                     'V(y,r)<+absdelay(idt(V(u,r),0),1);',
                     'V(y,r)<+slew(idt(V(u,r),0),1,-1);']:
            with self.subTest(body=body), self.assertRaises((CompileError, KernelError)):
                execute(compiled(body))
        with self.assertRaises(KernelError):
            solve(compiled(), ['u'], [[1]], kernel=KERNEL)

    def test_operator_driven_cross_is_rejected_through_cancelled_relay(self):
        for expression in ['V(z,r)', 'V(z,r)-V(z,r)', '0*V(z,r)']:
            body = ('@(initial_step) n=0; @(cross(V(y,r),1)) n=n+1; '
                    f'V(z,r)<+idt(V(u,r),0); V(y,r)<+{expression};')
            with self.subTest(expression=expression), self.assertRaisesRegex(KernelError, 'unsupported_cross'):
                execute(compiled(body, 'electrical z; integer n;'))
        with self.assertRaises(CompileError):
            compiled('@(initial_step) n=0; @(cross(idt(V(u,r),0))) n=n+1; V(y,r)<+n;', 'integer n;')

    def test_source_cross_timer_sampling_and_discarded_overshoot(self):
        body = ('@(initial_step) begin q=0; n=0; end '
                '@(cross(V(u,r)-1,1,1e-12,1e-9)) n=n+1; '
                '@(timer(1,0,1e-12)) begin q=V(z,r); q=q+1; end '
                'V(z,r)<+idt(V(u,r),2); V(y,r)<+q+n;')
        program = compiled(body, 'real q; integer n; electrical z;')
        for step in [3, .125]:
            result = execute(program, [[0, 0], [3, 3]], [0, 1, 2, 3], step)
            self.assertEqual(values(result), [0, 4.5, 4.5, 4.5])
            self.assertEqual(len(result['transient']['events']), 2)
        result = execute(program, [[0, 0], [3, 3]], [0, 3], 3)
        self.assertGreater(result['transient']['discarded_trials'], 0)
        self.assertEqual(values(result), [0, 4.5])

    def test_cross_instance_operator_dependency_survives_cancelled_relay(self):
        producer = model('V(y,r)<+idt(V(u,r),0);')
        watcher = model('@(initial_step) n=0; @(cross(V(u,r),1)) n=n+1; V(y,r)<+n;',
                        'integer n;').replace('module m(', 'module watcher(')
        for expression in ['V(u,r)-V(u,r)', '0*V(u,r)']:
            relay = model(f'V(y,r)<+{expression};').replace('module m(', 'module relay(')
            instances = [instance('integrator', connections=dict(u='u', y='integral', r='0')),
                         instance('relay', module='relay', connections=dict(u='integral', y='guard', r='0')),
                         instance('observer', module='watcher', connections=dict(u='guard', y='count', r='0'))]
            for order in [instances, instances[::-1]]:
                program = compile_sources({'producer.va': producer, 'relay.va': relay, 'watcher.va': watcher}, order)
                with self.subTest(expression=expression, order=[i.name for i in order]):
                    with self.assertRaisesRegex(KernelError, 'unsupported_cross'):
                        execute(program)

    def test_raw_ir_rejects_bad_version_fields_and_dependencies(self):
        good = compiled().to_dict()
        self.assertEqual(good['schema_version'], SCHEMA_VERSION)
        mutations = []
        for key, value in [('ic', None), ('ic', '0'), ('reset', 0), ('ic', float('inf'))]:
            bad = copy.deepcopy(good)
            bad['operators'][0][key] = value
            mutations.append(bad)
        bad = copy.deepcopy(good)
        del bad['operators'][0]['ic']
        mutations.append(bad)
        for expr in [dict(op='operator', operator=0), dict(op='operator', operator=99),
                     dict(op='state', state=0),
                     dict(op='affine', constant=0, terms=[dict(node=good['nodes'].index('y'), coefficient=0)])]:
            bad = copy.deepcopy(good)
            bad['operators'][0]['input'] = expr
            mutations.append(bad)
        bad = copy.deepcopy(good)
        bad['operators'][0]['origin']['instance'] = 'other'
        mutations.append(bad)
        for program in mutations:
            response = subprocess.run([str(KERNEL)], input=json.dumps(dict(program=program, driven=['u'], samples=[],
                transient=dict(pwl=[POINTS], output_times=[0, 8], stop=8, max_step=8))),
                text=True, capture_output=True)
            with self.subTest(program=program):
                self.assertEqual(response.returncode, 2, response.stdout)
                self.assertIn(json.loads(response.stderr)['kind'], ['invalid_ir', 'invalid_request', 'unsupported_operator'])


if __name__ == '__main__':
    unittest.main()
