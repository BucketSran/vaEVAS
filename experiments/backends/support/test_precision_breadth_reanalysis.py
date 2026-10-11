import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('reanalysis',Path(__file__).with_name('precision_breadth_reanalysis.py'))
r = importlib.util.module_from_spec(spec);spec.loader.exec_module(r)


class ReanalysisCalibration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name);self.lane = self.root/'lane';self.lane.mkdir()

    def manifest(self):
        r.save(self.lane/'FILE_MANIFEST.json',{str(p.relative_to(self.lane)):{'sha256':r.sha(p),'bytes':p.stat().st_size}
              for p in self.lane.rglob('*') if p.is_file() and p.name!='FILE_MANIFEST.json'})

    def test_open_gate_keeps_legacy_binding_and_actual_integrator_obligations(self):
        q={'status':'qualified'};binding={'status':'matched'}
        adapter={key:q for key in ('identity','config','runtime','native','integrator')}
        config,native,runtime=r.open_gate(q,binding,adapter)
        self.assertEqual(config['status'],'qualified')
        for axis in ('identity','config','integrator'):
            changed={**adapter,axis:{'status':'unknown'}}
            self.assertEqual(r.open_gate(q,binding,changed)[0]['status'],'unknown')
        self.assertEqual(r.open_gate({'status':'unknown'},binding,adapter)[0]['status'],'unknown')
        self.assertEqual(r.open_gate(q,{'status':'unmatched'},adapter)[0]['status'],'unknown')
        self.assertEqual(native['status'],'qualified')
        self.assertEqual(runtime['status'],'qualified')

    def test_external_execution_manifest_is_independent_and_exhaustively_verified(self):
        inputs=self.root/'inputs';inputs.mkdir()
        p=inputs/'runs/backend/slot/dut.va';p.parent.mkdir(parents=True);p.write_text('original')
        r.save(inputs/'MANIFEST.json',{'runs/backend/slot/dut.va':r.sha(p)})
        self.assertEqual(r.verified_execution_inputs(inputs)['runs/backend/slot/dut.va'],r.sha(p))
        p.write_text('changed')
        with self.assertRaises(ValueError):r.verified_execution_inputs(inputs)
        r.save(inputs/'MANIFEST.json',{})
        with self.assertRaises(ValueError):r.verified_execution_inputs(inputs)

    def test_open_adapter_without_sealed_configuration_is_unknown(self):
        result=r.external_open_evidence(self.root,self.lane,{}, {'backend':'gnucap_modelgen','label':'slot'})
        self.assertEqual(result['integrator']['status'],'unknown')
        self.assertEqual(result['identity']['status'],'unknown')

    def test_external_seal_records_separate_identity_and_rejects_drift(self):
        adapter=self.root/'adapter.py';adapter.write_text('def qualify_open_backend(*a,**k): return {}')
        out=self.root/'out';out.mkdir();r.save(out/'ANALYSIS_IDENTITY.json',{'source_hashes':{'science.py':'fixed'}})
        args=types.SimpleNamespace(open_evidence_adapter=adapter,open_proof=None,
              approved_open_proof_sha256=None,approved_open_adapter_sha256=None,proof_evidence_root=None,execution_inputs=None)
        r.seal_open_evidence(args,out)
        self.assertEqual(r.load(out/'ANALYSIS_IDENTITY.json')['source_hashes'],{'science.py':'fixed'})
        record={'backend':'gnucap_modelgen','label':'slot'}
        self.assertEqual(r.external_open_evidence(out,self.lane,{},record)['native']['status'],'unknown')
        (out/'external-open-evidence/adapter.py').write_text('changed')
        with self.assertRaises(ValueError):r.external_open_evidence(out,self.lane,{},record)
        identity=r.load(out/'OPEN_EVIDENCE_IDENTITY.json');identity['approved_proof_sha256']='fictional'
        r.save(out/'OPEN_EVIDENCE_IDENTITY.json',identity)
        with self.assertRaises(ValueError):r.external_open_evidence(out,self.lane,{},record)

    def test_external_proof_attachment_cannot_escape_or_change(self):
        adapter=self.root/'adapter.py';adapter.write_text('pass')
        evidence=self.root/'evidence';evidence.mkdir();(evidence/'review.md').write_text('fixed review')
        proof=self.root/'proof.json';r.save(proof,{'attachments':{'review.md':'wrong-digest'}})
        out=self.root/'out';out.mkdir();r.save(out/'ANALYSIS_IDENTITY.json',{})
        args=types.SimpleNamespace(open_evidence_adapter=adapter,open_proof=proof,
             approved_open_proof_sha256=None,approved_open_adapter_sha256=None,proof_evidence_root=evidence,execution_inputs=None)
        with self.assertRaises(ValueError):r.seal_open_evidence(args,out)
        other=self.root/'outside';other.write_text('outside')
        r.save(proof,{'attachments':{'../outside':r.sha(other)}})
        out2=self.root/'out2';out2.mkdir();r.save(out2/'ANALYSIS_IDENTITY.json',{})
        with self.assertRaises(ValueError):r.seal_open_evidence(args,out2)

    def test_open_caller_uses_original_execution_manifest_and_rejects_missing_trust(self):
        backend='gnucap_modelgen';label='slot';work=self.lane/'runs'/label;work.mkdir(parents=True)
        names=(*r.OPEN_INPUTS,'tb.gc','simulate-final.json','simulate.log','waveform.txt','dut.so','INPUT_IDENTITY.json','RESULT.json')
        for name in names:(work/name).write_text('raw '+name)
        self.manifest()
        inputs=self.root/'inputs';inputs.mkdir()
        manifest={'runs/'+backend+'/'+label+'/'+name:'original-'+name for name in (*r.OPEN_INPUTS,'tb.gc')}
        # The sealed manifest is the independent input authority; the reviewed
        # adapter must subsequently match its bytes against the actual raw work.
        adapter=self.root/'adapter.py'
        adapter.write_text("def qualify_open_backend(work,backend,tool,frozen_manifest,raw_manifest,**kwargs):\n    return {axis:{'status':'qualified','frozen':frozen_manifest,'raw':raw_manifest} for axis in ('identity','config','runtime','native','integrator','diagnostics','observations')}\n")
        proof=self.root/'proof.json';r.save(proof,{'attachments':{}})
        out=self.root/'out';out.mkdir();r.save(out/'ANALYSIS_IDENTITY.json',{})
        args=types.SimpleNamespace(open_evidence_adapter=adapter,open_proof=proof,
             approved_open_proof_sha256=r.sha(proof),approved_open_adapter_sha256=r.sha(adapter),
             proof_evidence_root=None,execution_inputs=None)
        r.seal_open_evidence(args,out)
        r.save(out/'external-open-evidence/EXECUTION_MANIFEST.json',manifest)
        config=r.load(out/'OPEN_EVIDENCE_IDENTITY.json')
        config['sealed_files']['external-open-evidence/EXECUTION_MANIFEST.json']=r.sha(out/'external-open-evidence/EXECUTION_MANIFEST.json')
        r.save(out/'OPEN_EVIDENCE_IDENTITY.json',config)
        r.save(out/'ANALYSIS_IDENTITY.json',{'external_open_evidence_identity_sha256':r.sha(out/'OPEN_EVIDENCE_IDENTITY.json')})
        result=r.external_open_evidence(out,work,{}, {'backend':backend,'label':label})
        self.assertEqual(result['identity']['frozen']['dut.va'],'original-dut.va')
        self.assertEqual(result['identity']['raw']['dut.so'],r.sha(work/'dut.so'))
        config['approved_proof_sha256']=None;r.save(out/'OPEN_EVIDENCE_IDENTITY.json',config)
        r.save(out/'ANALYSIS_IDENTITY.json',{'external_open_evidence_identity_sha256':r.sha(out/'OPEN_EVIDENCE_IDENTITY.json')})
        self.assertEqual(r.external_open_evidence(out,work,{}, {'backend':backend,'label':label})['identity']['status'],'unknown')

    def test_external_integrator_axis_does_not_apply_to_evas_or_spectre(self):
        for backend in ('evas','spectre'):
            self.assertEqual(r.integrator_axis(backend,None)['status'],'not_applicable')
        self.assertEqual(r.integrator_axis('gnucap_modelgen',None)['status'],'unknown')
        self.assertEqual(r.integrator_axis('gnucap_modelgen',{'integrator':{'status':'qualified'}})['status'],'qualified')

    def test_manifest_rejects_changed_or_extra_files(self):
        p=self.lane/'raw';p.write_text('original');self.manifest()
        self.assertEqual(r.verify_lane(self.lane)['status'],'verified')
        p.write_text('modified')
        with self.assertRaises(ValueError): r.verify_lane(self.lane)
        p.write_text('original');(self.lane/'extra').write_text('extra')
        with self.assertRaises(ValueError): r.verify_lane(self.lane)

    def test_explicit_frozen_inputs_reject_card_or_checker_hash_drift(self):
        inputs=self.root/'inputs';inputs.mkdir();output=self.root/'output';output.mkdir()
        r.save(inputs/'cards.json',{'cards':[]})
        expected={'checker.py':'known-checker','evas/validation/paper/precision-v2.json':'known-contract'}
        r.save(inputs/'SOURCE_IDENTITY.json',expected)
        r.save(inputs/'PROFILE_BINDINGS.json',{'backend_tier_profiles':{},'profiles':{}})
        r.save(inputs/'MANIFEST.json',{name:r.sha(inputs/name) for name in ('cards.json','SOURCE_IDENTITY.json','PROFILE_BINDINGS.json')})
        r.freeze_inputs(inputs,output,expected)
        self.assertEqual(r.sha(output/'OFFICIAL_CARDS.json'),r.sha(inputs/'cards.json'))
        with self.assertRaises(ValueError):r.freeze_inputs(inputs,output,{**expected,'checker.py':'changed'})
        r.save(inputs/'cards.json',{'cards':['tampered']})
        with self.assertRaises(ValueError):r.freeze_inputs(inputs,output,expected)

    def test_source_rename_cannot_inherit_new_answer(self):
        c={'source':'module old; endmodule','id':'F03','group_id':'F03'}
        (self.lane/'dut.va').write_text(c['source']);r.save(self.lane/'condition.json',c)
        old={'source_sha256':r.sha(self.lane/'dut.va')}
        self.assertEqual(r.compatible(c,self.lane,old)['status'],'compatible')
        c['source']='module fixed; endmodule'
        self.assertEqual(r.compatible(c,self.lane,old)['status'],'incompatible')

    def test_same_source_different_input_is_incompatible(self):
        c={'source':'module x; endmodule','inputs':{'u':[[0,1]]}}
        (self.lane/'dut.va').write_text(c['source']);r.save(self.lane/'condition.json',c)
        old={'source_sha256':r.sha(self.lane/'dut.va')};c={**c,'inputs':{'u':[[0,2]]}}
        self.assertEqual(r.compatible(c,self.lane,old)['status'],'incompatible')

    def test_profile_binding_accepts_legacy_open_and_rejects_profile_tier_or_control_change(self):
        card={'id':'F11-base','unit_s':2e-6,'stop_s':10e-6}
        profile={'id':'deep','reltol':1e-10,'vabstol_V':1e-14,'iabstol_A':1e-17,'step_units':.0005}
        bindings={'backend_tier_profiles':{'gnucap_modelgen':{'Q3':'deep'}},'profiles':{'deep':profile}}
        old={'backend':'gnucap_modelgen','tier':'Q3','profile':'deep','condition':'F11-base','label':'F11-base--Q3'}
        requested={**profile,'target_tier':'Q3','stop_s':10e-6,'maxstep_s':1e-9,'spice_maxstep_s':1e-9}
        def write(value):
            r.save(self.lane/'requested_settings.json',value)
            r.save(self.lane/'INPUT_IDENTITY.json',{'requested_settings_sha256':r.sha(self.lane/'requested_settings.json')})
        write(requested)
        self.assertEqual(r.profile_binding(card,self.lane,old,bindings)['status'],'matched')
        for key,value in [('id','base'),('target_tier','Q1'),('reltol',1e-5),('maxstep_s',2e-9)]:
            write({**requested,key:value});result=r.profile_binding(card,self.lane,old,bindings)
            self.assertEqual(result['status'],'unmatched')
            self.assertIn(key,[issue['field'] for issue in result['issues']])
        write(requested)
        self.assertEqual(r.profile_binding(card,self.lane,{**old,'label':'F11-base--Q1'},bindings)['status'],'unmatched')
        assessment={'tiers':{'Q3':{'status':'numerical_error'}}};qualified={'status':'qualified'}
        self.assertEqual(r.slot_status('waveform_available',assessment,qualified,qualified,qualified,'Q3',{'status':'unmatched'}),'evidence_insufficient')

    def test_configuration_gate_does_not_hide_numeric_or_execution_failure(self):
        c={'tiers':{'Q1':{'status':'pass'}}};unknown={'status':'unknown'};qualified={'status':'qualified'}
        self.assertEqual(r.slot_status('waveform_available',c,unknown,qualified,qualified,'Q1'),'evidence_insufficient')
        c['tiers']['Q1']['status']='numerical_error'
        self.assertEqual(r.slot_status('waveform_available',c,unknown,unknown,unknown,'Q1'),'numerical_error')
        self.assertEqual(r.slot_status('execution_failed',c,qualified,qualified,qualified,'Q1'),'execution_failed')
        self.assertEqual(r.slot_status('not_run',c,unknown,unknown,unknown,'Q1'),'evidence_insufficient')

    def test_exact_input_candidate_rejects_adjacent_binary64_even_inside_budget(self):
        import math
        c={'input_exact_evidence_required':True,'inputs':{'u':[[0,.5],[1,.5]]}}
        qualified={'status':'qualified'}
        result=r.exact_dc_inputs(c,[{'u':.5}],'evas',qualified)
        self.assertEqual(result['status'],'candidate_chain_complete')
        self.assertFalse(result['qualification_override'])
        self.assertEqual(r.exact_dc_inputs(c,[{'u':math.nextafter(.5,math.inf)}],'evas',qualified)['status'],'unclosed')
        self.assertEqual(r.exact_dc_inputs(c,[{'u':.5}],'spectre',qualified)['status'],'unclosed')

    def test_single_lane_uses_prebound_target_slot_and_never_modifies_original(self):
        card={'id':'F01','group_id':'F01','source':'module x; endmodule','unit_s':1.0,'stop_s':1.0}
        contract={'cards':[card],'tiers':[{'id':q} for q in ('Q1','Q2','Q3')]}
        profiles={'base':{'id':'base','step_units':.1},'both':{'id':'both','step_units':.01}}
        bindings={'backend_tier_profiles':{'evas':{'Q1':'base','Q2':'both'}},'profiles':profiles}
        rows=[];runs=[]
        for q,status in [('Q1','pass'),('Q2','numerical_error')]:
            label='F01--'+q;work=self.lane/'runs'/label;work.mkdir(parents=True)
            (work/'dut.va').write_text(card['source']);r.save(work/'condition.json',card)
            (work/'waveform').write_text(status)
            old={'label':label,'backend':'evas','condition':'F01','group_id':'F01','tier':q,
                 'profile':bindings['backend_tier_profiles']['evas'][q],
                 'status':'waveform_available','source_sha256':r.sha(work/'dut.va'),
                 'waveform':'waveform','waveform_sha256':r.sha(work/'waveform')}
            profile=profiles[old['profile']]
            r.save(work/'requested_settings.json',{**profile,'target_tier':q,'stop_s':1.0,
                       'maxstep_s':profile['step_units'],'spice_maxstep_s':profile['step_units']})
            r.save(work/'INPUT_IDENTITY.json',{'requested_settings_sha256':r.sha(work/'requested_settings.json')})
            r.save(work/'RESULT.json',old);runs.append(old)
        r.save(self.lane/'EXECUTION.json',runs);r.save(self.lane/'TOOL_IDENTITY.json',{'kernel_sha256':'original-kernel'})
        self.manifest();before=r.verify_lane(self.lane)
        def assessment(card,observations,contract):
            return {'tiers':{q:{'status':observations,'numerical':{'status':observations},
                                'behavior':{'status':'pass'},'evidence':{'status':'complete'}} for q in ('Q1','Q2','Q3')}}
        def module(**kw): return types.SimpleNamespace(**kw)
        fake={'precision_breadth':module(load_contract=lambda:contract,assess=assessment),
              'precision_breadth_run':module(native_observation_evidence=lambda *a,card=None,contract=None,**k:{'status':'qualified'},
                                             runtime_control_evidence=lambda *a:{'status':'qualified'}),
              'precision_run':module(effective_settings=lambda *a:{}),
              'precision_report':module(qualification=lambda *a:{'status':'qualified'}),
              'observations':module(read_native=lambda path,backend:path.read_text())}
        out=self.root/'analysis';out.mkdir()
        r.save(out/'OFFICIAL_PROFILE_BINDINGS.json',bindings)
        r.save(out/'OFFICIAL_INPUT_IDENTITY.json',{'profile_bindings_sha256':r.sha(out/'OFFICIAL_PROFILE_BINDINGS.json')})
        with patch.dict(sys.modules,fake): r.worker(self.root/'frozen',self.lane,out)
        self.assertEqual(before,r.verify_lane(self.lane))
        groups=r.load(out/'GROUPS.json')
        self.assertEqual(groups[0]['status'],'pass')
        self.assertEqual(groups[1]['variant_statuses']['F01'],'numerical_error')
        self.assertEqual(groups[2]['variant_statuses']['F01'],'not_in_lane')
        missing=self.root/'missing-bindings';missing.mkdir()
        with patch.dict(sys.modules,fake):r.worker(self.root/'frozen',self.lane,missing)
        actual=r.load(missing/'REANALYSIS.json')
        self.assertEqual(actual[0]['assessment']['tiers']['Q1']['numerical']['status'],'pass')
        self.assertEqual(actual[1]['assessment']['tiers']['Q2']['numerical']['status'],'numerical_error')
        self.assertTrue(all(record['execution_status']=='waveform_available' for record in actual))
        self.assertTrue(all(record['configuration']['status']=='unknown' for record in actual))
        self.assertTrue(all(record['qualified_tiers'][record['executed_target_tier']]=='evidence_insufficient' for record in actual))


if __name__=='__main__':unittest.main()
