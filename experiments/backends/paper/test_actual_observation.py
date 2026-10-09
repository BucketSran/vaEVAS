"""Synthetic calibration only: these fixtures are not actual paper evidence."""
import copy
from fractions import Fraction as F
import unittest
from actual_observation import adapt,derive,canonical_sha,upper,input_curve_bound,sha


class ActualEvidence(unittest.TestCase):
    def setUp(self):
        self.card={'id':'fixture','source':'fixture source','stimulus':{'u':{'kind':'pwl','points_T_V':[[0,0],[1,1],[2,1]]}},
                   'stop_T':1,'observables':['u','count'],'anchors':[{'t_T':1}], 'observation_windows':[]}
        self.request={'inputs':{'u':[[0,0],[1e-6,1],[2e-6,1]]},'stop':1e-6}
        self.response={'nodes':['u','count'],'solutions':[{'voltages':[0,0]},{'voltages':[1,1]}],
                       'transient':{'times':[0,1e-6],'events':[{'time':0.5e-6}]},
                       'observation_evidence':{'schema_version':1,'nodes':['u','count'],
                            'voltage_bounds_V':[[[0,0],[0,0]],[[1,1],[0.99999,1.00001]]],
                            'sample_origins':['accepted_controller_frame']*2,'initial_settled':True,
                            'effective_controls':{'absolute_V':1e-7,'relative':0,'stop_s':1e-6,'max_step_s':1e-7,'max_step_applied':True}}}
        self.previous={'condition':'fixture','backend':'evas','rows':[{'time':0,'u':0,'count':0},{'time':1e-6,'u':1,'count':1}]}
        self.review={'schema_version':1,'core-v1.json_file_sha':'core','records':[{'condition':'fixture',
                     'source_sha256':'source','card_sha256':canonical_sha(self.card),'status':'reviewed','basis':'Synthetic calibration review only'}]}
    def run_derive(self):
        return derive(self.card,self.request,[0,1e-6],self.response,self.previous,self.review,core_sha='core',source_sha='source')
    def test_actual_radius_not_tolerance_and_continuous_input_sup(self):
        rows,origins,facts=self.run_derive()
        self.assertEqual(rows,self.previous['rows']);self.assertEqual(origins,['accepted']*2)
        self.assertGreater(facts['voltage_error_V'],1e-7)
        self.assertEqual(facts['missing_roles'],[])
        self.assertLess(facts['input_error_V'],1e-12)
        self.assertEqual(facts['roles']['native_initial']['status'],'established')
        self.assertGreaterEqual(F(facts['time_error_s']),abs(F(1e-6)-F(1,10**6)))
    def test_missing_interval_and_direct_query_are_not_promoted(self):
        self.response['observation_evidence']['voltage_bounds_V'][1]=None
        self.response['observation_evidence']['sample_origins'][1]='certified_causal_frame'
        _,origins,facts=self.run_derive()
        self.assertEqual(origins,['accepted','unknown'])
        self.assertIn('voltage',facts['missing_roles']);self.assertIn('native_counters',facts['missing_roles'])
    def test_initial_callback_bound_touching_zero_stays_unknown(self):
        self.response['transient']['events'][0]['observation_time_bounds']=[0,1e-6]
        self.assertEqual(self.run_derive()[2]['roles']['native_initial']['status'],'unknown')
    def test_identity_and_invalid_interval_fail_closed(self):
        original=copy.deepcopy(self.response)
        for mutation in ('raw','node','bounds','request','review'):
            self.setUp()
            if mutation=='raw':self.previous['rows'][1]['count']=2
            if mutation=='node':self.response['observation_evidence']['nodes'].reverse()
            if mutation=='bounds':self.response['observation_evidence']['voltage_bounds_V'][1][1]=[2,3]
            if mutation=='request':self.request['inputs']['u'][1][1]=2
            if mutation=='review':self.review['records'][0]['card_sha256']='wrong'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.run_derive()
        self.response=original
    def test_failed_unknown_or_empty_review_is_not_source_qualification(self):
        for status,basis in [('unknown','review'),('failed','review'),('reviewed','')]:
            self.review['records'][0].update(status=status,basis=basis)
            self.assertIn('source',self.run_derive()[2]['missing_roles'])
    def test_continuous_union_bound_detects_positive_and_negative_perturbations(self):
        for delta in (0.01,-0.01):
            actual=copy.deepcopy(self.request);actual['inputs']['u'][1][1]+=delta
            bound,details=input_curve_bound(self.card,actual)
            self.assertGreaterEqual(bound,abs(delta))
            self.assertGreaterEqual(details['inputs']['u']['union_knots'],3)
        actual=copy.deepcopy(self.request);actual['inputs']['u']=actual['inputs']['u'][:2]
        self.assertIsNone(input_curve_bound(self.card,actual)[0])

    def test_new_packet_preserves_raw_bytes_and_uses_actual_review_schema(self):
        import json,tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir()
            core=root/'core.json';source_review=root/'review.json';output=root/'new'
            contract={'sample_gap_s':2e-6,'required_observation_error':{'time_s':1e-11,'voltage_V':5e-5},'input_error_V':1e-5}
            core.write_text(json.dumps({'cards':[self.card],'shared_contract':contract}))
            (work/'dut.va').write_text(self.card['source'])
            request={**self.request,'requested_times':'times.json'}
            for name,value in [('condition.json',self.card),('request.json',request),('times.json',[0,1e-6]),('raw-response.json',self.response),('observation.json',self.previous)]:
                (work/name).write_text(json.dumps(value))
            review=copy.deepcopy(self.review);review.pop('core-v1.json_file_sha');review['cards_sha256']=sha(core)
            review['records'][0].update(source_sha256=sha(work/'dut.va'),basis=['Synthetic test only'])
            source_review.write_text(json.dumps(review))
            before={p.name:p.read_bytes() for p in work.iterdir()}
            report,normalized=adapt(core,'fixture',work,source_review,output)
            self.assertEqual(normalized['rows'],self.previous['rows'])
            self.assertEqual(report['missing_roles'],[])
            self.assertEqual(before,{p.name:p.read_bytes() for p in work.iterdir()})
            self.assertTrue((output/'evidence.json').exists())
            with self.assertRaises(ValueError):adapt(core,'fixture',work,source_review,output)

    def test_outward_conversion_never_shrinks_rational_bound(self):
        for value in (F(1,10),F(1,10**400),F(0),F(1,3)):
            self.assertGreaterEqual(F(upper(value)),value)

if __name__=='__main__':unittest.main()
