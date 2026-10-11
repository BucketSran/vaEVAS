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
    def test_declared_counter_and_event_extent_are_contract_errors(self):
        for fault in ('unknown_counter', 'past_final', 'before_initial', 'negative_window'):
            c = event_card()
            if fault == 'unknown_counter': c['events'][0]['counter'] = 'missing'
            elif fault == 'past_final': c['events'][0]['index'] = 2
            elif fault == 'before_initial': c['events'][0]['index'] = 0
            else: c['events'][0]['early_s'] = 1e-6
            with self.assertRaises(ValueError, msg=fault): load_contract(cards=[c])

    def test_invalid_undefined_obligations_are_contract_errors(self):
        for fault in ('left', 'right', 'output', 'finite', 'endpoint'):
            c = card(); p = {'time_s': 5e-7, 'left_s': 5e-7-2e-12,
                             'right_s': 5e-7+2e-12, 'outputs': ['y']}
            if fault == 'left': p['left_s'] = p['time_s']
            elif fault == 'right': p['right_s'] = 2e-6
            elif fault == 'output': p['outputs'] = ['nonexistent']
            elif fault == 'finite': p['time_s'] = float('nan')
            else: p['time_s'] = 0.; p['left_s'] = -2e-12
            c['undefined_points'] = [p]
            with self.assertRaises(ValueError, msg=fault): load_contract(cards=[c])

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

    def test_two_consumers_use_counter_history_not_separate_output_fits(self):
        c = event_card(); at = 5e-7
        rows = event_trace(c, at)
        rows.extend({'time':t, 'u':.25, 'y':.5, 'z':-1., 'count':float(t>=at)}
                    for t in (at-1e-15, at+1e-15))
        rows.sort(key=lambda r:r['time'])
        for row in rows: row['z'] = -1.
        def consumer_reference(c, t, bounds):
            lo, hi = bounds['sample']
            return {'outputs':{'y':[lo*1e6,hi*1e6], 'z':[-2e6*hi,-2e6*lo]},
                    'numerical_uncertainty_V':0., 'undefined':{}}
        result = self.check(c, rows, consumer_reference)
        self.assertTrue(all(q['status'] == 'pass' for q in result['tiers'].values()), result)
        for row in rows: row['z'] += 1e-3
        result = self.check(c, rows, consumer_reference)
        self.assertTrue(all(q['status'] == 'numerical_error' for q in result['tiers'].values()))

    def test_unobservable_declared_order_never_becomes_observed_failure_or_pass(self):
        for reverse in (False, True):
            c = card()
            c['events'] = [dict(id=str(i), index=1, nominal_s=t, early_s=1e-10, late_s=1e-10, kind='timer')
                           for i,t in enumerate(([7e-7,3e-7] if reverse else [3e-7,7e-7]))]
            result = self.check(c, trace(c))
            self.assertEqual(result['behavior']['status'], 'unknown')
            self.assertTrue(all(q['status'] == 'evidence_insufficient' for q in result['tiers'].values()))

    def test_cross_legal_window_requires_both_frozen_tolerances(self):
        c = event_card(); c['events'][0].update(kind='cross', early_s=0., late_s=1e-10,
                                               slope_V_s=1e6, expression_tolerance_V=5e-5)
        result = self.check(c, event_trace(c, 5e-7+7e-11))
        self.assertEqual(result['behavior']['status'], 'behavior_error')
        c['events'][0].pop('counter'); c['counter_channels'] = {}; c['outputs'].remove('count')
        result = self.check(c, event_trace(c))
        self.assertEqual(result['event_bounds_s']['sample'], [5e-7,5e-7+5e-11])
        self.assertEqual(result['behavior']['status'], 'unknown')

    def test_reference_stage_is_verified_counter_state_not_card_hint_or_output(self):
        c = event_card(); c['reference_counter_stages'] = {'count': 999}
        seen = []
        def oracle(model, t, bounds):
            seen.append((model['reference_counter_stages'], model['reference_event_stages']))
            return reference(model, t, bounds)
        rows = event_trace(c)
        result = self.check(c, rows, oracle)
        self.assertEqual([stage['count'] for stage, _ in seen], [int(r['count']) for r in rows])
        self.assertEqual([events['sample'] for _, events in seen], [bool(r['count']) for r in rows])
        self.assertEqual(result['tiers']['Q3']['status'], 'pass')
        seen.clear(); rows[-1]['count'] = 2.
        result = self.check(c, rows, oracle)
        self.assertEqual(result['behavior']['status'], 'behavior_error')
        self.assertTrue(all(not stage and not events for stage, events in seen))

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

    def test_input_deviation_and_actual_extent_gap_cannot_qualify(self):
        for fault in ('input', 'start', 'stop', 'gap'):
            c = card(); rows = trace(c)
            if fault == 'input': rows[10]['u'] += 1e-4
            elif fault == 'start': rows = rows[1:]
            elif fault == 'stop': rows = rows[:-1]
            else: rows = [r for r in rows if not 1e-7 < r['time'] < 4e-7]
            result = self.check(c, rows)
            if fault == 'input':
                self.assertGreater(result['input_error_upper_V']['u'], 9e-5)
                self.assertTrue(all('input uncertainty exceeds B/100' in q['evidence']['issues'] for q in result['tiers'].values()))
            else:
                reason = 'observation gap exceeds frozen limit' if fault == 'gap' else 'incomplete start/stop coverage'
                self.assertIn(reason, result['observation_issues'])
            self.assertTrue(all(q['status'] == 'evidence_insufficient' for q in result['tiers'].values()), fault)

    def test_undefined_is_not_a_serialization_window_exemption(self):
        import math
        c = card(); point = 5e-7
        c['undefined_points'] = [{'time_s':point, 'left_s':point-2e-12,
                                 'right_s':point+2e-12, 'outputs':['z']}]
        rows = trace(c)
        for row in rows:
            if row['time'] == point: row['time'] = math.nextafter(point, math.inf)
        def oracle(c, t, b):
            ans = reference(c, t, b)
            if t == math.nextafter(point, math.inf):
                del ans['outputs']['z']; ans['undefined'] = {'z':'fake undefined window'}
            return ans
        result = assess(c, rows, load_contract(cards=[c]), reference=oracle)
        self.assertTrue(all(q['numerical']['status'] == 'unknown' for q in result['tiers'].values()))
        self.assertTrue(any('undeclared mathematical undefined' in issue for issue in result['observation_issues']))

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

    def test_nonfinite_input_sensitivity_needs_actual_evidence(self):
        c = card()
        self.assertTrue(all(q['status'] == 'pass' for q in self.check(c, trace(c))['tiers'].values()))
        c['input_gain_evidence_required'] = 'derivative or input topology is not bounded by voltage maxnorm'
        c['input_gain_evidence'] = {'status': 'verified'}
        result = self.check(c, trace(c))
        self.assertEqual(result['input_gain_evidence']['status'], 'unknown')
        self.assertTrue(all(q['numerical']['status'] == 'unknown' for q in result['tiers'].values()))
        self.assertTrue(all(q['status'] == 'evidence_insufficient' for q in result['tiers'].values()))
        rows = trace(c); rows[-1]['y'] += .1
        result = self.check(c, rows)
        self.assertTrue(all(q['numerical']['status'] == 'unknown' for q in result['tiers'].values()))
        self.assertGreater(result['outputs']['y']['conditional_error_lower_V'], .09)
        c['input_gain_evidence_required'] = {'y': 'derivative requires topology evidence'}
        rows[-1]['z'] += .1
        self.assertTrue(all(q['numerical']['status'] == 'numerical_error'
                            for q in self.check(c, rows)['tiers'].values()))

    def test_unknown_initial_phase_does_not_accuse_transient_right_row(self):
        c = card(); c['phase_obligations'] = {'dc': {'time_s': 0., 'outputs': {'y': 0.}}}
        rows = trace(c); rows[0]['y'] = 0.
        result = self.check(c, rows)
        self.assertTrue(all(q['numerical']['status'] == 'unknown' for q in result['tiers'].values()))
        self.assertEqual(result['outputs']['y']['unqualified_observations'], 1)
        rows[-1]['y'] += .1
        result = self.check(c, rows)
        self.assertTrue(all(q['numerical']['status'] == 'numerical_error' for q in result['tiers'].values()))

    def test_real_derivative_filter_transient_right_is_not_accused_of_dc_error(self):
        import math
        import precision_breadth_composition as composition
        c = next(c for c in composition.cards() if c['group_id'] == 'EC16')
        times = observation_plan(c, load_contract(cards=[c]))['times_s']
        rows = [{'time': t, 'u': t/c['unit_s'], 'd': 1.,
                 'y': 1. - .5*math.exp(-t/(2*c['unit_s']))} for t in times]
        result = assess(c, rows, load_contract(cards=[c]), reference=composition.reference)
        self.assertTrue(all(q['numerical']['status'] == 'unknown' for q in result['tiers'].values()), result)
        # Isolate the phase obligation with independently stipulated input
        # topology in this control; it is not an actual adapter qualification.
        c.pop('input_gain_evidence_required')
        result = assess(c, rows, load_contract(cards=[c]), reference=composition.reference)
        self.assertTrue(all(q['numerical']['status'] == 'unknown' for q in result['tiers'].values()), result)
        self.assertEqual(result['outputs']['y']['unqualified_observations'], 1)
        rows[-1]['y'] += .1
        result = assess(c, rows, load_contract(cards=[c]), reference=composition.reference)
        self.assertTrue(all(q['numerical']['status'] == 'numerical_error' for q in result['tiers'].values()), result)

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


