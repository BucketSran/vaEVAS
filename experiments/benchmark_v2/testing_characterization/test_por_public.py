"""The solving package exposes one healthy fixture, not final instances."""
from pathlib import Path
import hashlib,json,unittest,importlib.util,tempfile

ROOT=Path(__file__).resolve().parents[3]
TASK=ROOT/'benchmark/tasks/v2-test-por-sequence'
class PublicBoundary(unittest.TestCase):
    def test_public_fixture_is_distinct_from_all_final_instances(self):
        public=json.loads((TASK/'environment/public/cases.json').read_text())
        hidden=json.loads((TASK/'tests/cases.json').read_text())
        self.assertEqual(len(public),1)
        self.assertEqual(len(hidden),4)
        self.assertNotIn('support',public[0])
        support=public[0]['support_files'];self.assertIn('models.spice',support)
        root=TASK/'environment/public'
        for item in support.values():
            data=(root/item['path']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),item['sha256'])
        analog=(root/support['analog.spice']['path']).read_text()
        self.assertIn('MF=6 m=6',analog)
        self.assertTrue(all(c['support']['analog.spice']!=analog for c in hidden))
    def test_public_default_resolves_only_original_healthy_assets(self):
        root=TASK/'environment/public'
        deck=(root/'public-default.scs').read_text()
        self.assertIn('ahdl_include "dut.va"',deck)
        self.assertIn('por_observe mode=0',deck)
        import re
        for path in re.findall(r'(?:ahdl_include|\.include) "(/work/public/[^"\n]+)"',deck):
            self.assertTrue((root/path.removeprefix('/work/public/')).is_file(),path)
        self.assertIn('save avdd por power osc first_response_us',deck)
    def test_public_contains_no_final_checker_or_candidate(self):
        names={p.name for p in (TASK/'environment/public').rglob('*') if p.is_file()}
        self.assertFalse(names & {'verify.py','v2_testing.py','v2_runtime.py','solve.sh','dut.va'})

    def test_public_materializer_preserves_identity_and_rejects_changed_asset(self):
        spec=importlib.util.spec_from_file_location('public_case',ROOT/'experiments/benchmark_v2/testing_characterization/por_public_case.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        resolved=module.load_cases(TASK/'environment/public')
        self.assertEqual(len(resolved),1)
        self.assertEqual(resolved[0]['name'],'public-healthy')
        self.assertIn('MF=6 m=6',resolved[0]['support']['analog.spice'])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);(path/'model.spice').write_text('changed bytes')
            (path/'cases.json').write_text(json.dumps([{'support_files':{'model.spice':{'path':'model.spice','sha256':hashlib.sha256(b'original bytes').hexdigest()}}}]))
            with self.assertRaisesRegex(ValueError,'identity mismatch'):module.load_cases(path)

if __name__=='__main__':unittest.main()
