"""Calibration of the two independent validation verdicts."""
import copy
import unittest
from reference_verdicts import Verdict as V, LayeredVerdict, assess_layers


def response():
    return {'nodes':['y'],'solutions':[{'voltages':[1.]}],
            'observation_evidence':{'nodes':['y'],'voltage_bounds_V':[[[1.,1.]]]}}


class ReferenceVerdictCalibration(unittest.TestCase):
    def test_each_reference_can_fail_independently(self):
        self.assertEqual(assess_layers(response(),physical_expected=1,root_expected=2,budget=1e-8),
                         LayeredVerdict(V.PASS,V.FAIL))
        self.assertEqual(assess_layers(response(),physical_expected=2,root_expected=1,budget=1e-8),
                         LayeredVerdict(V.FAIL,V.PASS))

    def test_unknown_and_rejection_never_grant_a_root_certificate(self):
        self.assertEqual(assess_layers(response(),physical_expected=1,root_expected=None,budget=1e-8),
                         LayeredVerdict(V.PASS,V.UNKNOWN))
        self.assertEqual(assess_layers(None,physical_expected=1,root_expected=1,budget=1e-8),
                         LayeredVerdict(V.REJECTED,V.UNKNOWN))

    def test_physical_answer_needs_the_full_published_enclosure(self):
        for bounds in [[0.,2.],[2.,2.]]:
            with self.subTest(bounds=bounds):
                altered=copy.deepcopy(response())
                altered['observation_evidence']['voltage_bounds_V']=[[[*bounds]]]
                self.assertEqual(assess_layers(altered,physical_expected=1,root_expected=1,budget=1e-8),
                                 LayeredVerdict(V.FAIL,V.PASS))