class FoundationStageCalibration(unittest.TestCase):
    """Handwritten trajectories, not rows generated by the graded reference."""
    def setUp(self):
        import precision_breadth_foundation as foundation
        self.foundation = foundation
        self.cards = {c['group_id']: c for c in foundation.cards()}

    def perfect_trace(self, group):
        c = self.cards[group]; unit = 1e-6
        callbacks = ([unit / 4 + 50e-12, unit / 2 + 50e-12] if group == 'F07'
                     else [unit + 50e-12, 3 * unit + 50e-12])
        points = {i * unit / 32 for i in range(round(c['stop_s'] / unit * 32) + 1)}
        for t in c['critical_times_s']:
            points.update((t - 2e-12, t, t + 2e-12))
        for t in callbacks:
            points.update((t - 1e-14, t + 1e-14))
        rows = []
        for t in sorted(t for t in points if 0 <= t <= c['stop_s']):
            n = sum(t >= e for e in callbacks)
            if group == 'F07':
                first, last = [(0., 1.), (1., 12.), (11., 122.)][n]
                rows.append({'time': t, 'u': t / unit, 'first': first, 'last': last,
                             'y': first + last, 'count': float(n)})
            else:
                rise = min(1., max(0., (t - callbacks[0] - unit / 4) / (unit / 2)))
                fall = min(1., max(0., (t - callbacks[1] - unit / 4) / unit))
                rows.append({'time': t, 'y': .5 * (rise - fall),
                             'state': .5 if n == 1 else 0., 'count': float(n)})
        return c, rows

    def test_perfect_array_and_transition_counters_qualify_all_tiers(self):
        for group in ('F07', 'F19'):
            c, rows = self.perfect_trace(group)
            result = assess(c, rows, load_contract(cards=[c]), reference=self.foundation.reference)
            self.assertEqual(result['behavior']['status'], 'pass', (group, result))
            self.assertTrue(all(q['status'] == 'pass' for q in result['tiers'].values()), (group, result))

    def test_missing_event_disables_stage_conditioning(self):
        for group in ('F07', 'F19'):
            c, rows = self.perfect_trace(group)
            for r in rows:
                if r['count'] == 2: r['count'] = 1.
            result = assess(c, rows, load_contract(cards=[c]), reference=self.foundation.reference)
            self.assertEqual(result['behavior']['status'], 'behavior_error')
            self.assertTrue(all(q['status'] == 'behavior_error' for q in result['tiers'].values()))

    def test_card_cannot_forge_verified_stage_to_explain_wrong_state(self):
        for group in ('F07', 'F19'):
            c, rows = self.perfect_trace(group)
            c['reference_counter_stages'] = {'count': 2}
            r = next(row for row in rows if row['count'] == 1)
            r['first' if group == 'F07' else 'state'] = 11. if group == 'F07' else 0.
            result = assess(c, rows, load_contract(cards=[c]), reference=self.foundation.reference)
            self.assertTrue(all(q['numerical']['status'] == 'numerical_error' for q in result['tiers'].values()))


if __name__ == '__main__':
    unittest.main()
