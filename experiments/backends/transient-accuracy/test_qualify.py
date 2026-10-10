import copy
import math
import unittest

from check import dynamic_reference
from qualify import qualify_dynamic, compare_native


class ReferenceQualification(unittest.TestCase):
    def rows(self, event=False):
        return [dict(time=t, **dynamic_reference(t, event))
                for t in [0., .125, .25, .5-1e-10, .5, .5+1e-10, .5+1e-8, .75, 1.]]

    def test_independent_anchors_and_correct_event(self):
        for event in (False, True):
            report = qualify_dynamic(self.rows(event), event)
            self.assertTrue(report['qualified_finite_observations'])
            self.assertTrue(report['legacy']['pass'])
        # Hand-derived values: z(.25)=4/5 and z(1) after rate change=2/5.
        self.assertEqual(self.rows()[2]['z'], .8)
        self.assertEqual(self.rows(True)[-1]['z'], .4)

    def test_native_ulp_offset_keeps_old_failure_and_original_data(self):
        rows = self.rows()
        rows[1]['time'] = math.nextafter(.125, 1.)
        before = copy.deepcopy(rows)
        report = qualify_dynamic(rows)
        self.assertTrue(report['qualified_finite_observations'])
        self.assertFalse(report['legacy']['pass'])
        self.assertEqual(report['legacy']['failures'][0]['kind'], 'missing_anchor')
        self.assertEqual(rows, before)
        anchor = report['anchors'][1]
        self.assertFalse(anchor['exact_time'])
        self.assertGreater(anchor['voltage_time_shift_V']['amp'], 0.)

    def test_absent_or_far_anchor_rejected(self):
        for time in (None, .125+2e-12):
            rows = self.rows()
            if time is None:
                del rows[1]
            else:
                rows[1]['time'] = time
            self.assertFalse(qualify_dynamic(rows)['qualified_finite_observations'])

    def test_event_and_endpoints_require_exact_time(self):
        for index in (0, 4, -1):
            rows = self.rows(True)
            rows[index]['time'] = math.nextafter(rows[index]['time'], 0.25)
            self.assertFalse(qualify_dynamic(rows, True)['qualified_finite_observations'])

    def test_time_shift_cannot_spend_extra_voltage_budget(self):
        rows = self.rows()
        # Native voltage itself meets 1 mV, but transferring it to the requested
        # anchor would exceed that budget; the triangle bound must reject it.
        t = .125+5e-13
        rows[1] = dict(time=t, **dynamic_reference(t))
        rows[1]['amp'] += .001-1e-9
        report = qualify_dynamic(rows)
        self.assertTrue(report['native_math_pass'])
        self.assertFalse(report['continuous_anchor_contract_pass'])
        self.assertFalse(report['qualified_finite_observations'])

    def test_voltage_and_event_failures_never_waived(self):
        rows = self.rows(); rows[-1]['amp'] = .002
        self.assertFalse(qualify_dynamic(rows)['qualified_finite_observations'])
        rows = self.rows(True); rows[-1]['count'] = 2
        self.assertFalse(qualify_dynamic(rows, True)['qualified_finite_observations'])
        self.assertFalse(qualify_dynamic(self.rows(True), True, [{'time': .500001}])['qualified_finite_observations'])

    def test_invalid_duplicate_and_reordered_data(self):
        for change in ('nan', 'duplicate', 'reverse'):
            rows = self.rows()
            if change == 'nan': rows[1]['z'] = float('nan')
            if change == 'duplicate': rows.insert(2, copy.deepcopy(rows[1]))
            if change == 'reverse': rows.reverse()
            self.assertFalse(qualify_dynamic(rows)['qualified_finite_observations'])

    def test_request_budget_remains_separate(self):
        rows = self.rows(); rows[-1]['amp'] = .0005
        report = qualify_dynamic(rows, tolerances={'absolute': 1e-8, 'relative': 1e-5})
        self.assertTrue(report['native_math_pass'])
        self.assertFalse(report['request_budget_pass'])
        self.assertFalse(report['qualified_finite_observations'])

    def test_pairing_requires_same_actual_times_and_budget(self):
        rows = self.rows()
        self.assertTrue(compare_native(rows, rows)['pass'])
        for kind in ('time', 'voltage', 'missing'):
            changed = copy.deepcopy(rows)
            if kind == 'time': changed[1]['time'] = math.nextafter(.125, 1.)
            if kind == 'voltage': changed[-1]['amp'] = .002
            if kind == 'missing': changed.pop()
            self.assertFalse(compare_native(rows, changed)['pass'])
