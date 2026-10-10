"""The solving package exposes one healthy fixture, not final instances."""
from pathlib import Path
import hashlib,json,unittest,importlib.util,tempfile

ROOT=Path(__file__).resolve().parents[3]
TASK=ROOT/'benchmark/tasks/v2-test-por-sequence'
class PublicBoundary(unittest.TestCase):
    def materializer(self):
        spec=importlib.util.spec_from_file_location('public_case',ROOT/'experiments/benchmark_v2/testing_characterization/por_public_case.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_final_prepare_resolves_five_immutable_instances_under_inventory_cap(self):
        root=TASK/'tests'
        encoded=json.loads((root/'cases.json').read_text())
        self.assertTrue(all('support' not in c and 'support_files' in c for c in encoded))
        resolved=self.materializer().load_cases(root)
        self.assertEqual(len(resolved),5)
        self.assertIn('missing-first-fall',{c['name'] for c in resolved})
        self.assertEqual(len({c['support_files']['models.spice']['path'] for c in encoded}),1)
        self.assertLess(sum(p.stat().st_size for p in TASK.rglob('*') if p.is_file()),16*1024*1024)
        expected='d61cfa1b7321e7614b57f15d11749bbf69f6ae8ba3e14f04fd0ce340433d1365'
        self.assertTrue(all(hashlib.sha256(c['support']['models.spice'].encode()).hexdigest()==expected for c in resolved))


    def test_final_runtime_materializes_all_five_conditions_before_backend(self):
        # Process fixture validates package preparation only, not POR physics.
        import sys,os
        from unittest.mock import patch
        sys.path.insert(0,str(ROOT/'benchmark/checkers'))
        from v2_runtime import verify
        cases=json.loads((TASK/'tests/cases.json').read_text())
        signals=cases[0]['signals']
        psf='VALUE\n'+''.join('"time" '+str(t)+'\n'+''.join('"'+name+'" 0\n' for name in signals) for t in [0.,.006])+'END\n'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);candidate=root/'dut.va';candidate.write_bytes((TASK/'solution/dut.va').read_bytes())
            binary=root/'backend-fixture'
            binary.write_text('#!/usr/bin/env python3\nfrom pathlib import Path\nimport sys\nif "-W" in sys.argv:print("package fixture only");raise SystemExit(0)\nPath("psf").mkdir()\nPath("psf/tran.tran.tran").write_text('+repr(psf)+')\n')
            binary.chmod(0o700)
            with patch.dict(os.environ,{'SPECTRE':str(binary)}):
                report=verify(candidate,root/'output',TASK/'tests',lambda rows,case,work:{'passed':True})
            self.assertEqual(report['reward'],1,report)
            self.assertEqual(len(report['cases']),5)
            for case in cases:
                for name,item in case['support_files'].items():
                    self.assertEqual(hashlib.sha256((root/'output'/case['name']/name).read_bytes()).hexdigest(),item['sha256'])

    def test_public_fixture_is_distinct_from_all_final_instances(self):
        public=json.loads((TASK/'environment/public/cases.json').read_text())
        hidden=self.materializer().load_cases(TASK/'tests')
        self.assertEqual(len(public),1)
        self.assertEqual(len(hidden),5)
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
