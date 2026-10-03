"""Keep normal jobs and historical channel amendments separately scoreable."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        (self.run / "input-manifest.json").write_text("{}")
        (self.run / "protocol.json").write_text("{}")

    def trial(self, job, model):
        trial = self.run / job / "va01-and2__sample"
        (trial / "agent").mkdir(parents=True)
        (trial / "verifier").mkdir()
        candidate = b"module dut; endmodule\n"
        prompt = b"Generate a model.\n"
        (trial / "agent/dut.va").write_bytes(candidate)
        (trial / "agent/prompt.md").write_bytes(prompt)
        generation = dict(model_requested=model, cli_version="fixture", elapsed_s=0,
                          candidate_sha256=hashlib.sha256(candidate).hexdigest(),
                          instruction_sha256=hashlib.sha256(prompt).hexdigest(),
                          num_turns=1, model_usage={model: {"webSearchRequests": 0}})
        (trial / "agent/generation.json").write_text(json.dumps(generation))
        (trial / "agent/stdout.jsonl").write_text('{"type":"turn.completed"}\n')
        report = dict(candidate_sha256=generation["candidate_sha256"], reward=1,
                      status="completed", cases_sha256="fixture", checker_sha256="fixture",
                      cases=[dict(name="condition", status="graded", passed=True)],
                      remote_root="fixture")
        (trial / "verifier/report.json").write_text(json.dumps(report))
        (trial / "result.json").write_text(json.dumps({"verifier_result": {"rewards": {"reward": 1}}}))

    def summarize(self):
        output = self.run / "summary.json"
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "experiments.va_screen.summarize",
             str(self.run), "--output", str(output)], capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(output.read_text())

    def test_normal_run_scores_codex_and_glm_without_amendment(self):
        self.trial("codex", "gpt-6.1-sol")
        self.trial("glm", "glm-5.3")
        summary = self.summarize()
        self.assertEqual(summary["graded_submissions"], 2)
        self.assertEqual({r["channel"] for r in summary["records"]}, {"codex", "glm"})
        self.assertEqual(summary["infrastructure_events"], [])
        self.assertIsNone(summary["channel_amendment"])

    def test_historical_amendment_keeps_old_request_failure_out_of_scores(self):
        self.trial("codex-native", "gpt-6.1-sol")
        self.trial("glm", "glm-5.3")
        failed = self.run / "codex/va01-and2__rejected"
        failed.mkdir(parents=True)
        (failed / "result.json").write_text(json.dumps({"exception_info": "request rejected"}))
        amendment = dict(scored_codex_jobs=["codex-native-preflight", "codex-native"],
                         scored_glm_jobs=["glm"])
        (self.run / "channel-amendment.json").write_text(json.dumps(amendment))
        summary = self.summarize()
        self.assertEqual(summary["graded_submissions"], 2)
        self.assertEqual(summary["channel_amendment"], amendment)
        self.assertEqual(summary["infrastructure_events"], [dict(
            channel="codex-old-cli", trial="codex/va01-and2__rejected", exception="request rejected")])


if __name__ == "__main__":
    unittest.main()
