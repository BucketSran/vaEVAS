"""Reject misleading paired evidence; fixtures do not execute a simulator."""
import copy
import unittest

from performance import paired_summary


class PairIdentityTests(unittest.TestCase):
    def setUp(self):
        self.records = []
        self.manifest = []
        for pair in range(6):
            for side, cost in (("baseline", 10.0), ("reference", 2.0)):
                self.manifest.append(dict(task_id="fixture", condition_id="load",
                    phase="warmup" if pair == 0 else "measurement", pair=pair, side=side,
                    candidate_sha256=side, criteria_sha256="criteria"))
                self.records.append(dict(task_id="fixture", condition_id="load",
                    job_id=f"{pair}-{side}", candidate_bundle_sha256=side,
                    source_sha256=side, criteria_sha256="criteria", netlist_sha256="netlist",
                    native_host_identity_sha256="host", solver_argv=["spectre", "+mt=1"],
                    solver_process_elapsed_s=cost + 1,
                    native_statistics=dict(spectre_version="fixture", accepted_steps=int(cost * 100),
                        intrinsic_tran=dict(cpu_s=cost, elapsed_s=cost / 2))))

    def test_valid_sequence_reports_all_five_pairs(self):
        result = paired_summary(self.records, self.manifest)["fixture"]
        self.assertEqual(result["measurements"], 10)
        self.assertEqual(result["metrics"]["intrinsic_cpu_s"]["paired_baseline_over_reference"], [5.0] * 5)

    def test_non_alternating_or_missing_warmup_is_rejected(self):
        for indexes in (list(range(2, 12)), [1, 0] + list(range(2, 12))):
            with self.assertRaises(ValueError):
                paired_summary([self.records[i] for i in indexes], [self.manifest[i] for i in indexes])

    def test_duplicate_job_and_changed_experiment_are_rejected(self):
        for key in ("job_id", "native_host_identity_sha256", "criteria_sha256",
                    "source_sha256", "solver_argv", "candidate_bundle_sha256"):
            with self.subTest(key=key):
                records = copy.deepcopy(self.records)
                records[-1][key] = records[0][key] if key == "job_id" else ["other"] if key == "solver_argv" else "other"
                with self.assertRaises(ValueError):
                    paired_summary(records, self.manifest)


if __name__ == "__main__":
    unittest.main()
