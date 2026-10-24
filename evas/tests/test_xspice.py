"""Public VA->XSPICE artifact contract; independent of the Rust solver."""

GUARDS = ["DEV:xspice-compile", "LANG", "CROSS", "TIMER", "TRANSITION", "EVENT-ORDER"]
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evas import CompileError
from evas.xspice import compile_model

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "examples/xspice/sample_hold.va").read_text()


class XspiceCompilation(unittest.TestCase):
    def compile(self, text=SOURCE, **kwargs):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "model"
            result = compile_model({"sample_hold.va": text}, path, **kwargs)
            return result, {
                p.name: p.read_text() for p in path.iterdir() if p.is_file()
            }

    def test_actual_frontend_and_source_identity(self):
        meta, files = self.compile(model_name="sample_hold_cm")
        from evas.ir import SCHEMA_VERSION

        self.assertEqual(meta["ir_schema_version"], SCHEMA_VERSION)
        self.assertEqual(
            meta["ports"],
            [
                "din",
                "clk",
                "out",
                "held_out",
                "count_out",
                "ticks_out",
                "order_out",
                "stamp_out",
            ],
        )
        self.assertEqual(
            [e["trigger"]["kind"] for e in json.loads(files["ir.json"])["events"]],
            ["cross", "timer"],
        )
        self.assertEqual(
            json.loads(files["source-inputs.json"]), {"sample_hold.va": SOURCE}
        )
        self.assertIn("Spice_Model_Name: sample_hold_cm", files["ifspec.ifs"])
        self.assertIn(".model sample_hold_cm sample_hold_cm", files["model.inc"])
        self.assertFalse(meta["test_hooks"])

    def test_arbitrary_state_names_and_order_are_not_hardcoded(self):
        source = (
            SOURCE.replace("held", "sampled")
            .replace("last_event", "moment")
            .replace("count", "samples")
        )
        source = source.replace(
            "real sampled,moment,order;", "real order,moment,sampled;"
        )
        meta, files = self.compile(source)
        self.assertIn("sampled", meta["state_names"])
        self.assertNotIn("COUNT_STATE", files["cfunc.mod"])

    def test_specialized_variants_have_distinct_model_types(self):
        a, _ = self.compile(parameters={"rise": 1e-7})
        b, _ = self.compile(parameters={"rise": 2e-7})
        self.assertNotEqual(a["model_name"], b["model_name"])

    def test_default_model_types_distinguish_test_hook_mode(self):
        a, _ = self.compile(test_hooks=False)
        b, _ = self.compile(test_hooks=True)
        self.assertNotEqual(a["model_name"], b["model_name"])

    def test_rejection_does_not_publish_an_artifact(self):
        cases = [
            SOURCE.replace("threshold,+1", "threshold,-1"),
            SOURCE.replace("timer_start=1.18e-6", "timer_start=0"),
            SOURCE.replace("transition(held,", "transition(V(din),"),
            SOURCE.replace(
                "V(out)<+transition(held,delay,rise,fall);",
                "V(out)<+transition(held,delay,rise,fall); V(out)<+0.1;",
            ),
        ]
        for text in cases:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as t:
                out = Path(t) / "rejected"
                with self.assertRaises(CompileError):
                    compile_model({"model.va": text}, out)
                self.assertFalse(out.exists())

    def test_bounded_r53_counter_clock_and_continuous_comparator_are_admitted(self):
        # These exact public VA sources used to fail admission before their
        # independent native counter/clock/nonlinear contracts could run.
        for name in ("two_bit_counter_marker.va", "multiphase_clock_generator_4ph.va",
                     "smooth_comparator_tanh.va"):
            with self.subTest(source=name):
                meta, files = self.compile((ROOT / "examples/xspice/r53" / name).read_text())
                self.assertEqual(meta["backend_version"], 2)
                self.assertTrue(json.loads(files["ir.json"])["contributions"])

    def test_alias_sources_keep_one_constant_division(self):
        # validate_aliases.py already scores these three sources. The threshold
        # binding is one real division by the constant 2; real subtraction of
        # two bindings stays outside the slice.
        alias = ROOT / "examples/xspice/aliases"
        for name in (
            "affine_input_aliases.va",
            "selected_body_alias.va",
            "direct_input_expressions.va",
        ):
            with self.subTest(source=name):
                meta, _ = self.compile((alias / name).read_text())
                self.assertEqual(meta["backend_version"], 2)
        _, files = self.compile((alias / "affine_input_aliases.va").read_text())
        generated = files["cfunc.mod"]
        self.assertEqual(generated.count("ad_div("), 3)
        self.assertIn("locals[2] = ad_div(ad_add(locals[0], locals[1]), ad_const(2.0));", generated)
        _, plain = self.compile()
        self.assertNotIn("ad_div(", plain["cfunc.mod"])
        subtracted = """
`include "disciplines.vams"
module alias_box(a, b, y);
input a, b; output y;
electrical a, b, y;
real vh, vl, q;
analog begin
  @(initial_step) q = 0;
  vh = V(a); vl = V(b);
  @(cross(V(a) - 0.5, +1)) q = vh - vl;
  V(y) <+ transition(q, 0, 1n, 1n);
end
endmodule
"""
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(CompileError, "subtract"):
                compile_model({"alias_box.va": subtracted}, Path(directory) / "model")

    def test_reference_connection_retains_the_original_va_port_order(self):
        source = (ROOT / "examples/xspice/r53/multiphase_clock_generator_4ph.va").read_text()
        meta, files = self.compile(source)
        self.assertEqual(meta["ports"], ["vss", "clk0", "clk90", "clk180", "clk270"])
        self.assertEqual(meta["instance_connections"], ["vss", "%vd(clk0 vss)",
            "%vd(clk90 vss)", "%vd(clk180 vss)", "%vd(clk270 vss)"])
        self.assertIn("vss %vd(clk0 vss)", files["instance.cir"])

    def test_unqualified_math_and_dynamic_timer_leave_no_artifact(self):
        cases = [
            (ROOT / "examples/xspice/r53/smooth_comparator_tanh.va").read_text().replace("tanh(", "exp("),
            (ROOT / "examples/xspice/r53/multiphase_clock_generator_4ph.va").read_text().replace("timer(10n, 10n)", "timer(level0, 10n)"),
        ]
        for source in cases:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                out = Path(directory) / "model"
                with self.assertRaises(CompileError):
                    compile_model({"dut.va": source}, out)
                self.assertFalse(out.exists())

    def test_no_output_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "existing"
            p.mkdir()
            (p / "keep").write_text("original")
            with self.assertRaises((CompileError, FileExistsError)):
                compile_model({"m.va": SOURCE}, p)
            self.assertEqual((p / "keep").read_text(), "original")

    def test_public_cli_compiles_without_kernel(self):
        with tempfile.TemporaryDirectory() as t:
            source = Path(t) / "source.va"
            source.write_text(SOURCE)
            out = Path(t) / "output with spaces"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "evas",
                    "xspice",
                    "compile",
                    str(source),
                    "-o",
                    str(out),
                ],
                env=dict(os.environ, EVAS_KERNEL="/missing/never/invoked"),
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "compiled")
            self.assertTrue((out / "ifspec.ifs").is_file())

    def test_cli_errors_are_machine_readable(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "evas",
                "xspice",
                "compile",
                "/does-not-exist.va",
                "-o",
                "/unused",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("code", json.loads(proc.stderr))


class XspiceBuildAdmission(unittest.TestCase):
    def test_tampered_source_never_reaches_toolchain(self):
        from evas.xspice import build_model

        with tempfile.TemporaryDirectory() as t:
            artifact = Path(t) / "artifact"
            compile_model({"m.va": SOURCE}, artifact)
            (artifact / "cfunc.mod").write_text("changed")
            out = Path(t) / "build"
            with self.assertRaisesRegex(CompileError, "changed after compilation"):
                build_model(artifact, {}, out)
            self.assertFalse(out.exists())

    def test_missing_sdk_leaves_compiled_artifact_intact(self):
        from evas.xspice import build_model

        with tempfile.TemporaryDirectory() as t:
            artifact = Path(t) / "artifact"
            compile_model({"m.va": SOURCE}, artifact)
            before = (artifact / "manifest.json").read_bytes()
            with self.assertRaisesRegex(CompileError, "source_tree"):
                build_model(artifact, {"sdk_version": 1})
            self.assertEqual((artifact / "manifest.json").read_bytes(), before)
            self.assertFalse((artifact / "native").exists())

    def test_fault_hooks_are_explicit_in_artifact(self):
        with tempfile.TemporaryDirectory() as t:
            artifact = Path(t) / "artifact"
            m = compile_model({"m.va": SOURCE}, artifact, test_hooks=True)
            self.assertTrue(m["test_hooks"])
            self.assertIn("#define TEST_HOOKS 1", (artifact / "cfunc.mod").read_text())

    def test_reserved_diagnostics_and_model_names_are_rejected(self):
        for source, name in [
            (SOURCE.replace("threshold=0.9", "evas_trace=0.9"), "m"),
            (SOURCE, "../bad"),
        ]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as t:
                with self.assertRaises(CompileError):
                    compile_model({"m.va": source}, Path(t) / "out", model_name=name)


if __name__ == "__main__":
    unittest.main()
