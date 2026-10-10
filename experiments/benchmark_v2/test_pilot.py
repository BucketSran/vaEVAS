"""Public pilot boundaries: materials, candidate bytes, and attempt identity."""
import json
from pathlib import Path
import tempfile
import unittest
from experiments.benchmark_v2 import pilot


class PilotTests(unittest.TestCase):
    def test_public_export_does_not_include_solutions_or_tests(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            task = root / 'source'
            (task / 'environment/public/project').mkdir(parents=True)
            (task / 'environment/public/project/device.va').write_bytes(b'public\r\n')
            (task / 'instruction.md').write_text('Build the public circuit.')
            (task / 'tests').mkdir()
            (task / 'tests/secret.json').write_text('hidden criterion')
            (task / 'solution').mkdir()
            (task / 'solution/dut.va').write_text('reference answer')
            destination = root / 'export'
            pilot.export_public(task, destination)
            self.assertEqual((destination / 'public/project/device.va').read_bytes(), b'public\r\n')
            self.assertFalse((destination / 'tests').exists())
            self.assertFalse((destination / 'solution').exists())
            self.assertNotIn('reference answer', pilot.one_shot_prompt(destination, ['dut.va']))
            with self.assertRaises(FileExistsError):
                pilot.export_public(task, destination)

    def test_one_shot_keeps_raw_response_and_candidate_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            response = '{"files":{"dut.va":"module x;\\r\\nendmodule\\r\\n","rtl/a.va":"alpha\\n"}}'
            pilot.save_one_shot_candidate(response, root, ['dut.va', 'rtl/a.va'])
            self.assertEqual((root / 'raw-response.txt').read_text(), response)
            self.assertEqual((root / 'candidate/dut.va').read_bytes(), b'module x;\r\nendmodule\r\n')
            self.assertEqual((root / 'candidate/rtl/a.va').read_bytes(), b'alpha\n')
            self.assertEqual(json.loads((root / 'candidate-identity.json').read_text())['selection'], 'only-response-no-best-of')
            with self.assertRaises(FileExistsError):
                pilot.save_one_shot_candidate(response, root, ['dut.va', 'rtl/a.va'])

    def test_outside_candidate_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                pilot.save_one_shot_candidate('{"files":{"../escape":"bad"}}', root, ['dut.va'])
            self.assertFalse((root.parent / 'escape').exists())

    def test_one_outer_json_fence_preserves_exact_candidate_contents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            contents = 'module x;\r\n// ``` inside source\r\nendmodule\r\n'
            response = '```json\n' + json.dumps({'files': {'dut.va': contents}}) + '\n```'
            pilot.save_one_shot_candidate(response, root, ['dut.va'])
            self.assertEqual((root / 'candidate/dut.va').read_bytes(), contents.encode())
            self.assertEqual((root / 'raw-response.txt').read_text(), response)

    def test_explanatory_text_is_not_silently_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                pilot.save_one_shot_candidate(
                    'Here is the answer:\n```json\n{"files":{"dut.va":"model"}}\n```',
                    root, ['dut.va'])
            self.assertFalse((root / 'candidate').exists())

    def test_public_package_uses_only_declared_input_netlist(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            task = root / 'task'
            public = task / 'environment/input'
            public.mkdir(parents=True)
            (public / 'dut.va').write_text('starter')
            (public / 'public_test.scs').write_text('simulator lang=spectre\n')
            (task / 'instruction.md').write_text('Public problem')
            package = root / 'package'
            pilot.public_package(task, package, ['dut.va'], 'public_test.scs')
            self.assertEqual((package / 'public/public_test.scs').read_text(), 'simulator lang=spectre\n')
            self.assertFalse((package / 'public/dut.va').exists())
            manifest = json.loads((package / 'manifest.json').read_text())
            self.assertEqual(manifest['purpose'], 'public')
            self.assertEqual(manifest['feedback_fields'], ['diagnostics', 'observations'])


if __name__ == '__main__':
    unittest.main()
