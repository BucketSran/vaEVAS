"""Fast feedback keeps final obligations and cannot lose tests or trust stale evidence."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StageSelection(unittest.TestCase):
    def test_draft_keeps_focused_regression_and_explicit_delivery_obligations(self):
        ci = load("ci_selection")
        paths = ["evas/rust_core/src/transition_source_state.rs"]
        plan = ci.execution_plan(ROOT, paths, ci.classify(paths), "iteration")
        self.assertEqual(plan["mode"], "iteration")
        self.assertIn("test_transition", plan["modules"])
        self.assertFalse(plan["package"])
        self.assertFalse(plan["fuzz"])
        self.assertTrue(plan["delivery_required"]["package"])
        self.assertTrue(plan["delivery_required"]["regression"])
        self.assertFalse(plan["delivery_complete"])

    def test_final_candidate_and_unknown_source_keep_complete_checks(self):
        ci = load("ci_selection")
        for paths, stage in [
            (["evas/rust_core/src/transition.rs"], "delivery"),
            (["evas/rust_core/src/new_shared.rs"], "iteration"),
            ([".github/workflows/numerical-assurance.yml"], "iteration"),
        ]:
            with self.subTest(paths=paths, stage=stage):
                plan = ci.execution_plan(ROOT, paths, ci.classify(paths), stage)
                self.assertEqual(plan["mode"], "delivery")
                self.assertTrue(plan["regression"])
                self.assertTrue(plan["package"])
                self.assertEqual(plan["modules"], [])

    def test_common_runtime_iteration_does_not_discharge_full_delivery(self):
        policy = load("evas_check_policy")
        result = policy.evaluate(
            dict(
                protocol_version=1,
                operation="plan",
                paths=["evas/rust_core/src/operators.rs"],
                stage="iteration",
            )
        )["result"]
        self.assertNotIn("python-regression", result["checks"])
        for consumer in (
            "lifecycle_closure", "event_accuracy", "event_history_continuation",
            "passive_events", "passive_history_phase", "display",
        ):
            self.assertIn(f"python:test_{consumer}.py", result["checks"])
        self.assertIn(
            "python-regression",
            [x["check"] for x in result["check_selection"]["delivery"]],
        )
        self.assertFalse(result["acceptance_complete"])

    def test_latest_delta_limits_iteration_without_erasing_cumulative_requirements(
        self,
    ):
        ci = load("ci_selection")
        cumulative = [
            "evas/src/evas/runtime.py",
            "evas/rust_core/src/transition_source_state.rs",
        ]
        plan = ci.execution_plan(
            ROOT,
            cumulative,
            ci.classify(cumulative),
            "iteration",
            iteration_paths=["evas/docs/development/diagnostic-inventory.json"],
        )
        self.assertEqual(plan["mode"], "iteration")
        self.assertFalse(plan["regression"])
        self.assertFalse(plan["focused"])
        self.assertTrue(plan["delivery_required"]["regression"])
        self.assertTrue(plan["delivery_required"]["package"])


class Sharding(unittest.TestCase):
    def test_module_shards_are_disjoint_complete_and_keep_failure_red(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(5):
                assertion = 'self.fail("retained failure")' if index == 3 else "pass"
                (root / f"test_case{index}.py").write_text(
                    "import unittest\nclass Cases(unittest.TestCase):\n"
                    f"    def test_{index}(self): {assertion}\n"
                )
            manifests, statuses = [], []
            for index in range(2):
                report = root / f"report-{index}.json"
                process = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(ROOT / "scripts/run_regression.py"),
                        "--start-directory",
                        str(root),
                        "--shard-count",
                        "2",
                        "--shard-index",
                        str(index),
                        "--report",
                        str(report),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertTrue(report.exists(), process.stderr)
                result = json.loads(report.read_text())
                manifests.append(set(result["selected_test_ids"]))
                statuses.append(process.returncode)
                self.assertEqual(result["tests_run"], len(result["selected_test_ids"]))
            self.assertFalse(manifests[0] & manifests[1])
            self.assertEqual(len(manifests[0] | manifests[1]), 5)
            self.assertEqual(sorted(statuses), [0, 1])

    def test_reservation_moves_the_heavy_module_off_shard_zero(self):
        regression = load("run_regression")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test_heavy.py").write_text(
                "import unittest\nclass C(unittest.TestCase):\n def test_a(self): pass\n"
            )
            (root / "test_light.py").write_text(
                "import unittest\nclass C(unittest.TestCase):\n def test_a(self): pass\n"
            )
            weights = {
                "module_seconds": {"test_heavy": 100, "test_light": 1},
                "shard_reserved_seconds": [50, 0],
            }
            (root / "weights.json").write_text(json.dumps(weights))
            reports = []
            for index in range(2):
                report = root / f"report-{index}.json"
                subprocess.run(
                    [
                        sys.executable, "-B", str(ROOT / "scripts/run_regression.py"),
                        "--start-directory", str(root),
                        "--shard-count", "2", "--shard-index", str(index),
                        "--weights", str(root / "weights.json"),
                        "--report", str(report),
                    ],
                    check=True, capture_output=True, text=True, timeout=20,
                )
                reports.append(json.loads(report.read_text()))
            self.assertEqual(reports[0]["selected_test_ids"], ["test_light.C.test_a"])
            self.assertEqual(reports[1]["selected_test_ids"], ["test_heavy.C.test_a"])
            self.assertTrue(reports[0]["successful"] and reports[1]["successful"])
            weights["shard_reserved_seconds"] = [1000, 0]
            (root / "weights.json").write_text(json.dumps(weights))
            empty = root / "empty.json"
            subprocess.run(
                [
                    sys.executable, "-B", str(ROOT / "scripts/run_regression.py"),
                    "--start-directory", str(root),
                    "--shard-count", "2", "--shard-index", "0",
                    "--weights", str(root / "weights.json"),
                    "--report", str(empty),
                ],
                check=True, capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(json.loads(empty.read_text())["selected_test_ids"], [])
            with self.assertRaises(ValueError):
                regression.partition(unittest.TestSuite(), [], 2, {}, reserved=(-1, 0))

    def test_unknown_module_cannot_turn_a_typo_into_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "report.json"
            (root / "test_real.py").write_text(
                "import unittest\nclass C(unittest.TestCase):\n def test_ok(self): pass\n"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/run_regression.py"),
                    "--start-directory",
                    str(root),
                    "--modules",
                    "test_typo",
                    "--report",
                    str(report),
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertNotEqual(result.returncode, 0)


class EvidenceIdentity(unittest.TestCase):
    def test_changed_code_tests_tools_or_budget_invalidates_evidence(self):
        evidence = load("ci_evidence")
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            files = [
                "evas/rust_core/src/main.rs",
                "evas/tests/test_real.py",
                "evas/rust_core/Cargo.lock",
                "scripts/run_regression.py",
                "evas/docs/development/diagnostic-inventory.json",
            ]
            for name in files:
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("original\n")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            base = evidence.fingerprint(repo, {"toolchain": "fixed", "budget": 120})
            for name in files:
                with self.subTest(name=name):
                    path = repo / name
                    path.write_text("changed\n")
                    changed = evidence.fingerprint(
                        repo, {"toolchain": "fixed", "budget": 120}
                    )
                    self.assertEqual(base == changed, name in evidence.EXCLUDED)
                    path.write_text("original\n")
            path = repo / files[0]
            old_mode = path.stat().st_mode
            path.chmod(0o755)
            self.assertNotEqual(
                base, evidence.fingerprint(repo, {"toolchain": "fixed", "budget": 120})
            )
            path.chmod(old_mode)
            self.assertNotEqual(
                base, evidence.fingerprint(repo, {"toolchain": "new", "budget": 120})
            )
            self.assertNotEqual(
                base, evidence.fingerprint(repo, {"toolchain": "fixed", "budget": 121})
            )
            for receipt in [
                {},
                {
                    "identity": base,
                    "shard": "0",
                    "successful": False,
                    "report_sha256": "x",
                },
                {
                    "identity": base,
                    "shard": "1",
                    "successful": True,
                    "report_sha256": "x",
                },
            ]:
                self.assertFalse(evidence.valid_receipt(receipt, base, "0"))


class CoverageGate(unittest.TestCase):
    def test_missing_overlapping_failed_or_mismatched_shard_cannot_pass(self):
        runner = load("run_regression")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = []
            for index in range(2):
                name = f"test_fixture.C.test_{index}"
                report = dict(
                    shard_count=2,
                    shard_index=index,
                    discovered_test_ids=[f"test_fixture.C.test_{i}" for i in range(2)],
                    assignment=[[f"test_fixture.C.test_{i}"] for i in range(2)],
                    selected_test_ids=[name],
                    tests=[{"id": name, "seconds": 0.1, "outcome": "passed"}],
                    complete=True,
                    successful=True,
                    seconds=0.1,
                )
                path = root / f"{index}.json"
                path.write_text(json.dumps(report))
                reports.append(path)
            self.assertTrue(runner.merge_reports(reports)["successful"])
            with self.assertRaises(ValueError):
                runner.merge_reports(reports[:1])
            original = json.loads(reports[1].read_text())
            for key, value in [
                ("successful", False),
                ("complete", False),
                ("shard_index", 0),
                ("selected_test_ids", []),
                ("tests", []),
                ("failures", 1),
                (
                    "tests",
                    [
                        {
                            "id": "test_fixture.C.test_1",
                            "seconds": 0.1,
                            "outcome": "failed",
                        }
                    ],
                ),
                ("discovered_test_ids", []),
            ]:
                with self.subTest(key=key):
                    reports[1].write_text(json.dumps({**original, key: value}))
                    with self.assertRaises(ValueError):
                        runner.merge_reports(reports)
            reports[1].write_text(json.dumps(original))

    def test_new_gate_requires_fast_checks_and_complete_shard_coverage(self):
        ci = load("ci_selection")
        flags = ci.flags("regression")
        outputs = {k: str(v).lower() for k, v in flags.items()}
        outputs.update(plan_version="2", mode="delivery")
        needs = {
            "selection": {"result": "success", "outputs": outputs},
            "fast-checks": {"result": "success"},
            "regression-coverage": {"result": "success"},
        }
        for job, selectors in ci.JOB_FLAGS.items():
            needs[job] = {
                "result": "success" if any(flags[x] for x in selectors) else "skipped"
            }
        self.assertEqual(ci.gate_errors(needs), [])
        for job in ["fast-checks", "regression-coverage"]:
            needs[job]["result"] = "skipped"
            self.assertTrue(ci.gate_errors(needs))
            needs[job]["result"] = "success"


class GitDraftStages(unittest.TestCase):
    def test_incremental_draft_and_ready_use_different_scopes(self):
        ci = load("ci_selection")
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)

            def git(*args):
                return subprocess.check_output(
                    ["git", *args], cwd=repo, text=True
                ).strip()

            git("init", "-q")
            git("config", "user.name", "Workflow fixture")
            git("config", "user.email", "workflow@example.invalid")
            hooks = repo / "empty-hooks"
            hooks.mkdir()

            def commit():
                git("add", ".")
                git(
                    "-c",
                    "commit.gpgsign=false",
                    "-c",
                    "core.hooksPath=" + str(hooks),
                    "commit",
                    "-qm",
                    "fixture",
                )
                return git("rev-parse", "HEAD")

            (repo / "README.md").write_text("base\n")
            base = commit()
            source = repo / "evas/src/evas/runtime.py"
            source.parent.mkdir(parents=True)
            source.write_text("value=1\n")
            before = commit()
            audit = repo / "evas/docs/development/diagnostic-inventory.json"
            audit.parent.mkdir(parents=True)
            audit.write_text("{}\n")
            head = commit()
            event = {
                "before": before,
                "pull_request": {
                    "draft": True,
                    "base": {"sha": base},
                    "head": {"sha": head},
                },
            }
            draft = ci.select(repo, "pull_request", event)
            self.assertEqual(draft["mode"], "iteration")
            self.assertEqual(
                draft["iteration_paths"],
                ["evas/docs/development/diagnostic-inventory.json"],
            )
            self.assertTrue(draft["delivery_required"]["regression"])
            self.assertFalse(draft["regression"])
            event["pull_request"]["draft"] = False
            ready = ci.select(repo, "pull_request", event)
            self.assertEqual(ready["mode"], "delivery")
            self.assertTrue(ready["regression"])
            event["pull_request"]["draft"] = True
            event["before"] = "0" * 40
            self.assertEqual(ci.select(repo, "pull_request", event)["mode"], "delivery")
            manual = ci.select(
                repo,
                "workflow_dispatch",
                {"inputs": {"stage": "iteration", "base": before}},
            )
            self.assertEqual(manual["mode"], "iteration")
            self.assertTrue(manual["delivery_required"]["regression"])
            self.assertFalse(manual["regression"])
            self.assertEqual(
                ci.select(
                    repo,
                    "workflow_dispatch",
                    {"inputs": {"stage": "iteration", "base": "0" * 40}},
                )["mode"],
                "delivery",
            )


class ReceiptRoundTrip(unittest.TestCase):
    def test_real_report_round_trip_rejects_corruption_drift_and_failed_results(self):
        from unittest.mock import patch

        evidence = load("ci_evidence")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            source = root / "test_fixture.py"
            source.write_text(
                "import unittest\nclass Case(unittest.TestCase):\n def test_ok(self): pass\n"
            )
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            report = root / "report.json"
            identity = root / "identity.json"
            receipt = root / "receipt.json"
            tools = {"toolchain": "fixture", "kernel_sha256": "fixture", "budget": 120}

            def call(operation):
                argv = [
                    "ci_evidence.py",
                    operation,
                    "--repo",
                    str(root),
                    "--identity",
                    str(identity),
                    "--receipt",
                    str(receipt),
                    "--report",
                    str(report),
                    "--shard",
                    "0-of-1",
                ]
                with (
                    patch.object(sys, "argv", argv),
                    patch.object(evidence, "environment", lambda repo: tools),
                ):
                    return evidence.main()

            self.assertEqual(call("identity"), 0)
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/run_regression.py"),
                    "--start-directory",
                    str(root),
                    "--input-identity",
                    str(identity),
                    "--report",
                    str(report),
                ],
                check=True,
                capture_output=True,
            )
            self.assertEqual(call("verify"), 1)
            self.assertEqual(call("record"), 0)
            self.assertEqual(call("verify"), 0)
            original = report.read_bytes()
            report.write_bytes(original + b" ")
            self.assertEqual(call("verify"), 1)
            report.write_bytes(original)
            tools["budget"] = 121
            self.assertEqual(call("verify"), 1)
            tools["budget"] = 120
            original_source = source.read_text()
            source.write_text(original_source + "# changed\n")
            self.assertEqual(call("verify"), 1)
            self.assertEqual(call("record"), 1)
            source.write_text(original_source)
            failed = json.loads(original)
            failed["successful"] = False
            report.write_text(json.dumps(failed))
            self.assertEqual(call("record"), 1)


class FixtureSkipAccounting(unittest.TestCase):
    def test_setup_skip_is_explicit_and_does_not_invent_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test_fixture.py").write_text("""import unittest
