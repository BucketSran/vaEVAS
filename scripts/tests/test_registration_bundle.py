"""Exercise bundle consumption through the actual fixed-bootstrap workflow."""
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

import git_fixture
import regression_registration_fixtures as fixtures

ROOT = Path(__file__).resolve().parents[2]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

support = module('bundle_loader_test_support', ROOT/'scripts/tests/test_trusted_regression_gate.py')
admission = module('bundle_workflow_test_support', ROOT/'scripts/tests/test_regression_admission.py')
HELPER = 'scripts/materialize_registration_bundle.py'
POINTER = 'scripts/context-registration-bundle.json'
BASELINE = support.BASELINE_PATH
materializer = module('bundle_materializer', ROOT/HELPER)


class BundleWorkflowTests(unittest.TestCase):
    git = support.TrustedLoaderTests.git
    write = support.TrustedLoaderTests.write
    commit = support.TrustedLoaderTests.commit
    workflow_job = admission.AdmissionIntegrationTests.workflow_job
    run_body = admission.AdmissionIntegrationTests.run_body
    pin_body = admission.AdmissionIntegrationTests.pin_body

    def setUp(self):
        support.TrustedLoaderTests.setUp(self)
        self.fixture = fixtures.make_fixture()
        self.write('scripts/run_trusted_regression_gate.py', support.LOADER.read_bytes())
        self.write('scripts/regression_context_registration.py',
                   (ROOT/'scripts/regression_context_registration.py').read_bytes())
        self.write(HELPER, (ROOT/HELPER).read_bytes())
        self.write(BASELINE, fixtures.raw(self.fixture['baseline']))
        self.write(fixtures.api.REVIEW, fixtures.raw(self.fixture['review']))
        self.write('archive/report.json', self.fixture['e1_bytes'])
        for role, raw in self.fixture['blobs'].items():
            self.write('archive/'+role, raw)
        archive = self.commit('synthetic archived bundle and preinstalled maintained sources')
        self.write(POINTER, fixtures.raw(dict(schema_version=1, commit=archive, prefix='archive')))
        self.trusted = self.commit('trusted pointer and exact synthetic authorization')
        self.bootstrap = self.trusted
        origin = self.root/'origin.git'
        git_fixture.run(['clone','--bare',str(self.repo),str(origin)],scratch=self.root,
                        check=True,capture_output=True)
        self.git('remote','add','origin',str(origin))
        self.append()
        (self.repo/'runs').mkdir()
        self.current_report = self.repo/'runs/python-regression.json'
        self.current_report.write_bytes(self.fixture['current_bytes'])
        self.bin = self.root/'bin'; self.bin.mkdir()
        (self.bin/'python3').symlink_to(sys.executable)

    def append(self):
        self.write(BASELINE, fixtures.raw(self.fixture['head']))
        self.commit('append only the exact preauthorized baseline context')

    def rebuild_base(self, pointer=None, helper=None):
        # runs are untrusted observations, never part of a baseline transaction.
        self.write('.gitignore', 'runs/\n')
        self.write(BASELINE, fixtures.raw(self.fixture['baseline']))
        if pointer is not None: self.write(POINTER, pointer)
        if helper is not None: self.write(HELPER, helper)
        self.trusted = self.commit('reviewed synthetic base variation')

    def call_workflow(self, event_name='pull_request'):
        repository = dict(full_name='fixture/project', default_branch='main')
        if event_name == 'pull_request':
            event = dict(repository=repository, pull_request=dict(base=dict(
                sha=self.trusted, ref='main', repo=dict(full_name='fixture/project'))))
        elif event_name == 'push':
            event = dict(repository=repository, ref='refs/heads/main', before=self.trusted)
        else:
            event = dict(repository=repository, inputs=dict(base=self.git('rev-parse','HEAD')))
        self.event_path.write_text(json.dumps(event))
        body = self.pin_body(self.run_body('regression-admission',
                            'Compare raw observations with the trusted comparator'), self.bootstrap)
        env = git_fixture.child_env(GITHUB_EVENT_NAME=event_name, GITHUB_EVENT_PATH=str(self.event_path),
                                   PATH=str(self.bin)+os.pathsep+os.environ.get('PATH',''))
        process = subprocess.run(['bash','-e','-c',body],cwd=self.repo,env=env,capture_output=True,text=True)
        facts = json.loads((self.repo/'runs/regression-admission.json').read_text())
        source_path = self.repo/'runs/regression-bundle-source.json'
        bundle = json.loads(source_path.read_text()) if source_path.exists() else None
        return process, facts, bundle

    def test_trusted_pointer_registers_for_each_supported_event(self):
        for event in ('pull_request','push','schedule','workflow_dispatch'):
            with self.subTest(event=event):
                result, facts, bundle = self.call_workflow(event)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertTrue(facts['transition']['registration'])
                self.assertFalse(facts['semantic_qualification'])
                self.assertFalse(facts['raw_successful'])
                self.assertEqual(facts['trust']['trusted_commit'],self.trusted)
                self.assertTrue(bundle['requested'])
                self.assertTrue(bundle['materialized'])
                self.assertEqual(bundle['trusted_commit'],self.trusted)
                self.assertEqual(bundle['helper_sha256'],hashlib.sha256((ROOT/HELPER).read_bytes()).hexdigest())
                self.assertEqual(len(bundle['inventory']['files']),10)

    def test_no_append_does_not_read_pointer_or_execute_helper(self):
        marker = self.root/'helper-executed'
        self.rebuild_base(pointer='not JSON',helper='from pathlib import Path\nPath('+repr(str(marker))+').touch()\nraise RuntimeError("hostile helper")\n')
        result, facts, bundle = self.call_workflow()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(facts['merge_allowed'])
        self.assertFalse(bundle['requested'])
        self.assertFalse(marker.exists())

    def test_c0_refusal_precedes_pointer_and_helper_reads(self):
        marker = self.root/'helper-executed'
        self.rebuild_base(pointer='not JSON',helper='from pathlib import Path\nPath('+repr(str(marker))+').touch()\n')
        self.append()
        changed = copy.deepcopy(self.fixture['current'])
        changed['tests'][0]['conditions'][0]['id'] = 'new-C0-failure'
        self.current_report.write_bytes(fixtures.raw(changed))
        result, facts, bundle = self.call_workflow()
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertFalse(facts['trusted_comparison']['merge_allowed'])
        self.assertFalse(facts['trust']['candidate_baseline']['evaluated'])
        self.assertFalse(bundle['requested'])
        self.assertFalse(marker.exists())

    def test_head_pointer_and_helper_cannot_replace_base_authority(self):
        marker = self.root/'head-helper-executed'
        self.write('.gitignore','runs/\n')
        self.write(POINTER,'not JSON')
        self.write(HELPER,'from pathlib import Path\nPath('+repr(str(marker))+').touch()\n')
        self.commit('hostile HEAD data and helper')
        result, facts, bundle = self.call_workflow()
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('only fixed baseline path',' '.join(facts['differences']))
        self.assertTrue(bundle['materialized'])
        self.assertEqual(bundle['helper_sha256'],hashlib.sha256((ROOT/HELPER).read_bytes()).hexdigest())
        self.assertFalse(marker.exists())

    def test_changed_bundle_bytes_cannot_register(self):
        self.rebuild_base()
        self.write('archive/stdout',self.fixture['blobs']['stdout']+b'changed')
        changed_archive = self.commit('untrusted changed artifact')
        self.rebuild_base(pointer=fixtures.raw(dict(schema_version=1,commit=changed_archive,prefix='archive')))
        self.append()
        result, facts, bundle = self.call_workflow()
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertTrue(bundle['materialized'])
        self.assertIn('missing or changed artifact bytes: stdout',' '.join(facts['differences']))

    def test_schema2_pointer_materializes_decoded_kernel(self):
        kernel = self.fixture['blobs']['kernel_binary']
        stored = gzip.compress(kernel, mtime=0)
        self.write('archive/kernel_binary', stored)
        archive = self.commit('gzip only the synthetic kernel blob')
        pointer = dict(schema_version=2, commit=archive, prefix='archive', kernel_binary=dict(
            encoding='gzip', decoded_bytes=len(kernel),
            decoded_sha256=hashlib.sha256(kernel).hexdigest()))
        self.rebuild_base(pointer=fixtures.raw(pointer))
        self.append()
        result, facts, bundle = self.call_workflow()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(facts['transition']['registration'])
        self.assertFalse(facts['semantic_qualification'])
        self.assertTrue(bundle['materialized'])
        self.assertEqual(bundle['helper_sha256'], hashlib.sha256((ROOT / HELPER).read_bytes()).hexdigest())
        rows = {row['name']: row for row in bundle['inventory']['files']}
        self.assertEqual(len(rows), 10)
        decoded = rows['kernel_binary']
        self.assertEqual(decoded['encoding'], 'gzip')
        self.assertEqual(decoded['materialized_sha256'], hashlib.sha256(kernel).hexdigest())
        self.assertEqual(decoded['materialized_byte_count'], len(kernel))
        self.assertEqual(decoded['stored_sha256'], hashlib.sha256(stored).hexdigest())
        self.assertEqual(decoded['stored_byte_count'], len(stored))
        self.assertNotEqual(decoded['stored_sha256'], decoded['materialized_sha256'])
        self.assertNotIn('encoding', rows['stdout'])
        self.assertEqual(rows['stdout']['stored_sha256'], rows['stdout']['materialized_sha256'])

    def test_schema2_checksum_failure_does_not_register(self):
        kernel = self.fixture['blobs']['kernel_binary']
        stored = bytearray(gzip.compress(kernel, mtime=0))
        stored[-8] ^= 0x01
        self.write('archive/kernel_binary', bytes(stored))
        archive = self.commit('corrupt the gzip trailer of the synthetic kernel')
        pointer = dict(schema_version=2, commit=archive, prefix='archive', kernel_binary=dict(
            encoding='gzip', decoded_bytes=len(kernel),
            decoded_sha256=hashlib.sha256(kernel).hexdigest()))
        self.rebuild_base(pointer=fixtures.raw(pointer))
        self.append()
        result, facts, bundle = self.call_workflow()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(facts['merge_allowed'])
        self.assertTrue(bundle['requested'])
        self.assertFalse(bundle['materialized'])
        self.assertIn('checksum', bundle['error'])

    def test_missing_or_nonregular_base_data_fails_without_head_fallback(self):
        original_pointer = (self.repo/POINTER).read_bytes()
        for path in (POINTER, HELPER):
            for kind in ('missing', 'symlink'):
                with self.subTest(path=path, kind=kind):
                    self.rebuild_base(pointer=original_pointer, helper=(ROOT/HELPER).read_bytes())
                    target = self.repo/path
                    target.unlink()
                    if kind == 'symlink':
                        target.symlink_to('HEAD-fallback')
                    self.trusted = self.commit('unavailable base blob')
                    # A readable HEAD replacement cannot repair the base input.
                    target.unlink(missing_ok=True)
                    target.write_bytes(original_pointer if path == POINTER else (ROOT/HELPER).read_bytes())
                    self.append()
                    result, facts, bundle = self.call_workflow()
                    self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
                    self.assertFalse(facts['merge_allowed'])
                    self.assertTrue(bundle['requested'])
                    self.assertFalse(bundle['materialized'])
                    self.assertIn('regular Git blob', bundle['error'])


