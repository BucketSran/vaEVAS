"""Metadata updates may edit suite manifests, while task inputs stay unchanged."""
import json
from pathlib import Path
import tempfile
import unittest

from experiments.benchmark_first_batch.sync_metadata import normalize


class MetadataTests(unittest.TestCase):
    def test_normalize_colocated_manifest_without_changing_task_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = root / "benchmark/tasks"
            task = tasks / "spec-example"
            (task / "solution").mkdir(parents=True)
            (task / "task.toml").write_text('[metadata]\ncategory = "analog"\n')
            (task / "SOURCE.md").write_text("Original source notes.\n")
            circuit = task / "solution/dut.va"
            circuit.write_bytes(b"module example; endmodule\n")
            original = circuit.read_bytes()
            names = ("model_repair", "identification", "integration",
                     "verification_measurement", "optimization")
            for name in names:
                entries = [{"id": "spec-example", "action": "specification",
                            "source_group": "example-source",
                            "path": "benchmark/tasks/spec-example"}] if name == "model_repair" else []
                (tasks / f"first_batch-{name}.json").write_text(json.dumps({"tasks": entries}))
            manifest = tasks / "first_batch-model_repair.json"
            before = manifest.read_bytes()
            count, stale = normalize(root, check=True)
            self.assertEqual(count, 1)
            self.assertIn("benchmark/tasks/first_batch-model_repair.json", stale)
            self.assertEqual(manifest.read_bytes(), before)

            normalize(root)
            row = json.loads(manifest.read_text())["tasks"][0]
            self.assertEqual(row["engineering_action"], "specification-modeling")
            self.assertNotIn("action", row)
            self.assertEqual(circuit.read_bytes(), original)
            self.assertEqual(normalize(root, check=True), (1, []))


if __name__ == "__main__":
    unittest.main()
