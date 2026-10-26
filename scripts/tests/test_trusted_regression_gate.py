"""Trusted-code loader contract through its public CLI and real temporary Git."""
import copy
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LOADER = ROOT / 'scripts/run_trusted_regression_gate.py'
# Capture the maintained source once; temporary Git contains the trusted copy.
CODE = (ROOT / 'scripts/regression_gate.py').read_bytes()
BASELINE_PATH = 'evas/validation/baselines/regression-v1.json'
CODE_PATH = 'scripts/regression_gate.py'


def report():
    site = dict(module='test_fixture', function='Case.test_one', line=10, source_sha256='a'*64)
    condition = dict(id='A', phase='test', site=site, identity_complete=True, outcome='failed',
                     reason=dict(kind='assertion', exception_type='builtins.AssertionError',
                                 message='original A failure', site=site, attribution='unreviewed-observation'))
    return dict(schema_version=3, complete=True, collection_complete=True, successful=False,
                tests_run=1, failures=1, errors=0, skipped=0, expected_failures=0, unexpected_successes=0,
                tests=[dict(id='demo.Case.test_one', outcome='failed', seconds=.1, conditions=[condition])],
                fixtures=[], setup_skipped_test_ids=[], discovered_test_ids=['demo.Case.test_one'],
                selected_test_ids=['demo.Case.test_one'], assignment=[['demo.Case.test_one']],
                shard_count=1, shard_index=0, metadata=dict(criteria_id='1'*64, language_profile='2'*64,
                collector_sha256='3'*64, runtime_profile={'backend':'debug'}, invocation={'pattern':'test_*.py'}))


def baseline(observed):
    spec = importlib.util.spec_from_file_location('reviewed_fixture_gate', ROOT / 'scripts/regression_gate.py')
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    return gate.propose_baseline(observed, {'commit':'b'*40},
         dict(status='approved', reviewer='independent-synthetic-reviewer', reference='synthetic-review:1',
              semantic_status='pending'))


class TrustedLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / 'checkout'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.old = report()
        self.write(CODE_PATH, CODE)
        self.baseline = baseline(self.old)
        self.write(BASELINE_PATH, json.dumps(self.baseline))
        self.trusted = self.commit('reviewed gate and synthetic baseline')
        self.report_path = self.root / 'report.json'
        self.report_path.write_text(json.dumps(self.old))
        self.event_path = self.root / 'event.json'

    def git(self, *args, check=True):
        result = subprocess.run(['git','-C',str(self.repo),*args],capture_output=True,text=True)
        if check and result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    def write(self, path, value):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value if isinstance(value, bytes) else value.encode())

    def commit(self, message):
        self.git('add', '.')
        self.git('-c','user.name=Trusted Test','-c','user.email=test@example.invalid','commit','-m',message)
        return self.git('rev-parse','HEAD')

    def call(self, name='pull_request', event=None, *args):
        if event is None:
            event = dict(repository={'full_name':'fixture/project','default_branch':'main'},
                         pull_request={'base':{'sha':self.trusted,'ref':'main',
                                              'repo':{'full_name':'fixture/project'}}})
        self.event_path.write_text(json.dumps(event))
        env = dict(os.environ, GITHUB_EVENT_NAME=name, GITHUB_EVENT_PATH=str(self.event_path))
        return subprocess.run([sys.executable,'-I',str(LOADER),'--repo',str(self.repo),
                               '--report',str(self.report_path),*args],env=env,cwd=self.repo,
                              capture_output=True,text=True)

    def attack_head(self):
        changed = copy.deepcopy(self.old)
        changed['tests'][0]['conditions'][0]['id'] = 'B'
        changed['tests'][0]['conditions'][0]['reason']['message'] = 'new B failure'
        self.report_path.write_text(json.dumps(changed))
        self.write(CODE_PATH, 'def validate_report(report): return {"valid":True}\n'
                   'def compare_report(report, baseline):\n'
                   ' return {"valid":True,"merge_allowed":True,"raw_successful":report["successful"]}\n')
        self.write(BASELINE_PATH, json.dumps(baseline(changed)))
        return self.commit('untrusted head broadens baseline and always allows')

    def test_head_code_and_baseline_cannot_self_exempt_new_failure(self):
        head = self.attack_head()
        self.assertNotEqual(head,self.trusted)
        result = self.call()
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        facts = json.loads(result.stdout)
        self.assertFalse(facts['merge_allowed'])
        self.assertFalse(facts['raw_successful'])
        self.assertEqual(facts['trust']['trusted_commit'],self.trusted)
        self.assertEqual(facts['trust']['code_sha256'],hashlib.sha256(CODE).hexdigest())

    def test_push_main_selects_exact_event_before(self):
        event = dict(ref='refs/heads/main', before=self.trusted,
                     repository={'full_name':'fixture/project','default_branch':'main'})
        result = self.call('push',event)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['trust']['source'],'event.before')
        self.attack_head()
        result = self.call('push',event)
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['trust']['trusted_commit'],self.trusted)

    def test_schedule_and_manual_fetch_origin_main_and_ignore_manual_base(self):
        origin = self.root / 'origin.git'
        subprocess.run(['git','clone','--bare',str(self.repo),str(origin)],
                       check=True,capture_output=True,text=True)
        self.git('remote','add','origin',str(origin))
        malicious = self.attack_head()
        for name in ('schedule','workflow_dispatch'):
            self.git('update-ref','refs/remotes/origin/main',malicious)
            event = dict(repository={'full_name':'fixture/project','default_branch':'main'},
                         inputs={'base':malicious})
            result = self.call(name,event)
            self.assertEqual(result.returncode,1,result.stdout+result.stderr)
            facts=json.loads(result.stdout)
            self.assertEqual(facts['trust']['trusted_commit'],self.trusted)
            self.assertEqual(facts['trust']['source'],'fresh-fetch.origin/main')
            self.assertFalse(facts['merge_allowed'])

    def test_missing_empty_unknown_or_nonregular_trusted_sources_refuse(self):
        cases = [(BASELINE_PATH,None), (BASELINE_PATH,''),
                 (BASELINE_PATH,json.dumps({'schema_version':1,'contexts':[]})),
                 (BASELINE_PATH,json.dumps({'schema_version':99,'contexts':[{}]})),
                 (BASELINE_PATH,json.dumps({'schema_version':1,'contexts':[{}]})),
                 (CODE_PATH,None), (CODE_PATH,''),
                 (CODE_PATH,'def unrelated(): pass\n'),
                 (CODE_PATH,'def compare_report(report,baseline): this is invalid syntax!\n')]
        for index,(path,value) in enumerate(cases):
            self.write(CODE_PATH,CODE)
            self.write(BASELINE_PATH,json.dumps(self.baseline))
            if value is None:
                (self.repo/path).unlink()
            else:
                self.write(path,value)
            self.trusted=self.commit('malformed trusted source '+str(index))
            result=self.call()
            self.assertNotEqual(result.returncode,0,(path,value,result.stdout))
            facts=json.loads(result.stdout)
            self.assertFalse(facts['merge_allowed'])
            self.assertFalse(facts['raw_successful'])
        self.write(CODE_PATH,CODE)
        target=self.repo/BASELINE_PATH
        target.unlink()
        target.symlink_to('../../../scripts/regression_gate.py')
        self.trusted=self.commit('nonregular trusted baseline')
        self.assertNotEqual(self.call().returncode,0)

    def test_invalid_refs_missing_event_fields_and_cli_override_refuse(self):
        for ref in ('HEAD',self.trusted[:12],'0'*40,'f'*40,'--help',None):
            event=dict(repository={'full_name':'fixture/project'},
                       pull_request={'base':{'sha':ref,'ref':'main',
                                            'repo':{'full_name':'fixture/project'}}})
            result=self.call('pull_request',event)
            self.assertNotEqual(result.returncode,0,ref)
            self.assertFalse(json.loads(result.stdout)['merge_allowed'])
        for name,event in [('pull_request',{}),('push',{'before':self.trusted}),
                           ('unknown',{'repository':{'full_name':'fixture/project'}})]:
            self.assertNotEqual(self.call(name,event).returncode,0)
        self.assertNotEqual(self.call('pull_request',None,'--trusted-base',self.trusted).returncode,0)
        self.assertNotEqual(self.call('pull_request',None,'--default-branch','../bad').returncode,0)

    def test_missing_origin_default_branch_cannot_fallback_to_head_or_manual_base(self):
        event=dict(repository={'full_name':'fixture/project'},inputs={'base':self.trusted})
        for name in ('schedule','workflow_dispatch'):
            result=self.call(name,event)
            self.assertNotEqual(result.returncode,0,result.stdout)
        origin=self.root/'origin.git'
        subprocess.run(['git','clone','--bare',str(self.repo),str(origin)],check=True,capture_output=True)
        subprocess.run(['git','--git-dir',str(origin),'branch','-m','main','other'],
                       check=True,capture_output=True)
        self.git('remote','add','origin',str(origin))
        self.git('fetch','--no-tags','origin','refs/heads/other')
        event['inputs']['base']=self.trusted
        event['inputs']['default_branch']='other'
        result=self.call('workflow_dispatch',event)
        self.assertNotEqual(result.returncode,0,result.stdout)
        result=self.call('workflow_dispatch',event,'--default-branch','other')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['trust']['trusted_commit'],self.trusted)

    def test_head_module_names_and_pythonpath_are_not_imported(self):
        marker=self.root/'head-module-imported'
        payload='open(' + repr(str(marker)) + ', "w").write("executed")\n' + \
                'raise RuntimeError("head module was imported")\n'
        for path in ('json.py','regression_gate.py','scripts/json.py','sitecustomize.py'):
            self.write(path,payload)
        old=os.environ.get('PYTHONPATH')
        os.environ['PYTHONPATH']=str(self.repo)
        try:
            result=self.call()
        finally:
            if old is None:
                os.environ.pop('PYTHONPATH',None)
            else:
                os.environ['PYTHONPATH']=old
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertFalse(marker.exists())

    def test_reviewed_known_raw_failure_is_allowed_by_trusted_code(self):
        result = self.call()
        self.assertEqual(result.returncode,0,result.stderr)
        facts = json.loads(result.stdout)
        self.assertFalse(facts['raw_successful'])
        self.assertTrue(facts['merge_allowed'])
        self.assertEqual(facts['trust']['trusted_commit'],self.trusted)
        self.assertEqual(facts['trust']['code_sha256'],hashlib.sha256(CODE).hexdigest())
        self.assertEqual(facts['trust']['baseline_sha256'],hashlib.sha256(json.dumps(self.baseline).encode()).hexdigest())


