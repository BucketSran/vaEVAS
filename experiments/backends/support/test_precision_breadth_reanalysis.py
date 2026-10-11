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
        r.save(inputs/'MANIFEST.json',{name:r.sha(inputs/name) for name in ('cards.json','SOURCE_IDENTITY.json')})
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
        card={'id':'F01','group_id':'F01','source':'module x; endmodule'}
        contract={'cards':[card],'tiers':[{'id':q} for q in ('Q1','Q2','Q3')]}
        rows=[];runs=[]
        for q,status in [('Q1','pass'),('Q2','numerical_error')]:
            label='F01--'+q;work=self.lane/'runs'/label;work.mkdir(parents=True)
            (work/'dut.va').write_text(card['source']);r.save(work/'condition.json',card)
            (work/'waveform').write_text(status)
            old={'label':label,'backend':'evas','condition':'F01','group_id':'F01','tier':q,
                 'status':'waveform_available','source_sha256':r.sha(work/'dut.va'),
                 'waveform':'waveform','waveform_sha256':r.sha(work/'waveform')}
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
        with patch.dict(sys.modules,fake): r.worker(self.root/'frozen',self.lane,out)
        self.assertEqual(before,r.verify_lane(self.lane))
        groups=r.load(out/'GROUPS.json')
        self.assertEqual(groups[0]['status'],'pass')
        self.assertEqual(groups[1]['variant_statuses']['F01'],'numerical_error')
        self.assertEqual(groups[2]['variant_statuses']['F01'],'not_in_lane')


if __name__=='__main__':unittest.main()
