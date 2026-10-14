"""Evidence-only observation helper: handwritten PWL oracles and Astra corruptions.

The helper (evas/validation/observation_evidence.py) is validation-side
tooling: it validates and preserves archived observation evidence and never
produces a behavioral pass verdict.  Expected provenance below is derived by
hand from one analytic PWL (``vin: 0->1->0->1`` over [0, 3] on a save grid
that misses the interior knots), independent of any kernel.  The corruption
cases replay the independent N04 review's mutations (NaN at a hit query,
missing row, missing required column, duplicate node/time, reversed rows or
events, non-finite and bool values, out-of-range queries) and must each land
in ``invalid``/``incomplete`` -- never in a numeric summary or a pass field.
"""
# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["QUALIFICATION", "DEV:observation-evidence"]

import copy
import importlib.util
import json
import math
import pathlib
import unittest
from fractions import Fraction as Q

_spec = importlib.util.spec_from_file_location(
    "observation_evidence",
    pathlib.Path(__file__).resolve().parents[1] / "validation/observation_evidence.py")
oe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oe)

# Handwritten analytic fixture.  Declared PWL rises 0->1 on [0,1], falls to 0
# at 2 and rises to 1 at 3.  The save grid deliberately misses knots 1 and 2.
DECLARED = [[0.0, 0.0], [1.0, 1.0], [2.0, 0.0], [3.0, 1.0]]
GRID = [0.0, 0.5, 1.5, 2.5, 3.0]
VIN = [0.0, 0.5, 0.5, 0.5, 1.0]
VOUT = [2.0 * v for v in VIN]
EVENTS = [
    {'time': 1.0, 'observation_time_bounds': [1.0, 1.0], 'event': 0,
     'origin': 'test.va:5:9 (X)', 'kind': 'cross', 'guard_value': 0.0,
     'before': [0.0], 'after': [1.0]},
    {'time': 1.0, 'event': 1, 'origin': 'test.va:6:9 (X)', 'kind': 'or',
     'fired_triggers': [{'trigger': 0, 'kind': 'cross', 'guard_value': 1e-14,
                         'time_bounds': [0.9999999999999999, 1.0]}],
     'before': [1.0], 'after': [2.0]},
    {'time': 2.5, 'observation_time_bounds': [2.4999999999999995, 2.5], 'event': 2,
     'origin': 'test.va:7:9 (X)', 'kind': 'cross', 'guard_value': -3e-14,
     'before': [2.0], 'after': [3.0]},
]
DISPLAYS = [{'time': 1.0, 'event': 1, 'origin': 'test.va:6:9 (X)',
             'text': 'sampled q=2.000000'}]


def fixture_response():
    nodes = ['vin', 'vout']
    solutions = [{'voltages': [VIN[i], VOUT[i]], 'max_residual_v': 0.0,
                  'max_residual_ratio': 0.0} for i in range(5)]
    evidence = {
        'schema_version': 1, 'nodes': nodes,
        'effective_controls': {'absolute_V': 1e-9, 'relative': 1e-6,
                               'stop_s': 3.0, 'max_step_s': 0.5,
                               'max_step_applied': True},
        'sample_origins': ['accepted_controller_frame'] * 5,
        'initial_settled': True,
        'voltage_bounds_V': [[[v - 1e-12, v + 1e-12] for v in row] for row in
                             zip(VIN, VOUT)]}
    return {
        'schema_version': 21, 'engine': 'fixture-engine', 'nodes': nodes,
        'solutions': solutions,
        'saved': {'nodes': nodes, 'times': list(GRID),
                  'values': [[a, b] for a, b in zip(VIN, VOUT)]},
        'observation_evidence': evidence,
        'transient': {'times': list(GRID), 'state_names': ['X:q'],
                      'states': [[float(i)] for i in range(5)],
                      'events': copy.deepcopy(EVENTS),
                      'display_records': copy.deepcopy(DISPLAYS),
                      'accepted_steps': 7, 'discarded_trials': 0}}


