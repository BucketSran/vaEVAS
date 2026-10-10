"""Input-root recovery uses the unchanged engineering voltage budget.

The 10 nV + 1 ppm fixed-scale rule is precision-engineering-v1's external
acceptance, not a claim that equal backend tolerance names mean equal accuracy.
"""
GUARDS = ["CROSS", "EVENT-ORDER", "COMPOSE", "DEV:precision-chain"]

import json
import math
from pathlib import Path
import tempfile
import unittest

from evas import KernelError
from evas.runtime import _invoke
from test_affine import KERNEL
from test_continuous_dynamics import compile_model, values


def request_for(body, declarations='real q;', *, sources=None, times=None,
                budget=2.01e-6):
    sources = sources or {'u': [[0, 0], [3, 3]]}
    ports = ','.join([*sources, 'y', 'r'])
    program = compile_model(body, declarations, ports=ports,
                            directions=f"input {','.join(sources)}; output y; inout r;")
    return dict(program=program.to_dict(), driven=list(sources), samples=[],
                transient=dict(pwl=list(sources.values()),
                               output_times=times or [0, 1, 2, 3], stop=3, max_step=3),
                tolerances=dict(absolute=budget, relative=0))


def observe(request):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'diagnostics.json'
        try:
            response = _invoke(request, KERNEL, diagnostics_path=path)
            error = None
        except KernelError as exc:
            response, error = None, exc.detail
        return response, error, json.loads(path.read_text())


def details(report, kind):
    return [json.loads(r['reason']) for r in report['records'] if r['kind'] == kind]


