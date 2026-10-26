"""Actual Git staging/file-mode tests for the fingerprint subject producer."""
import copy
import importlib.util
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
D=Path(__file__).resolve().parent
SOURCE=D.parent/'ci_evidence.py'
spec=importlib.util.spec_from_file_location('actual_subject_producer',SOURCE);producer=importlib.util.module_from_spec(spec);spec.loader.exec_module(producer)

class SubjectProducerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=D);self.root=Path(self.temp.name)
        subprocess.run(['git','init',str(self.root)],check=True,capture_output=True)
        self.files={'evas/validation/baselines/regression-v1.json':'baseline-A','evas/validation/baselines/regression-v1.review.json':'review-A','config/settings.json':'real-config','evas/src/dut_fixture.py':'real-DUT'}
        for name,text in self.files.items():
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);p.chmod(0o644)
        subprocess.run(['git','-C',str(self.root),'add','.'],check=True,capture_output=True)
        self.env={'tool':'actual-fixture-tool-1','kernel_sha256':None,'variables':{'fixture':'yes'},'shard':'0-of-2'}
    def tearDown(self):self.temp.cleanup()
    def fp(self,env=None):return producer.fingerprint(self.root,env or self.env)
    def test_only_two_baseline_files_are_non_circular_and_full_key_keeps_them(self):
        before=self.fp()
        for name in list(self.files)[:2]:(self.root/name).write_text('updated-'+self.files[name])
        after=self.fp()
        self.assertNotEqual(before['key'],after['key'])
        self.assertEqual(before['comparison_subject'],after['comparison_subject'])
        self.assertEqual(before['comparison_subject']['input_count'],2)
        self.assertEqual(before['comparison_subject']['excluded_baseline_paths'],['evas/validation/baselines/regression-v1.json','evas/validation/baselines/regression-v1.review.json'])
    def test_other_config_changes_comparison_subject(self):
        before=self.fp();(self.root/'config/settings.json').write_text('changed-real-config')
        self.assertNotEqual(before['comparison_subject'],self.fp()['comparison_subject'])
    def test_new_tracked_file_changes_comparison_subject(self):
        before=self.fp();(self.root/'config/new.json').write_text('new-input')
        subprocess.run(['git','-C',str(self.root),'add','config/new.json'],check=True,capture_output=True)
        self.assertNotEqual(before['comparison_subject'],self.fp()['comparison_subject'])
    def test_actual_file_mode_is_bound_even_when_Git_index_mode_stays(self):
        before=self.fp();(self.root/'config/settings.json').chmod(0o600)
        self.assertNotEqual(before['comparison_subject'],self.fp()['comparison_subject'])
    def test_Git_index_mode_is_bound_separately_from_actual_file_mode(self):
        before=self.fp()
        subprocess.run(['git','-C',str(self.root),'update-index','--chmod=+x','config/settings.json'],check=True,capture_output=True)
        self.assertEqual(stat.S_IMODE((self.root/'config/settings.json').stat().st_mode),0o644)
        self.assertNotEqual(before['comparison_subject'],self.fp()['comparison_subject'])
    def test_environment_only_excludes_shard(self):
        before=self.fp();env=copy.deepcopy(self.env);env['shard']='1-of-2';other_shard=self.fp(env)
        self.assertNotEqual(before['key'],other_shard['key'])
        self.assertEqual(before['comparison_subject'],other_shard['comparison_subject'])
        env['tool']='different-tool'
        self.assertNotEqual(before['comparison_subject'],self.fp(env)['comparison_subject'])
    def test_another_file_in_baseline_directory_is_retained(self):
        before=self.fp();p=self.root/'evas/validation/baselines/other-policy.json';p.write_text('must-bind')
        subprocess.run(['git','-C',str(self.root),'add',str(p.relative_to(self.root))],check=True,capture_output=True)
        after=self.fp();self.assertNotEqual(before['comparison_subject'],after['comparison_subject'])
        self.assertEqual(after['comparison_subject']['input_count'],3)

if __name__=='__main__':unittest.main()
