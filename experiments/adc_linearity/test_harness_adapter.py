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
    def test_private_workspace_rejects_visible_mount_overlap_and_symlink_alias(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);visible=root/'trial';visible.mkdir()
            private=root/'private';private.mkdir(mode=0o700)
            work=adapter.private_workspace(private,[visible],'adc-probe')
            self.assertTrue(work.is_relative_to(private.resolve()))
            exposed=visible/'private';exposed.mkdir(mode=0o700)
            with self.assertRaises(ValueError): adapter.private_workspace(exposed,[visible],'bad')
            alias=root/'visible-alias';alias.symlink_to(private,target_is_directory=True)
            with self.assertRaises(ValueError): adapter.private_workspace(private,[alias],'bad-alias')
            with self.assertRaises(ValueError): adapter.private_workspace(private,[root],'bad-parent')

    def test_source_relocation_preserves_crlf_and_inactive_examples(self):
        source=(adapter.TASK/'solution/reference.va').read_bytes().replace(b'\n',b'\r\n')
        source+=b'// never $fopen("secret.txt","r") or $system.\r\n'
        with tempfile.TemporaryDirectory() as folder:
            executed,receipt=checker.relocate_output_paths(source,folder)
            restored=executed
            for original,new in receipt['mapping'].items(): restored=restored.replace(new.encode(),original.encode())
            self.assertEqual(restored,source)
            self.assertTrue(receipt['inverse_verified'])
            self.assertEqual(executed.count(b'\r\n'),source.count(b'\r\n'))

    def test_active_calls_and_directives_are_identified_without_comment_or_string_false_positives(self):
        reference=(adapter.TASK/'solution/reference.va').read_bytes()
        legal=reference+b'\n// $fopen("secret","r") $system("ls")\n/* `include "secret" */\n'
        legal+=b'string note="$fopen(\\"secret\\",\\"r\\")";\n'
        self.assertEqual(len(checker.source_contract(legal)),2)
        for extra in [b' $system("ls");',b' $fopen("secret","r");',b' `define NAME $system',b' `include "secret"']:
            with self.subTest(extra=extra),self.assertRaises(ValueError): checker.source_contract(reference+extra)

    def test_relocation_changes_only_two_allowed_path_tokens(self):
        source=(adapter.TASK/'solution/reference.va').read_text()
        with tempfile.TemporaryDirectory() as folder:
            executed,receipt=checker.relocate_output_paths(source,folder)
            restored=executed
            for original,new in receipt['mapping'].items(): restored=restored.replace('"'+new+'"','"'+original+'"')
            self.assertEqual(restored,source)
            self.assertNotEqual(executed,source)
            self.assertEqual(receipt['version'],'adc-output-paths-v2')
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
            self.assertEqual(report['status'],'completed')

    @unittest.skipUnless(HARNESS.is_dir(),'explicit local circuit harness absent')
    def test_completed_report_projects_through_real_harness(self):
        _,packages,_=adapter.load_harness(HARNESS)
        report=dict(status='completed',reward=1,cases=[dict(status='graded',passed=True)])
        self.assertEqual(packages.project_report(report,purpose='final',feedback_fields=[])['execution'],'ok')

    def test_final_projection_excludes_private_result_and_does_not_follow_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);output=root/'visible';output.mkdir()
            target=root/'private';target.write_text('preserve')
            (output/'report.json').symlink_to(target)
            adapter.publish_result(output,dict(status='completed',reward=1,results=[{'hidden':'secret'}]))
            self.assertEqual(target.read_text(),'preserve')
            self.assertEqual(json.loads((output/'report.json').read_text()),{'status':'completed','reward':1})
            self.assertEqual(sorted(p.name for p in output.iterdir()),['report.json','reward.txt'])

    def test_all_hidden_thresholds_differ_from_public_development_devices(self):
        import re
        public=[]
        for path in (adapter.TASK/'environment/public').glob('*_adc.va'):
            public.append([float(v) for v in re.findall(r'if \(V\(vin\) >= ([^\)]+)\)',path.read_text())])
        cases=json.loads((adapter.TASK/'tests/cases.json').read_text())
        self.assertEqual(len(cases),4)
        for case in cases:
            self.assertNotIn(case['thresholds'],public)
            self.assertEqual(len(case['thresholds']),255)
            self.assertEqual(case['thresholds'],sorted(case['thresholds']))

    def test_incomplete_execution_cannot_become_score(self):
        self.assertIsNone(adapter.aggregate([{'execution':'unclassified_failure','score':None}])['reward'])
        self.assertEqual(adapter.aggregate([{'execution':'ok','score':1},{'execution':'ok','score':0}])['reward'],0)
        self.assertEqual(adapter.aggregate([{'execution':'ok','score':1}])['reward'],1)

if __name__=='__main__': unittest.main()
