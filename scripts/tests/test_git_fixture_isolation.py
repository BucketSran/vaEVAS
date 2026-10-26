"""Negative control for inherited Git location and config injection.

The two repositories created here are the only red-case repositories. Their
linked worktrees are fixture checkouts of those repositories, and every resolved
common dir and work tree stays inside this scratch. The unfixed command path is
marked intentional-unfixed-incident and keeps the process stdout, stderr, and
return code.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import git_fixture


INCIDENT = (
    ['git', 'init', '-q'],
    ['git', 'config', 'user.email', 'ci-test@example.invalid'],
    ['git', 'config', 'user.name', 'CI Test'],
    ['git', 'config', 'commit.gpgsign', 'false'],
)


def _clean_env():
    return {key: value for key, value in os.environ.items() if not git_fixture.injected(key)}


def _run(argv, cwd, env):
    completed = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True)
    return {'argv': argv, 'cwd': str(cwd), 'returncode': completed.returncode,
            'stdout': completed.stdout, 'stderr': completed.stderr}


def _git(argv, cwd, env):
    record = _run(argv, cwd, env)
    if record['returncode'] != 0:
        raise AssertionError(json.dumps(record))
    return record


def _sha(path):
    file = Path(path)
    if not file.exists():
        return None
    return hashlib.sha256(file.read_bytes()).hexdigest()


def _manifest(root):
    rows = []
    root = Path(root)
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            rows.append(['symlink', relative, os.readlink(path)])
        elif path.is_file():
            rows.append(['file', relative, _sha(path), path.stat().st_mode])
        else:
            rows.append(['dir', relative])
    return rows


def _resolved_identity(worktree, env):
    git_dir = subprocess.check_output(
        ['git', '-C', str(worktree), 'rev-parse', '--absolute-git-dir'], env=env, text=True).strip()
    common = subprocess.check_output(
        ['git', '-C', str(worktree), 'rev-parse', '--path-format=absolute', '--git-common-dir'],
        env=env, text=True).strip()
    head = subprocess.check_output(
        ['git', '--git-dir', git_dir, '--work-tree', str(worktree), 'rev-parse', 'HEAD'],
        env=env, text=True).strip()
    return {'git_dir': str(Path(git_dir).resolve()), 'common_dir': str(Path(common).resolve()),
            'work_tree': str(Path(worktree).resolve()), 'head': head}


def _inside(path, scratch):
    Path(path).resolve().relative_to(Path(scratch).resolve())


def _create_linked(repo, worktree, env, records):
    repo.mkdir(parents=True)
    records.append(_git(['git', 'init', '-q', '-b', 'main'], repo, env))
    (repo / 'keep.txt').write_text('baseline\n')
    records.append(_git(['git', '-C', str(repo), 'add', 'keep.txt'], repo, env))
    records.append(_git(['git', '-C', str(repo), '-c', 'user.name=Sentinel',
                         '-c', 'user.email=sentinel@example.invalid', 'commit', '-qm', 'base'], repo, env))
    records.append(_run(['git', '-C', str(repo), 'worktree', 'add', '-b', 'task', str(worktree)], repo, env))
    if records[-1]['returncode'] != 0:
        raise AssertionError(json.dumps(records[-1]))
    identity = _resolved_identity(worktree, env)
    return identity


def _poison(identity):
    common = Path(identity['common_dir'])
    git_dir = Path(identity['git_dir'])
    return {
        'GIT_DIR': str(git_dir),
        'GIT_WORK_TREE': identity['work_tree'],
        'GIT_COMMON_DIR': str(common),
        'GIT_INDEX_FILE': str(git_dir / 'index'),
        'GIT_OBJECT_DIRECTORY': str(common / 'objects'),
        'GIT_ALTERNATE_OBJECT_DIRECTORIES': str(common / 'objects'),
        'GIT_CONFIG_GLOBAL': str(common / 'config'),
        'GIT_CONFIG_COUNT': '1',
        'GIT_CONFIG_KEY_0': 'user.name',
        'GIT_CONFIG_VALUE_0': 'poisoned-sentinel',
        'GIT_CONFIG_PARAMETERS': "'core.commentChar=;'",
    }


class GitFixtureIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        retain = os.environ.get('GIT_FIXTURE_RETAIN_DIR')
        if retain:
            cls.retain = Path(retain).resolve()
            cls.retain.mkdir(parents=True, exist_ok=False)
        else:
            cls.retain = Path(tempfile.mkdtemp(prefix='vaevas-git-fixture-isolation-'))
        print('Git fixture evidence retained at ' + str(cls.retain), flush=True)
        cls.env = _clean_env()
        cls.setup_records = []
        cls.red = _create_linked(cls.retain / 'red-repo', cls.retain / 'red-worktree', cls.env, cls.setup_records)
        cls.hold = _create_linked(cls.retain / 'hold-repo', cls.retain / 'hold-worktree', cls.env, cls.setup_records)
        for identity in (cls.red, cls.hold):
            _inside(identity['git_dir'], cls.retain)
            _inside(identity['common_dir'], cls.retain)
            _inside(identity['work_tree'], cls.retain)
        cls.hold_before = {'repo': _manifest(cls.retain / 'hold-repo'),
                           'worktree': _manifest(cls.retain / 'hold-worktree')}
        cls.receipt = {'red_commands': None, 'escapes': [], 'green': None}

    @classmethod
    def tearDownClass(cls):
        path = os.environ.get('GIT_FIXTURE_ISOLATION_RECEIPT', str(cls.retain / 'receipt.json'))
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {'retain': str(cls.retain.resolve()), 'red': cls.red, 'hold': cls.hold,
                   'setup_records': cls.setup_records, **cls.receipt}
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')

    def _incident_config(self):
        return Path(self.red['common_dir'], 'config').read_text()

    def test_unfixed_incident_writes_linked_worktree_common_config(self):
        """intentional-unfixed-incident: raw Git inherits the sentinel location."""
        head = self.red['head']
        keep = (Path(self.red['work_tree']) / 'keep.txt').read_text()
        index = _sha(Path(self.red['git_dir']) / 'index')
        cwd = self.retain / 'incident-cwd'
        cwd.mkdir(exist_ok=True)
        env = dict(self.env)
        env['GIT_DIR'] = self.red['git_dir']
        env['GIT_WORK_TREE'] = self.red['work_tree']
        records = [_run(argv, cwd, env) for argv in INCIDENT]  # intentional-unfixed-incident
        self.receipt['red_commands'] = records
        for record in records:
            self.assertEqual(record['returncode'], 0, record)
            self.assertEqual(record['stdout'], '')
            self.assertEqual(record['stderr'], '')
        self.assertFalse((cwd / '.git').exists())
        config = self._incident_config()
        self.assertIn('email = ci-test@example.invalid', config)
        self.assertIn('name = CI Test', config)
        self.assertIn('gpgsign = false', config)
        import re
        match = re.search(r'(?m)^[ \t]*worktree = (.+)$', config)
        self.assertIsNotNone(match)
        self.assertEqual(Path(match.group(1).strip()).resolve(), Path(self.red['work_tree']).resolve())
        self.assertEqual((Path(self.red['work_tree']) / 'keep.txt').read_text(), keep)
        after = _resolved_identity(self.red['work_tree'], self.env)
        self.assertEqual(after['head'], head)
        self.assertEqual(_sha(Path(self.red['git_dir']) / 'index'), index)
        _inside(after['common_dir'], self.retain)
        _inside(after['work_tree'], self.retain)

    def test_gitfile_and_symlink_targets_are_refused(self):
        scratch = self.retain / 'escape-scratch'
        fake = scratch / 'fake'
        fake.mkdir(parents=True)
        (fake / '.git').write_text('gitdir: ' + self.hold['git_dir'] + '\n')
        with self.assertRaises(git_fixture.GitFixtureBoundary):
            git_fixture.run(['config', 'user.name', 'escaped'], cwd=fake, scratch=scratch,
                            capture_output=True, text=True)
        linked = scratch / 'linked-dotgit'
        linked.mkdir()
        (linked / '.git').symlink_to(self.hold['git_dir'], target_is_directory=True)
        with self.assertRaises(git_fixture.GitFixtureBoundary):
            git_fixture.run(['config', 'user.email', 'escaped@example.invalid'], cwd=linked,
                            scratch=scratch, capture_output=True, text=True)
        escaped = scratch / 'init-link'
        escaped.symlink_to(self.hold['work_tree'], target_is_directory=True)
        with self.assertRaises(git_fixture.GitFixtureBoundary):
            git_fixture.run(['init', '-q', str(escaped)], scratch=scratch, capture_output=True, text=True)
        self.assertEqual({'repo': _manifest(self.retain / 'hold-repo'),
                          'worktree': _manifest(self.retain / 'hold-worktree')}, self.hold_before)
        self.receipt['escapes'] = ['gitfile', 'dotgit-symlink', 'init-symlink']

    def test_fixed_incident_fixture_and_select_leave_hold_sentinel(self):
        import test_ci_selection as selection
        saved = os.environ.copy()
        os.environ.update(_poison(self.hold))
        try:
            case = selection.GitChangeTests()
            case.setUp()
            try:
                case.write('evas/docs/new.md', 'maintenance fixture\n')
                head = case.commit()
                self.assertRegex(head, r'^[0-9a-f]{40}$')
                plan = selection.ci.select(case.repo, 'push', {'before': case.base, 'after': head})
                self.assertEqual(plan['paths'], ['evas/docs/new.md'])
                event = case.repo / 'event.json'
                event.write_text(json.dumps({'before': case.base, 'after': head}))
                completed = subprocess.run(
                    [sys.executable, '-B', str(selection.SCRIPT), 'select', '--repo', str(case.repo),
                     '--event-name', 'push', '--event-path', str(event), '--json'],
                    env=git_fixture.child_env(), capture_output=True, text=True, check=True)
                self.assertFalse(json.loads(completed.stdout)['regression'])
                self.receipt['green'] = {'fixture_head': head, 'select_paths': plan['paths'],
                                         'cli_returncode': completed.returncode,
                                         'cli_stdout': completed.stdout, 'cli_stderr': completed.stderr}
            finally:
                case.doCleanups()
        finally:
            os.environ.clear()
            os.environ.update(saved)
        self.assertEqual({'repo': _manifest(self.retain / 'hold-repo'),
                          'worktree': _manifest(self.retain / 'hold-worktree')}, self.hold_before)

    def test_poisoned_fixture_entrypoints_leave_hold_sentinel(self):
        import test_asset_observer
        import test_ci_evidence_v3
        import test_discover_rust
        import test_fast_feedback
        import test_independent_ci
        import test_regression_admission
        import test_regression_gate
        import test_regression_input_subject
        import test_registration_bundle
        import test_rust_catalog_reconcile
        import test_trusted_regression_gate
        import test_workspaces
        saved = os.environ.copy()
        os.environ.update(_poison(self.hold))
        exercised = []
        try:
            classes = (
                test_independent_ci.IndependentDelivery,
                test_workspaces.WorkspaceChecks,
                test_trusted_regression_gate.TrustedLoaderTests,
                test_discover_rust.RustListingTests,
                test_asset_observer.ImmutableObserverTests,
                test_regression_input_subject.SubjectProducerTests,
                test_ci_evidence_v3.EvidenceV3Tests,
                test_registration_bundle.BundleWorkflowTests,
                test_rust_catalog_reconcile.RustCatalogReconciliation,
            )
            for cls in classes:
                case = cls('setUp')
                try:
                    case.setUp()
                    exercised.append(cls.__name__ + '.setUp')
                finally:
                    case.doCleanups()
            methods = (
                (test_fast_feedback.EvidenceIdentity,
                 'test_changed_code_tests_tools_or_budget_invalidates_evidence'),
                (test_fast_feedback.GitDraftStages,
                 'test_incremental_draft_and_ready_use_different_scopes'),
                (test_fast_feedback.ReceiptRoundTrip,
                 'test_real_report_round_trip_rejects_corruption_drift_and_failed_results'),
                (test_regression_gate.GateTests,
                 'test_cli_reads_trusted_commit_and_inactive_cannot_allow'),
                (test_regression_admission.AdmissionIntegrationTests,
                 'test_actual_coverage_then_admission_commands_preserve_raw_failure_and_reject_drift'),
                (test_registration_bundle.BundleMaterializationTests,
                 'test_partial_clone_missing_blobs_are_not_fetched'),
            )
            for cls, name in methods:
                case = cls(name)
                case.setUp()
                try:
                    getattr(case, name)()
                finally:
                    case.doCleanups()
                exercised.append(cls.__name__ + '.' + name)
        finally:
            os.environ.clear()
            os.environ.update(saved)
        self.receipt['exercised'] = exercised
        self.assertEqual({'repo': _manifest(self.retain / 'hold-repo'),
                          'worktree': _manifest(self.retain / 'hold-worktree')}, self.hold_before)
        self.assertGreaterEqual(len(exercised), 15)

    def _refused(self, argv, cwd, scratch):
        try:
            completed = git_fixture.run(argv, cwd=cwd, scratch=scratch, capture_output=True, text=True)
        except git_fixture.GitFixtureBoundary as error:
            return {'raised': type(error).__name__, 'message': str(error)}
        return {'raised': None, 'returncode': completed.returncode,
                'stdout': completed.stdout, 'stderr': completed.stderr}

    def test_stored_worktree_redirect_is_refused(self):
        root = self.retain / 'stored-worktree'
        repo, outside = root / 'inside', root / 'outside'
        repo.mkdir(parents=True)
        outside.mkdir()
        git_fixture.run(['init', '-q'], cwd=repo, scratch=repo, check=True)
        (outside / 'keep.txt').write_text('outside the owning fixture\n')
        with (repo / '.git/config').open('a') as stream:
            stream.write('\n[core]\n\tworktree = ' + str(outside) + '\n')
        before = _manifest(outside)
        record = self._refused(['add', 'keep.txt'], repo, repo)
        self.receipt['stored_worktree_redirect'] = record
        self.assertEqual(record['raised'], 'GitFixtureBoundary', record)
        self.assertEqual(_manifest(outside), before)

    def test_init_checks_existing_common_dir(self):
        root = self.retain / 'init-common-dir'
        repo, outside = root / 'inside', root / 'outside'
        repo.mkdir(parents=True)
        outside.mkdir()
        git_fixture.run(['init', '-q'], cwd=outside, scratch=outside, check=True)
        metadata = repo / '.git'
        metadata.mkdir()
        (metadata / 'HEAD').write_text('ref: refs/heads/main\n')
        (metadata / 'commondir').write_text(str(outside / '.git') + '\n')
        before = _manifest(outside)
        record = self._refused(['init', '-q'], repo, repo)
        self.receipt['init_existing_common_dir'] = record
        self.assertEqual(record['raised'], 'GitFixtureBoundary', record)
        self.assertEqual(_manifest(outside), before)

    def test_explicit_redirects_and_worktree_commitish_cannot_leave_scratch(self):
        root = self.retain / 'boundary-probes'
        allowed = root / 'init-allowed'
        allowed.mkdir(parents=True)
        outside_git = root / 'init-outside.git'
        init_record = self._refused(
            ['--git-dir=' + str(outside_git), '--work-tree=' + str(allowed), 'init', '-q'],
            allowed, allowed)
        self.assertEqual(init_record['raised'], 'GitFixtureBoundary')
        self.assertIn('git dir escapes', init_record['message'])
        self.assertFalse(outside_git.exists())

        repo = root / 'worktree-allowed'
        repo.mkdir()
        git_fixture.run(['init', '-q', '-b', 'main'], cwd=repo, scratch=repo, check=True,
                        capture_output=True)
        (repo / 'keep.txt').write_text('baseline\n')
        git_fixture.run(['add', 'keep.txt'], cwd=repo, scratch=repo, check=True, capture_output=True)
        git_fixture.run(['-c', 'user.name=Sentinel', '-c', 'user.email=sentinel@example.invalid',
                         'commit', '-qm', 'scratch fixture'],
                        cwd=repo, scratch=repo, check=True, capture_output=True)
        outside_worktree = root / 'worktree-outside'
        worktree_record = self._refused(
            ['worktree', 'add', '--detach', str(outside_worktree), 'HEAD'], repo, repo)
        self.assertEqual(worktree_record['raised'], 'GitFixtureBoundary')
        self.assertIn('worktree path escapes', worktree_record['message'])
        self.assertFalse(outside_worktree.exists())

        decoy = allowed / 'decoy-git'
        decoy.mkdir()
        (decoy / 'HEAD').write_text('ref: refs/heads/main\n')
        outside_common = root / 'common-outside'
        outside_common.mkdir()
        (decoy / 'commondir').write_text(str(outside_common.resolve()) + '\n')
        common_record = self._refused(
            ['--git-dir', str(decoy), 'status', '--porcelain'], allowed, allowed)
        self.assertEqual(common_record['raised'], 'GitFixtureBoundary')
        self.assertIn('common dir escapes', common_record['message'])
        self.assertEqual(list(outside_common.iterdir()), [])

        inner = allowed / 'inner'
        git_fixture.run(['init', '-q', '-b', 'main', str(inner)], cwd=allowed, scratch=allowed,
                        check=True, capture_output=True)
        outside_tree = root / 'worktree-redirect'
        tree_record = self._refused(
            ['--git-dir', str(inner / '.git'), '--work-tree', str(outside_tree), 'status', '--porcelain'],
            allowed, allowed)
        self.assertEqual(tree_record['raised'], 'GitFixtureBoundary')
        self.assertIn('work tree escapes', tree_record['message'])
        self.assertFalse(outside_tree.exists())
        config_record = self._refused(
            ['config', 'core.worktree', str(outside_tree)], inner, allowed)
        self.assertEqual(config_record['raised'], 'GitFixtureBoundary')
        self.assertIn('work tree escapes', config_record['message'])

        linked = root / 'supported-linked'
        git_fixture.run(['-C', str(repo), 'worktree', 'add', '-b', 'task', str(linked)],
                        scratch=root, check=True, capture_output=True, text=True)
        self.assertTrue((linked / 'keep.txt').is_file())
        self.receipt['boundary_probes'] = {
            'explicit-git-dir-init-escape': init_record,
            'worktree-path-before-commit-escape': worktree_record,
            'common-dir-redirect': common_record,
            'work-tree-redirect': tree_record,
            'config-worktree-redirect': config_record,
            'supported_worktree_add': True,
        }
        self.assertEqual({'repo': _manifest(self.retain / 'hold-repo'),
                          'worktree': _manifest(self.retain / 'hold-worktree')}, self.hold_before)


if __name__ == '__main__':
    unittest.main()
