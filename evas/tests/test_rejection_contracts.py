"""Transport failure must never satisfy a numerical refusal regression."""

GUARDS = ["DYNAMICS"]

import subprocess
import unittest
from unittest.mock import patch

import test_dynamic_closure
import test_implicit_dynamics


class RejectionContracts(unittest.TestCase):
    def test_negative_dynamics_cases_fail_when_the_kernel_times_out(self):
        cases = [
            (test_implicit_dynamics.ImplicitDynamicsContracts,
             "test_singular_algebraic_jacobian_cannot_silently_switch_branches"),
            (test_dynamic_closure.NonlinearIntegralContracts,
             "test_finite_time_blowup_is_not_reported_as_valid_waveform"),
        ]
        for case_type, name in cases:
            with self.subTest(case=name):
                result = unittest.TestResult()
                with patch("evas.runtime.subprocess.run", side_effect=
                           subprocess.TimeoutExpired("evas-kernel", 300)):
                    case_type(name).run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.wasSuccessful(),
                                 "kernel timeout was accepted as numerical refusal")
