"""Local package/identity and file-location integration, without remote calls."""
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import os
import shutil
import test_checker as fixtures
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('adapter',ROOT/'experiments/adc_linearity/harness_adapter.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
spec=importlib.util.spec_from_file_location('checker',ROOT/'benchmark/checkers/adc_linearity.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
HARNESS=ROOT.parents[2]/'circuits/harness'


class Integration(unittest.TestCase):
    def test_relocation_changes_only_two_allowed_path_tokens(self):
        source=(adapter.TASK/'solution/reference.va').read_text()
        with tempfile.TemporaryDirectory() as folder:
            executed,receipt=checker.relocate_output_paths(source,folder)
            restored=executed
            for original,new in receipt['mapping'].items(): restored=restored.replace('"'+new+'"','"'+original+'"')
            self.assertEqual(restored,source)
            self.assertNotEqual(executed,source)
            self.assertEqual(receipt['version'],'adc-output-paths-v1')
            self.assertIn('"'+str(Path(folder).resolve()/'samples.csv')+'"',executed)

    @unittest.skipUnless(HARNESS.is_dir(),'explicit local circuit harness absent')
    def test_frozen_candidate_and_four_packages_pass_existing_harness_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'prepared'
            record=adapter.prepare(HARNESS,adapter.TASK/'solution/reference.va',output)
            self.assertEqual(len(record['cases']),4)
            self.assertFalse(record['simulator_executed'])
            self.assertEqual((output/'frozen/files/dut.va').read_bytes(),(adapter.TASK/'solution/reference.va').read_bytes())
            _,packages,remote=adapter.load_harness(HARNESS)
            for case in record['cases']:
                identity=packages.package_identity(Path(case['package']),purpose='final')
                self.assertEqual(identity['sha256'],case['sha256'])
                payload=remote.transfer_payload(output/'frozen',Path(case['package']))
                self.assertEqual(set(payload),{'candidate','task-package'})
                self.assertEqual(len(json.loads((Path(case['package'])/'tests/cases.json').read_text())),1)

    def test_process_fixture_writes_private_paths_and_produces_harness_grade(self):
        # A process fixture checks runtime file plumbing, not Verilog-A semantics.
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder);case,hits,rows=fixtures.fixture()
            verifier=work/'verify.py';verifier.write_bytes((adapter.TASK/'tests/verify.py').read_bytes())
            (work/'cases.json').write_text(json.dumps([case]))
            fixtures.write_csv(work/'linearity.csv',hits)
            with (work/'samples.csv').open('w') as stream:
                stream.write('index,time,code\n')
                codes=[k for k,h in enumerate(hits) for _ in range(h)]
                for n,code in enumerate(codes): stream.write(f'{n},{checker.T0+(n+.75)*checker.T:.17g},{code}\n')
            with (work/'fixture.psf').open('w') as stream:
                stream.write('HEADER\nVALUE\n')
                for row in rows:
                    for key,value in row.items(): stream.write(f'"{key}" {value:.17g}\n')
                stream.write('END\n')
            program=work/'spectre-fixture'
            program.write_text('#!'+sys.executable+'\n'+
                'import pathlib,re,shutil,sys\n'
                'if "-W" in sys.argv: print("PROCESS FIXTURE, NOT SPECTRE"); sys.exit(0)\n'
                f'fixtures=pathlib.Path({str(work)!r})\n'
                'source=pathlib.Path("dut.va").read_text()\n'
                'assert "/work/output/" not in source\n'
                'paths=re.findall(r\'\\$fopen\\s*\\(\\s*"([^\\"]+)"\',source)\n'
                'for name in ["linearity.csv","samples.csv"]:\n'
                ' target=next(path for path in paths if path.endswith("/"+name))\n'
                ' shutil.copyfile(fixtures/name,target)\n'
                'pathlib.Path("psf").mkdir()\n'
                'shutil.copyfile(fixtures/"fixture.psf","psf/tran.tran.tran")\n')
            program.chmod(0o755);output=work/'result'
            run=subprocess.run([sys.executable,'-B',str(verifier),'--candidate',str(adapter.TASK/'solution/reference.va'),'--output',str(output)],
                env={**os.environ,'SPECTRE':str(program)},capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            report=json.loads((output/'report.json').read_text());self.assertEqual(report['reward'],1,report)
            self.assertEqual(report['cases'][0]['original_source_sha256'],report['candidate_sha256'])
            self.assertNotEqual(report['cases'][0]['executed_source_sha256'],report['candidate_sha256'])
            _,packages,_=adapter.load_harness(HARNESS)
            self.assertEqual(packages.project_report(report,purpose='final',feedback_fields=[])['execution'],'ok')

    def test_incomplete_execution_cannot_become_score(self):
        self.assertIsNone(adapter.aggregate([{'execution':'unclassified_failure','score':None}])['reward'])
        self.assertEqual(adapter.aggregate([{'execution':'ok','score':1},{'execution':'ok','score':0}])['reward'],0)
        self.assertEqual(adapter.aggregate([{'execution':'ok','score':1}])['reward'],1)

if __name__=='__main__': unittest.main()