class Skipped(unittest.TestCase):
 @classmethod
 def setUpClass(cls): raise unittest.SkipTest("fixture unavailable")
 def test_a(self): pass
 def test_b(self): pass
class Live(unittest.TestCase):
 def test_ok(self): pass
""")
            report = root / "report.json"
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/run_regression.py"),
                    "--start-directory",
                    str(root),
                    "--report",
                    str(report),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(report.read_text())
            self.assertEqual(result["tests_run"], 1)
            self.assertEqual(len(result["setup_skipped_test_ids"]), 2)
            self.assertEqual(len(result["tests"]), 1)
            merged = load("run_regression").merge_reports([report])
            self.assertEqual(merged["tests_run"], 1)
            self.assertEqual(merged["planned_tests"], 3)


class SkipOnlyShard(unittest.TestCase):
    def test_a_skip_only_module_can_share_full_coverage_with_live_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test_skipped.py").write_text("""import unittest
class Skipped(unittest.TestCase):
 @classmethod
 def setUpClass(cls): raise unittest.SkipTest("fixture unavailable")
 def test_a(self): pass
 def test_b(self): pass
""")
            (root / "test_live.py").write_text(
                "import unittest\nclass Live(unittest.TestCase):\n def test_ok(self): pass\n"
            )
            reports = []
            for index in range(2):
                report = root / f"shard{index}.json"
                reports.append(report)
                result = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(ROOT / "scripts/run_regression.py"),
                        "--start-directory",
                        str(root),
                        "--shard-count",
                        "2",
                        "--shard-index",
                        str(index),
                        "--report",
                        str(report),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            merged = load("run_regression").merge_reports(reports)
            self.assertEqual(merged["tests_run"], 1)
            self.assertEqual(len(merged["setup_skipped_test_ids"]), 2)
            for report in reports:
                skipped = json.loads(report.read_text())
                skipped.update(
                    tests=[],
                    tests_run=0,
                    setup_skipped_test_ids=skipped["selected_test_ids"],
                )
                report.write_text(json.dumps(skipped))
            with self.assertRaises(ValueError):
                load("run_regression").merge_reports(reports)
