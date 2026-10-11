"""Configuration qualification and complete-plan negative controls."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'evas/validation/paper'))
from precision_v2 import load_contract
from precision_v2_report import control_qualification, select, step_path_is_verified, verify_case_inputs, sha


class ReportingChecks(unittest.TestCase):
    def test_aborted_or_absent_configs_keep_whole_denominator(self):
        contract=load_contract();summary=select([],contract)
        self.assertTrue(all(v['total']==4 and v['passed']==0 for family in summary.values() for backend in family.values() for v in backend.values()))

    def test_selection_is_per_tier_and_regression_does_not_disappear(self):
        c=load_contract();rows=[]
        for p in c['profiles']:
            rows.append({'backend':'evas','condition':'LP-RAMP','profile':p['id'],
                         'tiers':{q:{'status':('pass' if p['id']=='tol' else 'numerical_error')} for q in ('Q1','Q2','Q3')}})
        r=select(rows,c)['first_order']['evas']['Q2']
        self.assertEqual(r['passed'],1);self.assertEqual(r['total'],4)
        self.assertEqual(r['conditions']['LP-RAMP']['selected_profile'],'tol')
        self.assertEqual(len(r['later_nonpass']),3)

    def test_requested_echo_does_not_establish_effective_setting(self):
        c=load_contract()
        request={'reltol':1e-8,'vabstol_V':1e-12,'iabstol_A':1e-15,'maxstep_s':1e-9,'stop_s':1e-6}
        q={'issues':[],'actual':{'reltol':1e-8,'vabstol':1e-12,'maxstep':1e-9,'stop':1e-6},
           'additional_controls':{'max_step_applied':True}}
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);(work/'requested_settings.json').write_text(json.dumps(request))
            for mutation in ('unchanged','wrong_tol','unapplied','missing'):
                value=copy.deepcopy(q)
                if mutation=='wrong_tol':value['actual']['reltol']=1e-5
                if mutation=='unapplied':value['additional_controls']['max_step_applied']=False
                if mutation=='missing':value['actual'].pop('maxstep')
                with patch('precision_v2_report.legacy_qualification',return_value=value):
                    result=control_qualification(work,'evas',{},[],c,{})
                self.assertEqual(result['status'],'qualified' if mutation=='unchanged' else 'evidence_insufficient')

    def test_missing_extra_controls_and_step_proof_reject(self):
        c=load_contract()
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            (work/'requested_settings.json').write_text(json.dumps({'reltol':1e-8,'vabstol_V':1e-12,'iabstol_A':1e-15}))
            (work/'simulate.log').write_text('* Current simulation options *\ntrtol = 7\nchgtol = 1e-14\nitl4 = 10\n')
            base={'issues':[],'actual':{'reltol':1e-8,'vabstol':1e-12,'iabstol':1e-15},'additional_controls':{}}
            with patch('precision_v2_report.legacy_qualification',return_value=copy.deepcopy(base)):
                r=control_qualification(work,'openvaf_r_ngspice',{},[],c,{})
            self.assertEqual(r['status'],'evidence_insufficient')
            self.assertIn('maxstep/stop',r['issues'][0])
            (work/'simulate.log').write_text('trtol = 70\n')
            with patch('precision_v2_report.legacy_qualification',return_value=copy.deepcopy(base)):
                r=control_qualification(work,'openvaf_r_ngspice',{},[],c,{})
            self.assertGreater(len(r['issues']),1)

    def test_step_proof_requires_identity_attachments_and_review(self):
        self.assertFalse(step_path_is_verified({'verified':True},None))
        self.assertFalse(step_path_is_verified({'verified':True,'image_id':''},''))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audit=root/'audit.json';review=root/'review.md'
            audit.write_text(json.dumps({'image_id':'sha256:installed','method':'installed_source_parameter_path',
                'controls':['maxstep','stop'],'source_hashes':{'source.cc':'source-digest'},'binary_hashes':{'solver':'binary-digest'}}))
            review.write_text('Synthetic audit fixture, not actual backend evidence.')
            evidence={'verified':True,'image_id':'sha256:installed',
                'artifact':{'path':audit.name,'sha256':sha(audit)},
                'review':{'path':review.name,'sha256':sha(review),'reviewer':'calibration'}}
            with patch('precision_v2_report.ROOT',root):
                self.assertTrue(step_path_is_verified(evidence,'sha256:installed'))
                self.assertFalse(step_path_is_verified(evidence,'sha256:another-build'))
                for field in ('artifact','review'):
                    bad=copy.deepcopy(evidence);bad[field]['sha256']='changed'
                    self.assertFalse(step_path_is_verified(bad,'sha256:installed'))
                bad=copy.deepcopy(evidence);bad['verified']=1
                self.assertFalse(step_path_is_verified(bad,'sha256:installed'))
                bad=copy.deepcopy(evidence);bad['review']['reviewer']=''
                self.assertFalse(step_path_is_verified(bad,'sha256:installed'))

    def test_executed_cards_controls_and_observations_are_bound_to_frozen_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);frozen=root/'frozen';work=root/'work';frozen.mkdir();work.mkdir()
            names=('dut.va','dut.cir','condition.json','requested_settings.json','requested_times.json','observation_plan.json')
            for name in names:
                (frozen/name).write_text('frozen '+name);(work/name).write_text('frozen '+name)
            p={'deck':'dut.cir','source_sha256':sha(work/'dut.va')}
            verify_case_inputs(work,frozen,p)
            for name in names:
                (work/name).write_text('different')
                with self.assertRaisesRegex(ValueError,'executed input drift'):
                    verify_case_inputs(work,frozen,p)
                (work/name).write_bytes((frozen/name).read_bytes())

    def test_gnucap_tick_quantization_is_not_exact_requested_deep_control(self):
        c=load_contract()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'audit.json').write_text(json.dumps({'mapping':'gnucap-time-ticks-v1'}))
            (root/'simulate.log').write_text('dtmin= 1e-16 trtol= 7 dtratio= 1e9\n')
            for step,expected in ((3.125e-8,'qualified'),(4.8828125e-10,'evidence_insufficient')):
                request={'reltol':1e-8,'vabstol_V':1e-12,'iabstol_A':1e-15,'maxstep_s':step,'stop_s':8e-6}
                (root/'requested_settings.json').write_text(json.dumps(request))
                base={'issues':[],'actual':{'reltol':1e-8,'vabstol':1e-12,'iabstol':1e-15},'additional_controls':{}}
                with patch('precision_v2_report.ROOT',root),patch('precision_v2_report.step_path_is_verified',return_value=True),patch('precision_v2_report.legacy_qualification',return_value=base):
                    result=control_qualification(root,'gnucap_modelgen',{},[],c,{}, {'artifact':{'path':'audit.json'}})
                self.assertEqual(result['status'],expected)
                if expected!='qualified':
                    self.assertAlmostEqual(result['source_mapped_controls']['maxstep_s'],4.882813e-10,delta=1e-25)


if __name__=='__main__':unittest.main()