class BundleMaterializationTests(unittest.TestCase):
    git = support.TrustedLoaderTests.git
    write = support.TrustedLoaderTests.write
    commit = support.TrustedLoaderTests.commit

    def setUp(self):
        support.TrustedLoaderTests.setUp(self)
        self.payloads = {name: ('untrusted bytes: '+name).encode() for name in materializer.FIXED_FILES}
        for name, payload in self.payloads.items():
            self.write('archive/'+name, payload)
        self.archive = self.commit('ten immutable data blobs')
        self.manifest = self.root/'manifest.json'
        self.output = self.root/'materialized'
        self.select(self.archive)

    def select(self, commit, prefix='archive'):
        self.manifest.write_text(json.dumps(dict(schema_version=1, commit=commit, prefix=prefix)))

    def test_exact_bytes_and_git_identity_are_retained(self):
        before = (self.git('rev-parse','HEAD'), self.git('status','--porcelain'),
                  (self.repo/'.git/index').read_bytes())
        result = materializer.materialize(self.repo, self.manifest, self.output)
        self.assertEqual(result['schema_version'], 1)
        self.assertEqual(set(result), {'schema_version', 'kind', 'materialized', 'commit', 'tree',
                                       'prefix', 'output', 'files'})
        self.assertEqual(result['commit'], self.archive)
        self.assertEqual(result['tree'], self.git('rev-parse', self.archive+'^{tree}'))
        self.assertEqual({row['name'] for row in result['files']}, set(self.payloads))
        self.assertEqual(set(result['files'][0]), {'name', 'path', 'mode', 'blob', 'sha256', 'byte_count'})
        for row in result['files']:
            self.assertEqual((self.output/row['name']).read_bytes(), self.payloads[row['name']])
            self.assertEqual(row['sha256'], hashlib.sha256(self.payloads[row['name']]).hexdigest())
            self.assertEqual(row['blob'], self.git('rev-parse', self.archive+':archive/'+row['name']))
        self.assertEqual(before, (self.git('rev-parse','HEAD'), self.git('status','--porcelain'),
                                  (self.repo/'.git/index').read_bytes()))

    def test_manifest_cannot_select_floating_refs_or_escaping_paths(self):
        for commit, prefix in [('HEAD','archive'), ('0'*40,'archive'), ('f'*40,'archive')]+[
                (self.archive, p) for p in ('../archive','/archive','archive/../archive',
                                          'archive/','archive//data',':(glob)archive','archive*','archive\\data')]:
            with self.subTest(commit=commit, prefix=prefix):
                self.select(commit, prefix)
                with self.assertRaises(ValueError):
                    materializer.materialize(self.repo, self.manifest, self.output)
                self.assertFalse(self.output.exists())

    def test_missing_symlink_and_tree_are_rejected_without_partial_output(self):
        target = self.repo/'archive/stdout'
        for kind in ('missing','symlink','tree'):
            with self.subTest(kind=kind):
                if target.is_file() or target.is_symlink():
                    target.unlink()
                if kind == 'symlink':
                    target.symlink_to('stderr')
                elif kind == 'tree':
                    target.mkdir()
                    (target/'child').write_text('tree member')
                self.select(self.commit('nonregular '+kind))
                with self.assertRaises(ValueError):
                    materializer.materialize(self.repo, self.manifest, self.output)
                self.assertFalse(self.output.exists())

    def test_failed_publish_preserves_another_output_owner(self):
        output = self.output

        def collision(source, destination):
            self.assertEqual(destination, output)
            destination.mkdir()
            (destination/'other-owner').write_text('preserve')
            raise OSError('destination was created concurrently')

        with mock.patch.object(Path, 'rename', new=collision):
            with self.assertRaises(OSError):
                materializer.materialize(self.repo, self.manifest, output)
        self.assertEqual((output/'other-owner').read_text(), 'preserve')
        self.assertFalse(list(self.root.glob('.materialize-*')))

    def test_partial_clone_missing_blobs_are_not_fetched(self):
        self.git('config', 'uploadpack.allowFilter', 'true')
        clone = self.root/'partial-clone'
        git_fixture.run(['clone', '--filter=blob:none', '--no-checkout',
                         self.repo.as_uri(), str(clone)], scratch=self.root,
                        check=True, capture_output=True)

        def missing():
            output = git_fixture.run(['-C', str(clone), 'rev-list', '--objects', '--missing=print', 'HEAD'],
                                     scratch=self.root, check=True, capture_output=True, text=True).stdout
            return {line for line in output.splitlines() if line.startswith('?')}

        before = missing()
        self.assertGreaterEqual(len(before), len(self.payloads))
        trace = self.root/'helper-git-trace.txt'
        # A caller's fetch preference cannot override the helper's local-only boundary.
        env = git_fixture.child_env(GIT_NO_LAZY_FETCH='0', GIT_TRACE=str(trace))
        process = subprocess.run([sys.executable, '-I', str(ROOT/HELPER), '--repo', str(clone),
                                  '--manifest', str(self.manifest), '--output', str(self.output)],
                                 env=env, capture_output=True, text=True)
        self.assertEqual(process.returncode, 2, process.stdout+process.stderr)
        self.assertFalse(json.loads(process.stdout)['materialized'])
        self.assertFalse(self.output.exists())
        self.assertEqual(missing(), before)
        self.assertNotIn(' fetch ', trace.read_text())
        self.manifest.write_text(json.dumps(dict(
            schema_version=2, commit=self.archive, prefix='archive',
            kernel_binary=dict(encoding='gzip', decoded_bytes=1, decoded_sha256='ab' * 32))))
        again = subprocess.run([sys.executable, '-I', str(ROOT / HELPER), '--repo', str(clone),
                                '--manifest', str(self.manifest), '--output', str(self.output)],
                               env=env, capture_output=True, text=True)
        self.assertEqual(again.returncode, 2, again.stdout + again.stderr)
        self.assertFalse(json.loads(again.stdout)['materialized'])
        self.assertFalse(self.output.exists())
        self.assertEqual(missing(), before)
        self.assertNotIn(' fetch ', trace.read_text())

    def write_schema2(self, commit, kernel, prefix='archive'):
        self.manifest.write_text(json.dumps(dict(
            schema_version=2, commit=commit, prefix=prefix,
            kernel_binary=dict(encoding='gzip', decoded_bytes=len(kernel),
                               decoded_sha256=hashlib.sha256(kernel).hexdigest()))))

    def assert_rejected(self, document):
        self.manifest.write_text(json.dumps(document) if not isinstance(document, str) else document)
        with self.assertRaises(ValueError):
            materializer.materialize(self.repo, self.manifest, self.output)
        self.assertFalse(self.output.exists())
        self.assertFalse(Path(str(self.output) + '.inventory.json').exists())
        self.assertFalse(list(self.root.glob('.materialize-*')))

    def test_schema1_does_not_decode_a_gzip_kernel(self):
        kernel = b'original kernel bytes'
        stored = gzip.compress(kernel, mtime=0)
        self.write('archive/kernel_binary', stored)
        commit = self.commit('schema1 keeps the gzip bytes')
        self.select(commit)
        result = materializer.materialize(self.repo, self.manifest, self.output)
        self.assertEqual(result['schema_version'], 1)
        self.assertEqual((self.output / 'kernel_binary').read_bytes(), stored)
        row = next(item for item in result['files'] if item['name'] == 'kernel_binary')
        self.assertEqual(row['sha256'], hashlib.sha256(stored).hexdigest())
        self.assertEqual(row['byte_count'], len(stored))
        self.assertNotIn('encoding', row)

    def test_schema2_decodes_only_the_kernel_member(self):
        kernel = b'#!/bin/sh\necho not-executed\n'
        stored = gzip.compress(kernel, mtime=0)
        decoy_text = b'decoy plaintext that must stay compressed'
        decoy = gzip.compress(decoy_text, mtime=0)
        self.write('archive/kernel_binary', stored)
        self.write('archive/stdout', decoy)
        commit = self.commit('gzip kernel and a gzip-shaped stdout')
        self.write_schema2(commit, kernel)
        result = materializer.materialize(self.repo, self.manifest, self.output)
        self.assertEqual(result['schema_version'], 2)
        self.assertEqual(set(result), {'schema_version', 'kind', 'materialized', 'commit', 'tree',
                                       'prefix', 'output', 'files'})
        self.assertEqual((self.output / 'kernel_binary').read_bytes(), kernel)
        self.assertEqual((self.output / 'stdout').read_bytes(), decoy)
        self.assertFalse((self.root / 'not-executed').exists())
        rows = {row['name']: row for row in result['files']}
        decoded = rows['kernel_binary']
        self.assertEqual(decoded['encoding'], 'gzip')
        self.assertEqual(decoded['blob'], self.git('rev-parse', commit + ':archive/kernel_binary'))
        self.assertEqual(decoded['stored_sha256'], hashlib.sha256(stored).hexdigest())
        self.assertEqual(decoded['stored_byte_count'], len(stored))
        self.assertEqual(decoded['materialized_sha256'], hashlib.sha256(kernel).hexdigest())
        self.assertEqual(decoded['materialized_byte_count'], len(kernel))
        self.assertNotIn('sha256', decoded)
        for name, payload in self.payloads.items():
            if name == 'kernel_binary':
                continue
            expected = decoy if name == 'stdout' else payload
            self.assertEqual((self.output / name).read_bytes(), expected)
            row = rows[name]
            self.assertNotIn('encoding', row)
            self.assertEqual(row['stored_sha256'], row['materialized_sha256'])
            self.assertEqual(row['stored_byte_count'], row['materialized_byte_count'])
            self.assertEqual(row['materialized_sha256'], hashlib.sha256(expected).hexdigest())

    def test_schema2_accepts_a_named_single_member(self):
        kernel = b'named-header kernel'
        buffer = __import__('io').BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode='wb', filename='kernel_binary', mtime=0) as member:
            member.write(kernel)
        self.write('archive/kernel_binary', buffer.getvalue())
        commit = self.commit('gzip member with a filename header')
        self.write_schema2(commit, kernel)
        materializer.materialize(self.repo, self.manifest, self.output)
        self.assertEqual((self.output / 'kernel_binary').read_bytes(), kernel)

    def test_schema2_rejects_bad_members_without_output(self):
        kernel = b'abcdefghijklmnopqrstuvwxyz'
        stored = gzip.compress(kernel, mtime=0)
        self.write('archive/kernel_binary', stored)
        commit = self.commit('one valid kernel member')
        digest = hashlib.sha256(kernel).hexdigest()

        def descriptor(**updates):
            value = dict(encoding='gzip', decoded_bytes=len(kernel), decoded_sha256=digest)
            value.update(updates)
            return value

        corrupt = bytearray(stored)
        corrupt[-8] ^= 0x01
        isize = bytearray(stored)
        isize[-1] ^= 0x01
        cases = {
            'truncated': (stored[:-1], descriptor()),
            'checksum': (bytes(corrupt), descriptor()),
            'isize': (bytes(isize), descriptor()),
            'trailing': (stored + b'x', descriptor()),
            'second-member': (stored + gzip.compress(b'next', mtime=0), descriptor()),
            'concatenated-length': (stored + gzip.compress(b'next', mtime=0),
                                    dict(encoding='gzip', decoded_bytes=len(kernel) + 4,
                                         decoded_sha256=hashlib.sha256(kernel + b'next').hexdigest())),
            'overlong': (stored, descriptor(decoded_bytes=len(kernel) - 1)),
            'short': (stored, descriptor(decoded_bytes=len(kernel) + 5)),
            'hash': (stored, descriptor(decoded_sha256='ab' * 32)),
            'not-gzip': (b'not gzip', descriptor()),
        }
        for label, (payload, spec) in cases.items():
            with self.subTest(label=label):
                self.write('archive/kernel_binary', payload)
                if self.git('status', '--porcelain'):
                    current = self.commit('stored kernel case ' + label)
                else:
                    current = self.git('rev-parse', 'HEAD')
                self.manifest.write_text(json.dumps(dict(
                    schema_version=2, commit=current, prefix='archive', kernel_binary=spec)))
                with self.assertRaises(ValueError) as caught:
                    materializer.materialize(self.repo, self.manifest, self.output)
                self.assertFalse(self.output.exists())
                self.assertFalse(Path(str(self.output) + '.inventory.json').exists())
                self.assertFalse(list(self.root.glob('.materialize-*')))
                text = str(caught.exception)
                if label == 'checksum' or label == 'isize':
                    self.assertIn('checksum', text)
                elif label == 'truncated' or label == 'not-gzip':
                    self.assertIn('truncated', text)
                elif label in ('trailing', 'second-member', 'concatenated-length'):
                    self.assertIn('trailing', text)
                elif label == 'overlong':
                    self.assertIn('exceeds declared', text)
                elif label == 'short':
                    self.assertIn('length', text)
                elif label == 'hash':
                    self.assertIn('sha256', text)

    def test_schema2_large_declaration_is_not_preallocated(self):
        kernel = b'abc'
        self.write('archive/kernel_binary', gzip.compress(kernel, mtime=0))
        commit = self.commit('tiny gzip with a huge declaration')
        self.manifest.write_text(json.dumps(dict(
            schema_version=2, commit=commit, prefix='archive',
            kernel_binary=dict(encoding='gzip', decoded_bytes=10 ** 18,
                               decoded_sha256=hashlib.sha256(kernel).hexdigest()))))
        with self.assertRaises(ValueError) as caught:
            materializer.materialize(self.repo, self.manifest, self.output)
        self.assertIn('length', str(caught.exception))
        self.assertFalse(self.output.exists())

    def test_schema2_descriptor_and_schema_are_strict(self):
        kernel = b'abc'
        stored = gzip.compress(kernel, mtime=0)
        self.write('archive/kernel_binary', stored)
        commit = self.commit('strict descriptor base')
        digest = hashlib.sha256(kernel).hexdigest()
        valid = dict(encoding='gzip', decoded_bytes=len(kernel), decoded_sha256=digest)
        documents = {
            'version-3': dict(schema_version=3, commit=commit, prefix='archive'),
            'version-string': dict(schema_version='2', commit=commit, prefix='archive', kernel_binary=valid),
            'version-bool': dict(schema_version=True, commit=commit, prefix='archive'),
            'schema1-extra': dict(schema_version=1, commit=commit, prefix='archive', kernel_binary=valid),
            'missing-kernel': dict(schema_version=2, commit=commit, prefix='archive'),
            'extra-field': dict(schema_version=2, commit=commit, prefix='archive', kernel_binary=valid, level=9),
            'head': dict(schema_version=2, commit='HEAD', prefix='archive', kernel_binary=valid),
            'zero-commit': dict(schema_version=2, commit='0' * 40, prefix='archive', kernel_binary=valid),
            'escape': dict(schema_version=2, commit=commit, prefix='../archive', kernel_binary=valid),
            'bad-encoding': dict(schema_version=2, commit=commit, prefix='archive',
                                 kernel_binary=dict(valid, encoding='identity')),
            'gzip-case': dict(schema_version=2, commit=commit, prefix='archive',
                              kernel_binary=dict(valid, encoding='GZIP')),
            'extra-descriptor': dict(schema_version=2, commit=commit, prefix='archive',
                                     kernel_binary=dict(valid, level=9)),
            'bool-size': dict(schema_version=2, commit=commit, prefix='archive',
                              kernel_binary=dict(valid, decoded_bytes=True)),
            'zero-size': dict(schema_version=2, commit=commit, prefix='archive',
                              kernel_binary=dict(valid, decoded_bytes=0)),
            'negative-size': dict(schema_version=2, commit=commit, prefix='archive',
                                  kernel_binary=dict(valid, decoded_bytes=-1)),
            'float-size': dict(schema_version=2, commit=commit, prefix='archive',
                               kernel_binary=dict(valid, decoded_bytes=1.0)),
            'upper-sha': dict(schema_version=2, commit=commit, prefix='archive',
                              kernel_binary=dict(valid, decoded_sha256=digest.upper())),
            'short-sha': dict(schema_version=2, commit=commit, prefix='archive',
                              kernel_binary=dict(valid, decoded_sha256='ab' * 31)),
        }
        for label, document in documents.items():
            with self.subTest(label=label):
                self.assert_rejected(document)
        self.assert_rejected('{"schema_version": 2, "commit": "' + commit
                             + '", "prefix": "archive", "kernel_binary": {"encoding": "gzip", '
                             + '"decoded_bytes": "3", "decoded_sha256": "' + digest + '"}}')

    def test_schema2_cli_round_trip_and_checksum_failure(self):
        kernel = b'cli kernel'
        stored = gzip.compress(kernel, mtime=0)
        self.write('archive/kernel_binary', stored)
        commit = self.commit('schema2 cli kernel')
        self.write_schema2(commit, kernel)
        env = git_fixture.child_env()
        argv = [sys.executable, '-I', str(ROOT / HELPER), '--repo', str(self.repo),
                '--manifest', str(self.manifest), '--output', str(self.output)]
        process = subprocess.run(argv, env=env, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(process.stderr, '')
        inventory = json.loads(process.stdout)
        self.assertEqual(inventory['schema_version'], 2)
        self.assertEqual((self.output / 'kernel_binary').read_bytes(), kernel)
        failed = self.output.with_name('failed-output')
        corrupt = bytearray(stored)
        corrupt[-8] ^= 0x01
        self.write('archive/kernel_binary', bytes(corrupt))
        bad = self.commit('schema2 cli corrupt kernel')
        self.write_schema2(bad, kernel)
        failed_argv = [sys.executable, '-I', str(ROOT / HELPER), '--repo', str(self.repo),
                       '--manifest', str(self.manifest), '--output', str(failed)]
        rejected = subprocess.run(failed_argv, env=env, capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 2, rejected.stdout + rejected.stderr)
        self.assertNotIn('Traceback', rejected.stderr)
        body = json.loads(rejected.stdout)
        self.assertFalse(body['materialized'])
        self.assertIn('checksum', body['error'])
        self.assertFalse(failed.exists())
        self.assertFalse(Path(str(failed) + '.inventory.json').exists())

    def test_schema2_symlink_sibling_is_rejected(self):
        kernel = b'kernel'
        self.write('archive/kernel_binary', gzip.compress(kernel, mtime=0))
        target = self.repo / 'archive/stdout'
        target.unlink()
        target.symlink_to('stderr')
        commit = self.commit('schema2 stdout symlink')
        self.write_schema2(commit, kernel)
        with self.assertRaises(ValueError) as caught:
            materializer.materialize(self.repo, self.manifest, self.output)
        self.assertIn('symlink', str(caught.exception))
        self.assertFalse(self.output.exists())
        self.assertFalse(Path(str(self.output) + '.inventory.json').exists())


if __name__ == '__main__':
    unittest.main()
