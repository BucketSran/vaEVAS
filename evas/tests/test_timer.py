"""Fixed-clock development probes, independent of any backend timestamps.

Nominal answers use exact Fraction arithmetic on the submitted binary64 values.
The t=0/stop counts below test EVAS's explicit convention, not universal LRM
qualification. These tests do not change the original 31-condition denominator.
"""
# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["TIMER", "TIMED-OPERATOR"]

import copy
from fractions import Fraction as Q
import json
import math
import subprocess
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from evas.ir import SCHEMA_VERSION
from test_affine import KERNEL, instance, model


def timer_source(arguments="2,5,0.001", initial=0):
    return model(f'''@(initial_step) n={initial};
      @(timer({arguments})) n=n+1; V(y,r)<+n;''', 'integer n;')


def run_timer(source=None, *, stop=19, times=None, step=100, instances=None):
    program = compile_sources({'timer.va': source or timer_source()}, instances or [instance()])
    return transient(program, {'u': [[0, 0], [stop, stop]]},
                     times or [0, 1, 3, 8, 13, 18, stop],
                     stop=stop, max_step=step, kernel=KERNEL)


class TimerContracts(unittest.TestCase):
    def test_representable_pwl_roots_coincide_despite_rounded_division(self):
        for exponent in [-30, 0, 20]:
            unit = 2.0**exponent
            for threshold in [1, 3, 8, 11, 17]:
                start, stop = threshold*unit, 19*unit
                # Fraction anchors the expected equality, independently of Rust.
                root = Q(stop)*Q(threshold)/19
                self.assertEqual(root, Q(start))
                source = model(f'''@(initial_step) begin n=0; m=0; end
                  @(timer({start!r},0,{unit/1024!r})) n=n+1;
                  @(cross(V(u,r)-{threshold},1,{unit/1024!r},0.001)) m=m+1;
                  V(y,r)<+n+m;''', 'integer n,m;')
                program=compile_sources({'timer.va':source},[instance()])
                result=transient(program,{'u':[[0,0],[stop,19]]},[0,stop],
                                 stop=stop,max_step=stop,kernel=KERNEL)
                self.assertEqual([e['time'] for e in result['transient']['events']], [start,start])
                self.assertEqual(result['transient']['states'][-1], [1,1])

    def test_representable_root_outside_three_rounded_guesses_is_found(self):
        # 22*(15/22) rounds down; neither outward endpoint equals the exact 15.
        self.assertNotEqual(22*(15/22),15)
        self.assertEqual(Q(22)*Q(15)/22,15)
        source=model('''@(initial_step) begin n=0; m=0; end
            @(timer(15,0,0.01)) n=n+1;
            @(cross(V(u,r)-15,1,0.01,0.01)) m=m+1;
            V(y,r)<+n+m;''','integer n,m;')
        result=run_timer(source,stop=22,times=[0,22])
        self.assertEqual([e['time'] for e in result['transient']['events']],[15.,15.])

    def test_one_ulp_neighbors_of_certified_root_remain_distinct(self):
        for start in [math.nextafter(8.,0.), math.nextafter(8.,math.inf)]:
            source=model(f'''@(initial_step) begin n=0; m=0; end
              @(timer({start!r},0,0.1)) n=n+1;
              @(cross(V(u,r)-8,1,0.1,0.1)) m=m+1;
              V(y,r)<+n+m;''','integer n,m;')
            result=run_timer(source,stop=19,times=[0,19])
            self.assertEqual([e['time'] for e in result['transient']['events']],sorted([8.,start]))
            self.assertEqual(result['transient']['states'][-1], [1,1])

    def test_periodic_independent_count_answers_and_typed_records(self):
        for arguments in ['2,5,0.001', '2,5', '2,5,']:
            with self.subTest(arguments=arguments):
                result = run_timer(timer_source(arguments))
                self.assertEqual(result['schema_version'], SCHEMA_VERSION)
                self.assertEqual(result['transient']['states'], [[n] for n in [0, 0, 1, 2, 3, 4, 4]])
                self.assertEqual([e['time'] for e in result['transient']['events']], [2, 7, 12, 17])
                for event in result['transient']['events']:
                    self.assertEqual(event['kind'], 'timer')
                    self.assertNotIn('guard_value', event)
                self.assertEqual([s['voltages'][result['nodes'].index('y')] for s in result['solutions']],
                                 [0, 0, 1, 2, 3, 4, 4])

    def test_absent_zero_and_negative_period_each_fire_once(self):
        for arguments in ['2', '2,', '2,,', '2,,0.001', '2,0,0.001', '2,-5,0.001']:
            with self.subTest(arguments=arguments):
                result = run_timer(timer_source(arguments))
                self.assertEqual([e['time'] for e in result['transient']['events']], [2])
                self.assertEqual(result['transient']['states'][-1], [1])

    def test_zero_initialization_and_stop_are_committed_before_observation(self):
        for times in [[0, 0.25, 0.5, 1], [0.25]]:
            result = run_timer(timer_source('0,0.5,0.001', initial=7), stop=1, times=times)
            self.assertEqual([e['time'] for e in result['transient']['events']], [0, 0.5, 1])
            expected = {0: 8, 0.25: 8, 0.5: 9, 1: 10}
            self.assertEqual(result['transient']['states'], [[expected[t]] for t in times])
            self.assertEqual(result['transient']['events'][0]['before'], [7])
            self.assertEqual(result['transient']['events'][-1]['after'], [10])

    def test_stop_before_at_and_after_one_shot(self):
        for start, expected in [(0.5, 1), (1, 1), (1.5, 0)]:
            result = run_timer(timer_source(f'{start},0,0.6'), stop=1, times=[0, 1])
            self.assertEqual(len(result['transient']['events']), expected)
            self.assertEqual(result['transient']['states'][-1], [expected])

    def test_constant_enable_and_instance_parameter_binding(self):
        for enable, count in [(0, 0), (-2, 4), (0.5, 4)]:
            for tolerance in ['0.001', '']:
                result = run_timer(timer_source(f'2,5,{tolerance},{enable}'))
                self.assertEqual(len(result['transient']['events']), count)
        source = model('''@(initial_step) n=0;
            @(timer(start,period,tol,enable)) n=n+1; V(y,r)<+n;''',
            'parameter real start=2; parameter real period=5; parameter real tol=0.001; parameter real enable=1; integer n;')
        result = run_timer(source, instances=[instance(parameters={'start': 1, 'period': 6, 'enable': 0})])
        self.assertEqual(result['transient']['events'], [])

    def test_event_calendar_does_not_depend_on_step_or_output_grid(self):
        reference = run_timer()['transient']['events']
        for step in [0.13, 0.71, 100]:
            for times in [[0, 19], [0.3, 2, 4.1, 7, 17, 18.4]]:
                result = run_timer(times=times, step=step)
                self.assertEqual(result['transient']['events'], reference)

    def test_two_instances_have_private_timer_state(self):
        instances = [instance('a', connections=dict(u='u', y='ya', r='0')),
                     instance('b', connections=dict(u='u', y='yb', r='0'))]
        result = run_timer(instances=instances)
        self.assertEqual(result['transient']['states'][-1], [4, 4])
        self.assertEqual(len(result['transient']['events']), 8)
        for k in range(4):
            events = result['transient']['events'][2*k:2*k+2]
            self.assertEqual([e['before'] for e in events], [[k, k]]*2)
            self.assertEqual([e['after'] for e in events], [[k+1, k+1]]*2)

    def test_timer_and_cross_share_settled_voltage_and_old_state(self):
        statements = ['@(timer(0.5,0,0.001)) n=n+1;',
                      '@(cross(V(u,r)-0.5,1,0.001,0.001)) held=V(y,r);']
        for order in [statements, statements[::-1]]:
            source = model('''@(initial_step) begin n=0; held=-1; end
                ''' + ''.join(order) + 'V(y,r)<+n; V(z,r)<+held;',
                'electrical z; integer n; real held;')
            result = run_timer(source, stop=1, times=[0, 0.5, 1])
            self.assertEqual(result['transient']['states'], [[0, -1], [1, 1], [1, 1]])
            self.assertEqual({e['kind'] for e in result['transient']['events']}, {'cross', 'timer'})
            self.assertEqual([e['before'] for e in result['transient']['events']], [[0, -1]]*2)
            self.assertEqual([e['after'] for e in result['transient']['events']], [[1, 1]]*2)

    def test_distinct_nearby_events_are_not_merged_by_time_tolerance(self):
        source = model('''@(initial_step) begin n=0; held=-1; end
          @(timer(0.5001,0,0.1)) held=V(y,r);
          @(cross(V(u,r)-0.5,1,0.1,0.1)) n=n+1;
          V(y,r)<+n; V(z,r)<+held;''', 'electrical z; integer n; real held;')
        result = run_timer(source, stop=1, times=[0, 1])
        self.assertEqual([e['time'] for e in result['transient']['events']], [0.5, 0.5001])
        self.assertEqual(result['transient']['states'][-1], [1, 1])

    def test_fraction_clock_bounds_long_history_and_large_absolute_time(self):
        for start, period, count, tolerance in [(0.13, 0.007, 2000, 1e-12),
                                              (2**40, 0.0023, 1000, 0.001)]:
            stop = float(Q(start) + (count - Q(1, 2)) * Q(period))
            result = run_timer(timer_source(f'{start},{period},{tolerance}'), stop=stop, times=[0, stop], step=stop)
            events = result['transient']['events']
            self.assertEqual(len(events), count)
            for k, event in enumerate(events):
                self.assertLessEqual(abs(Q(event['time']) - (Q(start) + k*Q(period))), Q(tolerance))
            self.assertTrue(all(a['time'] < b['time'] for a, b in zip(events, events[1:])))

    def test_timer_representatives_are_not_early(self):
        # Exact rational clocks expose downward binary64 rounding. Merely
        # checking an absolute tolerance would miss an early default event.
        for arguments in ['0.1,0.1,1e-12', '0.1,0.1']:
            with self.subTest(arguments=arguments):
                result = run_timer(timer_source(arguments), stop=.95, times=[0, .95])
                events = result['transient']['events']
                self.assertEqual(len(events), 9)
                for k, event in enumerate(events):
                    delay = Q(event['time']) - (Q(.1) + k*Q(.1))
                    self.assertGreaterEqual(delay, 0)
                    self.assertLessEqual(delay, Q(1e-12))

    def test_unrepresentable_small_tolerance_and_period_fail(self):
        for args, stop in [('0.1,0.1,1e-30', 1), ('1e16,0.25,1', 1e16+4),
                           ('1099511627776,0.0023', 2**40+.01)]:
            with self.subTest(args=args), self.assertRaises(KernelError) as caught:
                run_timer(timer_source(args), stop=stop, times=[0, stop], step=stop)
            self.assertEqual(caught.exception.detail['kind'], 'event_resolution')

    def test_budget_rejects_before_materializing_unbounded_calendar(self):
        with self.assertRaises(KernelError) as caught:
            run_timer(timer_source('0,1e-12,1e-18'), stop=1, times=[0, 1])
        self.assertEqual(caught.exception.detail['kind'], 'event_budget')

    def test_finite_stop_does_not_require_representing_future_overflow(self):
        result = run_timer(timer_source('1e308,1e308,1'), stop=1.5e308, times=[0, 1.5e308], step=1.5e308)
        self.assertEqual([e['time'] for e in result['transient']['events']], [1e308])

    def test_overflowing_time_bound_cannot_silently_drop_a_finite_event(self):
        stop = float.fromhex('0x1.fffffffffffffp+1023')
        start = math.nextafter(stop, 0.)
        period = .75*math.ulp(stop)
        self.assertLess(Q(start)+Q(period), Q(stop))
        # The second nominal event is inside the domain, but its outward
        # upper bound is infinite. This is uncertainty, not a past-stop proof.
        with self.assertRaisesRegex(KernelError, 'event_resolution'):
            run_timer(timer_source(f'{start},{period},{math.ulp(stop)}'),
                      stop=stop, times=[0, stop], step=stop)

    def test_frontend_rejects_invalid_or_unsupported_settings(self):
        for arguments in ['', ',5', '2,5,0', '-1,0,1', 'V(u)', 'V(u),0,1',
                          '0,0,n', '0,0,1,1,1', '0,,,', '0,0,1 or cross(V(u))']:
            with self.subTest(arguments=arguments), self.assertRaises(CompileError):
                compile_sources({'timer.va': timer_source(arguments)}, [instance()])

    def test_shared_self_increments_preserve_cross_and_timer_counts(self):
        for statement in ['@(cross(V(u)-0.5,1)) n=n+1;',
                          '@(timer(0.5,0,0.001)) n=n+1;']:
            source = model('''@(initial_step) begin n=0; m=0; end
                @(timer(0,0,0.001)) n=n+1;''' + statement + 'V(y,r)<+n+m;', 'integer n,m;')
            with self.subTest(statement=statement):
                result = run_timer(source, stop=1, times=[0, 1])
                self.assertEqual(result['transient']['states'], [[1,0],[2,0]])
                self.assertEqual([event['time'] for event in result['transient']['events']], [0,.5])

    def test_cross_block_other_state_read_restriction_remains(self):
        source = model('''@(initial_step) begin n=0; m=0; end
            @(timer(0,0,0.001)) n=n+1;
            @(timer(0.5,0,0.001)) m=n+1; V(y,r)<+n+m;''', 'integer n,m;')
        with self.assertRaisesRegex(KernelError, 'unsupported_cross'):
            run_timer(source, stop=1, times=[0, 1])

    def test_raw_ir_rejects_malformed_timer_and_legacy_event_fields(self):
        program = compile_sources({'timer.va': timer_source()}, [instance()]).to_dict()
        base = dict(program=program, driven=['u'], samples=[], transient=dict(
            pwl=[[[0, 0], [19, 19]]], output_times=[0, 19], stop=19, max_step=19))
        for mutation, kind in [
            (lambda t: t.update(start=-1), 'invalid_ir'),
            (lambda t: t.update(time_tolerance=0), 'invalid_ir'),
            (lambda t: t.update(period='5'), 'invalid_request'),
            (lambda t: t.update(enabled=1), 'invalid_request'),
            (lambda t: t.update(guard={'op': 'affine', 'constant': 0, 'terms': []}), 'invalid_request'),
            (lambda t: t.pop('start'), 'invalid_request'),
            (lambda t: t.update(kind='other'), 'invalid_request'),
        ]:
            request = copy.deepcopy(base)
            mutation(request['program']['events'][0]['trigger'])
            result = subprocess.run([str(KERNEL)], input=json.dumps(request), text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            self.assertEqual(json.loads(result.stderr)['kind'], kind)

        legacy = copy.deepcopy(base)
        event = legacy['program']['events'][0]
        event.update(event.pop('trigger'))
        result = subprocess.run([str(KERNEL)], input=json.dumps(legacy), text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertEqual(json.loads(result.stderr)['kind'], 'invalid_request')

    def test_overflow_and_uncertifiable_constraints_produce_no_partial_response(self):
        for residual in [False, True]:
            sources = {'timer.va': timer_source('0,0,0.001', initial=0 if residual else 2147483647)}
            instances = [instance()]
            if residual:
                sources['clamp.va'] = model('V(y,r)<+0;').replace('module m(', 'module clamp(')
                instances.append(instance('clamp', module='clamp'))
            program = compile_sources(sources, instances).to_dict()
            request = dict(program=program, driven=['u'], samples=[], transient=dict(
                pwl=[[[0, 0], [1, 1]]], output_times=[0, 1], stop=1, max_step=1))
            result = subprocess.run([str(KERNEL)], input=json.dumps(request), text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            error = json.loads(result.stderr)
            if residual:
                # y=n and y=0 agree only at the initial n=0. They are not
                # identities over the state domain of the affine error map;
                # uniform initialization certification now refuses them before
                # the timer fires. Candidate residual failure/rollback remains
                # covered by the Rust idt_residual_failure regression.
                self.assertEqual(error['kind'], 'event_accuracy')
                self.assertIn('redundant event constraints as identities', error['message'])
            else:
                self.assertEqual(error['kind'], 'state_range')
