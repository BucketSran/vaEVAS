"""Actual CLI plumbing with fake tools/harnesses; no Rust compilation or science."""
import hashlib
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import re
import textwrap
import unittest

import git_fixture

HELPER = Path(__file__).resolve().parents[1] / 'capabilities/discover_rust.py'


class RustListingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        git_fixture.bind(self, Path(self.tmp.name))
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.write('.gitignore', 'runs/\nevas/rust_core/target/\n')
        self.write('evas/rust_core/Cargo.toml', '[package]\nname="evas-kernel"\nversion="0.25.0"\n[workspace]\nmembers=["ir"]\n')
        self.write('evas/rust_core/ir/Cargo.toml', '[package]\nname="evas-ir"\nversion="0.1.0"\n')
        self.write('evas/rust_core/Cargo.lock', 'version = 4\n')
        self.write('evas/rust_core/src/main.rs', 'fn main() {}\n')
        self.write('evas/rust_core/ir/src/lib.rs', '// source identity fixture only, not compiled\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'owned source fixture')
        self.commit = self.git('rev-parse', 'HEAD')
        self.target = self.repo / 'evas/rust_core/target'
        self.targets = []
        self.artifacts = []
        self.executables = []
        self.metadata = dict(packages=[], workspace_members=[], target_directory=str(self.target), version=1)
        for index, (name, version, folder, kind, src) in enumerate([
                ('evas-kernel', '0.25.0', '', 'bin', 'src/main.rs'),
                ('evas-ir', '0.1.0', 'ir', 'lib', 'src/lib.rs')]):
            crate = self.repo / 'evas/rust_core' / folder
            package = 'path+' + crate.as_uri() + '#' + name + '@' + version
            target = dict(name=name.replace('-', '_') if kind == 'lib' else name,
                          kind=[kind], src_path=str(crate / src), test=True)
            self.metadata['packages'].append(dict(id=package, name=name, version=version,
                manifest_path=str(crate / 'Cargo.toml'), targets=[target]))
            self.metadata['workspace_members'].append(package)
            executable = self.target / 'debug/deps' / ('fixture-harness-' + str(index))
            self.harness(executable, 'same: test\nignored: test\n\n2 tests, 0 benchmarks\n' if index == 0 else 'same: test\n\n1 test, 0 benchmarks\n',
                         'ignored: test\n\n1 test, 0 benchmarks\n' if index == 0 else '0 tests, 0 benchmarks\n')
            self.targets.append(target)
            self.executables.append(executable)
            self.artifacts.append(dict(reason='compiler-artifact', package_id=package, target=target,
                profile=dict(test=True, opt_level='1', debug_assertions=True, overflow_checks=True),
                executable=str(executable), fresh=False))
        tools = Path(self.tmp.name) / 'tools'
        tools.mkdir()
        self.metadata_path = Path(self.tmp.name) / 'metadata.json'
        self.metadata_path.write_text(json.dumps(self.metadata))
        for tool in ('cargo', 'rustc'):
            script = tools / tool
            if tool == 'cargo':
                body=('import pathlib,sys,os\n'
                      'if "metadata" in sys.argv:\n print(pathlib.Path('+repr(str(self.metadata_path))+').read_text())\n'
                      'elif "--no-run" in sys.argv:\n print(pathlib.Path('+repr(str(self.repo/'runs/build.jsonl'))+').read_text(),end="")\n raise SystemExit(int(os.environ.get("FIXTURE_BUILD_EXIT","0")))\n'
                      'else: print("cargo FAKE-fixture-not-Rust")\n')
            else:
                body='print("rustc FAKE-fixture-not-Rust\\nhost: fixture")\n'
            script.write_text('#!' + sys.executable + '\n' + body)
            script.chmod(0o755)
        self.env = git_fixture.child_env(PATH=str(tools) + os.pathsep + os.environ['PATH'],
                                         CARGO_PROFILE_DEV_OPT_LEVEL='1',
                                         CARGO_PROFILE_DEV_DEBUG_ASSERTIONS='true',
                                         CARGO_PROFILE_DEV_OVERFLOW_CHECKS='true')
        self.build = self.repo / 'runs/build.jsonl'
        self.report = self.repo / 'runs/listing.json'
        self.raw = self.repo / 'runs/listing'
        self.messages = self.artifacts + [dict(reason='build-finished', success=True)]
        self.write_messages()

    def git(self, *args):
        return git_fixture.run(['-C', str(self.repo), *args], scratch=Path(self.tmp.name),
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                               check=True).stdout.strip()

    def write(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def harness(self, path, listing, ignored, exit_code=0):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#!' + sys.executable + '\nimport sys\n'
            + 'print(' + repr(ignored) + ' if "--ignored" in sys.argv else ' + repr(listing) + ',end="")\n'
            + 'raise SystemExit(' + str(exit_code) + ')\n')
        path.chmod(0o755)

    def write_messages(self):
        self.build.parent.mkdir(parents=True, exist_ok=True)
        self.build.write_text(''.join(json.dumps(row) + '\n' for row in self.messages))

    def run_helper(self, build_exit=0):
        result = subprocess.run([sys.executable, '-B', str(HELPER), '--repo', str(self.repo),
            '--build-messages', str(self.build), '--build-exit', str(build_exit),
            '--report', str(self.report), '--raw-directory', str(self.raw)], env=self.env,
            capture_output=True, text=True)
        payload = json.loads(self.report.read_text()) if self.report.exists() else None
        return result, payload

    def test_missing_duplicate_unknown_or_shared_executable_artifacts_refused(self):
        cases=[]
        missing=copy.deepcopy(self.messages);missing.pop(0);cases.append(missing)
        duplicate=copy.deepcopy(self.messages);duplicate.insert(0,copy.deepcopy(duplicate[0]));cases.append(duplicate)
        unknown=copy.deepcopy(self.messages);unknown[0]['target']['name']='not-an-owned-target';cases.append(unknown)
        shared=copy.deepcopy(self.messages);shared[1]['executable']=shared[0]['executable'];cases.append(shared)
        for rows in cases:
            self.messages=rows;self.write_messages()
            result,report=self.run_helper()
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(report['complete'])
            self.assertTrue(report['errors'])

    def test_compiler_failure_terminal_missing_and_truncated_json_refused(self):
        result,report=self.run_helper(9)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(report['binaries'],[])
        for rows in (self.artifacts, self.artifacts+[{'reason':'build-finished','success':False}],
                     self.messages+[{'reason':'surprise'}],
                     self.artifacts+[{'reason':'new-cargo-event'}]+[{'reason':'build-finished','success':True}]):
            self.messages=rows;self.write_messages()
            result,report=self.run_helper()
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(report['complete'])
        self.build.write_text('{"reason":')
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])

    def test_summary_duplicates_unknown_stdout_and_nonzero_exit_retain_binary_receipt(self):
        for output,ignored,code in [
                ('same: test\n2 tests, 0 benchmarks\n','0 tests, 0 benchmarks\n',0),
                ('same: test\nsame: test\n2 tests, 0 benchmarks\n','0 tests, 0 benchmarks\n',0),
                ('unrecognized output\n1 test, 0 benchmarks\n','0 tests, 0 benchmarks\n',0),
                ('same: test\n1 test, 0 benchmarks\n','absent: test\n1 test, 0 benchmarks\n',0),
                ('same: test\n1 test, 0 benchmarks\n','0 tests, 0 benchmarks\n',4)]:
            self.harness(self.executables[0],output,ignored,code)
            result,report=self.run_helper()
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(report['complete'])
            self.assertEqual(report['binaries'][0]['binary_sha256'],hashlib.sha256(self.executables[0].read_bytes()).hexdigest())
            self.assertTrue(report['binaries'][0]['listing']['all']['argv'])
            self.assertTrue((self.raw/'00-all.stdout.txt').exists())

    def test_effective_artifact_profile_must_match_requested_ci_profile(self):
        self.messages[0]['profile']['overflow_checks']=False
        self.write_messages()
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])

    def test_unknown_metadata_structures_refuse_with_error_report(self):
        missing=copy.deepcopy(self.metadata)
        missing['workspace_members'].append('path+file:///missing-owned-member#extra@0.1.0')
        malformed=copy.deepcopy(self.metadata);malformed['packages']=[None]
        for metadata in (malformed,missing):
            self.metadata_path.write_text(json.dumps(metadata))
            result,report=self.run_helper()
            self.assertNotEqual(result.returncode,0)
            self.assertIsNotNone(report)
            self.assertFalse(report['complete'])
            self.assertTrue(report['errors'])

    def test_empty_complete_listing_and_nonregular_or_outside_executable_refused(self):
        for exe in self.executables:
            self.harness(exe,'0 tests, 0 benchmarks\n','0 tests, 0 benchmarks\n')
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(report['tests_discovered'],0)
        self.assertFalse(report['complete'])
        original=self.executables[0].read_bytes()
        self.executables[0].unlink()
        outside=Path(self.tmp.name)/'outside-harness'
        outside.write_bytes(original);outside.chmod(0o755)
        self.executables[0].symlink_to(outside)
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])
        self.messages[0]['executable']=str(outside)
        self.write_messages()
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])

    def test_binary_mutation_and_dirty_rust_source_refused(self):
        executable=self.executables[0]
        executable.write_text('#!'+sys.executable+'\nfrom pathlib import Path\nimport sys\n'
          + 'p=Path(__file__);p.write_text(p.read_text()+"\\n# mutated\\n")\n'
          + 'print("0 tests, 0 benchmarks" if "--ignored" in sys.argv else "same: test\\n1 test, 0 benchmarks")\n')
        executable.chmod(0o755)
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])
        self.write('evas/rust_core/src/main.rs','fn main() { panic!("changed"); }\n')
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])

    def test_ci_uses_one_fixed_rust_toolchain(self):
        root=HELPER.parents[2]
        main=root/'.github/workflows/numerical-assurance.yml'
        text=main.read_text()
        pins=re.findall(r"^  RUSTUP_TOOLCHAIN: '([^']*)'$",text,re.M)
        self.assertEqual(len(pins),1)
        self.assertRegex(pins[0],r'^[0-9]+\.[0-9]+\.[0-9]+$')
        self.assertRegex(text,r"(?m)^env:\n  RUSTUP_TOOLCHAIN: '")
        # Every workflow, reusable workflow and composite action, not only the caller.
        ci=sorted([*(root/'.github/workflows').glob('*.yml'),*(root/'.github/actions').glob('**/action.yml')])
        self.assertIn(root/'.github/workflows/package-install.yml',ci)
        self.assertIn(root/'.github/actions/rust-cache/action.yml',ci)
        channel=(r'\+stable',r'(?:toolchain install|update|default|override set)\s+stable\b',
                 r'(?m)^\s*(?:- )?toolchain:\s*[\'"]?stable\b',r'RUSTUP_TOOLCHAIN:\s*[\'"]?stable\b')
        for path in [*ci,HELPER,root/'scripts/ci_evidence.py',root/'scripts/ci_lint.py']:
            with self.subTest(path=path.name):
                for pattern in channel:self.assertNotRegex(path.read_text(),pattern)
        # The one source line that still names the pre-pin channel admits historical receipts only.
        listing=(root/'evas/capabilities/rust_listing.py').read_text().splitlines()
        self.assertEqual([line.split(' =')[0] for line in listing if '+stable' in line],['HISTORICAL_TOOLCHAIN_ARGV'])
        # One authoritative literal: no other CI file repeats the version or assigns a version literal.
        self.assertEqual({path.name:path.read_text().count(pins[0]) for path in ci if pins[0] in path.read_text()},{main.name:1})
        for path in ci:
            if path!=main:
                with self.subTest(literal=path.name):
                    self.assertNotRegex(path.read_text(),r'RUSTUP_TOOLCHAIN:\s*[\'"]?[0-9]')
        # Allowed exception: fuzz-smoke installs and names nightly, which cargo-fuzz requires.
        for path in ci:
            installs=re.findall(r'rustup toolchain install (\S+)',path.read_text())
            with self.subTest(installs=path.name):
                self.assertTrue(all(name=='"$RUSTUP_TOOLCHAIN"' or (path==main and name=='nightly') for name in installs),installs)
        self.assertEqual(re.findall(r'rustup toolchain install (\S+)',text).count('nightly'),1)
        fuzz=re.search(r'^  fuzz-smoke:\n(.*?)(?=^  package:)',text,re.M|re.S).group(1)
        self.assertIn('rustup toolchain install nightly',fuzz)
        self.assertEqual(re.findall(r'\bcargo (?!\+nightly)\S+',fuzz),[])

    def test_reusable_workflows_take_the_fixed_toolchain_from_their_caller(self):
        root=HELPER.parents[2]
        main=(root/'.github/workflows/numerical-assurance.yml').read_text()
        # selection is the one job that reads the workflow-level env into an output.
        selection=re.search(r'^  selection:\n(.*?)(?=^  fast-checks:)',main,re.M|re.S).group(1)
        self.assertEqual(re.findall(r'^      rust_toolchain: (.*)$',selection,re.M),['${{ env.RUSTUP_TOOLCHAIN }}'])
        parts=re.split(r'(?m)^  ([a-z-]+):\n',main[main.index('\njobs:\n'):])
        jobs=dict(zip(parts[1::2],parts[2::2]))
        reusable=[path for path in sorted((root/'.github/workflows').glob('*.yml')) if re.search(r'(?m)^  workflow_call:',path.read_text())]
        self.assertIn('package-install.yml',[path.name for path in reusable])
        for path in reusable:
            text=path.read_text()
            if not re.search(r'\b(?:rustup|cargo|rustc|maturin)\b|rust-cache|python -m build|pip wheel',text):continue
            with self.subTest(workflow=path.name):
                block=re.search(r'^  workflow_call:\n    inputs:\n(.*?)(?=^    outputs:|^[a-z])',text,re.M|re.S)
                self.assertIsNotNone(block,'a Rust-using reusable workflow must declare the toolchain input')
                self.assertEqual(re.findall(r'^      ([a-z_]+):\n',block.group(1),re.M),['rust_toolchain'])
                self.assertNotIn('default:',block.group(1))
                self.assertIn('        required: true\n',block.group(1))
                self.assertEqual(re.findall(r'^ *RUSTUP_TOOLCHAIN: (.*)$',text,re.M),['${{ inputs.rust_toolchain }}'])
                self.assertEqual(re.findall(r'rustup toolchain install (\S+)',text),['"$RUSTUP_TOOLCHAIN"'])
                callers=[body for body in jobs.values() if '    uses: ./.github/workflows/'+path.name+'\n' in body]
                self.assertTrue(callers,'a reusable Rust workflow needs a caller that passes the toolchain')
                for body in callers:
                    self.assertIn('    with:\n      rust_toolchain: ${{ needs.selection.outputs.rust_toolchain }}\n',body)
                    self.assertRegex(body,r'(?m)^    needs: \[selection[,\]]')

    def test_real_workflow_listing_block_keeps_build_failure_and_raw_artifacts(self):
        workflow=HELPER.parents[2]/'.github/workflows/numerical-assurance.yml'
        text=workflow.read_text()
        job=re.search(r'^  rust-regression:\n(.*?)(?=^  regression:)',text,re.M|re.S).group(1)
        self.assertIn('run: cargo test --locked --workspace --manifest-path evas/rust_core/Cargo.toml',job)
        self.assertNotIn('continue-on-error',job)
        self.assertIn('if: always()',job)
        self.assertNotIn('target/debug/deps',job)
        self.assertIn('--require-catalog evas/capabilities/data',job)
        self.assertIn('--listing-profile linux-x86_64-regression-opt1-v1',job)
        self.assertIn('--source-repository vaevas=.',job)
        lines=job.splitlines()
        start=next(i for i,line in enumerate(lines) if line=='      - name: Collect actual owned Rust binary listing')
        run=next(i for i in range(start,len(lines)) if lines[i]=='        run: |')
        body=[]
        for line in lines[run+1:]:
            if line and not line.startswith('          '): break
            body.append(line)
        body=textwrap.dedent('\n'.join(body))+'\n'
        self.assertEqual(subprocess.run(['bash','-n'],input=body,text=True,capture_output=True).returncode,0)
        self.write('scripts/capabilities/discover_rust.py',HELPER.read_text())
        # This workflow plumbing fixture uses a labelled catalogue stub. The
        # independent catalogue tests exercise the real immutable-source protocol.
        self.write('evas/capabilities/registry.py', '''
import os
from pathlib import Path
class StubCatalog:
    def reconcile_rust_listing(self, receipt, *, profile):
        assert profile == 'linux-x86_64-regression-opt1-v1'
        if os.environ['FIXTURE_CATALOG_RECONCILED'] != 'true':
            raise ValueError('explicit fixture catalogue refusal')
        return {'reconciled': True, 'scope': 'fixture plumbing only'}
class StubRegistry:
    def catalog(self):
        return StubCatalog()
def load(data_dir, *, root, repositories):
    assert Path(data_dir) == Path('evas/capabilities/data')
    assert Path(root).resolve() == Path.cwd()
    assert repositories == {'vaevas': Path('.')}
    return StubRegistry()
''')
        for code, admitted in ((0,True),(9,True),(0,False)):
            result=subprocess.run(['bash','-e','-c',body],cwd=self.repo,
                                  env=dict(self.env,FIXTURE_BUILD_EXIT=str(code),
                                           FIXTURE_CATALOG_RECONCILED=str(admitted).lower()),capture_output=True,text=True)
            report=json.loads((self.repo/'runs/rust-test-listing.json').read_text())
            self.assertEqual(result.returncode,0 if code==0 and admitted else 1,result.stdout+result.stderr)
            self.assertEqual(report['complete'],code==0)
            self.assertEqual(report['catalog_reconciliation']['reconciled'],code==0 and admitted)
            self.assertTrue((self.repo/'runs/rust-test-build.jsonl').exists())
            self.assertTrue((self.repo/'runs/rust-test-build.stderr.txt').exists())
            self.assertEqual(report['test_body_execution'],'not_observed_by_this_helper')

    def test_custom_harness_manifest_cannot_claim_native_test_listing(self):
        path=self.repo/'evas/rust_core/Cargo.toml'
        path.write_text(path.read_text()+'[[bin]]\nname="evas-kernel"\nharness=false\n')
        self.git('add','evas/rust_core/Cargo.toml')
        self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','custom unsupported harness')
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])

    def test_actual_fake_harness_listings_have_independent_binary_denominators(self):
        result, report = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(report['complete'])
        self.assertTrue(report['listing_only'])
        self.assertEqual(report['test_body_execution'], 'not_observed_by_this_helper')
        self.assertEqual(report['tests_discovered'], 3)
        self.assertEqual(report['ignored_tests_discovered'], 1)
        self.assertEqual({row['id'] for row in report['tests']},{
            'rust:evas-kernel@0.25.0/bin/evas-kernel::same',
            'rust:evas-kernel@0.25.0/bin/evas-kernel::ignored',
            'rust:evas-ir@0.1.0/lib/evas_ir::same'})
        self.assertEqual(report['source']['commit'], self.commit)
        self.assertEqual(report['binaries'][0]['binary_sha256'], hashlib.sha256(self.executables[0].read_bytes()).hexdigest())
        self.assertTrue((self.raw / '00-all.stdout.txt').exists())
        self.assertIn('FAKE-fixture-not-Rust', report['toolchain']['cargo']['stdout'])


if __name__ == '__main__':
    unittest.main()
