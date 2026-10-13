"""Independent root/actual-sampling controls for the EC04-v3 wrapper."""
from copy import deepcopy
from fractions import Fraction as F
import hashlib
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/backends/support'))
import precision_breadth as science
from precision_breadth_composition import cards
from precision_composition_root_v3 import reanalyze_evas, reanalyze_spectre
from root_windows import reference_roots
from breadth_callback_trace import instrument


def fixture(box=None):
    card = next(c for c in cards() if c['id'] == 'EC04-v1')
    contract = science.load_contract(cards=[card])
    root = reference_roots(card)[0]
    box = list(root.bounds) if box is None else list(box)
    point = box[1]
    times = set(science.observation_plan(card, contract)['times_s'])
    times.update((point - 2e-12, point, point + 2e-12))
    rows = []
    for t in sorted(times):
        x, c = F(t) / F(card['unit_s']), F(point) / F(card['unit_s'])
        sampled = 2*c + 1
        after = t >= point
        # Separate exact-rational replay of source assignment and held area.
        rows.append(dict(time=t, u=float(x), n=int(after),
                         q=float(sampled if after else F(2)),
                         y=float(5+4*c+sampled*sampled*(x-c) if after else 5+4*x)))
    origin = dict(instance='dut', source='dut.va', line=10, column=1)
    program = dict(schema_version=18, nodes=['0', 'n', 'u'],
                   states=[dict(initial=2., instance='dut'), dict(initial=0., instance='dut')],
                   contributions=[dict(positive=1, negative=0, rhs=dict(op='state', state=1))],
                   events=[dict(origin=origin, trigger=dict(kind='cross', direction=1,
                       expression_tolerance=.0005, guard=dict(op='multiply',
                       left=dict(op='affine', terms=[dict(node=2, coefficient=1.)]),
                       right=dict(op='affine', terms=[dict(node=2, coefficient=1.)]))))])
    record = dict(event=0, origin='dut.va:10:1 (dut)', kind='cross', time=point,
                  observation_time_bounds=box, guard_value=0., before=[2., 0.],
                  after=[float(2*F(point)/F(card['unit_s'])+1), 1.])
    response = dict(schema_version=18, nodes=program['nodes'],
                    observation_evidence=dict(initial_settled=True), transient=dict(events=[record]))
    return card, program, response, rows, contract


