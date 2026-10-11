"""Independent positive/negative calibration of the breadth grading API."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'validation' / 'paper'))
from precision_breadth import load_contract, observation_plan, assess


def card():
    return {'id': 'F01-control', 'group_id': 'F01', 'family': 'foundation',
            'title': 'two constant voltage outputs', 'source': 'module control; endmodule',
            'top': 'control', 'ports': ['u', 'y', 'z'], 'parameters': {},
            'inputs': {'u': [[0., .25], [1e-6, .25]]}, 'outputs': ['y', 'z'],
            'scale_V': 1., 'unit_s': 1e-6, 'stop_s': 1e-6,
            'critical_times_s': [5e-7], 'events': [], 'counter_channels': {},
            'input_gain_bound': 2., 'output_slope_bound_V_s': 0.,
            'reference_kind': 'constant', 'reference_parameters': {}}


def reference(c, t, bounds):
    return {'outputs': {'y': [.5, .5], 'z': [-.25, -.25]},
            'numerical_uncertainty_V': 0., 'undefined': {}}


def trace(c):
    times = {i * 1e-6 / 32 for i in range(33)}
    times.update((5e-7 - 2e-12, 5e-7 + 2e-12))
    return [{'time': t, 'u': .25, 'y': .5, 'z': -.25} for t in sorted(times)]


class ContractCalibration(unittest.TestCase):
    def test_fixed_q_budgets_and_all_outputs(self):
        c = card(); contract = load_contract(cards=[c])
        self.assertEqual([q['factor'] for q in contract['tiers']], [10, 1, .1])
        result = assess(c, trace(c), contract, reference=reference)
        self.assertEqual([q['status'] for q in result['tiers'].values()], ['pass'] * 3)
        self.assertEqual(set(result['outputs']), {'y', 'z'})
        self.assertEqual(result['setting_evidence']['status'], 'unknown')


def event_card():
    c = card()
    c['outputs'].append('count')
    c['counter_channels'] = {'count': {'initial': 0, 'final': 1}}
    c['events'] = [{'id': 'sample', 'counter': 'count', 'index': 1,
                    'nominal_s': 5e-7, 'early_s': 1e-10, 'late_s': 1e-10, 'kind': 'timer'}]
    return c


def event_trace(c, at=5e-7):
    times = {r['time'] for r in trace(c)}
    for t in (5e-7 - 1e-10, 5e-7 + 1e-10):
        times.update((t - 2e-12, t, t + 2e-12))
    times.update((at - 1e-14, at + 1e-14))
    return [{'time': t, 'u': .25, 'y': .5, 'z': -.25, 'count': float(t >= at)} for t in sorted(times)]


class EventCalibration(unittest.TestCase):
    def check(self, c, rows, ref=reference):
        return assess(c, rows, load_contract(cards=[c]), reference=ref)

    def test_one_global_counter_bracket_for_all_outputs(self):
        c = event_card(); seen = []
        def oracle(c, t, bounds):
            seen.append(dict(bounds))
            return reference(c, t, bounds)
        result = self.check(c, event_trace(c), oracle)
        self.assertEqual(result['tiers']['Q3']['status'], 'pass', result)
        self.assertIn('sample', result['event_bounds_s'])
        self.assertTrue(all(b == result['event_bounds_s'] for b in seen))

    def test_wrong_count_initial_missing_repeated_and_noninteger(self):
        c = event_card()
        for fault in ('initial', 'missing', 'repeated', 'noninteger'):
            rows = event_trace(c)
            if fault == 'initial': rows[0]['count'] = 1.
            elif fault == 'missing':
                for r in rows: r['count'] = 0.
            elif fault == 'repeated':
                for r in rows:
                    if r['count']: r['count'] = 2.
            else: rows[3]['count'] = .25
            result = self.check(c, rows)
            self.assertEqual(result['behavior']['status'], 'behavior_error', (fault, result))
            self.assertTrue(all(q['status'] == 'behavior_error' for q in result['tiers'].values()))

    def test_outside_event_and_partial_window_overlap(self):
        c = event_card()
        self.assertEqual(self.check(c, event_trace(c, 5e-7 + 2e-10))['behavior']['status'], 'behavior_error')
        rows = event_trace(c, 5e-7 + 1e-10)
        rows = [r for r in rows if abs(r['time'] - (5e-7 + 1e-10)) > 1e-13]
        result = self.check(c, rows)
        self.assertEqual(result['behavior']['status'], 'unknown')
        self.assertTrue(all(q['status'] != 'pass' for q in result['tiers'].values()))

    def test_unobservable_callback_cannot_qualify_timing(self):
        c = card(); c['timing_evidence_required'] = True
        c['events'] = [{'id': 'hidden', 'index': 1, 'nominal_s': 5e-7, 'early_s': 1e-10,
                        'late_s': 1e-10, 'kind': 'timer'}]
        result = self.check(c, event_trace(c))
        self.assertIn('callback lacks observable counter: hidden', result['behavior']['issues'])
        self.assertTrue(all(q['status'] != 'pass' for q in result['tiers'].values()))


class ObservationAndReferenceCalibration(unittest.TestCase):
    def check(self, c, rows, ref=reference):
        return assess(c, rows, load_contract(cards=[c]), reference=ref)

    def test_numeric_error_does_not_hide_missing_boundary_evidence(self):
        c = card(); rows = trace(c)
        rows = [r for r in rows if abs(r['time'] - 5e-7) > 3e-12]
        for r in rows: r['z'] += 1e-3
        result = self.check(c, rows)
        self.assertEqual(result['tiers']['Q3']['numerical']['status'], 'numerical_error')
        self.assertEqual(result['tiers']['Q3']['evidence']['status'], 'evidence_insufficient')

    def test_wrong_second_output_and_initial_state_are_not_omitted(self):
        for index in (0, 10):
            c = card(); rows = trace(c); rows[index]['z'] = 0.
            self.assertTrue(all(q['status'] == 'numerical_error' for q in self.check(c, rows)['tiers'].values()))

    def test_missing_nan_and_duplicate_actual_times_are_unknown(self):
        for fault in ('missing', 'nan', 'duplicate'):
            c = card(); rows = trace(c)
            if fault == 'missing': del rows[0]['z']
            elif fault == 'nan': rows[0]['z'] = float('nan')
            else: rows[3]['time'] = rows[2]['time']
            self.assertTrue(all(q['status'] == 'evidence_insufficient' for q in self.check(c, rows)['tiers'].values()))

    def test_input_amplification_and_reference_uncertainty_are_separate(self):
        c = card(); c['input_gain_bound'] = 1000.
        rows = trace(c)
        for r in rows: r['u'] += 1e-10
        result = self.check(c, rows)
        self.assertIn('amplified input uncertainty exceeds B/100', result['tiers']['Q3']['evidence']['issues'])
        def uncertain(c, t, b):
            ans = reference(c, t, b); ans['numerical_uncertainty_V'] = 2e-9; return ans
        result = self.check(card(), trace(card()), uncertain)
        self.assertEqual(result['tiers']['Q3']['numerical']['status'], 'pass')
        self.assertEqual(result['tiers']['Q3']['evidence']['status'], 'evidence_insufficient')

    def test_support_probe_and_invalid_reference_cannot_pass(self):
        def unsupported(c, t, b): raise NotImplementedError('unsettled contract')
        def missing(c, t, b):
            ans = reference(c, t, b); del ans['outputs']['z']; return ans
        def invalid(c, t, b):
            ans = reference(c, t, b); ans['outputs']['z'] = [float('nan'), 0.]; return ans
        for ref in (unsupported, missing, invalid):
            result = self.check(card(), trace(card()), ref)
            self.assertTrue(all(q['status'] == 'evidence_insufficient' for q in result['tiers'].values()))

    def test_request_resource_cap_keeps_event_and_reports_unachieved_density(self):
        c = event_card(); c['event_sensitivity_bound_V_s'] = 1e15
        plan = observation_plan(c, load_contract(cards=[c]))
        self.assertIn(5e-7, plan['times_s'])
        self.assertLess(len(plan['times_s']), 20100)
        self.assertTrue(plan['event_grids'][0]['request_density_capped'])
        self.assertGreater(plan['event_grids'][0]['requested_intervals'], plan['event_grids'][0]['planned_intervals'])

    def test_true_undefined_point_requires_named_one_sided_obligations(self):
        c = card(); c['undefined_points'] = [{'time_s': 5e-7, 'outputs': ['z'],
                                             'left_s': 5e-7 - 2e-12, 'right_s': 5e-7 + 2e-12}]
        def oracle(c, t, b):
            ans = reference(c, t, b)
            if t == 5e-7: del ans['outputs']['z']; ans['undefined'] = {'z': 'PWL derivative corner'}
            return ans
        result = self.check(c, trace(c), oracle)
        self.assertEqual(result['tiers']['Q3']['status'], 'pass', result)
        self.assertEqual(len(result['undefined_observations']), 1)
        c.pop('undefined_points')
        self.assertTrue(all(q['status'] != 'pass' for q in self.check(c, trace(c), oracle)['tiers'].values()))

    def test_observation_plan_keeps_event_windows_and_dense_high_gain_requests(self):
        c = event_card(); c['inputs']['u'] = [[0., 0.], [1e-6, .1]]
        c['input_gain_bound'] = 1.
        plan = observation_plan(c, load_contract(cards=[c]))
        for t in (0., 1e-6, 5e-7 - 1e-10, 5e-7, 5e-7 + 1e-10):
            self.assertIn(t, plan['times_s'])
        self.assertLess(min(b-a for a,b in zip(plan['times_s'], plan['times_s'][1:])), 1e-13)


class QualificationCalibration(unittest.TestCase):
    def check(self, c, rows):
        return assess(c, rows, load_contract(cards=[c]), reference=reference)

    def test_two_independent_counters_must_prove_event_order(self):
        c = event_card(); c['outputs'].append('other')
        c['counter_channels']['other'] = {'initial': 0, 'final': 1}
        e = dict(c['events'][0]); e.update(id='second', counter='other', nominal_s=5e-7 + 2e-11)
        c['events'].append(e)
        rows = event_trace(c)
        for r in rows: r['other'] = r['count']
        result = self.check(c, rows)
        self.assertEqual(result['behavior']['status'], 'unknown')
        self.assertIn('cross-channel callback order is unresolved', result['behavior']['issues'])
        # Counter and waveform values remain the same; an explicit sequence
        # evidence obligation must never become pass merely from final counts.
        c['events'] = c['events'][:1]; c['outputs'].remove('other'); c['counter_channels'].pop('other')
        c['order_evidence_required'] = True
        self.assertTrue(all(q['status'] != 'pass' for q in self.check(c, rows)['tiers'].values()))

    def test_dc_transient_phase_is_not_inferred_from_time_zero(self):
        c = card(); c['phase_obligations'] = ['DC initial state', 'transient startup state']
        result = self.check(c, trace(c))
        self.assertEqual(result['phase_evidence']['status'], 'unknown')
        self.assertTrue(all(q['status'] != 'pass' for q in result['tiers'].values()))

    def test_wide_reference_range_and_wrap_do_not_use_nearest_answer(self):
        c = card()
        def interval(c, t, b):
            ans = reference(c, t, b); ans['outputs']['z'] = [-.25, .75]; return ans
        result = assess(c, trace(c), load_contract(cards=[c]), reference=interval)
        self.assertEqual(result['outputs']['z']['error_lower_V'], 0.)
        self.assertGreater(result['outputs']['z']['error_upper_V'], .99)
        self.assertTrue(all(q['status'] == 'evidence_insufficient' for q in result['tiers'].values()))

    def test_actual_shifted_rows_use_actual_time_without_interpolation(self):
        c = card(); c['outputs'] = ['y']; c['output_slope_bound_V_s'] = 1e6
        def ramp(c, t, b):
            return {'outputs': {'y': [t * 1e6, t * 1e6]}, 'numerical_uncertainty_V': 0., 'undefined': {}}
        rows = trace(c)
        for r in rows:
            if 0 < r['time'] < 1e-6 and abs(r['time'] - 5e-7) > 3e-12: r['time'] += 1e-13
            r['y'] = r['time'] * 1e6
        result = assess(c, rows, load_contract(cards=[c]), reference=ramp)
        self.assertEqual(result['tiers']['Q3']['status'], 'pass')

    def test_adjacent_input_identity_needs_evidence_beyond_voltage_budget(self):
        c = card(); c['input_exact_evidence_required'] = True
        result = self.check(c, trace(c))
        self.assertTrue(all(q['numerical']['status'] == 'pass' for q in result['tiers'].values()))
        self.assertTrue(all(q['status'] == 'evidence_insufficient' for q in result['tiers'].values()))

    def test_reference_receives_whole_query_time_box_without_card_mutation(self):
        import math
        c = card(); c['reference_time_uncertainty_s'] = 0.; c['output_slope_bound_V_s'] = 1e6
        seen = []
        def oracle(model, t, bounds):
            seen.append(model['reference_time_uncertainty_s'])
            ans = reference(model, t, bounds)
            ans['time_uncertainty_included'] = True
            return ans
        result = assess(c, trace(c), load_contract(cards=[c]), reference=oracle)
        self.assertTrue(all(t == 16 * math.ulp(1e-6) for t in seen))
        self.assertEqual(c['reference_time_uncertainty_s'], 0.)
        # A declared whole-box reference needs only voltage export rounding;
        # the large smooth derivative must not be counted a second time.
        self.assertLess(result['outputs']['y']['unresolved_uncertainty_V'], 2e-15)

    def test_query_time_box_keeps_half_open_wrap_boundary_defined(self):
        import math
        c = card(); c['critical_times_s'] = [5e-7]
        c['outputs'] = ['y']; c['output_slope_bound_V_s'] = 1e6
        def wrap(model, t, bounds):
            ut = model['reference_time_uncertainty_s']
            interval = [0., 1.] if abs(t - 5e-7) <= ut else ([.75, .75] if t < 5e-7 else [.25, .25])
            return {'outputs': {'y': interval}, 'numerical_uncertainty_V': 0.,
                    'undefined': {}, 'time_uncertainty_included': True}
        rows = trace(c)
        for r in rows: r['y'] = .75 if r['time'] < 5e-7 else .25
        result = assess(c, rows, load_contract(cards=[c]), reference=wrap)
        self.assertEqual(result['undefined_observations'], [])
        self.assertEqual(result['outputs']['y']['defined_observations'], len(rows))
        self.assertGreater(result['outputs']['y']['error_upper_V'], .74)
        self.assertTrue(all(q['status'] == 'evidence_insufficient' for q in result['tiers'].values()))

    def test_invalid_contract_metadata_is_rejected_before_execution(self):
        c = card(); c['input_gain_bound'] = -1.
        with self.assertRaises(ValueError): load_contract(cards=[c])


if __name__ == '__main__':
    unittest.main()
