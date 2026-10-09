"""Synthetic calibration only: these fixtures are not actual paper evidence."""
import copy
from fractions import Fraction as F
import unittest
from actual_observation import adapt,derive,canonical_sha,upper,input_curve_bound,sha,execution_identity


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
        return derive(self.card,self.request,[0,1e-6],self.response,self.previous,self.review,core_sha='core',source_sha='source',execution={'verified':True,'stateless_program':True},breakpoints=getattr(self,'breakpoints',None))
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
            self.assertGreaterEqual(F(bound),abs(F(actual['inputs']['u'][1][1])-F(actual['stop'])/F(1,10**6)))
            self.assertGreaterEqual(details['inputs']['u']['union_knots'],2)
        actual=copy.deepcopy(self.request);actual['inputs']['u']=[[0,0],[0.5e-6,1]]
        self.assertIsNone(input_curve_bound(self.card,actual)[0])

    def test_executed_domain_and_stop_roundoff_are_explicit(self):
        self.card['stop_T']=8;self.card['anchors']=[]
        self.card['stimulus']['u']['points_T_V']=[[0,0],[8,1]]
        request={'stop':8e-6,'inputs':{'u':[[0,0],[8e-6,1]]}}
        bound,details=input_curve_bound(self.card,request)
        self.assertIsNotNone(bound);self.assertEqual(details['domain_s'][1],8e-6)
        # Opposite roundoff sign uses existing decimal oracle endpoint hold,
        # while the actual source remains covered through its actual endpoint.
        self.card['stop_T']=6;self.card['stimulus']['u']['points_T_V']=[[0,0],[6,1]]
        request={'stop':6e-6,'inputs':{'u':[[0,0],[6e-6,1]]}}
        self.assertIsNotNone(input_curve_bound(self.card,request)[0])

    def test_causal_and_stateless_native_require_certificate_and_execution_identity(self):
        for origin in ('certified_causal_frame','stateless_working_point'):
            self.response['observation_evidence']['sample_origins']=[origin]*2
            if origin=='stateless_working_point':self.response['transient']['events']=[]
            self.assertEqual(self.run_derive()[1],['accepted']*2)
            no_identity=derive(self.card,self.request,[0,1e-6],self.response,self.previous,self.review,core_sha='core',source_sha='source')
            self.assertEqual(no_identity[1],['unknown']*2)
        self.response['observation_evidence']['sample_origins']=['implicit_history_evaluation']*2
        self.assertEqual(self.run_derive()[1],['accepted','unknown'])

    def test_boundary_role_uses_unique_actual_request_id_and_same_response(self):
        self.card['observation_windows']=[{'center_T':1,'start_T':0.9,'end_T':1,'max_gap_s':1e-6,'include_exact_center':True}]
        self.review['records'][0]['card_sha256']=canonical_sha(self.card)
        self.breakpoints={'records':[{'time_s':1e-6,'request_id':'fixture:breakpoint:actual'}]}
        facts=self.run_derive()[2]
        self.assertIn('boundary_cohort',facts['required_roles']);self.assertNotIn('boundary_cohort',facts['missing_roles'])
        self.assertEqual(facts['boundary_cohort']['records'],[{'nominal_time_s':1e-6,'row_index':1,'request_id':'fixture:breakpoint:actual'}])
        self.breakpoints['records'].append(copy.deepcopy(self.breakpoints['records'][0]))
        self.assertIn('boundary_cohort',self.run_derive()[2]['missing_roles'])
        self.breakpoints={'records':[{'time_s':0.9e-6,'request_id':'nearest-is-not-center'}]}
        self.assertIn('boundary_cohort',self.run_derive()[2]['missing_roles'])

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
            self.assertIn('native_initial',report['missing_roles'])
            self.assertIn('native_counters',report['missing_roles'])
            self.assertEqual(before,{p.name:p.read_bytes() for p in work.iterdir()})
            self.assertTrue((output/'evidence.json').exists())
            with self.assertRaises(ValueError):adapt(core,'fixture',work,source_review,output)

    def test_full_existing_receipt_chain_and_boundary_packet_fail_closed_on_drift(self):
        import json,tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);lane=root/'lane';work=lane/'runs'/'fixture';work.mkdir(parents=True)
            core=root/'core.json';review_path=root/'review.json';build_path=root/'BUILD.json';sources_path=root/'SOURCE_MANIFEST.json';profile_path=root/'profile.json'
            self.card['observation_windows']=[{'center_T':1,'start_T':0.9,'end_T':1,'max_gap_s':1e-6,'include_exact_center':True}]
            contract={'sample_gap_s':2e-6,'required_observation_error':{'time_s':1e-11,'voltage_V':5e-5},'input_error_V':1e-5}
            def write(path,value):path.write_text(json.dumps(value))
            write(core,{'cards':[self.card],'shared_contract':contract});(work/'dut.va').write_text(self.card['source'])
            for name,value in [('request.json',{**self.request,'requested_times':'times.json'}),('times.json',[0,1e-6]),('condition.json',self.card),
                    ('raw-response.json',self.response),('observation.json',self.previous),('program.json',{'nodes':['u','count'],'states':[],'events':[],'operators':[]}),
                    ('worker-result.json',{'status':'waveform_available'}),('breakpoint_requests.json',{'records':[{'time_s':1e-6,'request_id':'fixture:real-id'}]})]:write(work/name,value)
            sources={name:sha(Path(__file__).resolve().parents[3]/name) for name in
                     ('evas/rust_core/src/transient.rs','evas/rust_core/src/transient_event_acceptance.rs','evas/rust_core/src/implicit_dynamics.rs','evas/rust_core/src/observation.rs','evas/rust_core/src/exact_source.rs','evas/rust_core/Cargo.lock')}
            write(sources_path,sources)
            stage={'status':'completed','returncode':0,'timeout':False,'cleanup':{'complete':True},'argv':['kernel']}
            build={'stage':stage,'kernel_sha256':'synthetic-kernel','source_revision':'synthetic-revision','source_manifest_sha256':sha(sources_path),
                   'cargo_lock_sha256':sources['evas/rust_core/Cargo.lock'],'compiler_identity':{'cargo':{'actual_binary_sha256':'synthetic-cargo'},'rustc':{'actual_binary_sha256':'synthetic-rustc'}}}
            write(build_path,build)
            profile={'backend':'evas','kernel':'kernel','kernel_sha256':'synthetic-kernel','build_record_sha256':sha(build_path)};write(profile_path,profile)
            tool={'kernel':'kernel','kernel_sha256':'synthetic-kernel','profile_identity':canonical_sha(profile),'probe':stage};write(lane/'TOOL_IDENTITY.json',tool)
            write(work/'STARTED.json',{'condition':'fixture','source_sha256':sha(work/'dut.va'),'deck_sha256':sha(work/'request.json'),'tool_identity_sha256':sha(lane/'TOOL_IDENTITY.json')})
            write(lane/'final-record-fixture.json',{'backend':'evas','condition':'fixture','status':'waveform_available','source_sha256':sha(work/'dut.va'),
                  'condition_identity':canonical_sha(self.card),'stages':[stage],'observation':{'path':'runs/fixture/observation.json','sha256':sha(work/'observation.json')}})
            write(lane/'FILE_MANIFEST.json',{str(p.relative_to(lane)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in lane.rglob('*') if p.is_file()})
            review=copy.deepcopy(self.review);review['core-v1.json_file_sha']=sha(core);review['records'][0].update(card_sha256=canonical_sha(self.card),source_sha256=sha(work/'dut.va'));write(review_path,review)
            options={'lane':lane,'build_record':build_path,'source_manifest':sources_path,'tool_profile':profile_path}
            report,normalized=adapt(core,'fixture',work,review_path,root/'out',**options)
            self.assertEqual(report['missing_roles'],[]);self.assertTrue(normalized['qualification']['qualified'])
            self.assertEqual(normalized['qualification']['boundary_cohort']['records'][0]['request_id'],'fixture:real-id')
            build['kernel_sha256']='different';write(build_path,build)
            with self.assertRaisesRegex(ValueError,'build/tool chain'):execution_identity(lane,work,self.card,**{k:v for k,v in options.items() if k!='lane'})
            write(build_path,{**build,'kernel_sha256':'synthetic-kernel'})
            (work/'raw-response.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'manifest identity'):execution_identity(lane,work,self.card,**{k:v for k,v in options.items() if k!='lane'})

    def test_outward_conversion_never_shrinks_rational_bound(self):
        for value in (F(1,10),F(1,10**400),F(0),F(1,3)):
            self.assertGreaterEqual(F(upper(value)),value)

if __name__=='__main__':unittest.main()
