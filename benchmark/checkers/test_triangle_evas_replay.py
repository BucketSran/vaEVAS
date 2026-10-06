"""Public replay adapter contracts; constructed responses never certify EVAS."""
import json
from pathlib import Path
import unittest
import tempfile
import sys
import os
from unittest.mock import patch
import triangle_evas_replay as adapter
import build_triangle_evas_replay as builder

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / 'benchmark/tasks/va07-triangle-repair/tests/cases.json').read_text())

class ReplayMapping(unittest.TestCase):
    def test_original_eight_cases_preserve_parameters_inputs_and_density(self):
        self.assertEqual(len(CASES), 8)
        counts = [(601,607)]*4 + [(601,611)]*2 + [(501,505)]*2
        for case, expected in zip(CASES, counts):
            requests, mapping = adapter.prepare_requests(case)
            self.assertEqual(mapping['source_case'], case)
            self.assertEqual(mapping['unmapped_solver_settings'], {'iabstol':case['iabstol'], 'method':case['method']})
            self.assertEqual(requests['baseline']['transient']['sources']['ctl'],case['control'])
            self.assertEqual(requests['baseline']['instances'][0]['parameters']['direction'],case['direction'])
            self.assertEqual(tuple(len(r['transient']['output_times']) for r in requests.values()), expected)

def constant_response(times, speed=1, shift=0):
    values=[]
    for t in times:
        phase=(speed*t+.5)%2
        z=-.5+(phase if phase<=1 else 2-phase)
        values.append({'voltages':[z,sum(t>=r+shift for r in [.5,1.5,2.5])]})
    return {'nodes':['z','count'],'solutions':values,'transient':{'times':times,'events':[{'time':0.5}]}}

class IndependentAssessment(unittest.TestCase):
    def test_pass_fail_and_unresolved_timing_are_distinct(self):
        case=CASES[1]
        requests,_=adapter.prepare_requests(case)
        for speed,shift,expected in [(1,0,'pass'),(.5,0,'fail'),*[(1,shift,'inconclusive') for shift in [150e-9,-150e-9,1e-6,-1e-6]]]:
            data={name:constant_response(r['transient']['output_times'],speed,shift) for name,r in requests.items()}
            self.assertEqual(adapter.assess_case(case,**data)['verdict'],expected)

    def test_incomplete_response_never_grades_a_candidate(self):
        case=CASES[1]
        requests,_=adapter.prepare_requests(case)
        data={name:constant_response(r['transient']['output_times']) for name,r in requests.items()}
        data['observation']['solutions'].pop()
        self.assertEqual(adapter.assess_case(case,**data)['verdict'],'not_evaluated')

class CompleteReport(unittest.TestCase):
    def test_missing_kernel_preserves_all_eight_without_score(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            candidate=root/'dut.va'; candidate.write_text('module triangle; endmodule')
            report=adapter.verify(candidate,root/'result',ROOT/'benchmark/tasks/va07-triangle-repair/tests/cases.json',root/'missing',adapter.SOLVER_OPTIONS)
            self.assertEqual(len(report['cases']),8)
            self.assertIsNone(report['reward'])
            self.assertTrue(all(c['status']=='not_evaluated' for c in report['cases']))

class ProcessBoundary(unittest.TestCase):
    def test_constructed_cli_retains_eight_passes_failures_and_backend_errors(self):
        fake = """
import json, os, sys
from pathlib import Path
r=json.loads(Path(sys.argv[2]).read_text())
if os.environ['REPLAY_TEST_MODE']=='timeout':
    import time
    time.sleep(10)
if os.environ['REPLAY_TEST_MODE']=='drift':
    Path(__file__).write_text(Path(__file__).read_text()+'\\n# changed runtime')
if os.environ['REPLAY_TEST_MODE']=='backend':
    raise SystemExit(9)
p=r['instances'][0]['parameters']; control=r['transient']['sources']['ctl']; times=r['transient']['output_times']
rootsets={3:[.5,1.5,2.5],6:[.75,2.75,4.75]}
if len(control)==5:
    roots=[.3520303695138075,1.3591663046625437]
elif control[-1][1]==2.5:
    roots=[.4494897427831781,1.162277660168379,1.7416573867739416,2.242640687119285,2.6904157598234293]
else:
    roots=rootsets[r['transient']['stop']]
solutions=[]
for t in times:
    area=0
    for (a,x),(b,y) in zip(control,control[1:]):
        dt=max(0,min(t,b)-a)
        area+=x*dt+(y-x)*dt*dt/(2*(b-a))
    width=p['upper']-p['lower']; phase=p['initial_voltage']-p['lower']
    if p['direction']<0: phase=2*width-phase
    phase=(phase+area)%(2*width)
    z=p['lower']+(phase if phase<=width else 2*width-phase)
    if os.environ['REPLAY_TEST_MODE']=='fail' or (os.environ['REPLAY_TEST_MODE']=='mixed' and p['upper']==.75): z+=.1
    shift=150e-9 if os.environ['REPLAY_TEST_MODE']=='inconclusive' else 0
    solutions.append({'voltages':[z,sum(t>=root+shift for root in roots)]})
print(json.dumps({'nodes':['z','count'],'solutions':solutions,'transient':{'times':times,'events':[{'time':-999}]}}))
"""
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); package=root/'evas'; package.mkdir(); (package/'__init__.py').write_text('')
            (package/'__main__.py').write_text(fake)
            kernel=root/'kernel'; kernel.write_text('constructed identity only')
            candidate=root/'dut.va'; candidate.write_bytes((ROOT/'benchmark/tasks/va07-triangle-repair/solution/dut.va').read_bytes())
            with patch.dict(os.environ,{'PYTHONPATH':str(root)}), patch.object(sys,'path',[str(root),*sys.path]):
                for mode,reward in [('pass',1),('fail',0),('mixed',0),('backend',None),('inconclusive',None),('timeout',None),('drift',None)]:
                    (package/'__main__.py').write_text(fake)
                    with patch.dict(os.environ,{'REPLAY_TEST_MODE':mode}):
                        report=adapter.verify(candidate,root/mode,ROOT/'benchmark/tasks/va07-triangle-repair/tests/cases.json',kernel,adapter.SOLVER_OPTIONS,timeout_s=.05 if mode=='timeout' else 15)
                    self.assertEqual(report['reward'],reward,report)
                    self.assertEqual(len(report['cases']),8)
                    if mode=='mixed':
                        self.assertEqual(sum(c['passed'] is True for c in report['cases']),6)
                    if reward is not None:
                        self.assertTrue(all(c['status']=='graded' and c['waveform_sha256'] for c in report['cases']))