class RootRecovery(unittest.TestCase):
    def test_sample_gets_voltage_demand_and_stops_at_a_certified_target(self):
        request = request_for(
            '@(initial_step) q=0; '
            '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3)) q=V(u,r); V(y,r)<+q;')
        result, error, report = observe(request)
        self.assertIsNone(error)
        self.assertEqual(_invoke(request, KERNEL), result)
        for actual in values(result)[2:]:
            self.assertLessEqual(abs(actual-math.sqrt(2)), 2.01e-6)
        self.assertEqual(len(result['transient']['events']), 1)
        demand = details(report, 'root_demand')
        self.assertEqual(len(demand), 1)
        self.assertEqual(demand[0]['source'], 'current_root')
        self.assertEqual(demand[0]['consumer'], 'y')
        self.assertGreater(demand[0]['target_width'], 0)
        refinement = details(report, 'root_refinement')[-1]
        self.assertEqual(refinement['stop'], 'target_reached')
        self.assertLessEqual(refinement['width_after'], demand[0]['target_width'])
        self.assertGreater(refinement['width_after'], 1e-14)

    def test_close_queries_do_not_change_the_accepted_root_or_samples(self):
        body = ('@(initial_step) q=0; '
                '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3)) q=V(u,r); V(y,r)<+q;')
        sparse = [0, 1, 2, 3]
        dense = [0, 1, math.sqrt(2)-1e-12, math.sqrt(2)+1e-12, 2, 3]
        first, error, _ = observe(request_for(body, times=sparse))
        self.assertIsNone(error)
        second, error, _ = observe(request_for(body, times=dense))
        self.assertIsNone(error)
        self.assertEqual(first['transient']['events'], second['transient']['events'])
        self.assertEqual(first['solutions'], [second['solutions'][dense.index(t)] for t in sparse])
        self.assertEqual(values(second)[2], 0)
        self.assertLessEqual(abs(values(second)[3]-math.sqrt(2)), 2.01e-6)

    def test_inherited_sample_failure_does_not_refine_an_unrelated_root(self):
        request = request_for(
            '@(initial_step) q=0; '
            '@(timer(1,0,1e-12) or cross(pow(V(c,r),2)-2,1,1e-3,1e-3)) '
            'if(V(c,r)<1.2) q=V(u,r)-1; else q=1e16*q; V(y,r)<+q;',
            sources={'u': [[0, 1], [3, math.nextafter(1, math.inf)]],
                     'c': [[0, 0], [3, 3]]})
        result, error, report = observe(request)
        self.assertIsNone(result)
        self.assertEqual(error['kind'], 'event_accuracy')
        demand = details(report, 'root_demand')[-1]
        self.assertEqual(demand['source'], 'retained')
        self.assertGreater(demand['inherited_state_bound'], demand['budget'])
        self.assertEqual(report['counters'].get('root_refinement_iterations', 0), 0)
        self.assertFalse(details(report, 'root_refinement'))

    def test_second_consumer_can_require_a_bounded_fallback(self):
        request = request_for(
            '@(initial_step) q=0; '
            '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3)) q=V(u,r); '
            'V(z,r)<+q; V(y,r)<+1e6*q;', 'real q; electrical z;')
        result, error, report = observe(request)
        self.assertIsNone(error)
        for actual in values(result)[2:]:
            self.assertLessEqual(abs(actual-1e6*math.sqrt(2)), 2.01e-6)
        trials = details(report, 'root_refinement')
        self.assertEqual(len(trials), 2)
        self.assertIsNotNone(trials[0]['target_width'])
        self.assertIsNone(trials[1]['target_width'])
        self.assertLessEqual(sum(t['iterations'] for t in trials), 256)

    def test_sampling_and_observation_time_do_not_cancel(self):
        request = request_for(
            '@(initial_step) q=0; '
            '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3)) q=V(u,r); V(y,r)<+q-V(u,r);')
        result, error, report = observe(request)
        self.assertIsNone(error)
        self.assertGreater(details(report, 'root_demand')[0]['time_sensitivity'], 0)
        for t, actual in zip([2, 3], values(result)[2:]):
            self.assertLessEqual(abs(actual-(math.sqrt(2)-t)), 2.01e-6)

    def test_filter_unknown_uses_existing_recovery_and_old_error_is_retained(self):
        request = request_for(
            '@(initial_step) q=0; '
            '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3)) q=1; '
            'V(e,r)<+transition(q,0,0.5,0.5); '
            "V(y,r)<+laplace_nd(V(e,r),'{1},'{1,0.25});", 'real q; electrical e;',
            budget=1.01e-6)
        result, error, report = observe(request)
        self.assertIsNone(error)
        self.assertEqual(details(report, 'root_demand')[0]['source'], 'unknown')
        from test_sample_edge_filter import ramp_filter
        for t, actual in zip([0, 1, 2, 3], values(result)):
            self.assertLessEqual(abs(actual-ramp_filter(t, start=math.sqrt(2))), 1.01e-6)

        request = request_for(
            '@(initial_step) q=1; @(timer(1,1,1e-12)) q=1e16*(V(u,r)-1); '
            "V(y,r)<+laplace_nd(q,'{1},'{1,1});",
            sources={'u': [[0, 1], [3, math.nextafter(1, math.inf)]]},
            times=[0, 1, 1.5, 3], budget=1.01e-6)
        result, error, report = observe(request)
        self.assertIsNone(result)
        self.assertEqual(error['kind'], 'waveform_accuracy')
        self.assertFalse(details(report, 'root_refinement'))
        self.assertTrue(any(r['kind'] == 'event_batch' and r['start'] == 1
                            for r in report['records']))

    def test_too_small_budget_stops_without_losing_the_original_failure(self):
        request = request_for(
            '@(initial_step) q=0; '
            '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3)) q=V(u,r); V(y,r)<+q;',
            budget=1e-30)
        result, error, report = observe(request)
        self.assertIsNone(result)
        self.assertEqual(error['kind'], 'event_accuracy')
        trials = details(report, 'root_refinement')
        self.assertLessEqual(len(trials), 2)
        self.assertLessEqual(sum(t['iterations'] for t in trials), 256)
        self.assertIn(trials[-1]['stop'], ['arithmetic_floor', 'stalled'])
        failures = details(report, 'accuracy_failure')
        self.assertTrue(any(f['consumer'] == 'y' and f['error_bound'] > f['budget']
                            for f in failures))

    def test_later_event_amplification_keeps_legacy_recovery(self):
        request = request_for(
            '@(initial_step) q=0; '
            '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3) or '
            'cross(pow(V(u,r),2)-5,1,1e-3,1e-3)) '
            'if(V(u,r)<2) q=V(u,r); else q=1e6*q; V(y,r)<+q;')
        result, error, report = observe(request)
        self.assertIsNone(error)
        self.assertLessEqual(abs(values(result)[-1]-1e6*math.sqrt(2)), 2.01e-6)
        self.assertEqual(len(result['transient']['events']), 2)

    def test_future_zero_crossing_keeps_the_original_relative_budget(self):
        request = request_for(
            '@(initial_step) q=0; '
            '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3)) q=V(u,r); '
            'V(y,r)<+q-0.5*V(u,r);', times=[0, 1, 2*math.sqrt(2), 3])
        request['tolerances'] = dict(absolute=1e-12, relative=1e-4)
        result, error, report = observe(request)
        self.assertIsNone(error)
        self.assertLessEqual(abs(values(result)[2]), 1e-12)
        self.assertTrue(all(t['target_width'] is None
                            for t in details(report, 'root_refinement')))


if __name__ == '__main__':
    unittest.main()
