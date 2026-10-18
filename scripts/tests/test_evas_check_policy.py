"""Exercise the checkout-owned developer policy through its command interface."""

import json
import runpy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "scripts/evas_check_policy.py"


class PolicyCommands(unittest.TestCase):
    def test_representation_and_budget_require_early_evidence_without_new_protocol(self):
        for path, obligation in (
                ('evas/src/evas/compact_source_select.py', 'representation-compatibility'),
                ('evas/src/evas/event_index_domains.py', 'proof-budget'),
                ('evas/rust_core/src/initial_state_invariance.rs', 'proof-budget')):
            with self.subTest(path=path):
                plan = self.request(operation='plan', paths=[path], stage='iteration')
                self.assertNotIn('python-regression', plan['checks'])
                item = next(p for p in plan['pending_acceptance'] if p['id'] == obligation)
                self.assertEqual(item['before'], 'dependent-integration')
                self.assertIn('--early-checks', item['command'])
                self.assertFalse(plan['acceptance_complete'])
                self.assertEqual([x['check'] for x in plan['check_selection']['delivery']],
                                 ['python-regression'])

    def request(self, **request):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(json.dumps({"protocol_version": 1, **request}))
            process = subprocess.run(
                [sys.executable, "-I", "-B", str(POLICY), "--request", str(path)],
                text=True,
                capture_output=True,
            )
        self.assertEqual(process.returncode, 0, process.stderr)
        response = json.loads(process.stdout)
        self.assertEqual(response["protocol_version"], 1)
        return response["result"]

    def test_sparse_plan_preserves_stage_coverage_and_external_obligations(self):
        plan = self.request(
            operation="plan",
            paths=["evas/rust_core/src/linear/sparse.rs"],
            stage="iteration",
        )
        self.assertEqual(
            plan["checks"], ["python:test_affine.py", "python:test_sparse.py"]
        )
        self.assertEqual(
            [c["check"] for c in plan["check_selection"]["delivery"]],
            [
                "python:test_affine.py",
                "python:test_reuse.py",
                "python:test_accuracy.py",
                "python:test_sparse.py",
                "python:test_sparse_transient.py",
            ],
        )
        pending = {item["id"] for item in plan["pending_acceptance"]}
        self.assertTrue(
            {
                "rust-tests",
                "original-request",
                "spectre-alignment",
                "affected-consumers",
                "ci:regression",
            }
            <= pending
        )
        self.assertFalse(plan["acceptance_complete"])

    def test_shared_and_mixed_build_changes_keep_full_coverage(self):
        for paths in (
            ["evas/src/evas/ir.py"],
            ["evas/rust_core/src/new_shared.rs"],
            ["evas/pyproject.toml", "evas/src/evas/parameters.py"],
        ):
            with self.subTest(paths=paths):
                plan = self.request(operation="plan", paths=paths, stage="delivery")
                self.assertEqual(plan["checks"], ["python-regression"])
                reasons = plan["check_selection"]["delivery"][0]["reasons"]
                self.assertTrue(any(r["path"] == paths[0] for r in reasons))
                self.assertIn(
                    "spectre-alignment", {p["id"] for p in plan["pending_acceptance"]}
                )

    def test_ci_obligations_do_not_expand_known_local_checks(self):
        cases = [
            ("evas/README.md", [], "documentation-review"),
            (".github/workflows/ci.yml", ["ci-routing"], "ci:regression"),
            (
                "evas/validation/checker.py",
                ["python-regression"],
                "checker-calibration",
            ),
            (
                "evas/validation/differential/test_ngspice_compare.py",
                [],
                "checker-calibration",
            ),
        ]
        for path, checks, obligation in cases:
            with self.subTest(path=path):
                plan = self.request(operation="plan", paths=[path], stage="iteration")
                self.assertEqual(plan["checks"], checks)
                self.assertIn(obligation, {p["id"] for p in plan["pending_acceptance"]})
                self.assertNotIn(
                    "spectre-alignment", {p["id"] for p in plan["pending_acceptance"]}
                )
                if obligation == "checker-calibration":
                    item = next(
                        p for p in plan["pending_acceptance"] if p["id"] == obligation
                    )
                    self.assertEqual(item["paths"], [path])

    def test_missing_and_deleted_required_modules_remain_blocked(self):
        # A real temporary source tree supplies policy, classifier and missing tests.
        import shutil

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            for name in ("evas_check_policy.py", "ci_selection.py"):
                shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
            policy = runpy.run_path(str(root / "scripts/evas_check_policy.py"))
            for paths in (
                ["evas/rust_core/src/linear/sparse.rs"],
                ["evas/tests/test_deleted.py"],
            ):
                with self.subTest(paths=paths):
                    result = policy["evaluate"](
                        dict(
                            protocol_version=1,
                            operation="plan",
                            paths=paths,
                            stage="iteration",
                        )
                    )["result"]
                    self.assertTrue(result["blocked_checks"])
                    self.assertEqual(
                        {b["check"] for b in result["blocked_checks"]},
                        set(result["checks"]),
                    )
                    self.assertTrue(
                        any(
                            p["id"].startswith("missing:")
                            for p in result["pending_acceptance"]
                        )
                    )

    def test_acceptance_closes_only_successful_local_checks(self):
        plan = self.request(
            operation="plan",
            paths=["evas/rust_core/src/linear/sparse.rs"],
            stage="iteration",
        )
        for passed in (False, True):
            with self.subTest(passed=passed):
                state = self.request(
                    operation="acceptance",
                    plan=plan,
                    results=[dict(check="python:test_affine.py", passed=passed)],
                )
                pending = {p["id"] for p in state["pending_acceptance"]}
                self.assertEqual("local:python:test_affine.py" in pending, not passed)
                self.assertIn("local:python:test_sparse_transient.py", pending)
                self.assertTrue(
                    {"spectre-alignment", "ci:regression", "original-request"}
                    <= pending
                )
                self.assertFalse(state["acceptance_complete"])
                self.assertFalse(state["ci_complete"])
        full = self.request(
            operation="acceptance",
            plan=plan,
            results=[dict(check="python-regression", passed=True)],
        )
        self.assertFalse(
            any(p["id"].startswith("local:python:") for p in full["pending_acceptance"])
        )
        self.assertTrue(full["pending_acceptance"])

    def test_invalid_protocol_and_execution_facts_fail_closed(self):
        requests = [
            dict(protocol_version=2, operation="plan", paths=[], stage="iteration"),
            dict(protocol_version=True, operation="plan", paths=[], stage="iteration"),
            dict(operation="plan", paths=["evas/README.md"], stage="fastest"),
            dict(
                operation="acceptance",
                plan={},
                results=[dict(check="x", passed="true")],
            ),
        ]
        for request in requests:
            with (
                self.subTest(request=request),
                tempfile.TemporaryDirectory() as directory,
            ):
                path = Path(directory) / "request.json"
                path.write_text(json.dumps(dict(protocol_version=1) | request))
                result = subprocess.run(
                    [sys.executable, "-I", "-B", str(POLICY), "--request", str(path)],
                    capture_output=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_document_sync_preserves_manual_text_and_detects_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            doc = Path(directory) / "skill.md"
            doc.write_text(
                "Manual requirement.\n<!-- evas-check-policy:begin -->\n"
                "stale\n<!-- evas-check-policy:end -->\nManual rationale.\n"
            )
            command = [sys.executable, "-I", "-B", str(POLICY), "--document", str(doc)]
            original = doc.read_bytes()
            failed = subprocess.run([*command, "--check-docs"], capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(doc.read_bytes(), original)
            written = subprocess.run([*command, "--write-docs"], capture_output=True)
            self.assertEqual(written.returncode, 0, written.stderr)
            text = doc.read_text()
            self.assertTrue(text.startswith("Manual requirement.\n"))
            self.assertTrue(text.endswith("Manual rationale.\n"))
            self.assertIn("test_sparse_transient", text)
            self.assertEqual(
                subprocess.run(
                    [*command, "--check-docs"], capture_output=True
                ).returncode,
                0,
            )

    def test_invalid_document_markers_never_write(self):
        for content in (
            "manual only",
            "<!-- evas-check-policy:end --><!-- evas-check-policy:begin -->",
            "<!-- evas-check-policy:begin --><!-- evas-check-policy:begin --><!-- evas-check-policy:end -->",
        ):
            with (
                self.subTest(content=content),
                tempfile.TemporaryDirectory() as directory,
            ):
                doc = Path(directory) / "skill.md"
                doc.write_text(content)
                result = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-B",
                        str(POLICY),
                        "--document",
                        str(doc),
                        "--write-docs",
                    ],
                    capture_output=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(doc.read_text(), content)


if __name__ == "__main__":
    unittest.main()
