"""Held source targets: analytic limiter answers, independent of output grids."""
# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["SLEW", "TIMED-OPERATOR"]

from fractions import Fraction as F
import os
import json
import subprocess
from pathlib import Path
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL as DEFAULT_KERNEL, instance, model

KERNEL = Path(os.environ.get('EVAS_SOURCE_SLEW_KERNEL', DEFAULT_KERNEL))


def run(body='V(y,r)<+slew(V(u,r)>0.5?1.0:0.0,1,-2);', *,
        points=None, times=None, stop=2, step=2, atol=1e-12,
        declarations='', extra_sources=None):
    program = compile_sources({'selected_slew.va': model(body, declarations)}, [instance()])
    sources = {'u': points or [[0, 0], [1, 1], [2, 1]]}
    sources.update(extra_sources or {})
    return transient(program, sources, times or [0, .25, .5, .75, 1, 1.5, 2],
                     stop=stop, max_step=step, vabstol=atol, reltol=0, kernel=KERNEL)


def values(result, node='y'):
    index = result['nodes'].index(node)
    return [row['voltages'][index] for row in result['solutions']]


class SourceSelectedSlew(unittest.TestCase):
    def test_target_step_is_continuous_rate_limited_and_grid_independent(self):
        times = [0, .25, .5, .75, 1, 1.5, 2]
        expected = [0, 0, 0, .25, .5, 1, 1]
        for step in [2, .125]:
            result = run(times=times, step=step)
            self.assertEqual(values(result), expected)
        # Extra observations cannot define a different physical target history.
        dense_times = sorted(set(times + [i/32 for i in range(65)]))
        dense = run(times=dense_times)
        selected = dict(zip(dense_times, values(dense)))
        self.assertEqual([selected[t] for t in times], expected)

    def test_reversal_carries_old_output_and_uses_asymmetric_fall(self):
        # target switches 0->1 at1/2, then1->0 at5/4; y(5/4)=3/4,
        # and the falling edge reaches zero at13/8.
        times = [0, .5, 1, 1.25, 1.5, 1.625, 2]
        result = run(points=[[0, 0], [1, 1], [1.5, 0], [2, 0]], times=times)
        self.assertEqual(values(result), [0, 0, .5, .75, .25, 0, 0])

    def test_point_seed_and_right_target_are_distinct_at_zero(self):
        for relation, initial in [('>', 0), ('>=', 1)]:
            result = run(f'V(y,r)<+slew(V(u,r){relation}0?1.0:0.0,1,-2);',
                         points=[[0, 0], [2, 2]], times=[0, .25, 1, 2])
            self.assertEqual(values(result), [initial, max(initial, .25), 1, 1])

    def test_two_calls_keep_independent_history(self):
        result = run('V(y,r)<+slew(V(u,r)>0.5?1.0:0.0,1,-2)'
                     '+slew(V(u,r)>0.75?1.0:0.0,2,-1);',
                     times=[0, .5, .75, 1, 1.25, 2])
        self.assertEqual(values(result), [0, 0, .25, 1, 1.75, 2])

    def test_rational_root_window_survives_future_amplification(self):
        body = 'V(y,r)<+1073741824*slew(V(u,r)>1?1.0:0.0,1,-2);'
        points = [[0, 0], [1, 3], [2, 3]]
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            run(body, points=points, times=[0, .5, 1, 2], atol=1e-10)
        result = run(body, points=points, times=[0, .5, 1, 2], atol=1e-5)
        for actual, t in zip(values(result), [0, F(1, 2), 1, 2]):
            expected = 2**30 * min(F(1), max(F(0), F(t)-F(1, 3)))
            self.assertLessEqual(abs(F(actual)-expected), F(1e-5))

    def test_sampled_root_error_survives_storage_and_later_gain(self):
        body = ('@(initial_step) begin b=0;c=0;end '
                '@(timer(0.5,0,0.001)) b=V(y,r); '
                '@(timer(1,0,0.001)) c=1073741824*V(z,r)-178956970.66666666+1; '
                'V(y,r)<+slew(V(u,r)>1?1.0:0.0,1,-2); '
                'V(z,r)<+b; V(w,r)<+c;')
        options = dict(points=[[0, 0], [1, 3], [2, 3]], times=[0, .5, 1, 2],
                       declarations='real b,c; electrical z,w;')
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            run(body, atol=1e-9, **options)
        result = run(body, atol=1e-5, **options)
        exact = F(2**30, 6)-F(178956970.66666666)+1
        self.assertLessEqual(abs(F(values(result, 'dut:w')[2])-exact), F(1e-5))

    def test_adjacent_physical_roots_are_not_merged(self):
        # A steep rate makes the one-ulp-wide target pulse observable.
        import math
        threshold = math.nextafter(.5, 1)
        result = run(f'V(y,r)<+slew((V(u,r)>0.5 && V(u,r)<{threshold!r})?1.0:0.0,1e16,-1e16);',
                     points=[[0, 0], [1, 1], [2, 1]], times=[0, .5, threshold, 1, 2])
        # The isolated upper endpoint is the old or right mode; output remains
        # continuous, and must remember the physical interval between roots.
        self.assertGreater(values(result)[2], .9)
        self.assertEqual(values(result)[-1], 0)

    def test_distinct_rational_roots_with_one_representative_reject(self):
        # Binary thresholds .1 and its successor divided by3 are distinct,
        # but have the same binary64 upper representative. No equality proof
        # may be inferred from those overlapping root windows.
        with self.assertRaisesRegex(KernelError, 'event_resolution'):
            run('V(y,r)<+slew((V(u,r)>0.1 && V(u,r)<0.10000000000000002)?1.0:0.0,1e18,-1e18);',
                points=[[0, 0], [1, 3], [2, 3]], times=[0, .1, 2])

    def test_large_epoch_keeps_the_source_cut_local_duration(self):
        epoch = 2**54
        times = [0, epoch, epoch+32, epoch+40, epoch+64, epoch+96, epoch+128]
        result = run('V(y,r)<+slew(V(u,r)>0.5?4.0:0.0,0.0625,-0.125);',
                     points=[[0, 0], [epoch, 0], [epoch+64, 1], [epoch+128, 1]],
                     times=times, stop=epoch+128, step=epoch+128)
        self.assertEqual(values(result), [0, 0, 0, .5, 2, 4, 4])

    def test_isolated_target_point_is_not_a_fictitious_pulse(self):
        result = run('V(y,r)<+slew(V(u,r)==0.5?1.0:0.0,1,-2);')
        self.assertEqual(values(result), [0] * 7)

    def test_simultaneous_predicates_preserve_a_third_boundary_point(self):
        result = run('V(y,r)<+slew((V(u,r)>0.5?2.0:0.0)'
                     '+(V(u,r)<0.5?1.0:0.0),1,-2);')
        # target is1 to the left,0 at the root,2 to the right. The isolated
        # point cannot reset a continuous limiter or create a falling pulse.
        self.assertEqual(values(result), [1, 1, 1, 1.25, 1.5, 2, 2])

    def test_isolated_initial_seed_is_preserved_and_terminal_point_has_no_pulse(self):
        initial = run('V(y,r)<+slew(V(u,r)==0?1.0:0.0,1,-2);')
        self.assertEqual(values(initial), [1, .5, 0, 0, 0, 0, 0])
        terminal = run('V(y,r)<+slew(V(u,r)==2?1.0:0.0,1,-2);',
                       points=[[0, 0], [2, 2]])
        self.assertEqual(values(terminal), [0] * 7)

    def test_transition_third_boundary_point_remains_rejected(self):
        with self.assertRaisesRegex(KernelError, 'condition_precision'):
            run('V(y,r)<+transition((V(u,r)>0.5?2.0:0.0)'
                '+(V(u,r)<0.5?1.0:0.0),0,1,1);')

    def test_state_or_history_targets_and_nonheld_leaves_still_reject(self):
        bodies = [
            ('@(initial_step) q=0; V(y,r)<+slew(V(u,r)>0.5?q:1.0,1,-2);', 'real q;'),
            ('V(y,r)<+slew(V(u,r)>0.5?V(u,r):0.0,1,-2);', ''),
            ('V(y,r)<+slew(V(y,r)>0.5?1.0:0.0,1,-2);', ''),
            ('V(y,r)<+slew(slew(V(u,r)>0.5?1.0:0.0,1,-2),1,-2);', ''),
        ]
        for body, declarations in bodies:
            with self.subTest(body=body), self.assertRaises((CompileError, KernelError)):
                run(body, declarations=declarations)

    def test_nonzero_source_error_is_not_erased_by_selected_target(self):
        program = compile_sources({'error.va': model(
            'V(y,r)<+1073741824*slew(V(u,r)>0.5?1.0:0.0,1,-2);')}, [instance()])
        # A physical source error can move the threshold time. The current
        # first slice has no shaped-source theorem and must explicitly reject.
        with self.assertRaises(KernelError):
            transient(program, {'u': [[0, 0], [2, 2]]}, [0, 1, 2],
                      source_errors={'u': 1e-6}, stop=2, max_step=2, kernel=KERNEL)

    def test_raw_dead_arm_indices_are_validated_before_selection(self):
        program = compile_sources({'raw.va': model(
            'V(y,r)<+slew(V(u,r)>0.5?1.0:0.0,1,-2);')}, [instance()]).to_dict()
        program['operators'][0]['input']['then_value'] = {
            'op': 'affine', 'constant': 1, 'terms': [{'node': 1000000, 'coefficient': 1}]}
        request = dict(program=program, driven=['u'], samples=[],
                       transient=dict(pwl=[[[0, 0], [2, 0]]], output_times=[0, 2],
                                      stop=2, max_step=2))
        response = subprocess.run([str(KERNEL)], input=json.dumps(request),
                                  text=True, capture_output=True, check=False)
        self.assertNotEqual(response.returncode, 0)
        self.assertEqual(json.loads(response.stderr)['kind'], 'invalid_ir')

    def test_transition_and_selected_slew_share_the_128_plan_quota(self):
        def body(transitions):
            terms = ['transition(V(u,r)>0.5?1.0:0.0,0,1,1)'] * transitions
            terms += ['slew(V(u,r)>0.5?1.0:0.0,1,-2)'] * 2
            return ''.join('V(y,r)<+' + term + ';' for term in terms)
        result = run(body(126), times=[0, 1, 2], atol=1e-9)
        self.assertEqual(values(result), [0, 64, 128])
        with self.assertRaisesRegex(KernelError, 'step_budget.*slot 0'):
            run(body(127), times=[0, 1, 2], atol=1e-9)

    def test_invalid_rate_rejects_before_running_history(self):
        for rise, fall in [(0, -2), (1, 0), (-1, -2)]:
            with self.subTest(rise=rise, fall=fall), self.assertRaises((CompileError, KernelError)):
                run(f'V(y,r)<+slew(V(u,r)>0.5?1.0:0.0,{rise},{fall});')


if __name__ == '__main__':
    unittest.main()
