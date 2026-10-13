"""Independent root/window calibration; original checkers remain unchanged."""
import copy
from fractions import Fraction as F
import math
import unittest

from precision_v2 import load_contract
from precision_breadth_composition import cards
from root_windows import reference_roots, timing, reference_card
from precision_reference import outward


class RootWindowCalibration(unittest.TestCase):
    def setUp(self):
        self.shx = next(c for c in load_contract()['cards'] if c['id'] == 'SH-X-RAMP')
        self.ec04 = next(c for c in cards() if c['id'] == 'EC04-v1')

    def test_all_affine_roots_use_actual_endpoints(self):
        roots = reference_roots(self.shx)
        self.assertEqual(len(roots), 8)
        rising = [(a, b) for a, b in zip(self.shx['inputs']['clk'], self.shx['inputs']['clk'][1:])
                  if a[1] < .5 <= b[1]]
        for root, ((a, u), (b, v)) in zip(roots, rising):
            exact = F(a) + (F(.5) - F(u)) * (F(b) - F(a)) / (F(v) - F(u))
            self.assertEqual(root.exact, exact)
            self.assertLessEqual(F(root.bounds[0]), exact)
            self.assertGreaterEqual(F(root.bounds[1]), exact)

    def test_nonlinear_root_contains_sqrt2_by_exact_squares(self):
        root, = reference_roots(self.ec04)
        T = F(self.ec04['unit_s'])
        self.assertLess((F(root.bounds[0]) / T) ** 2, 2)
        self.assertGreater((F(root.bounds[1]) / T) ** 2, 2)
        self.assertLess(root.bounds[0], self.ec04['events'][0]['nominal_s'])

    def test_correct_root_box_passes_resolution_but_not_strict_side(self):
        root, = reference_roots(self.ec04)
        result = timing(root, root.bounds, self.ec04['stop_s'], 16)
        self.assertEqual(result['serialized_resolution_timing'], 'pass')
        self.assertEqual(result['strict_semantic_timing'], 'unresolved')

    def test_outside_both_ends_is_rejected_without_clipping(self):
        for card in (self.shx, self.ec04):
            root = reference_roots(card)[0]
            for box in ([root.bounds[0]-1e-11]*2, [root.bounds[1]+2e-10]*2):
                result = timing(root, box, card['stop_s'], 16)
                self.assertEqual(result['serialized_resolution_timing'], 'behavior_error')
                self.assertEqual(result['callback_bounds_s'], box)

    def test_overlap_does_not_qualify_a_broad_callback(self):
        root, = reference_roots(self.ec04)
        box = [root.bounds[0]-1e-11, root.bounds[1]+2e-10]
        self.assertNotEqual(timing(root, box, self.ec04['stop_s'],16)['serialized_resolution_timing'], 'pass')

    def test_zero_resolution_does_not_claim_exact_no_early(self):
        root, = reference_roots(self.ec04)
        result = timing(root, root.bounds, self.ec04['stop_s'], 0)
        self.assertNotEqual(result['serialized_resolution_timing'], 'pass')

    def test_reference_metadata_change_does_not_change_model_or_inputs(self):
        original = copy.deepcopy(self.ec04)
        new = reference_card(self.ec04, 16)
        for key in ('source','inputs','parameters','outputs','stop_s'):
            self.assertEqual(new[key], original[key])
        self.assertEqual(self.ec04, original)
        root, = reference_roots(self.ec04)
        self.assertLessEqual(new['events'][0]['nominal_s'], root.bounds[0])

    def test_reference_metadata_covers_same_high_under_both_additions(self):
        root, = reference_roots(self.ec04)
        for ulps in (0, 16):
            reserve = F(ulps)*F(math.ulp(self.ec04['stop_s']))
            high = outward(F(root.bounds[1])+root.late+reserve, True)
            event = reference_card(self.ec04, ulps)['events'][0]
            low, width = event['nominal_s'], event['late_s']
            self.assertGreaterEqual(low+width, high)
            self.assertGreaterEqual(F(low)+F(width), F(high))

    def test_float_addition_pass_does_not_prove_exact_sum_coverage(self):
        # Independent negative control: nearest width sums to 1 in binary64,
        # while its exact represented sum is below that same upper endpoint.
        low, high = 1e-10, 1.
        nearest_width = float(F(high)-F(low))
        self.assertEqual(low+nearest_width, high)
        self.assertLess(F(low)+F(nearest_width), F(high))
        width = outward(F(high)-F(low), True)
        self.assertGreaterEqual(low+width, high)
        self.assertGreaterEqual(F(low)+F(width), F(high))

    def test_invalid_contract_and_nonfinite_boxes_are_rejected(self):
        root, = reference_roots(self.ec04)
        for box in ([math.nan, 0.], [0., math.inf], [1.,0.]):
            with self.assertRaises(ValueError):timing(root, box, self.ec04['stop_s'],16)
        bad=copy.deepcopy(self.shx);bad['source']=bad['source'].replace('+1,TT','-1,TT')
        with self.assertRaises(ValueError):reference_roots(bad)