class TransitionIntegrationTests(unittest.TestCase):
    """Real producer/stdlib DUT Git chain, explicitly not EVAS or CI."""
    setUp=TrustedLoaderTests.setUp
    git=TrustedLoaderTests.git
    write=TrustedLoaderTests.write
    commit=TrustedLoaderTests.commit
    call=TrustedLoaderTests.call

    def load_module(self,path,name):
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def execute_fixture(self,label):
        policy=self.load_module(self.repo/'scripts/ci_evidence.py','fixture_evidence_'+label)
        env=dict(os.environ,PYTHONPATH=str(self.repo/'evas/src'),PYTHONDONTWRITEBYTECODE='1')
        env.pop('GITHUB_STEP_SUMMARY',None)
        actual=dict(python=sys.version,platform=platform.platform(),machine=platform.machine(),
                    kernel_sha256=None,fixture='actual-stdlib-DUT-not-EVAS',shard='0-of-1',
                    variables={key:env.get(key) for key in policy.ENVIRONMENT})
        identity=policy.fingerprint(self.repo,actual)
        identity_path=self.root/(label+'-identity.json')
        identity_path.write_text(json.dumps(identity))
        result=subprocess.run([sys.executable,'-B',str(self.repo/'scripts/run_regression.py'),
                               '--source-root',str(self.repo),'--start-directory',str(self.repo/'evas/tests'),
                               '--input-identity',str(identity_path),'--report',str(self.report_path)],
                              cwd=self.repo,env=env,capture_output=True,text=True)
        report=json.loads(self.report_path.read_text())
        self.assertEqual(policy.fingerprint(self.repo,actual),identity)
        policy.bound_report(report,identity,'0-of-1')
        self.assertEqual(report['source_identity']['dut_files'],
                         [['evas/src/dut_fixture.py',hashlib.sha256((self.repo/'evas/src/dut_fixture.py').read_bytes()).hexdigest()]])
        self.evidence[label]={'raw':report,'raw_exit':result.returncode,
                              'raw_file_sha256':hashlib.sha256(self.report_path.read_bytes()).hexdigest()}
        return report

    def proposal(self,report,label):
        review=dict(status='approved',reviewer='fixture-independent-reviewer',reference='fixture-review:'+label,
                    semantic_status='not-EVAS-or-actual-CI',source_commit=self.git('rev-parse','HEAD'))
        return self.gate.propose_baseline(report,dict(source_commit=review['source_commit'],
                   raw_file_sha256=hashlib.sha256(self.report_path.read_bytes()).hexdigest()),review)

    def check_loader(self,label,expected):
        result=self.call()
        self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
        facts=json.loads(result.stdout)
        self.evidence[label]=facts
        return facts

    def test_real_git_fix_retained_then_same_failure_in_next_pr_rejected(self):
        self.evidence={'scope':'Actual stdlib fixture DUT and maintained producers; not EVAS or CI authority'}
        self.gate=self.load_module(ROOT/'scripts/regression_gate.py','maintained_transition_gate')
        for name in ('run_regression.py','ci_evidence.py','regression_reason_identity.py','regression_observation_policy.json'):
            self.write('scripts/'+name,(ROOT/'scripts'/name).read_bytes())
        self.write('evas/capabilities/data/language-profile.json',
                   (ROOT/'evas/capabilities/data/language-profile.json').read_bytes())
        self.write('evas/tests/test_fixture.py',
                   'import unittest\nfrom dut_fixture import value_a, value_b\nclass Case(unittest.TestCase):\n'
                   ' def test_obligations(self):\n'
                   '  with self.subTest(obligation="A"): self.assertEqual(value_a(),1)\n'
                   '  with self.subTest(obligation="B"): self.assertEqual(value_b(),1)\n')
        def dut(a,b=1):
            self.write('evas/src/dut_fixture.py',f'def value_a():\n return {a}\ndef value_b():\n return {b}\n')
        dut(0)
        self.commit('actual fixture A defect and fixed criteria')
        original=self.execute_fixture('original-A')
        self.assertFalse(original['successful'])
        old=self.proposal(original,'original-A')
        self.write(BASELINE_PATH,json.dumps(old))
        self.trusted=self.commit('approved complete A baseline')
        self.evidence['old_trusted_commit']=self.trusted
        self.execute_fixture('known-A')
        self.assertTrue(self.check_loader('known-A-admission',0)['merge_allowed'])
        self.git('checkout','-b','fixture-fix-PR')
        dut(1)
        self.commit('actually fix A before proposal')
        fixed=self.execute_fixture('fixed-before-proposal')
        self.assertTrue(fixed['successful'])
        self.assertEqual(original['metadata'],fixed['metadata'])
        stale=self.check_loader('stale-head-baseline',1)
        self.assertTrue(stale['trusted_comparison']['merge_allowed'])
        proposal=self.proposal(fixed,'fixed')
        self.write(BASELINE_PATH,json.dumps(proposal))
        self.git('add',BASELINE_PATH)
        uncommitted=self.check_loader('uncommitted-proposal-not-authority',1)
        self.assertTrue(uncommitted['trusted_comparison']['merge_allowed'])
        self.assertNotEqual(uncommitted['trust']['candidate_baseline']['sha256'],
                            hashlib.sha256((self.repo/BASELINE_PATH).read_bytes()).hexdigest())
        refreshed=self.commit('approved complete subject-bound improvement proposal')
        final=self.execute_fixture('fixed-with-proposal')
        self.assertEqual(fixed['metadata'],final['metadata'])
        self.assertEqual(self.gate.execution_subject(fixed),self.gate.execution_subject(final))
        admitted=self.check_loader('reviewed-improvement-admitted',0)
        self.assertTrue(admitted['transition']['accepted'])
        self.assertEqual(admitted['trust']['candidate_baseline']['commit'],refreshed)
        self.assertFalse(admitted['trust']['candidate_baseline']['is_authority'])
        self.assertEqual(admitted['trust']['trusted_commit'],self.trusted)
        self.git('checkout','main')
        self.git('merge','--ff-only',refreshed)
        self.trusted=refreshed
        self.evidence['new_trusted_commit']=refreshed
        self.git('checkout','-b','fixture-next-PR')
        dut(0)
        self.commit('next PR reintroduces exact A defect')
        recurrence=self.execute_fixture('same-A-recurrence')
        self.assertEqual(original['metadata'],recurrence['metadata'])
        refused=self.check_loader('recurrence-refused',1)
        self.assertFalse(refused['trusted_comparison']['merge_allowed'])
        self.assertFalse(refused['transition']['proposal_evaluated'])
        self.assertFalse(refused['trust']['candidate_baseline']['evaluated'])
        dut(1,0)
        self.commit('replace A defect with new B defect')
        replacement=self.execute_fixture('new-B-defect')
        waiver=self.proposal(replacement,'untrusted-B-waiver')
        self.write(BASELINE_PATH,json.dumps(waiver))
        self.write(CODE_PATH,'raise RuntimeError("head comparator must not execute")\n')
        self.commit('head self-waiver and hostile comparator')
        refused=self.check_loader('head-B-waiver-refused',1)
        self.assertFalse(refused['trusted_comparison']['merge_allowed'])
        self.assertEqual(refused['trust']['code_sha256'],hashlib.sha256(CODE).hexdigest())

    def test_original_refusal_survives_missing_bad_or_hostile_head_baseline(self):
        self.evidence={}
        changed=copy.deepcopy(self.old)
        changed['tests'][0]['conditions'][0]['id']='new-B'
        self.report_path.write_text(json.dumps(changed))
        for index,value in enumerate((None,'not JSON',json.dumps({'schema_version':99}))):
            path=self.repo/BASELINE_PATH
            if value is None: path.unlink()
            else: self.write(BASELINE_PATH,value)
            self.commit('bad head data '+str(index))
            facts=self.check_loader('refused-'+str(index),1)
            self.assertFalse(facts['trusted_comparison']['merge_allowed'])
            self.assertFalse(facts['transition']['proposal_evaluated'])
            self.assertFalse(facts['trust']['candidate_baseline']['evaluated'])
        denied=self.call('pull_request',None,'--proposal',str(self.repo/BASELINE_PATH))
        self.assertNotEqual(denied.returncode,0)

    def test_bad_or_nonregular_head_proposal_refused_after_old_comparison_allows(self):
        self.evidence={}
        for index,value in enumerate((None,'not JSON',json.dumps({'schema_version':99}),'symlink')):
            path=self.repo/BASELINE_PATH
            if path.exists() or path.is_symlink(): path.unlink()
            if value=='symlink': path.symlink_to('../../../scripts/regression_gate.py')
            elif value is not None: self.write(BASELINE_PATH,value)
            head=self.commit('invalid candidate HEAD data '+str(index))
            facts=self.check_loader('invalid-candidate-'+str(index),1)
            self.assertTrue(facts['trusted_comparison']['merge_allowed'])
            self.assertTrue(facts['trust']['candidate_baseline']['evaluated'])
            self.assertEqual(facts['trust']['candidate_baseline']['commit'],head)
            self.assertFalse(facts['merge_allowed'])

    def test_missing_trusted_transition_api_refused(self):
        self.write(CODE_PATH,CODE.replace(b'def validate_baseline_transition(',b'def legacy_transition('))
        self.trusted=self.commit('trusted source lacks new transition API')
        result=self.call()
        self.assertEqual(result.returncode,2,result.stdout+result.stderr)
        self.assertFalse(json.loads(result.stdout)['merge_allowed'])




