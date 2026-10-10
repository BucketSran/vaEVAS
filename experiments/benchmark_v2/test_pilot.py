"""Public pilot boundaries: materials, candidate bytes, and attempt identity."""
import hashlib
import json
import os
import subprocess
import sys
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


class PublicDeploymentTests(unittest.TestCase):
    def deploy(self, root, files, *, netlist='visible.scs', spec=None, candidate_helper=None):
        task = root / 'task'
        public = task / 'environment/public'
        public.mkdir(parents=True)
        for name, content in files.items():
            target = public / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (task / 'instruction.md').write_text('Public fixture')
        package = root / 'package'
        pilot.public_package(task, package, ['dut.va', 'rtl/helper.va'], netlist)
        candidates = root / 'candidate'
        (candidates / 'rtl').mkdir(parents=True)
        (candidates / 'dut.va').write_bytes(b'module dut;\r\nendmodule\r\n')
        (candidates / 'rtl/helper.va').write_bytes(candidate_helper if candidate_helper is not None else b'module helper; endmodule\n')
        if spec is not None:
            (candidates / '.public-testbench.json').write_text(json.dumps(spec))
        fake = root / 'fake-spectre'
        fake.write_text('#!' + sys.executable + '\n' + r'''import pathlib,re,sys
pathlib.Path('fake-called').write_text('called')
def visit(path, deck=True):
    assert path.is_file(), str(path)
    if deck:
        for kind, name in re.findall(r"(ahdl_include|include)\s+[\"']([^\"']+)[\"']", path.read_text()):
            visit(path.parent / name, deck=kind == 'include')
visit(pathlib.Path(sys.argv[2]))
psf=pathlib.Path('psf');psf.mkdir()
(psf/'fixture.tran.tran').write_text('VALUE\n"time" 0\n"out" 1\nEND\n')
''')
        fake.chmod(0o700)
        output = root / 'output'
        result = subprocess.run([sys.executable, str(package / 'public_feedback.py')],
            env={**os.environ, 'CANDIDATE': str(candidates / 'dut.va'),
                 'VERIFY_OUTPUT': str(output), 'SPECTRE': str(fake)},
            capture_output=True, timeout=10)
        return result, package, candidates, output

    def test_fixed_work_includes_deploy_with_unchanged_source_bytes(self):
        files = {
            'visible.scs': b'ahdl_include "/work/dut.va"\r\nahdl_include "/work/rtl/helper.va"\r\ninclude "/work/public/decks/nested.scs"\r\n',
            'decks/nested.scs': b'include "/work/public/decks/extra.inc"\n',
            'decks/extra.inc': b"ahdl_include '/work/public/support.va'\n",
            'support.va': b'module support; endmodule\r\n',
        }
        with tempfile.TemporaryDirectory() as folder:
            result, package, candidates, output = self.deploy(Path(folder), files)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            report = json.loads((output / 'report.json').read_text())
            self.assertEqual(report['diagnostics']['spectre_returncode'], 0)
            self.assertEqual(report['observations'], [{'time': 0.0, 'out': 1.0}])
            for name, content in files.items():
                self.assertEqual((package / 'public' / name).read_bytes(), content)
            self.assertEqual((output / 'condition/dut.va').read_bytes(), (candidates / 'dut.va').read_bytes())
            receipt = json.loads((output / 'netlist-identity.json').read_text())
            self.assertEqual(receipt['decks']['visible.scs']['original_sha256'], hashlib.sha256(files['visible.scs']).hexdigest())
            effective = (output / 'condition/visible.scs').read_bytes()
            self.assertEqual(receipt['decks']['visible.scs']['effective_sha256'], hashlib.sha256(effective).hexdigest())
            self.assertNotEqual(effective, files['visible.scs'])


    def test_relative_and_agent_testbench_inputs_use_declared_files(self):
        files = {'visible.scs': b'ahdl_include "./dut.va"\r\ninclude "./decks/nested.scs"\r\n',
                 'decks/nested.scs': b'ahdl_include "helper.va"\n',
                 'decks/helper.va': b'module public_helper; endmodule\n'}
        with tempfile.TemporaryDirectory() as folder:
            result, _, _, output = self.deploy(Path(folder), files)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(json.loads((output / 'report.json').read_text())['diagnostics']['spectre_returncode'], 0)
            self.assertEqual((output / 'condition/visible.scs').read_bytes(), files['visible.scs'])
        spec = {'netlist': 'ahdl_include "/work/dut.va"\ninclude "/work/public/decks/nested.scs"\nahdl_include "temporary/helper.va"\n',
                'support_files': {'temporary/helper.va': 'module temp; endmodule\n'}}
        with tempfile.TemporaryDirectory() as folder:
            result, _, candidates, output = self.deploy(Path(folder), files, spec=spec)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(json.loads((output / 'report.json').read_text())['diagnostics']['spectre_returncode'], 0)
            self.assertEqual((output / 'condition/dut.va').read_bytes(), (candidates / 'dut.va').read_bytes())
            receipt = json.loads((output / 'netlist-identity.json').read_text())
            self.assertEqual(receipt['netlist'], '.harness-public-testbench.scs')
            self.assertEqual(receipt['decks'][receipt['netlist']]['original_sha256'], hashlib.sha256(spec['netlist'].encode()).hexdigest())

    def test_unsafe_include_paths_are_rejected_before_spectre(self):
        for include in ['/etc/passwd', '/work/undeclared.va', '/work/public/secret.va',
                        '/work/public/../dut.va', '../dut.va', 'missing.va']:
            with self.subTest(include=include), tempfile.TemporaryDirectory() as folder:
                files = {'visible.scs': ('ahdl_include "' + include + '"\n').encode()}
                result, _, _, output = self.deploy(Path(folder), files)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((output / 'condition/fake-called').exists())
                self.assertFalse((output / 'report.json').exists())
        with tempfile.TemporaryDirectory() as folder:
            files = {'visible.scs': b'include "decks/nested.scs"\n',
                     'decks/nested.scs': b'ahdl_include "/etc/passwd"\n'}
            result, _, _, output = self.deploy(Path(folder), files)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((output / 'condition/fake-called').exists())
        with tempfile.TemporaryDirectory() as folder:
            spec = {'netlist': 'ahdl_include "/work/dut.va"\nahdl_include "/etc/passwd"\n', 'support_files': {}}
            result, _, _, output = self.deploy(Path(folder), {'visible.scs': b''}, spec=spec)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((output / 'condition/fake-called').exists())


    def test_temporary_text_deck_rejects_nested_absolute_include(self):
        spec = {'netlist': 'ahdl_include "/work/dut.va"\ninclude "temporary/nested.va"\n',
                'support_files': {'temporary/nested.va': 'include "/etc/passwd"\n'}}
        with tempfile.TemporaryDirectory() as folder:
            result, _, _, output = self.deploy(Path(folder), {'visible.scs': b''}, spec=spec)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((output / 'condition/fake-called').exists())
            self.assertFalse((output / 'report.json').exists())


    def test_temporary_text_deck_maps_declared_includes_and_records_both_hashes(self):
        nested = 'include "/work/public/decks/helper.inc"\n'
        # This model's source is deliberately opaque to the deck path adapter.
        model = 'module temp; // include "/vendor/private"\r\nendmodule\r\n'
        spec = {'netlist': 'include "temporary/nested.va"\nahdl_include "temporary/model.va"\n',
                'support_files': {'temporary/nested.va': nested, 'temporary/model.va': model}}
        with tempfile.TemporaryDirectory() as folder:
            result, _, _, output = self.deploy(Path(folder),
                {'visible.scs': b'', 'decks/helper.inc': b'ahdl_include "/work/dut.va"\n'}, spec=spec)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(json.loads((output / 'report.json').read_text())['diagnostics']['spectre_returncode'], 0)
            receipt = json.loads((output / 'netlist-identity.json').read_text())['decks']
            self.assertEqual(receipt['temporary/nested.va']['original_sha256'], hashlib.sha256(nested.encode()).hexdigest())
            effective = (output / 'condition/temporary/nested.va').read_bytes()
            self.assertEqual(receipt['temporary/nested.va']['effective_sha256'], hashlib.sha256(effective).hexdigest())
            self.assertIn('decks/helper.inc', receipt)
            self.assertNotIn('temporary/model.va', receipt)
            self.assertEqual((output / 'condition/temporary/model.va').read_bytes(), model.encode())

    def test_candidate_used_as_text_deck_is_checked_and_recorded(self):
        files = {'visible.scs': b'include "/work/rtl/helper.va"\n'}
        with tempfile.TemporaryDirectory() as folder:
            result, _, _, output = self.deploy(Path(folder), files,
                candidate_helper=b'include "/etc/passwd"\n')
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((output / 'condition/fake-called').exists())
        with tempfile.TemporaryDirectory() as folder:
            raw = b'// declared candidate text deck\r\n'
            result, _, candidates, output = self.deploy(Path(folder), files, candidate_helper=raw)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            receipt = json.loads((output / 'netlist-identity.json').read_text())['decks']
            digest = hashlib.sha256(raw).hexdigest()
            self.assertEqual(receipt['rtl/helper.va'], {'original_sha256': digest, 'effective_sha256': digest})
            self.assertEqual((candidates / 'rtl/helper.va').read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
