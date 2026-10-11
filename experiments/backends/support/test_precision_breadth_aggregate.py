import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('aggregate',Path(__file__).with_name('precision_breadth_aggregate.py'))
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)


def selection():return {'official_selection':a.POLICY,'old_batch':'batch','new_batch':'batch-v2'}
def card(name,group,family='foundation'):return {'id':name,'group_id':group,'family':family,'source':'module x; endmodule'}
def record(c,backend='evas',q='Q1',status='pass',compatibility='compatible'):
    return {'condition':c['id'],'group_id':c['group_id'],'backend':backend,'executed_target_tier':q,'label':c['id']+'--'+q,
            'execution_status':'waveform_available','inheritance':'same raw execution, new analysis',
            'identity':{'original_result_sha256':'original-result','kernel_or_binary_sha256':'original-kernel'},
            'source_compatibility':{'status':compatibility,'current_source_sha256':a.hashlib.sha256(c['source'].encode()).hexdigest()},
            'assessment':{'tiers':{tier:{'status':status,'numerical':{'status':status},'behavior':{'status':'pass'},
                                        'evidence':{'status':'complete'}} for tier in ('Q1','Q2','Q3')}},
            'configuration':{'status':'qualified'},'native_observations':{'status':'qualified'},
            'runtime_controls':{'status':'qualified'},'qualified_tiers':{tier:status for tier in ('Q1','Q2','Q3')}}