class RegistrationLoaderIntegrationTests(unittest.TestCase):
    """Exercise trusted/base versus HEAD authority through actual CLI and Git."""
    git = TrustedLoaderTests.git
    write = TrustedLoaderTests.write
    commit = TrustedLoaderTests.commit
    call = TrustedLoaderTests.call

    def setUp(self):
        TrustedLoaderTests.setUp(self)
        import regression_registration_fixtures as fixtures
        self.fixtures = fixtures
        self.fixture = fixtures.make_fixture()
        self.registration_path = 'scripts/regression_context_registration.py'
        self.review_path = 'evas/validation/baselines/regression-v1.review.json'
        self.write(self.registration_path, (ROOT / self.registration_path).read_bytes())
        self.write(BASELINE_PATH, fixtures.raw(self.fixture['baseline']))
        self.write(self.review_path, fixtures.raw(self.fixture['review']))
        self.trusted = self.commit('trusted context registration code and synthetic authorization')
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        (self.bundle / 'report.json').write_bytes(self.fixture['e1_bytes'])
        for role, raw in self.fixture['blobs'].items():
            (self.bundle / role).write_bytes(raw)
        self.report_path.write_bytes(self.fixture['current_bytes'])
        self.write(BASELINE_PATH, fixtures.raw(self.fixture['head']))
        self.commit('append exactly the preauthorized context')

    def test_exact_trusted_authorization_registers_via_real_cli(self):
        result = self.call('pull_request', None, '--registration-bundle', str(self.bundle))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        facts = json.loads(result.stdout)
        self.assertTrue(facts['merge_allowed'])
        self.assertTrue(facts['transition']['registration'])
        self.assertEqual(facts['trust']['registration']['trusted_commit'], self.trusted)
        self.assertFalse(facts['semantic_qualification'])

    def test_head_registration_code_cannot_execute_or_authorize_append(self):
        marker = self.root / 'head-code-executed'
        self.write(self.registration_path,
                   'from pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("bad")\n'
                   'def validate_context_registration(*args): return {"merge_allowed": True}\n')
        self.commit('untrusted HEAD registration code')
        result = self.call('pull_request', None, '--registration-bundle', str(self.bundle))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse(marker.exists())
        self.assertIn('only fixed baseline path', result.stdout)
        facts = json.loads(result.stdout)
        expected = hashlib.sha256((ROOT / self.registration_path).read_bytes()).hexdigest()
        self.assertEqual(facts['trust']['registration']['code_sha256'], expected)

    def test_unknown_current_context_stops_before_registration_bundle(self):
        current = copy.deepcopy(self.fixture['current'])
        current['metadata']['criteria_id'] = '9' * 64
        self.report_path.write_text(json.dumps(current))
        result = self.call('pull_request', None, '--registration-bundle', str(self.root / 'absent'))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        facts = json.loads(result.stdout)
        self.assertFalse(facts['trust']['candidate_baseline']['evaluated'])
        self.assertNotIn('registration', facts['trust'])

    def test_append_without_bundle_fails_closed(self):
        result = self.call()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('requires a fixed registration evidence bundle', result.stdout)

    def test_new_authorization_in_HEAD_cannot_supply_missing_base_authority(self):
        empty = copy.deepcopy(self.fixture['review'])
        empty['context_registration_authorizations'] = []
        self.write(BASELINE_PATH, self.fixtures.raw(self.fixture['baseline']))
        self.write(self.review_path, self.fixtures.raw(empty))
        self.trusted = self.commit('trusted base has no authorization')
        self.write(BASELINE_PATH, self.fixtures.raw(self.fixture['head']))
        self.write(self.review_path, self.fixtures.raw(self.fixture['review']))
        self.commit('head attempts to approve itself')
        result = self.call('pull_request', None, '--registration-bundle', str(self.bundle))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)['merge_allowed'])

    def test_base_registration_symlink_is_rejected(self):
        self.write(BASELINE_PATH, self.fixtures.raw(self.fixture['baseline']))
        target = self.repo / self.registration_path
        target.unlink()
        target.symlink_to('regression_gate.py')
        self.trusted = self.commit('nonregular trusted registration path')
        self.write(BASELINE_PATH, self.fixtures.raw(self.fixture['head']))
        self.commit('append cannot use nonregular trusted source')
        result = self.call('pull_request', None, '--registration-bundle', str(self.bundle))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('regular Git blob', result.stdout)


if __name__ == '__main__':
    unittest.main()