class RootCompositionCalibration(unittest.TestCase):
    def run_fixture(self, box=None, mutate=None, trust=True):
        values = fixture(box)
        if mutate:
            mutate(*values)
        return reanalyze_evas(*values, producer_qualified=trust)

    def test_exact_root_box_preserves_original_and_full_history(self):
        values = fixture()
        expected = science.assess(values[0], values[3], values[4])
        result = reanalyze_evas(*values, producer_qualified=True)
        self.assertEqual(result['original_assessment'], expected)
        self.assertEqual(result['serialized_resolution_timing'], 'pass')
        self.assertEqual(result['strict_semantic_timing'], 'unresolved')
        self.assertEqual(result['callback_evidence']['status'], 'qualified')
        self.assertEqual(result['new_assessment']['event_bounds_s'],
                         {'EC04-v1:sample': list(reference_roots(values[0])[0].bounds)})
        self.assertTrue(all(t['status'] == 'pass' for t in result['new_assessment']['tiers'].values()),
                        result['new_assessment'])

    def test_actual_delayed_sample_is_used_in_q_and_future_integral(self):
        c = fixture()[0]; r = reference_roots(c)[0]
        callback = r.bounds[1] + 4e-11
        result = self.run_fixture([callback, callback])
        self.assertEqual(result['strict_semantic_timing'], 'pass')
        self.assertEqual(result['callback_evidence']['status'], 'qualified')
        self.assertEqual(result['new_assessment']['outputs']['q']['defined_observations'], len(fixture([callback]*2)[3]))
        self.assertTrue(all(t['status'] == 'pass' for t in result['new_assessment']['tiers'].values()))

    def test_real_early_and_late_are_behavior_errors(self):
        c = fixture()[0]; r = reference_roots(c)[0]
        for point in (r.bounds[0]-1e-12, r.bounds[1]+float(r.late)+1e-12):
            result = self.run_fixture([point]*2)
            self.assertEqual(result['serialized_resolution_timing'], 'behavior_error')
            self.assertTrue(all(t['status'] == 'behavior_error' for t in result['new_assessment']['tiers'].values()))

    def test_one_ulp_early_is_only_a_finite_resolution_pass(self):
        c = fixture()[0]; r = reference_roots(c)[0]
        point = r.bounds[0]
        result = self.run_fixture([point]*2)
        self.assertEqual(result['serialized_resolution_timing'], 'pass')
        self.assertEqual(result['strict_semantic_timing'], 'behavior_error')
        self.assertTrue(all(t['status'] == 'pass' for t in result['new_assessment']['tiers'].values()))

    def test_ideal_root_output_cannot_replace_actual_delayed_sample(self):
        c = fixture()[0]; r = reference_roots(c)[0]
        point = r.bounds[1]+4e-11
        values = fixture([point]*2)
        ideal = 2*math.sqrt(2)+1
        for row in values[3]:
            if row['time'] >= point:
                row['q'] = ideal
        result = reanalyze_evas(*values, producer_qualified=True)
        self.assertEqual(result['serialized_resolution_timing'], 'pass')
        self.assertEqual(result['new_assessment']['tiers']['Q3']['status'], 'numerical_error')

    def test_observation_gap_and_input_failures_are_preserved(self):
        values = fixture()
        values[3][:] = [values[3][0], values[3][len(values[3])//2], values[3][-1]]
        result = reanalyze_evas(*values, producer_qualified=True)
        self.assertIn('observation gap exceeds frozen limit', result['new_assessment']['observation_issues'])
        self.assertFalse(any(t['status'] == 'pass' for t in result['new_assessment']['tiers'].values()))
        values = fixture()
        values[3][-1]['u'] += .01
        result = reanalyze_evas(*values, producer_qualified=True)
        for tier in result['new_assessment']['tiers'].values():
            self.assertIn('input uncertainty exceeds B/100', tier['evidence']['issues'])
            self.assertNotEqual(tier['status'], 'pass')

    def test_box_crossing_both_window_edges_is_insufficient_never_clipped(self):
        c = fixture()[0]; r = reference_roots(c)[0]
        box = [r.bounds[0]-1e-12, r.bounds[1]+float(r.late)+1e-12]
        result = self.run_fixture(box)
        self.assertEqual(result['serialized_resolution_timing'], 'evidence_insufficient')
        self.assertEqual(result['timing']['EC04-v1:sample']['callback_bounds_s'], box)
        self.assertFalse(any(t['status'] == 'pass' for t in result['new_assessment']['tiers'].values()))

    def test_wide_legal_box_retains_uncertainty_budget_failure(self):
        c = fixture()[0]; r = reference_roots(c)[0]
        box = [r.bounds[1], r.bounds[1]+float(r.late)/2]
        result = self.run_fixture(box)
        self.assertEqual(result['serialized_resolution_timing'], 'pass')
        self.assertEqual(result['new_assessment']['event_bounds_s']['EC04-v1:sample'], box)
        self.assertGreater(result['new_assessment']['outputs']['y']['unresolved_uncertainty_V'], 1e-5)
        self.assertFalse(all(t['status'] == 'pass' for t in result['new_assessment']['tiers'].values()))

    def test_wrong_output_remains_numerical_error(self):
        result = self.run_fixture(mutate=lambda c,p,r,w,k: w[-1].update(y=w[-1]['y']+.1))
        self.assertEqual(result['serialized_resolution_timing'], 'pass')
        self.assertTrue(all(t['status'] == 'numerical_error' for t in result['new_assessment']['tiers'].values()))

    def test_wrong_count_and_unreviewed_producer_cannot_pass(self):
        bad = self.run_fixture(mutate=lambda c,p,r,w,k: w[-1].update(n=2))
        self.assertEqual(bad['callback_evidence']['status'], 'unknown')
        self.assertTrue(all(t['status'] == 'behavior_error' for t in bad['new_assessment']['tiers'].values()))
        untrusted = self.run_fixture(trust=False)
        self.assertFalse(any(t['status'] == 'pass' for t in untrusted['new_assessment']['tiers'].values()))

    def test_canonical_source_card_and_budgets_are_required(self):
        for change in (lambda c,p,r,w,k:c.update(source=c['source']+'\n'),
                       lambda c,p,r,w,k:c.update(input_gain_bound=0),
                       lambda c,p,r,w,k:k['budgets'].update(time_serialization_ulps=32)):
            with self.assertRaises(ValueError):
                self.run_fixture(mutate=change)

    def test_spectre_read_only_trace_and_source_identity(self):
        c,p,r,w,k = fixture()
        point = r['transient']['events'][0]['time']
        source = instrument(c)[0]
        log = f'EVAS_BREADTH_CALLBACK n0 dut 1 {point:.17g}'
        good = reanalyze_spectre(c, source, log, w, k, producer_qualified=True)
        self.assertEqual(good['callback_evidence']['status'], 'qualified')
        self.assertTrue(all(t['status'] == 'pass' for t in good['new_assessment']['tiers'].values()))
        for bad_source, bad_log in ((source+'\n',log),(source,log+'\n'+log),
                                    (source,log.replace(' dut ', ' other '))):
            result = reanalyze_spectre(c,bad_source,bad_log,w,k,producer_qualified=True)
            self.assertEqual(result['callback_evidence']['status'], 'unknown')
            self.assertFalse(any(t['status'] == 'pass' for t in result['new_assessment']['tiers'].values()))

    def test_historical_checker_bytes_and_input_objects_are_unchanged(self):
        paths = [Path(science.__file__), ROOT/'experiments/backends/support/callback_evidence.py',
                 ROOT/'experiments/backends/support/spectre_callback_evidence.py']
        hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        values = fixture(); before = deepcopy(values)
        reanalyze_evas(*values, producer_qualified=True)
        self.assertEqual(values, before)
        self.assertEqual(hashes, [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths])


if __name__ == '__main__':
    unittest.main()