class AggregateCalibration(unittest.TestCase):
    def contract(self,cards):return {'cards':cards,'tiers':[{'id':q} for q in ('Q1','Q2','Q3')]}

    def test_added_execution_profile_does_not_change_old_or_scientific_contract(self):
        old={'cards':[card('one','F01')],'budgets':{'B':1},'profiles':[{'id':'deep','step':1}]}
        new={**old,'profiles':old['profiles']+[{'id':'deep_bound','step':2}]}
        self.assertEqual(a.compatible_contract(old,new)['added_official_profiles'],['deep_bound'])
        changed={**new,'profiles':[{'id':'deep','step':2}]}
        with self.assertRaises(ValueError):a.compatible_contract(old,changed)
        with self.assertRaises(ValueError):a.compatible_contract(old,{**new,'budgets':{'B':2}})

    def test_missing_mandatory_variants_never_disappear_or_pass_group(self):
        cards=[card('one','F01'),card('two','F01')]
        r=a.assemble(self.contract(cards),selection(),[('batch-v2','analysis',[record(cards[0])])])
        self.assertEqual(len(r['slots']),24)
        group=next(g for g in r['groups'] if g['backend']=='evas' and g['Q']=='Q1')
        self.assertEqual(group['mandatory_variants'],2);self.assertEqual(group['status'],'evidence_insufficient')
        self.assertEqual(group['variants']['two'],'evidence_insufficient')
        self.assertEqual(group['numeric'],'unknown')

    def test_no_best_of_old_success_vs_selected_new_failure(self):
        c=card('one','F01')
        r=a.assemble(self.contract([c]),selection(),[('batch','old',[record(c)]),
                 ('batch-v2','new',[record(c,status='numerical_error')])])
        picked=next(x for x in r['slots'] if x['backend']=='evas' and x['Q']=='Q1')
        self.assertEqual(picked['analysis'],'new');self.assertEqual(picked['final'],'numerical_error')
        self.assertEqual(len(r['excluded_original_attempts']),1)

    def test_numeric_pass_and_probe_do_not_certify_full_pass(self):
        c=card('one','F01');r=record(c,status='evidence_insufficient')
        r['assessment']['tiers']['Q1']['numerical']['status']='pass'
        picked=next(x for x in a.assemble(self.contract([c]),selection(),[('batch-v2','analysis',[r])])['slots']
                    if x['backend']=='evas' and x['Q']=='Q1')
        self.assertEqual(picked['numeric'],'pass');self.assertEqual(picked['final'],'evidence_insufficient')
        c['probe_only']=True
        with self.assertRaises(ValueError):a.assemble(self.contract([c]),selection(),[('batch-v2','analysis',[record(c)])])
        c['probe_only']=False;c['support_probe_only']=True
        with self.assertRaises(ValueError):a.assemble(self.contract([c]),selection(),[('batch-v2','analysis',[record(c)])])

    def test_explicit_group_selection_is_independent_of_batch_names(self):
        sel={'slot_selection':{backend:{'default_batch':'fresh','group_batches':{'F11':'archived'}} for backend in a.BACKENDS}}
        self.assertEqual(a.source_batch('evas',card('one','F01'),sel),'fresh')
        self.assertEqual(a.source_batch('evas',card('one','F11'),sel),'archived')

    def test_wrong_designated_profile_preserves_numeric_failure_and_original_execution(self):
        c=card('one','F01');r=record(c,status='numerical_error')
        r['profile_binding']={'status':'unmatched','issues':[{'field':'id','expected':'deep','actual':'base'}]}
        cell=next(x for x in a.assemble(self.contract([c]),selection(),[('batch-v2','analysis',[r])])['slots'] if x['backend']=='evas' and x['Q']=='Q1')
        self.assertEqual(cell['numeric'],'numerical_error');self.assertEqual(cell['config'],'unknown')
        self.assertEqual(cell['original_execution'],'waveform_available');self.assertEqual(cell['final'],'evidence_insufficient')

    def test_group_execution_failure_precedence_retains_independent_numeric_failure(self):
        cards=[card('one','F01'),card('two','F01')];r1=record(cards[0],status='numerical_error');r2=record(cards[1],status='execution_failed')
        r2['assessment']['tiers']['Q1']['numerical']['status']='unknown';r2['execution_status']='compile_failed'
        group=next(x for x in a.assemble(self.contract(cards),selection(),[('batch-v2','analysis',[r1,r2])])['groups'] if x['backend']=='evas' and x['Q']=='Q1')
        self.assertEqual(group['status'],'execution_failed');self.assertEqual(group['numeric'],'numerical_error')

    def test_duplicate_selected_attempt_is_rejected_even_if_one_is_better(self):
        c=card('one','F01')
        with self.assertRaises(ValueError):a.assemble(self.contract([c]),selection(),
           [('batch-v2','first',[record(c)]),('batch-v2','second',[record(c,status='numerical_error')])])

    def test_open_foundation_part2_reuses_only_preselected_old_batch(self):
        c=card('one','F11')
        r=a.assemble(self.contract([c]),selection(),[('batch','old',[record(c,backend='gnucap_modelgen',status='numerical_error')]),
                 ('batch-v2','new',[record(c,backend='gnucap_modelgen')])])
        cell=next(x for x in r['slots'] if x['backend']=='gnucap_modelgen' and x['Q']=='Q1')
        self.assertEqual(cell['final'],'numerical_error');self.assertEqual(cell['analysis'],'old')

    def test_incompatible_source_is_unknown_even_if_old_numeric_or_execution_failed(self):
        c=card('one','F01');old=record(c,status='numerical_error',compatibility='incompatible')
        old['execution_status']='execution_failed'
        r=a.assemble(self.contract([c]),selection(),[('batch-v2','analysis',[old])])
        cell=next(x for x in r['slots'] if x['backend']=='evas' and x['Q']=='Q1')
        self.assertEqual(cell['original_execution'],'execution_failed')
        self.assertEqual(cell['numeric'],'unknown');self.assertEqual(cell['final'],'evidence_insufficient')

    def test_full_official_denominator_remains_852_without_any_results(self):
        import sys
        root=Path(__file__).resolve().parents[3]
        sys.path.insert(0,str(root/'evas/validation/paper'))
        from precision_breadth import load_contract
        contract=load_contract();sel=selection()
        r=a.assemble(contract,sel,[])
        self.assertEqual(len(r['slots']),852);self.assertEqual(len(r['groups']),528)
        self.assertTrue(all(c['final']=='evidence_insufficient' for c in r['slots']))

    def test_analysis_artifact_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);a.save(path/'COMPLETION.json',{'returncode':0,'original_manifest_unchanged':True})
            (path/'raw').write_text('sealed')
            a.save(path/'ANALYSIS_MANIFEST.json',{p.name:{'sha256':a.sha(p),'bytes':p.stat().st_size} for p in path.iterdir()})
            a.verify_analysis(path);(path/'raw').write_text('tamper')
            with self.assertRaises(ValueError):a.verify_analysis(path)

    def test_raw_label_cannot_escape_runs_or_follow_a_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            lane=Path(temp)/'lane';runs=lane/'runs';runs.mkdir(parents=True)
            safe=runs/'F01--Q1';safe.mkdir()
            self.assertEqual(a.raw_work(lane,'F01--Q1'),safe.resolve())
            with self.assertRaises(ValueError):a.raw_work(lane,'../../outside')
            (runs/'alias').symlink_to(safe,target_is_directory=True)
            with self.assertRaises(ValueError):a.raw_work(lane,'alias')

    def test_unmanifested_official_profile_bindings_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            inputs=Path(temp)
            a.save(inputs/'PROFILE_BINDINGS.json',{'profiles':{}})
            with self.assertRaises(ValueError):a.verified_bindings(inputs,{})
            bindings=a.verified_bindings(inputs,{'PROFILE_BINDINGS.json':a.sha(inputs/'PROFILE_BINDINGS.json')})
            self.assertEqual(bindings,{'profiles':{}})


if __name__=='__main__':unittest.main()