def build(response=None, **kwargs):
    arguments = {'identity': [{'side': 'candidate', 'role': 'response',
                               'path': 'fixture/stdout.json',
                               'sha256': '0' * 64}],
                 'declared_sources': {'vin': DECLARED},
                 'query_plan': [{'time': t, 'origin': 'handwritten uniform'}
                                for t in (0.0, 1.0, 2.0, 3.0, 3.5)],
                 'query_meaning': {'time_unit': 's'},
                 'required_nodes': ['vin']}
    arguments.update(kwargs)
    return oe.build_evidence_report(response or fixture_response(), **arguments)


def kinds(report):
    return {issue['kind'] for issue in report['issues']}


class HandwrittenPWLProvenance(unittest.TestCase):
    def test_native_saved_query_keeps_row_index_origin_and_bounds(self):
        report = build()
        first = report['query_provenance']['per_query'][0]['candidate']['vin']
        self.assertEqual(first['status'], 'native_saved')
        self.assertEqual(first['row_index'], 0)
        self.assertEqual(first['sample_origin'], 'accepted_controller_frame')
        self.assertEqual(first['voltage_bounds_V'], [VIN[0] - 1e-12, VIN[0] + 1e-12])
        last = report['query_provenance']['per_query'][3]['candidate']['vin']
        self.assertEqual(last['status'], 'native_saved')
        self.assertEqual(last['row_index'], 4)

    def test_saved_evidence_requires_same_time_and_representative(self):
        for change in ('time', 'value'):
            response = fixture_response()
            if change == 'time':
                response['saved']['times'][1] = .25
            else:
                response['saved']['values'][0][0] = 100.
            report = build(response, query_plan=[0., .25])
            self.assertEqual(report['evidence_validity']['observation_evidence'], 'invalid')
            first = report['query_provenance']['per_query'][0]['candidate']['vin']
            self.assertEqual(first['voltage_bounds_V'], 'missing')

    def test_subset_saved_grid_maps_to_correct_solution_rows(self):
        response = fixture_response()
        response['saved']['times'] = [GRID[0], GRID[3]]
        response['saved']['values'] = [[VIN[i], VOUT[i]] for i in (0, 3)]
        response['observation_evidence']['sample_origins'][3] = 'certified_causal_frame'
        report = build(response, query_plan=[GRID[3]])
        result = report['query_provenance']['per_query'][0]['candidate']['vin']
        self.assertEqual(result['sample_origin'], 'certified_causal_frame')
        self.assertEqual(result['row_index'], 1)

    def test_metadata_cannot_overwrite_computed_provenance(self):
        metadata = {'time': 1., 'time_s': 999., 'candidate': {'vin': 42}}
        report = build(query_plan=[metadata])
        result = report['query_provenance']['per_query'][0]
        self.assertEqual(result['time_s'], 1.)
        self.assertEqual(result['candidate']['vin']['status'], 'interpolated')
        self.assertEqual(result['metadata']['candidate'], {'vin': 42})

    def test_missing_query_node_stays_in_denominator(self):
        report = build(query_nodes=['absent'], query_plan=[1.], require_full_coverage=True)
        self.assertEqual(report['evidence_validity']['query_plan'], 'incomplete')
        self.assertEqual(report['query_provenance']['per_query'][0]['candidate']['absent']['status'], 'missing')

    def test_invalid_query_is_not_downgraded_by_later_missing_query(self):
        report = build(query_plan=[float('nan'), 4.], require_full_coverage=True)
        self.assertEqual(report['evidence_validity']['query_plan'], 'invalid')
        json.dumps(report, allow_nan=False)

    def test_malformed_output_and_bound_shapes_are_invalid_without_exception(self):
        mutations = [
            lambda r: r['solutions'].__setitem__(0, None),
            lambda r: r['solutions'][0].__setitem__('voltages', []),
            lambda r: r['transient']['times'].__setitem__(1, float('nan')),
            lambda r: r['observation_evidence']['voltage_bounds_V'][0].__setitem__(0, None),
            lambda r: r['observation_evidence']['voltage_bounds_V'].append([[0., 1.], [0., 1.]]),
            lambda r: r['saved'].__setitem__('nodes', None),
            lambda r: r['saved']['values'][0].__setitem__(0, 10**400),
            lambda r: r['transient']['events'][0].__setitem__('observation_time_bounds', None),
            lambda r: r['transient']['events'][1]['fired_triggers'][0].__setitem__('time_bounds', None),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                response = fixture_response()
                mutate(response)
                report = build(response, query_nodes=['vin'])
                self.assertEqual(report['status'], 'invalid')
                self.assertEqual(report['source_deviations'], {})
                json.dumps(report, allow_nan=False)

    def test_malformed_pwl_and_missing_query_time_are_invalid(self):
        for points in ([], [[0, 0], [0, 1]], [[1, 0], [0, 1]], [[0, float('nan')]]):
            report = build(declared_sources={'vin': points})
            self.assertEqual(report['status'], 'invalid')
            json.dumps(report, allow_nan=False)
        self.assertEqual(build(query_plan=[{'origin': 'missing time'}])['status'], 'invalid')

    def test_opposite_large_finite_endpoints_interpolate_without_overflow(self):
        waveform = oe.SavedWaveform({'nodes': ['x'], 'times': [0., 1.],
                                     'values': [[-1e308], [1e308]]}, side='reference')
        result = waveform.classify(.5, 'x')
        self.assertEqual(result['value_v'], 0.)
        json.dumps(result, allow_nan=False)

    def test_invalid_reference_is_checked_without_queries(self):
        waveform = oe.SavedWaveform({'nodes': ['x'], 'times': [0., 0.],
                                     'values': [[0.], [0.]]}, side='reference')
        self.assertEqual(build(query_plan=[], reference_saved=waveform)['status'], 'invalid')

    def test_present_invalid_evidence_and_state_identity_are_not_absence(self):
        for malformed in (None, [], 0, 'bad'):
            response = fixture_response()
            response['observation_evidence'] = malformed
            self.assertEqual(build(response)['evidence_validity']['observation_evidence'], 'invalid')
        for names in ([None], ['x', 'x'], None):
            response = fixture_response()
            response['transient']['state_names'] = names
            self.assertEqual(build(response)['evidence_validity']['callback_events'], 'invalid')

    def test_duplicate_query_columns_are_invalid(self):
        report = build(query_nodes=['vin', 'vin'])
        self.assertEqual(report['evidence_validity']['query_plan'], 'invalid')
        self.assertIn('invalid_query_nodes', kinds(report))

    def test_cross_knot_interpolation_records_rows_endpoints_and_knots(self):
        report = build()
        middle = report['query_provenance']['per_query'][1]['candidate']['vin']
        self.assertEqual(middle['status'], 'interpolated')
        self.assertEqual(middle['row_indices'], [1, 2])
        self.assertEqual(middle['endpoint_times_s'], [0.5, 1.5])
        self.assertEqual(middle['straddled_declared_knots_s'], [1.0])
        self.assertEqual(middle['method'], 'linear_interpolation_of_saved_rows')
        self.assertEqual(middle['value_v'], 0.5)
        knot_two = report['query_provenance']['per_query'][2]['candidate']['vin']
        self.assertEqual(knot_two['straddled_declared_knots_s'], [2.0])

    def test_out_of_range_query_is_unavailable_not_extrapolated(self):
        report = build()
        beyond = report['query_provenance']['per_query'][4]['candidate']['vin']
        self.assertEqual(beyond['status'], 'unavailable')
        self.assertEqual(beyond['reason'], 'after_last_saved_row')
        self.assertEqual(beyond['last_time_s'], 3.0)
        self.assertNotIn('value_v', beyond)
        self.assertEqual(report['status'], 'valid')  # absence reported, not judged

    def test_required_coverage_contract_flags_out_of_range_queries(self):
        report = build(require_full_coverage=True)
        self.assertEqual(report['evidence_validity']['query_plan'], 'incomplete')
        self.assertIn('query_outside_saved_range', kinds(report))

    def test_interpolation_diagnostic_reports_declared_deviation_only(self):
        report = build()
        diagnostics = report['interpolation_diagnostics']['per_query'][1]['vin']
        self.assertEqual(diagnostics['resampled_v'], 0.5)
        self.assertEqual(Q(diagnostics['declared_exact_rational']), Q(1))
        self.assertEqual(diagnostics['abs_resampling_deviation_v'], 0.5)
        self.assertIn('never an integration error',
                      report['interpolation_diagnostics']['note'])
        self.assertNotIn('passed', json.dumps(diagnostics))

    def test_saved_vs_declared_deviation_has_no_tolerance_or_pass(self):
        report = build()
        deviation = report['source_deviations']['vin']
        self.assertEqual(deviation['max_abs_deviation_v']['abs_deviation_v'], 0.0)
        self.assertNotIn('tolerance_v', deviation)
        self.assertNotIn('tolerance_v', deviation['max_abs_deviation_v'])
        self.assertNotIn('passed', json.dumps(deviation))

    def test_declared_coverage_lists_missing_knots_without_repairing_them(self):
        report = build()
        coverage = report['coverage']['vin']
        self.assertEqual(coverage['knots_missing_from_save_grid'], [1.0, 2.0])
        self.assertEqual(coverage['knots_preserved_in_save_grid'], [0.0, 3.0])

    def test_reference_side_is_classified_independently_and_stays_unqualified(self):
        reference = oe.SavedWaveform(
            {'nodes': ['vin'], 'times': [0.0, 1.0, 2.0, 3.0],
             'values': [[0.0], [1.0], [0.0], [1.0]]}, side='reference')
        report = build(reference_saved=reference,
                       reference_identity={'role': 'archived reference trace'})
        queries = report['query_provenance']['per_query']
        self.assertEqual(queries[1]['candidate']['vin']['status'], 'interpolated')
        self.assertEqual(queries[1]['reference']['vin']['status'], 'native_saved')
        self.assertEqual(queries[4]['reference']['vin']['status'], 'unavailable')
        self.assertEqual(report['reference_side']['qualification']['native_query_precision'],
                         'unqualified')


class DeclaredSourceMathematics(unittest.TestCase):
    def test_point_evaluation_is_exact_rational_from_the_declaration(self):
        self.assertEqual(oe.declared_point(DECLARED, 1.0), Q(1))
        self.assertEqual(oe.declared_point(DECLARED, 0.25), Q(1, 4))
        self.assertEqual(oe.declared_point(DECLARED, 1.75), Q(1, 4))
        self.assertEqual(oe.declared_point(DECLARED, -0.5), Q(0))
        self.assertEqual(oe.declared_point(DECLARED, 9.0), Q(1))

    def test_interval_range_is_reported_but_stays_unqualified(self):
        # Over [0.5, 2.5] the PWL reaches 1 V at the interior knot 1.0 and
        # 0 V at the interior knot 2.0; endpoints sit at 0.5 V.
        interval = oe.declared_interval(DECLARED, 0.5, 2.5)
        self.assertEqual(interval['qualification'], 'unqualified')
        self.assertEqual(Q(interval['exact_low_rational']), Q(0))
        self.assertEqual(Q(interval['exact_high_rational']), Q(1))
        self.assertEqual(interval['low_v'], 0.0)
        self.assertEqual(interval['high_v'], 1.0)
        self.assertIn('not a certificate', interval['note'])


class AstraCorruptions(unittest.TestCase):
    def corrupt(self, change, **kwargs):
        response = fixture_response()
        change(response)
        return build(response, **kwargs)

    def test_nan_at_hit_query_is_invalid_and_withholds_numeric_summaries(self):
        def change(response):
            response['saved']['values'][2][0] = math.nan  # row hit by query 1.0/2.0 brackets
        report = self.corrupt(change)
        self.assertEqual(report['evidence_validity']['candidate_saved_waveform'], 'invalid')
        self.assertIn('invalid_row', kinds(report))
        self.assertEqual(report['source_deviations'], {})
        self.assertEqual(report['interpolation_diagnostics']['per_query'], [])
        self.assertTrue(all(p['status'] == 'missing'
                            for q in report['query_provenance']['per_query']
                            for p in q['candidate'].values()))

    def test_infinite_value_is_invalid(self):
        def change(response):
            response['saved']['values'][0][1] = math.inf
        report = self.corrupt(change)
        self.assertEqual(report['evidence_validity']['candidate_saved_waveform'], 'invalid')

    def test_bool_value_is_invalid(self):
        def change(response):
            response['saved']['values'][0][1] = True
        report = self.corrupt(change)
        self.assertEqual(report['evidence_validity']['candidate_saved_waveform'], 'invalid')
        self.assertIn('invalid_row', kinds(report))

    def test_missing_last_row_is_invalid_shape_not_silent_coverage_loss(self):
        def change(response):
            response['saved']['values'].pop()
        report = self.corrupt(change)
        self.assertEqual(report['evidence_validity']['candidate_saved_waveform'], 'invalid')
        self.assertIn('row_count_mismatch', kinds(report))

    def test_missing_required_column_is_incomplete_and_does_not_shrink_queries(self):
        def change(response):
            index = response['saved']['nodes'].index('vin')
            del response['saved']['nodes'][index]
            for row in response['saved']['values']:
                del row[index]
        report = self.corrupt(change)
        self.assertEqual(report['evidence_validity']['candidate_saved_waveform'], 'incomplete')
        self.assertIn('missing_required_nodes', kinds(report))
        self.assertEqual(report['coverage'], {})  # no claimed coverage without the node

    def test_duplicate_time_is_invalid(self):
        def change(response):
            response['saved']['times'][2] = response['saved']['times'][1]
        report = self.corrupt(change)
        self.assertIn('duplicate_time', kinds(report))
        self.assertEqual(report['evidence_validity']['candidate_saved_waveform'], 'invalid')

    def test_duplicate_node_is_invalid(self):
        def change(response):
            response['saved']['nodes'][1] = response['saved']['nodes'][0]
        report = self.corrupt(change)
        self.assertIn('duplicate_node', kinds(report))

    def test_reversed_rows_fail_monotonic_time_validation(self):
        def change(response):
            response['saved']['times'].reverse()
            response['saved']['values'].reverse()
        report = self.corrupt(change)
        self.assertIn('non_monotonic_times', kinds(report))
        self.assertEqual(report['evidence_validity']['candidate_saved_waveform'], 'invalid')

    def test_reversed_event_chronology_is_invalid(self):
        def change(response):
            response['transient']['events'].reverse()
        report = self.corrupt(change)
        self.assertEqual(report['evidence_validity']['callback_events'], 'invalid')
        self.assertIn('event_chronology', kinds(report))

    def test_nan_event_time_is_invalid(self):
        def change(response):
            response['transient']['events'][0]['time'] = math.nan
        report = self.corrupt(change)
        self.assertEqual(report['evidence_validity']['callback_events'], 'invalid')
        self.assertIn('invalid_event_time', kinds(report))

    def test_bool_control_flag_is_invalid(self):
        def change(response):
            response['observation_evidence']['effective_controls']['max_step_applied'] = 1
        report = self.corrupt(change)
        self.assertEqual(report['evidence_validity']['observation_evidence'], 'invalid')
        self.assertEqual(report['controls']['effective_controls'], {'state': 'missing'})

    def test_expected_row_count_mismatch_is_incomplete(self):
        report = build(expected_row_count=6)
        self.assertEqual(report['evidence_validity']['candidate_saved_waveform'], 'incomplete')
        self.assertIn('unexpected_row_count', kinds(report))


class CallbackAndDisplayPreservation(unittest.TestCase):
    def test_events_and_or_leaf_bounds_roundtrip_verbatim_in_order(self):
        report = build()
        payload = report['callbacks']['events']
        self.assertEqual(payload['count'], 3)
        self.assertEqual([r['verbatim'] for r in payload['records']], EVENTS)
        self.assertEqual(report['evidence_validity']['callback_events'], 'valid')

    def test_exact_point_and_nonpoint_intervals_are_both_legal(self):
        # Event 0 carries [1.0, 1.0]; event 2 carries a widened interval.
        report = build()
        self.assertEqual(report['evidence_validity']['callback_events'], 'valid')
        self.assertNotIn('invalid_time_bounds', kinds(report))

    def test_crossed_interval_bounds_are_invalid(self):
        def crossed(low):
            def change(response):
                response['transient']['events'][2]['observation_time_bounds'] = low
            return change
        for low in ([2.5, 2.4999999999999995], [math.inf, 2.5], [2.5]):
            report = build(_response_with(crossed(low)))
            self.assertEqual(report['evidence_validity']['callback_events'], 'invalid')
            self.assertIn('invalid_time_bounds', kinds(report))

    def test_crossed_voltage_bounds_are_invalid(self):
        def change(response):
            response['observation_evidence']['voltage_bounds_V'][0][0] = [1.0, -1.0]
        response = fixture_response()
        change(response)
        report = build(response)
        self.assertEqual(report['evidence_validity']['observation_evidence'], 'invalid')

    def test_same_time_events_are_legal_and_keep_order(self):
        response = fixture_response()
        response['transient']['events'] = copy.deepcopy(EVENTS[:2])
        report = build(response)
        self.assertEqual(report['evidence_validity']['callback_events'], 'valid')
        times = [r['verbatim']['time'] for r in report['callbacks']['events']['records']]
        self.assertEqual(times, [1.0, 1.0])

    def test_displays_roundtrip_verbatim(self):
        report = build()
        self.assertEqual(report['evidence_validity']['display_records'], 'valid')
        self.assertEqual([r['verbatim'] for r in report['callbacks']['display_records']['records']],
                         DISPLAYS)

    def test_unbound_display_record_is_incomplete_not_silently_dropped(self):
        def change(response):
            response['transient']['display_records'].append(
                {'time': 0.5, 'event': 2, 'origin': 'test.va:7:9 (X)', 'text': 'ghost'})
        response = fixture_response()
        change(response)
        report = build(response)
        self.assertEqual(report['evidence_validity']['display_records'], 'incomplete')
        self.assertIn('unbound_display_record', kinds(report))
        self.assertEqual(report['callbacks']['display_records']['count'], 2)

    def test_missing_display_records_stay_missing(self):
        response = fixture_response()
        response['transient'].pop('display_records')
        report = build(response)
        self.assertEqual(report['evidence_validity']['display_records'], 'missing')
        self.assertEqual(report['callbacks']['display_records']['records'], 'missing')


class ControlsAndVerdicts(unittest.TestCase):
    def test_effective_controls_preserved_and_requested_missing_stays_missing(self):
        report = build()
        self.assertEqual(report['controls']['effective_controls'],
                         {'absolute_V': 1e-9, 'relative': 1e-6, 'stop_s': 3.0,
                          'max_step_s': 0.5, 'max_step_applied': True})
        self.assertEqual(report['controls']['requested_controls']['state'], 'missing')
        self.assertIn('not inferred', report['controls']['requested_controls']['note'])

    def test_supplied_requested_controls_are_kept_separate(self):
        report = build(requested_controls={'stop_s': 3.0, 'source': 'task request'})
        self.assertEqual(report['controls']['requested_controls']['stop_s'], 3.0)

    def test_report_produces_no_pass_verdict_of_any_kind(self):
        report = build()
        text = json.dumps(report)

        def keys(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    yield key
                    yield from keys(value)
            elif isinstance(obj, list):
                for item in obj:
                    yield from keys(item)
        self.assertFalse([k for k in keys(report) if 'pass' in k.lower()])
        for token in ('accepted_output', 'native_query_pass', 'integration_pass',
                      'certified_native'):
            self.assertNotIn(token, text)
        self.assertEqual(report['verdicts']['produced'], 'none')

    def test_observation_evidence_absence_is_missing_not_failure(self):
        response = fixture_response()
        response.pop('observation_evidence')
        report = build(response)
        self.assertEqual(report['evidence_validity']['observation_evidence'], 'missing')
        first = report['query_provenance']['per_query'][0]['candidate']['vin']
        self.assertEqual(first['sample_origin'], 'missing')
        self.assertEqual(first['voltage_bounds_V'], 'missing')

    def test_identity_records_engine_verbatim_without_capability_inference(self):
        report = build()
        self.assertEqual(report['identity']['engine_recorded_verbatim'], 'fixture-engine')
        self.assertIn('never used to infer', report['identity']['note'])

    def test_worst_status_orders_structural_failure_above_absence(self):
        self.assertEqual(oe.worst_status(['valid', 'missing']), 'missing')
        self.assertEqual(oe.worst_status(['missing', 'incomplete']), 'incomplete')
        self.assertEqual(oe.worst_status(['incomplete', 'invalid', 'unqualified']), 'invalid')
        self.assertEqual(oe.worst_status(['valid', 'unqualified']), 'unqualified')


def _response_with(change):
    response = fixture_response()
    change(response)
    return response


if __name__ == '__main__':
    unittest.main()
