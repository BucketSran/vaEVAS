"""Temporary Git fixtures exercise immutable export bytes, never scientific code."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import git_fixture

FILE=Path(__file__).resolve().parents[1]/'capabilities/observe_assets.py'
spec=importlib.util.spec_from_file_location('asset_observer_under_test',FILE)
observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)

class ImmutableObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name);git_fixture.bind(self,self.parent);self.repo=self.parent/'repository';self.repo.mkdir()
        self.git('init','-q')
        (self.repo/'input.txt').write_bytes(b'immutable fixture\n')
        (self.repo/'nested').mkdir();(self.repo/'nested/run.py').write_bytes(b'print("data only")\n')
        self.git('add','.');self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture');self.commit=self.git('rev-parse','HEAD').strip()
        self.export=self.parent/'export';shutil.copytree(self.repo,self.export,ignore=shutil.ignore_patterns('.git'))

    def git(self,*args):
        return git_fixture.run(['-C',str(self.repo),*args],scratch=self.parent,stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL,text=True,check=True).stdout

    def observe(self,**kwargs):
        return observer.observe(self.export,source_repository=self.repo,source_revision=self.commit,**kwargs)

    def test_actual_immutable_export_verifies_commit_tree_blob_and_preserves_untracked_boundary(self):
        (self.export/'untracked.txt').write_text('not in immutable tree')
        actual=self.observe()
        self.assertEqual(actual['source_kind'],'immutable-export');self.assertEqual(actual['source_commit'],self.commit)
        self.assertEqual(actual['source_tree'],self.git('rev-parse',self.commit+'^{tree}').strip())
        self.assertEqual(actual['source_availability'],'local-only')
        self.assertEqual(actual['source_object_format'],'sha1')
        self.assertEqual(actual['content_binding'],'verified-git-blob-oids')
        self.assertEqual([r['path'] for r in actual['assets']],['input.txt','nested/run.py'])
        self.assertEqual(actual['scope']['untracked'],'excluded-explicitly')
        for row in actual['assets']:
            self.assertEqual(row['git_blob_oid'],self.git('rev-parse',self.commit+':'+row['path']).strip())
        self.assertFalse((self.export/'receipt.json').exists())

    def test_dirty_export_bytes_missing_file_and_nonregular_file_are_rejected(self):
        target=self.export/'input.txt';target.write_bytes(b'changed actual bytes\n')
        with self.assertRaises(ValueError):self.observe()
        target.unlink()
        with self.assertRaises(ValueError):self.observe()
        target.symlink_to(self.repo/'input.txt')
        with self.assertRaises(ValueError):self.observe()

    def test_symbolic_parent_in_export_and_nonregular_git_tree_are_rejected(self):
        shutil.rmtree(self.export/'nested');(self.export/'nested').symlink_to(self.repo/'nested',target_is_directory=True)
        with self.assertRaises(ValueError):self.observe()
        (self.repo/'link').symlink_to('input.txt');self.git('add','link')
        self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','link');commit=self.git('rev-parse','HEAD').strip()
        with self.assertRaises(ValueError):observer.observe(self.repo,source_repository=self.repo,source_revision=commit)

    def test_exact_revision_is_mandatory_paired_full_nonzero_and_no_fallback(self):
        for revision in (self.commit[:12],'HEAD','0'*40,'f'*40):
            with self.assertRaises(ValueError):observer.observe(self.export,source_repository=self.repo,source_revision=revision)
        with self.assertRaises(ValueError):observer.observe(self.export,source_repository=self.repo)
        with self.assertRaises(ValueError):observer.observe(self.export,source_revision=self.commit)

    def test_default_worktree_reports_dirty_actual_bytes_and_explicit_untracked_boundary(self):
        (self.repo/'input.txt').write_bytes(b'dirty checkout bytes\n')
        (self.repo/'untracked.txt').write_bytes(b'untracked\n')
        actual=observer.observe(self.repo)
        self.assertEqual(actual['source_kind'],'worktree');self.assertEqual(actual['source_commit'],self.commit)
        self.assertEqual(actual['source_commit_relationship'],'head-context-only')
        self.assertEqual(actual['dirty_paths'],['input.txt'])
        self.assertEqual(actual['content_binding'],'actual-checkout-bytes-not-commit-identity')
        self.assertNotIn('untracked.txt',[r['path'] for r in actual['assets']])
        row=next(r for r in actual['assets'] if r['path']=='input.txt')
        import hashlib
        self.assertEqual(row['sha256'],hashlib.sha256(b'dirty checkout bytes\n').hexdigest())

    def test_full_blob_oid_cannot_be_supplied_in_place_of_commit(self):
        blob=self.git('rev-parse',self.commit+':input.txt').strip()
        with self.assertRaises(ValueError):observer.observe(self.export,source_repository=self.repo,source_revision=blob)

    def test_cli_export_mode_does_not_need_git_in_export_directory(self):
        self.assertFalse((self.export/'.git').exists())
        result=subprocess.run([sys.executable,'-B',str(FILE),'--root',str(self.export),'--source-repository',str(self.repo),'--source-revision',self.commit],env=git_fixture.child_env(),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['source_commit'],self.commit)
        invalid=subprocess.run([sys.executable,'-B',str(FILE),'--root',str(self.export),'--source-revision',self.commit],env=git_fixture.child_env(),capture_output=True,text=True)
        self.assertNotEqual(invalid.returncode,0)

    def test_sha256_repository_object_format_is_used_for_actual_git_blob_verification(self):
        repo=self.parent/'sha256-repository'
        result=git_fixture.run(['init','-q','--object-format=sha256',str(repo)],scratch=self.parent,capture_output=True,text=True)
        if result.returncode:self.skipTest('installed Git lacks SHA256 repository support')
        self.repo=repo
        (repo/'data.txt').write_bytes(b'sha256 object fixture\n')
        self.git('add','data.txt');self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','sha256')
        commit=self.git('rev-parse','HEAD').strip()
        exported=self.parent/'sha256-export';shutil.copytree(repo,exported,ignore=shutil.ignore_patterns('.git'))
        actual=observer.observe(exported,source_repository=repo,source_revision=commit)
        self.assertEqual(actual['source_object_format'],'sha256');self.assertEqual(len(actual['source_commit']),64)
        self.assertEqual(actual['assets'][0]['git_blob_oid'],self.git('rev-parse',commit+':data.txt').strip())
        with self.assertRaises(ValueError):observer.observe(exported,source_repository=repo,source_revision='a'*40)

    def test_selected_commit_not_source_repository_head_or_dirty_checkout_controls_export(self):
        (self.repo/'later.txt').write_bytes(b'later commit data\n');self.git('add','later.txt')
        self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','later commit')
        self.assertNotEqual(self.git('rev-parse','HEAD').strip(),self.commit)
        (self.repo/'input.txt').write_bytes(b'dirty source repository checkout\n')
        index=self.repo/'.git/index';before=index.read_bytes()
        actual=self.observe()
        self.assertEqual(actual['source_commit'],self.commit)
        self.assertNotIn('later.txt',[r['path'] for r in actual['assets']])
        self.assertEqual(index.read_bytes(),before)
        self.assertEqual((self.repo/'input.txt').read_bytes(),b'dirty source repository checkout\n')

    def test_default_staged_rename_reports_both_paths_without_modifying_index(self):
        self.git('mv','input.txt','renamed.txt')
        index=self.repo/'.git/index';before=index.read_bytes()
        actual=observer.observe(self.repo)
        self.assertEqual(actual['dirty_paths'],['input.txt','renamed.txt'])
        self.assertIn('renamed.txt',[r['path'] for r in actual['assets']])
        self.assertEqual(index.read_bytes(),before)