class FrozenPackage(unittest.TestCase):
    def test_builder_keeps_original_case_bytes_and_backend_shared_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'package'
            manifest=builder.build_package(out)
            self.assertEqual((out/'cases.json').read_bytes(),(ROOT/'benchmark/tasks/va07-triangle-repair/tests/cases.json').read_bytes())
            self.assertEqual(manifest['condition_id'],'va07-original-eight-cases-df84f3123a91')
            self.assertEqual(manifest['task_version'],'dev-df643eaf9fd82a56')
            self.assertNotIn('dut.va',manifest['files'])
            for name,item in manifest['files'].items():
                self.assertEqual(item['sha256'],adapter.digest(out/name))
            self.assertEqual(len(json.loads((out/'mapping.json').read_text())['cases']),8)
            with self.assertRaises(FileExistsError): builder.build_package(out)

class MappingRejections(unittest.TestCase):
    def test_unknown_case_setting_is_not_ignored(self):
        case=dict(CASES[0],method_override='gear2')
        with self.assertRaises(ValueError): adapter.prepare_requests(case)

    def test_unmapped_solver_option_keeps_all_entries_ungraded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); candidate=root/'dut.va'; candidate.write_text('module triangle; endmodule')
            report=adapter.verify(candidate,root/'result',ROOT/'benchmark/tasks/va07-triangle-repair/tests/cases.json',root/'missing',dict(adapter.SOLVER_OPTIONS,iabstol=1e-18))
            self.assertIsNone(report['reward'])
            self.assertEqual(len(report['cases']),8)
            self.assertIn('mapping',report['reason'])

class OracleIdentity(unittest.TestCase):
    def test_report_only_oracle_copy_is_allowed_but_behavior_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); oracle=root/'oracle.py'
            original=adapter.ORACLE_PATH.read_text()
            oracle.write_text(original+'\n# report-only source annotation\n')
            builder.build_package(root/'allowed',oracle)
            reported=original.replace('def evaluate(rows, case, event_times=None):', 'class BehavioralRejection(ValueError):\n    \"Report classification only.\"\n\ndef evaluate(rows, case, event_times=None):')
            for message in ['noninteger count','missing, grouped or reversed count','incorrect count outside event windows','incorrect event count']:
                reported=reported.replace(f"raise ValueError('{message}')",f"raise BehavioralRejection('{message}')")
            oracle.write_text(reported)
            builder.build_package(root/'classified',oracle)
            oracle.write_text(original.replace("wave_atol'] and time_error", "wave_atol']*2 and time_error"))
            with self.assertRaisesRegex(ValueError,'behavior criteria'):
                builder.build_package(root/'rejected',oracle)

class HarnessPackageBoundary(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('HARNESS_CHECKOUT'),'explicit Harness checkout required')
    def test_generated_package_is_accepted_by_harness(self):
        with patch.object(sys,'path',[os.environ['HARNESS_CHECKOUT'],*sys.path]):
            from alphaapollo.common.execution.chips.benchmark_spectre import package_identity
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'package'; builder.build_package(root)
            identity=package_identity(root,purpose='final')
            self.assertEqual(identity['manifest']['task_set'],'extension')
            self.assertEqual(len(identity['files']),6)

if __name__ == '__main__':
    unittest.main()
