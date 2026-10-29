"""Active-workflow admission and immutable bootstrap source controls."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

import git_fixture

ROOT = Path(__file__).resolve().parents[2]
_spec=importlib.util.spec_from_file_location('inactive_bootstrap_test_support',Path(__file__).with_name('test_trusted_regression_gate.py'))
_support=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_support)
CODE=_support.CODE
report=_support.report
baseline=_support.baseline
BASELINE_PATH=_support.BASELINE_PATH
CODE_PATH=_support.CODE_PATH
LOADER=ROOT/'scripts/run_trusted_regression_gate.py'


class AdmissionIntegrationTests(unittest.TestCase):
    """Run the maintained workflow commands, rather than a parallel wrapper."""
    def workflow_job(self, name):
        text=(ROOT/'.github/workflows/numerical-assurance.yml').read_text()
        match=re.search(r'^  '+re.escape(name)+r':\n(.*?)(?=^  [a-z][a-z0-9-]*:|\Z)',text,re.M|re.S)
        self.assertIsNotNone(match, 'workflow job missing: '+name)
        return match.group(1)

    def run_body(self, job, step):
        lines=self.workflow_job(job).splitlines()
        start=next(i for i,line in enumerate(lines) if line.startswith('      - name: '+step))
        run=next(i for i in range(start,len(lines)) if lines[i]=='        run: |')
        body=[]
        for line in lines[run+1:]:
            if line and not line.startswith('          '):
                break
            body.append(line)
        return textwrap.dedent('\n'.join(body))+'\n'

    def pin_body(self,body,commit):
        # The fixture installs maintained loader bytes into its synthetic Git.
        # Pin both independently selected literals to that fixture source. Never
        # derive the expected SHA from the requested commit or hostile HEAD.
        body = re.sub(r'(?m)^BOOTSTRAP_COMMIT = "[^"]*"$',
                      'BOOTSTRAP_COMMIT = '+json.dumps(commit),body,count=1)
        fixture_sha = hashlib.sha256(LOADER.read_bytes()).hexdigest()
        return re.sub(r'(?m)^BOOTSTRAP_SHA256 = "[^"]*"$',
                      'BOOTSTRAP_SHA256 = '+json.dumps(fixture_sha),body,count=1)

    def needs(self, regression=True):
        flags=('maintenance','calibration','provenance','regression','differential','fuzz','package','benchmark')
        outputs={key:str(key=='regression' and regression).lower() for key in flags}
        outputs.update(plan_version='2',mode='delivery' if regression else 'iteration')
        needs={'selection':{'result':'success','outputs':outputs}, 'fast-checks':{'result':'success'},
               'catalog-inventory':{'result':'success'}}
        jobs=('static-checks','provenance-paper','provenance-support','regression','rust-regression',
              'regression-coverage','regression-admission','properties-and-ngspice','fuzz-smoke','package','benchmark')
        for job in jobs:
            enabled=regression and job in ('regression','rust-regression','regression-coverage','regression-admission')
            needs[job]={'result':'success' if enabled else 'skipped'}
        return needs

    def ci_gate(self, needs):
        return subprocess.run([sys.executable,'-B',str(ROOT/'scripts/ci_selection.py'),'gate'],
                               env=dict(os.environ,CI_NEEDS=json.dumps(needs)),capture_output=True,text=True)

    def test_selected_admission_failure_skip_or_absence_blocks_total_gate(self):
        passing=self.ci_gate(self.needs())
        self.assertEqual(passing.returncode,0,passing.stderr)
        for state in ('failure','skipped',None):
            needs=self.needs()
            if state is None:
                del needs['regression-admission']
            else:
                needs['regression-admission']['result']=state
            result=self.ci_gate(needs)
            self.assertNotEqual(result.returncode,0,(state,result.stderr))
        self.assertEqual(self.ci_gate(self.needs(False)).returncode,0)

    def test_required_job_wiring_and_separate_always_uploaded_artifacts(self):
        job=self.workflow_job('regression-admission')
        self.assertIn('needs: [selection, regression-coverage]',job)
        self.assertIn("if: always() && needs.selection.outputs.regression == 'true'",job)
        self.assertIn('fetch-depth: 0',job)
        self.assertIn('name: python-regression-timings',job)
        self.assertIn('name: python-regression-admission',job)
        self.assertIn('if: always()',job)
        self.assertIn('runs/regression-admission.json',job)
        self.assertIn('runs/regression-bootstrap-source.json',job)
        pin=re.search(r'^          BOOTSTRAP_COMMIT = \"([0-9a-f]*)\"$',job,re.M)
        self.assertIsNotNone(pin,'workflow must contain one literal bootstrap pin')
        if pin.group(1):
            self.assertRegex(pin.group(1),r'^(?:[0-9a-f]{40}|[0-9a-f]{64})$')
            self.assertNotEqual(set(pin.group(1)),{'0'})
        self.assertNotIn('python3 -I scripts/run_trusted_regression_gate.py',job)
        self.assertIn('regression-admission',self.workflow_job('ci-result').split('needs: ',1)[1].split('\n',1)[0])
        coverage=self.workflow_job('regression-coverage')
        self.assertIn('runs/regression-collection.json',coverage)
        self.assertNotIn('runs/regression-admission.json',coverage)
        for name,step in [('regression-coverage','Select the newest attempt of each regression shard'),
                          ('regression-coverage','Verify complete raw coverage'),
                          ('regression-admission','Compare raw observations with the trusted comparator')]:
            body=self.run_body(name,step)
            syntax=subprocess.run(['bash','-n'],input=body,text=True,capture_output=True)
            self.assertEqual(syntax.returncode,0,syntax.stderr)

    def test_actual_coverage_then_admission_commands_preserve_raw_failure_and_reject_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'scripts').mkdir()
            for name in ('run_regression.py','regression_gate.py','run_trusted_regression_gate.py'):
                shutil.copyfile(ROOT/'scripts'/name,root/'scripts'/name)
            ids=['demo.Case.test_'+str(i) for i in range(4)]
            for index in range(4):
                shard=report()
                method=shard['tests'][0]
                method['id']=ids[index]
                if index:
                    method['outcome']='passed'
                    method['conditions'][0]['outcome']='passed'
                    method['conditions'][0].pop('reason')
                    shard.update(successful=True,failures=0)
                shard.update(shard_count=4,shard_index=index,assignment=[[identity] for identity in ids],
                             selected_test_ids=[ids[index]],discovered_test_ids=ids,source_identity={},
                             input_identity='f'*64,setup_skips=[],seconds=.1)
                path=root/'runs/shards'/('python-regression-shard-%d-attempt-2'%index)/'regression-evidence/report.json'
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(shard))
            # A rerun leaves the first attempt's upload of shard 1 behind; only the newest attempt may be merged.
            stale=root/'runs/shards/python-regression-shard-1-attempt-1/regression-evidence/report.json'
            stale.parent.mkdir(parents=True)
            stale.write_text(json.dumps({'stale':True}))
            env=git_fixture.child_env(GITHUB_STEP_SUMMARY=str(root/'summary.md'),GITHUB_RUN_ATTEMPT='2')
            selection=self.run_body('regression-coverage','Select the newest attempt of each regression shard')
            result=subprocess.run(['bash','-e','-c',selection],cwd=root,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            chosen=json.loads((root/'runs/regression-shard-selection.json').read_text())
            self.assertEqual([item['artifact'] for item in chosen['selected']],
                             ['python-regression-shard-%d-attempt-2'%index for index in range(4)])
            self.assertEqual([item['artifact'] for item in chosen['superseded']],['python-regression-shard-1-attempt-1'])
            coverage=self.run_body('regression-coverage','Verify complete raw coverage')
            result=subprocess.run(['bash','-e','-c',coverage],cwd=root,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            merged=json.loads((root/'runs/python-regression.json').read_text())
            self.assertFalse(merged['successful'])
            collection=json.loads((root/'runs/regression-collection.json').read_text())
            self.assertTrue(collection['collection_valid'])
            self.assertNotIn('merge_allowed',collection)
            self.assertNotIn('gate_active',collection)
            path=root/BASELINE_PATH
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(baseline(merged)))
            git_fixture.run(['init','-b','main',str(root)],scratch=root,check=True,capture_output=True)
            git_fixture.run(['-C',str(root),'add','scripts','evas'],scratch=root,check=True,capture_output=True)
            git_fixture.run(['-C',str(root),'-c','user.name=Integration',
                             '-c','user.email=test@example.invalid','commit','-m','trusted'],
                            scratch=root,check=True,capture_output=True)
            trusted=git_fixture.run(['-C',str(root),'rev-parse','HEAD'],scratch=root,
                                    check=True,capture_output=True,text=True).stdout.strip()
            event=root/'event.json'
            event.write_text(json.dumps({'repository':{'full_name':'fixture/project'},'pull_request':{
                'base':{'sha':trusted,'ref':'main','repo':{'full_name':'fixture/project'}}}}))
            env.update(GITHUB_EVENT_NAME='pull_request',GITHUB_EVENT_PATH=str(event))
            admission=self.pin_body(self.run_body('regression-admission','Compare raw observations with the trusted comparator'),trusted)
            result=subprocess.run(['bash','-e','-c',admission],cwd=root,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            facts=json.loads((root/'runs/regression-admission.json').read_text())
            self.assertFalse(facts['raw_successful'])
            self.assertTrue(facts['merge_allowed'])
            self.assertEqual(facts['trust']['trusted_commit'],trusted)
            merged['tests'][0]['conditions'][0]['reason']['message']='new failure source'
            (root/'runs/python-regression.json').write_text(json.dumps(merged))
            result=subprocess.run(['bash','-e','-c',admission],cwd=root,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,1,result.stdout+result.stderr)
            self.assertFalse(json.loads((root/'runs/regression-admission.json').read_text())['merge_allowed'])
            path.unlink()
            git_fixture.run(['-C',str(root),'add','evas'],scratch=root,check=True,capture_output=True)
            git_fixture.run(['-C',str(root),'-c','user.name=Integration',
                             '-c','user.email=test@example.invalid','commit','-m','missing baseline'],
                            scratch=root,check=True,capture_output=True)
            missing=git_fixture.run(['-C',str(root),'rev-parse','HEAD'],scratch=root,
                                    check=True,capture_output=True,text=True).stdout.strip()
            payload=json.loads(event.read_text());payload['pull_request']['base']['sha']=missing
            event.write_text(json.dumps(payload))
            result=subprocess.run(['bash','-e','-c',admission],cwd=root,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertFalse(json.loads((root/'runs/regression-admission.json').read_text())['merge_allowed'])


class BootstrapSourceTests(unittest.TestCase):
    git=_support.TrustedLoaderTests.git
    write=_support.TrustedLoaderTests.write
    commit=_support.TrustedLoaderTests.commit
    workflow_job=AdmissionIntegrationTests.workflow_job
    run_body=AdmissionIntegrationTests.run_body
    pin_body=AdmissionIntegrationTests.pin_body

    def setUp(self):
        _support.TrustedLoaderTests.setUp(self)
        self.write('.gitignore','runs/\n')
        self.write('scripts/run_trusted_regression_gate.py',LOADER.read_bytes())
        self.bootstrap=self.commit('reviewed fixture bootstrap on main')
        scientific=copy.deepcopy(self.baseline)
        scientific['contexts'][0]['review']['reference']='review:separate-scientific-base'
        self.write(BASELINE_PATH,json.dumps(scientific))
        self.trusted=self.commit('later actual event scientific base')
        changed=copy.deepcopy(self.old)
        changed['tests'][0]['conditions'][0]['id']='new-B'
        changed['tests'][0]['conditions'][0]['reason']['message']='new B regression'
        self.write('runs/python-regression.json',json.dumps(changed))
        self.event_path.write_text(json.dumps({'repository':{'full_name':'fixture/project'},
            'pull_request':{'base':{'sha':self.trusted,'ref':'main','repo':{'full_name':'fixture/project'}}}}))
        self.env=git_fixture.child_env(GITHUB_EVENT_NAME='pull_request',GITHUB_EVENT_PATH=str(self.event_path))
        self.evidence={'scope':'Actual workflow shell body; local Git and synthetic raw only, not EVAS/CI',
                       'bootstrap_commit':self.bootstrap,'event_base_commit':self.trusted,
                       'raw_sha256':hashlib.sha256((self.repo/'runs/python-regression.json').read_bytes()).hexdigest()}

    def execute(self,pin=None):
        body=self.run_body('regression-admission','Compare raw observations with the trusted comparator')
        body=self.pin_body(body,self.bootstrap if pin is None else pin)
        result=subprocess.run(['bash','-e','-c',body],cwd=self.repo,env=self.env,
                              capture_output=True,text=True)
        admission=self.repo/'runs/regression-admission.json'
        source=self.repo/'runs/regression-bootstrap-source.json'
        facts={'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
               'result':json.loads(admission.read_text()) if admission.exists() else None,
               'source':json.loads(source.read_text()) if source.exists() else None,
               'executed_workflow_body_sha256':hashlib.sha256(body.encode()).hexdigest(),
               'raw_sha256':hashlib.sha256((self.repo/'runs/python-regression.json').read_bytes()).hexdigest(),
               'event_sha256':hashlib.sha256(self.event_path.read_bytes()).hexdigest()}
        return facts

    def hostile_head(self):
        self.write('scripts/run_trusted_regression_gate.py',
                   'import json\nprint(json.dumps({"valid":True,"merge_allowed":True,'
                   '"raw_successful":False,"source":"untrusted HEAD bootstrap"}))\n')
        return self.commit('head replaces only same-named bootstrap')

    def test_actual_workflow_rejects_new_B_after_only_head_loader_replacement(self):
        before=self.execute()
        self.evidence['original']=before
        self.assertEqual(before['exit'],1,before)
        head=self.hostile_head()
        after=self.execute()
        self.evidence.update(attacked_head=head,after=after,
                             changed_paths=self.git('diff','--name-only',self.trusted,head).splitlines())
        self.assertEqual(self.evidence['changed_paths'],['scripts/run_trusted_regression_gate.py'])
        self.assertEqual(after['exit'],1,after)
        self.assertEqual(before['raw_sha256'],after['raw_sha256'])
        self.assertEqual(before['event_sha256'],after['event_sha256'])
        self.assertFalse(after['result']['merge_allowed'])
        self.assertFalse(after['result']['raw_successful'])
        self.assertNotEqual(self.bootstrap,self.trusted)
        self.assertEqual(after['source']['bootstrap_commit'],self.bootstrap)
        self.assertEqual(after['source']['loader_sha256'],hashlib.sha256(LOADER.read_bytes()).hexdigest())
        self.assertEqual(after['result']['trust']['trusted_commit'],self.trusted)

    def test_missing_invalid_or_short_fixed_pin_never_uses_head_loader(self):
        self.hostile_head()
        for pin in ('','HEAD',self.bootstrap[:12],'0'*40,'f'*40):
            facts=self.execute(pin)
            self.evidence[repr(pin)]=facts
            self.assertEqual(facts['exit'],2,facts)
            self.assertFalse(facts['result']['merge_allowed'])
            self.assertFalse(facts['source']['loaded'])

    def test_fixed_bootstrap_hash_mismatch_refuses_without_head_fallback(self):
        self.write('scripts/run_trusted_regression_gate.py',LOADER.read_bytes()+b'\n# unexpected source bytes\n')
        mismatch=self.commit('regular bootstrap blob differs from independently reviewed bytes')
        self.hostile_head()
        facts=self.execute(mismatch)
        self.evidence['hash-mismatch']=facts
        self.assertEqual(facts['exit'],2,facts)
        self.assertFalse(facts['result']['merge_allowed'])
        self.assertFalse(facts['source']['loaded'])
        self.assertIn('SHA256 mismatch',facts['source']['error'])

    def test_missing_or_nonregular_bootstrap_blob_never_uses_head_loader(self):
        path=self.repo/'scripts/run_trusted_regression_gate.py'
        marker=self.repo/'runs/head-bootstrap-executed'
        payload='from pathlib import Path\nPath('+repr(str(marker))+').write_text(\"ran\")\n' + \
                'import json\nprint(json.dumps({\"merge_allowed\":True,\"raw_successful\":False}))\n'
        path.unlink()
        missing=self.commit('fixed source commit has no bootstrap')
        self.write('scripts/run_trusted_regression_gate.py',payload)
        facts=self.execute(missing)
        self.evidence['missing']=facts
        self.assertEqual(facts['exit'],2,facts)
        self.assertFalse(marker.exists(),'missing pin blob must not execute a HEAD fallback')
        path.unlink()
        self.write('scripts/other.py',payload)
        path.symlink_to('other.py')
        nonregular=self.commit('fixed bootstrap is a symlink')
        path.unlink()
        self.write('scripts/run_trusted_regression_gate.py',payload)
        facts=self.execute(nonregular)
        self.evidence['symlink']=facts
        self.assertEqual(facts['exit'],2,facts)
        self.assertFalse(facts['source']['loaded'])
        self.assertFalse(marker.exists(),'nonregular pin blob must not execute a HEAD fallback')


if __name__=='__main__':
    unittest.main()
