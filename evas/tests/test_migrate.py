import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from evas.ir import SCHEMA_VERSION
from evas.migrate import discover_manifests, recompile_manifest, recompile_manifests


ROOT = Path(__file__).resolve().parents[2]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def source(body="V(y,r)<+V(u,r)+1;"):
    return (
        "module m(u,y,r); input u; output y; inout r; electrical u,y,r; "
        f"analog begin {body} end endmodule"
    )


def manifest(model="dut.va", *, module="m"):
    return {
        "models": [model],
        "instances": [{
            "name": "dut",
            "module": module,
            "connections": {"u": "u", "y": "y", "r": "0"},
        }],
        "driven": ["u"],
        "samples": [[0.0]],
    }


class ManifestMigrationTests(unittest.TestCase):
    def test_default_inventory_uses_repository_examples(self):
        manifests = discover_manifests(repo_root=ROOT)
        names = {path.name for path in manifests}
        self.assertIn("static_sum.json", names)
        self.assertIn("idt.json", names)
        self.assertTrue(all(path.suffix == ".json" for path in manifests))

    def test_recompiles_current_manifest_and_records_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "cases/dut.va", source())
            mpath = write(root / "cases/demo.json", json.dumps(manifest()))
            batch = recompile_manifests([mpath], root / "out", repo_root=root)

            self.assertTrue(batch.ok)
            self.assertEqual(len(batch.results), 1)
            result = batch.results[0]
            self.assertEqual(result.status, "success")
            self.assertEqual(result.schema_version, SCHEMA_VERSION)
            self.assertEqual(result.manifest, "cases/demo.json")
            self.assertEqual(set(result.source_sha256), {"dut.va"})
            payload = json.loads((root / "out/cases/demo.ir.json").read_text())
            self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
            summary = json.loads((root / "out/summary.json").read_text())
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["results"][0]["output"], "out/cases/demo.ir.json")

    def test_invalid_manifest_reports_failure_without_ir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mpath = write(root / "bad.json", json.dumps({"models": ["missing.va"]}))
            batch = recompile_manifests([mpath], root / "out", repo_root=root)

            self.assertFalse(batch.ok)
            self.assertEqual(batch.results[0].status, "failure")
            self.assertIn("instances", batch.results[0].diagnostic)
            self.assertFalse((root / "out/bad.ir.json").exists())

    def test_invalid_source_is_a_diagnostic_not_a_fake_ir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "dut.va", source("V(y,r)<+1/0;"))
            mpath = write(root / "bad-source.json", json.dumps(manifest()))
            batch = recompile_manifests([mpath], root / "out", repo_root=root)

            self.assertFalse(batch.ok)
            self.assertEqual(batch.results[0].status, "failure")
            self.assertIn("nonzero constant denominator", batch.results[0].diagnostic)
            self.assertFalse((root / "out/bad-source.ir.json").exists())

    def test_refuses_to_overwrite_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "dut.va", source())
            mpath = write(root / "demo.json", json.dumps(manifest()))
            (root / "out").mkdir()
            with self.assertRaises(FileExistsError):
                recompile_manifests([mpath], root / "out", repo_root=root)

    def test_partial_failure_keeps_success_ir_and_failure_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "ok.va", source())
            write(root / "bad.va", source("V(y,r)<+missing;"))
            ok = write(root / "ok.json", json.dumps(manifest("ok.va")))
            bad = write(root / "bad.json", json.dumps(manifest("bad.va")))
            batch = recompile_manifests([ok, bad], root / "out", repo_root=root)

            self.assertFalse(batch.ok)
            statuses = {result.manifest: result.status for result in batch.results}
            self.assertEqual(statuses, {"ok.json": "success", "bad.json": "failure"})
            self.assertTrue((root / "out/ok.ir.json").exists())
            self.assertFalse((root / "out/bad.ir.json").exists())
            failed = next(result for result in batch.results if result.status == "failure")
            self.assertEqual(set(failed.source_sha256), {"bad.va"})
            self.assertIn("missing", failed.diagnostic)

    def test_empty_inventory_is_a_batch_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "empty").mkdir()
            batch = recompile_manifests([root / "empty"], root / "out", repo_root=root)

            self.assertFalse(batch.ok)
            self.assertEqual(len(batch.results), 1)
            self.assertEqual(batch.results[0].manifest, "<batch>")
            self.assertIn("no manifests", batch.results[0].diagnostic)
            summary = json.loads((root / "out/summary.json").read_text())
            self.assertFalse(summary["ok"])

    def test_unreadable_or_undecodable_manifest_is_per_item_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = write_bytes(root / "bad.json", b"\xff")
            batch = recompile_manifests([bad], root / "out", repo_root=root)

            self.assertFalse(batch.ok)
            self.assertEqual(batch.results[0].status, "failure")
            self.assertEqual(batch.results[0].manifest, "bad.json")
            self.assertNotEqual(batch.results[0].manifest_sha256, "")
            self.assertIn("utf-8", batch.results[0].diagnostic.lower())
            self.assertFalse((root / "out/bad.ir.json").exists())

    def test_source_read_error_is_per_item_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mpath = write(root / "missing-source.json", json.dumps(manifest("missing.va")))
            batch = recompile_manifests([mpath], root / "out", repo_root=root)

            self.assertFalse(batch.ok)
            self.assertEqual(batch.results[0].status, "failure")
            self.assertNotEqual(batch.results[0].manifest_sha256, "")
            self.assertEqual(batch.results[0].source_sha256, {})
            self.assertIn("missing.va", batch.results[0].diagnostic)
            self.assertFalse((root / "out/missing-source.ir.json").exists())

    def test_manifest_and_source_hash_match_exact_bytes_used_for_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_bytes = source().encode("utf-8")
            manifest_bytes = json.dumps(manifest(), sort_keys=True).encode("utf-8")
            write_bytes(root / "dut.va", source_bytes)
            mpath = write_bytes(root / "demo.json", manifest_bytes)
            batch = recompile_manifests([mpath], root / "out", repo_root=root)

            self.assertTrue(batch.ok)
            result = batch.results[0]
            self.assertEqual(result.manifest_sha256, hashlib.sha256(manifest_bytes).hexdigest())
            self.assertEqual(result.source_sha256["dut.va"], hashlib.sha256(source_bytes).hexdigest())

    def test_external_same_basename_manifests_get_distinct_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            external = root / "external"
            left = external / "left"
            right = external / "right"
            shared = source("V(y,r)<+1;")
            write(left / "dut.va", shared)
            write(right / "dut.va", shared)
            left_manifest = write(left / "case.json", json.dumps(manifest()))
            right_manifest = write(right / "case.json", json.dumps(manifest()))
            repo = root / "repo"
            repo.mkdir()
            batch = recompile_manifests([left_manifest, right_manifest], repo / "out", repo_root=repo)

            self.assertTrue(batch.ok)
            outputs = [result.output for result in batch.results]
            self.assertEqual(len(outputs), len(set(outputs)))
            self.assertEqual(len(list((repo / "out").rglob("case.ir.json"))), 2)
            self.assertEqual(batch.results[0].source_sha256["dut.va"], batch.results[1].source_sha256["dut.va"])

    def test_existing_output_path_is_a_failed_item_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "dut.va", source())
            mpath = write(root / "a.json", json.dumps(manifest()))
            existing = write(root / "existing.ir.json", "sentinel")
            original = existing.read_text()

            result = recompile_manifest(mpath, existing, repo_root=root)

            self.assertEqual(result.status, "failure")
            self.assertIn("exists", result.diagnostic)
            self.assertEqual(existing.read_text(), original)


if __name__ == "__main__":
    unittest.main()
