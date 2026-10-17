"""Independent physical-root contracts for overlapping timer/source windows.

These reduced inputs retain separate identities from original gold 101/314.
Expected values use binary64 rationals and LRM transition interruption rules;
no answer is fitted to a simulator response.
"""
GUARDS = ["EVENT-ORDER", "TIMED-OPERATOR", "TRANSITION", "EVENT-CONDITIONS"]
from fractions import Fraction as Q
import math
import os
from pathlib import Path
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

KERNEL = Path(os.environ.get('EVAS_TEST_KERNEL', str(KERNEL)))


def clip(x):
    return max(Q(0), min(Q(1), x))


def sine_bounds(value):
    """Alternating Taylor bounds on sin(x) for 0 <= x <= 2, using rationals."""
    assert 0 <= value <= 2
    term=value
    total=value
    for k in range(1,20):
        term=-term*value*value/Q((2*k)*(2*k+1))
        total+=term
    # The 20-term sum ends negative; the next positive term is an upper bound.
    next_term=-term*value*value/Q(40*41)
    return total,total+next_term


class SourceRootWindows(unittest.TestCase):
    def run_case(self, body, declarations, sources, times, stop, forced=False):
        program = compile_sources({'root-window.va': model(body, declarations)}, [instance()])
        result = transient(program, sources, times, stop=stop, max_step=80e-12,
                           strobetimes=times if forced else [], kernel=KERNEL, timeout=120)
        return program, result

    def check_answers(self, program, result, times, answers):
        bounds = result['observation_evidence']['voltage_bounds_V']
        for n, (time, solution) in enumerate(zip(times, result['solutions'])):
            for node, answer in answers.items():
                column = program.nodes.index(node)
                expected = answer(Q(time))
                lo, hi = map(Q, bounds[n][column])
                self.assertLessEqual(lo, expected, (node, time, 'lower', float(expected)))
                self.assertLessEqual(expected, hi, (node, time, 'upper', float(expected)))
                error = abs(Q(solution['voltages'][column]) - expected)
                self.assertLessEqual(error, Q(1e-12) + Q(1e-10) * abs(expected))

    def query_variants(self, body, declarations, sources, common, stop, answers, clock):
        # Ordinary and dense queries do not prescribe the physical schedule.
        dense = sorted(set(common + [(common[0] + (stop-common[0])*k/31) for k in range(32)]))
        runs = []
        for times, forced in [(common, False), (dense, False), (common, True)]:
            with self.subTest(forced=forced, output_count=len(times)):
                program, response = self.run_case(body, declarations, sources, times, stop, forced)
                self.check_answers(program, response, times, answers)
                runs.append((times, response))
        if len(runs) != 3:
            return  # The original subtest failures already carry their causes.
        first = runs[0][1]
        self.assertEqual(first['transient']['events'], runs[1][1]['transient']['events'])
        # Forced times can refine a representative/window. Physical callbacks
        # and their state changes must remain unchanged.
        event_state = lambda r: [(e['event'], e['kind'], e['before'], e['after'])
                                 for e in r['transient']['events']]
        self.assertEqual(event_state(first), event_state(runs[2][1]))
        # Pure extra queries retain identical history and common solutions.
        for t, row in zip(common, first['solutions']):
            self.assertEqual(row, runs[1][1]['solutions'][dense.index(t)])
        # Strobes deliberately tighten fixed-clock windows. Their floating
        # representative may change, while the certified physical root cannot.
        forced = runs[2][1]
        start, period = map(Q, clock)
        for index, (ordinary_event, forced_event) in enumerate(zip(
                first['transient']['events'], forced['transient']['events'])):
            root = start + index*period
            old_lo, old_hi = map(Q, ordinary_event.get(
                'observation_time_bounds', [ordinary_event['time']]*2))
            new_lo, new_hi = map(Q, forced_event.get(
                'observation_time_bounds', [forced_event['time']]*2))
            self.assertLessEqual(old_lo, new_lo)
            self.assertLessEqual(new_hi, old_hi)
            self.assertLessEqual(new_lo, root)
            self.assertLessEqual(root, new_hi)
        for n, t in enumerate(common):
            self.assertEqual(first['transient']['states'][n], forced['transient']['states'][n])
            old_bounds=first['observation_evidence']['voltage_bounds_V'][n]
            new_bounds=forced['observation_evidence']['voltage_bounds_V'][n]
            for column, (old, new) in enumerate(zip(old_bounds, new_bounds)):
                old_lo,old_hi=map(Q,old)
                new_lo,new_hi=map(Q,new)
                self.assertLessEqual(old_lo,new_lo,('forced lower',t,column))
                self.assertLessEqual(new_hi,old_hi,('forced upper',t,column))
                nominal=Q(forced['solutions'][n]['voltages'][column])
                self.assertLessEqual(new_lo,nominal)
                self.assertLessEqual(nominal,new_hi)
        # check_answers above still requires every selected output enclosure to
        # contain the independent rational answer at unchanged tolerances.

    def test_101_timer_before_time_cut_preserves_both_transition_histories(self):
        # The VA suffix literal 120n is parsed as binary64(120 * 1e-9).
        cut = Q(120 * 1e-9)
        event = 120 * Q(1e-9)
        rise = Q(300e-12)
        self.assertLess(event, cut)
        body = '''@(initial_step) q=0; @(timer(0,1n)) q=1-q;
            V(y,r)<+transition(($abstime>120n)?0.9:0,0,300p,300p);
            V(z,r)<+transition(q,0,300p,300p);'''
        common = [119.75e-9, 120e-9, float(cut), 120.075e-9, 120.15e-9, 120.3e-9, 120.5e-9]
        self.query_variants(body, 'real q; electrical z;', {'u': [[0, 0], [121e-9, 0]]},
                            common, common[-1], {'y': lambda t: Q(.9)*clip((t-cut)/rise),
                            'dut:z': lambda t: clip((t-event)/rise)}, clock=(0,1e-9))

    def test_314_timer_after_source_corner_keeps_phase_and_interrupted_history(self):
        cut = Q(52e-9)
        event = 104 * Q(500e-12)
        end = Q(52.1e-9)
        threshold = cut + (end-cut)*Q(.45)/Q(.9)
        rise = Q(200e-12)
        self.assertGreater(event, cut)
        self.assertLess(event, Q(math.nextafter(float(cut), math.inf)))
        def answer(t):
            if t <= threshold:
                return clip((t-event)/rise)
            return max(Q(0), (threshold-event)/rise - (t-threshold)/rise)
        body = '''@(initial_step) q=0; @(timer(0,500p)) q=1-q;
            V(y,r)<+transition((V(u,r)>0.45)?0:q,0,200p,200p);'''
        common = [51.75e-9, 52e-9, 52.025e-9, 52.05e-9, 52.075e-9, 52.2e-9, 52.25e-9]
        self.query_variants(body, 'real q;', {'u': [[0,0],[52e-9,0],[52.1e-9,.9],[53e-9,.9]]},
                            common, common[-1], {'y': answer}, clock=(0,500e-12))

    def test_physical_root_read_differs_from_upper_representative(self):
        cut, end = Q(52e-9), Q(52.1e-9)
        event = 104 * Q(500e-12)
        expected = Q(.9)*(event-cut)/(end-cut)
        upper = math.nextafter(float(cut), math.inf)
        representative_read = Q(.9)*(Q(upper)-cut)/(end-cut)
        self.assertEqual(representative_read, 8*expected)
        gain=Q(1000000)  # Make a wrong root read exceed the unchanged voltage budget.
        body = '''@(initial_step) q=0; @(timer(0,500p)) q=V(u,r);
            V(y,r)<+transition((V(u,r)>0.45)?0:1,0,200p,200p);
            V(z,r)<+1e6*transition(q,0,200p,200p);'''
        times = [52.01e-9, 52.2e-9, 52.25e-9]
        program, result = self.run_case(body, 'real q; electrical z;',
            {'u':[[0,0],[52e-9,0],[52.1e-9,.9],[53e-9,.9]]}, times, times[-1])
        answer=lambda t:gain*expected*clip((t-event)/Q(200e-12))
        self.check_answers(program, result, times, {'dut:z':answer})
        zi=program.nodes.index('dut:z')
        for t,bounds in zip(times,result['observation_evidence']['voltage_bounds_V']):
            lo,hi=map(Q,bounds[zi])
            wrong=gain*representative_read*clip((Q(t)-event)/Q(200e-12))
            self.assertGreater(abs(wrong-answer(Q(t))),
                               Q(1e-12)+Q(1e-10)*abs(answer(Q(t))))
            self.assertFalse(lo<=wrong<=hi)

    def test_changed_source_prefix_is_sampled_at_root_before_timer_update(self):
        cut=Q(52e-9)
        root=104*Q(500e-12)
        duration=Q(200e-12)
        sampled=(root-cut)/duration
        self.assertGreater(sampled,0)
        body='''@(initial_step) begin q=1; z=0; end
            @(timer(500p,500p)) if($abstime>=52n) begin z=V(y,r); q=2; end
            V(y,r)<+transition(($abstime>52n)?q:0,0,200p,200p);
            V(w,r)<+1e6*transition(z,0,200p,200p);'''
        times=[52.01e-9,52.2e-9,52.25e-9]
        program,result=self.run_case(body,'real q,z; electrical w;',
            {'u':[[0,0],[53e-9,0]]},times,times[-1])
        # Read the OLD rising prefix at root, then retain its first origin
        # while the new target 2 changes the rising slope to 2/duration.
        self.check_answers(program,result,times,{
            'y':lambda t:min(Q(2),sampled+2*(t-root)/duration),
            'dut:w':lambda t:Q(1000000)*sampled*clip((t-root)/duration)})

    def test_sine_of_old_transition_prefix_recomputes_at_physical_root(self):
        cut=Q(52e-9)
        root=104*Q(500e-12)
        duration=Q(200e-12)
        sampled=(root-cut)/duration
        sample_lo,sample_hi=sine_bounds(sampled)
        body='''@(initial_step) begin q=1; z=0; end
            @(timer(500p,500p)) if($abstime>=52n) begin z=V(y,r); q=2; end
            V(y,r)<+sin(transition(($abstime>52n)?q:0,0,200p,200p));
            V(w,r)<+1e6*transition(z,0,200p,200p);'''
        times=[52.01e-9,52.2e-9,52.25e-9]
        program,result=self.run_case(body,'real q,z; electrical w;',
            {'u':[[0,0],[53e-9,0]]},times,times[-1])
        def interval(node,t):
            if node=='y':
                return sine_bounds(min(Q(2),sampled+2*(t-root)/duration))
            factor=Q(1000000)*clip((t-root)/duration)
            return factor*sample_lo,factor*sample_hi
        # Every full Taylor enclosure must fit the DUT output enclosure. The
        # sine oracle is independent of Rust/Python floating point sin results.
        self.check_answers(program,result,times,{
            node:lambda t,node=node:interval(node,t)[0] for node in ['y','dut:w']})
        for n,t in enumerate(times):
            for node in ['y','dut:w']:
                column=program.nodes.index(node)
                lower,upper=interval(node,Q(t))
                lo,hi=map(Q,result['observation_evidence']['voltage_bounds_V'][n][column])
                self.assertLessEqual(lo,lower)
                self.assertLessEqual(upper,hi)
                nominal=Q(result['solutions'][n]['voltages'][column])
                error=max(abs(nominal-lower),abs(nominal-upper))
                self.assertLessEqual(error,Q(1e-12)+Q(1e-10)*abs(lower))

    def test_sub_ulp_interrupted_source_pulse_remains_explicitly_unsupported(self):
        cut=Q(52e-9)
        root=104*Q(500e-12)
        finish=2*root-cut
        next_float=Q(math.nextafter(float(cut),math.inf))
        self.assertLess(cut,root)
        self.assertLess(root,finish)
        self.assertLess(finish,next_float)
        # This is legal VA. The positive pulse spans 2*(root-cut), below one
        # binary64 ULP; current transition history requires representable time
        # progress and must refuse this unsupported interrupted edge.
        body='''@(initial_step) begin q=1; z=0; end
            @(timer(500p,500p)) if($abstime>=52n) begin z=V(y,r); q=0; end
            V(y,r)<+transition(($abstime>52n)?q:0,0,200p,200p);
            V(w,r)<+1e6*transition(z,0,200p,200p);'''
        # The interval target/current comparison can refuse before the later
        # representable-endpoint gate; both are explicit transition limits.
        with self.assertRaisesRegex(KernelError,
                'event_resolution: (cannot certify transition target relative to current output|transition edge cannot advance representable time)'):
            self.run_case(body,'real q,z; electrical w;',
                {'u':[[0,0],[53e-9,0]]},[52.01e-9,52.2e-9,52.25e-9],52.25e-9)

    def test_equal_source_corner_and_timer_remain_one_settlement(self):
        cut,end=Q(52e-9),Q(52.1e-9)
        mid=cut+(end-cut)/2
        rise=Q(200e-12)
        def answer(t):
            if t<=mid:
                return clip((t-cut)/rise)
            return max(Q(0),(mid-cut)/rise-(t-mid)/rise)
        body='''@(initial_step) q=0; @(timer(52n)) q=1;
            V(y,r)<+transition((V(u,r)>0.45)?0:q,0,200p,200p);'''
        times=[51.75e-9,52e-9,52.05e-9,52.075e-9,52.2e-9]
        self.query_variants(body,'real q;',{'u':[[0,0],[52e-9,0],[52.1e-9,.9],[53e-9,.9]]},
                            times,times[-1],{'y':answer},clock=(52e-9,0))

    def test_uncertified_held_clock_over_source_cut_still_rejects(self):
        # Sampling 0.1*binary64(0.3) produces a held interval without a
        # fixed-clock RootTime. Overlap with 0.03 cannot prove a phase.
        body = """@(initial_step) begin p=0.4; q=0; end
            @(timer(0.01)) p=0.1*V(u,r);
            @(timer(p)) q=1;
            V(y,r)<+transition(($abstime>0.03)?q:0,0,0.01,0.01);"""
        program=compile_sources({'unproved-root.va':model(body,'real p,q;')},[instance()])
        with self.assertRaisesRegex(KernelError,'event_resolution'):
            transient(program,{'u':[[0,0.3],[1,0.3]]},[0,0.025,0.03,0.1,1],
                      stop=1,max_step=0.1,kernel=KERNEL,timeout=120)

    def test_isolated_third_boundary_value_still_rejects(self):
        body='''V(y,r)<+transition(($abstime==52n)?1:0,0,200p,200p);'''
        with self.assertRaisesRegex(KernelError,'condition_precision.*(third boundary|isolated)'):
            self.run_case(body,'',{'u':[[0,0],[53e-9,0]]},[0,53e-9],53e-9)

    def test_unidentified_source_uncertainty_still_rejects(self):
        program=compile_sources({'unknown.va':model('''@(initial_step) q=0;
            @(timer(0,500p)) q=1-q;
            V(y,r)<+transition((V(u,r)>0.45)?0:q,0,200p,200p);''','real q;')},[instance()])
        with self.assertRaisesRegex(KernelError,'unsupported_source_uncertainty'):
            transient(program,{'u':[[0,0],[52e-9,0],[52.1e-9,.9],[53e-9,.9]]},[0,53e-9],
                      stop=53e-9,max_step=80e-12,source_errors={'u':1e-6},kernel=KERNEL,timeout=120)


if __name__ == '__main__':
    unittest.main()
