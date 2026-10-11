import copy,unittest,tempfile,pathlib,json,subprocess,sys
import curate_public_receipt as curator_module
from curate_public_receipt import verify,digest
from curate_public_receipt import curate,LAYERS

def fixture():
 c={'id':'F01-v1','group_id':'F01','title':'test','top':'probe','unit_s':1e-6,'stop_s':2e-6,'source':'module probe; endmodule'}
 s={'backend':'evas','variant':c['id'],'Q':'Q1','selected_batch':'batch-v2','final':'evidence_insufficient','numeric':'unknown','behavior':'pass','evidence':'evidence_insufficient','config':'qualified','native':'qualified','runtime':'qualified','original_execution':'waveform_available','output_witnesses':{'y':{'error_lower_V':0,'error_upper_V':1,'worst':{'actual_V':1,'reference_V':[0,1],'time_s':0}}}}
 r={'slots':[s], 'analyses':[], 'aggregate_source_sha256':'a','tool_source_hashes':{},'selection_sha256':'b','official_input_manifest_sha256':'c','groups':[]}
 f={'nonpass_slots':[{'backend':'evas','variant':c['id'],'Q':'Q1','unknown_by_origin':{'input_topology':['missing']}}], 'selected_slots':1,'full_pass':0}
 return r,f,[c]
class Controls(unittest.TestCase):
 def test_unknown_and_conditional_witness_stay_unknown(self):
  r,f,c=fixture();p=curate(r,f,c,expected_slots=1)
  self.assertEqual(p['slots'][0]['numeric'],'unknown');self.assertEqual(p['counts']['evas']['final'],{'evidence_insufficient':1});self.assertEqual(p['slots'][0]['key_failure_witness']['output'],'y')
 def test_duplicate_identity_rejected(self):
  r,f,c=fixture();r['slots']*=2
  with self.assertRaises(ValueError):curate(r,f,c,expected_slots=2)
 def test_missing_failure_denominator_rejected(self):
  r,f,c=fixture();f['nonpass_slots']=[]
  with self.assertRaises(ValueError):curate(r,f,c,expected_slots=1)
 def test_probe_cannot_pass(self):
  r,f,c=fixture();c[0]['support_probe_only']=True;r['slots'][0]['final']='pass';f.update(nonpass_slots=[],full_pass=1)
  with self.assertRaises(ValueError):curate(r,f,c,expected_slots=1)
 def test_settings_deduplicate_without_removing_slots(self):
  r,f,c=fixture();s=copy.deepcopy(r['slots'][0]);s['Q']='Q2';r['slots'].append(s);ff=copy.deepcopy(f['nonpass_slots'][0]);ff['Q']='Q2';f['nonpass_slots'].append(ff);f['selected_slots']=2
  p=curate(r,f,c,expected_slots=2);self.assertEqual(len(p['slots']),2);self.assertEqual(len(p['tables']['settings']),1);self.assertEqual(len(p['tables']['models']),1)
 def test_original_execution_failure_remains_separate(self):
  r,f,c=fixture();r['slots'][0].update(final='execution_failed',original_execution='runtime_timeout');f['nonpass_slots'][0]['execution_failure']={'status':'runtime_timeout'}
  p=curate(r,f,c,expected_slots=1);self.assertEqual(p['slots'][0]['original_execution'],'runtime_timeout');self.assertEqual(p['slots'][0]['numeric'],'unknown')
 def test_not_collected_is_not_execution(self):
  r,f,c=fixture();r['slots'][0]['original_execution']='not_collected'
  self.assertEqual(curate(r,f,c,expected_slots=1)['collected_slots'],0)
 def test_boundary_attribution_and_native_gap_retained(self):
  r,f,c=fixture();f['nonpass_slots'][0]['behavior_attribution']={'kind':'card_stop_boundary_requirement'};f['nonpass_slots'][0]['unknown_by_origin']['native_observation']={'status':'unknown','facts':{'origin_gap':'two requested times collapse'}}
  p=curate(r,f,c,expected_slots=1);reasons=list(p['tables']['reasons'].values())
  self.assertTrue(any(x.get('layer')=='behavior_attribution' for x in reasons));self.assertTrue(any(isinstance(x.get('facts'),dict) and x['facts'].get('origin_gap')=='two requested times collapse' for x in reasons))
 def test_unknown_analysis_reference_rejected(self):
  r,f,c=fixture();r['slots'][0]['analysis']='not-sealed'
  with self.assertRaises(ValueError):curate(r,f,c,expected_slots=1)
class ManifestControls(unittest.TestCase):
 def test_required_payload_must_be_manifest_member(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'MANIFEST.json').write_text('{}');(p/'OFFICIAL-DRAFT.json').write_text('{}')
   with self.assertRaisesRegex(ValueError,'absent'):verify(p,required=('OFFICIAL-DRAFT.json',))
 def test_required_payload_hash_and_path_verified(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);q=p/'FAILURES.json';q.write_text('{}');m=p/'MANIFEST.json';m.write_text(json.dumps({q.name:digest(q)}));verify(p,required=(q.name,));q.write_text('{"drift":1}')
   with self.assertRaisesRegex(ValueError,'drift'):verify(p,required=(q.name,))
 def test_required_payload_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);q=p/'elsewhere.json';q.write_text('{}');t=p/'FAILURES.json';t.symlink_to(q);(p/'MANIFEST.json').write_text(json.dumps({t.name:digest(q)}))
   with self.assertRaisesRegex(ValueError,'unsafe'):verify(p,required=(t.name,))
 def test_escape_and_manifest_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'MANIFEST.json').write_text(json.dumps({'../elsewhere.json':'x'}))
   with self.assertRaisesRegex(ValueError,'unsafe'):verify(p)
   (p/'MANIFEST.json').unlink();q=p/'other.json';q.write_text('{}');(p/'MANIFEST.json').symlink_to(q)
   with self.assertRaisesRegex(ValueError,'unsafe'):verify(p)
 def test_availability_does_not_imply_public_raw(self):
  r,f,c=fixture();p=curate(r,f,c,expected_slots=1)
  self.assertEqual(p['availability']['original_raw']['status'],'local-only');self.assertEqual(p['availability']['model_and_checker_source']['status'],'repository-contained');self.assertEqual(p['availability']['reexecution']['status'],'requires-backend-environment');self.assertNotIn('url',p['availability']['original_raw'])

class ReviewDeltaControls(unittest.TestCase):
 def test_unknown_scope_limit_retained(self):
  r,f,c=fixture();f['nonpass_slots'][0]['unknown_by_origin']={'native':{'status':'unknown','scope':'finite rows','limit':'not initial phase'}}
  p=curate(r,f,c,expected_slots=1);reason=next(x for x in p['tables']['reasons'].values() if x.get('origin')=='native')
  self.assertEqual(reason['facts']['scope'],'finite rows');self.assertEqual(reason['facts']['limit'],'not initial phase')
 def test_same_text_keeps_both_reason_layers(self):
  r,f,c=fixture();r['slots'][0].update(behavior_errors=['same reason'],evidence_issues=['same reason'])
  p=curate(r,f,c,expected_slots=1);self.assertEqual({x['layer'] for x in p['tables']['reasons'].values() if x.get('text')=='same reason'},{'behavior','evidence'})
 def test_manifest_claimed_size_and_missing_digest_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);q=p/'FAILURES.json';q.write_text('{}');m=p/'MANIFEST.json';m.write_text(json.dumps({q.name:{'sha256':digest(q),'bytes':3}}))
   with self.assertRaisesRegex(ValueError,'size'):verify(p,required=(q.name,))
   m.write_text(json.dumps({q.name:{'bytes':2}}))
   with self.assertRaisesRegex(ValueError,'digest'):verify(p,required=(q.name,))
 def test_output_cannot_be_inside_either_input_tree(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);a=root/'aggregate';f=root/'failures';a.mkdir();f.mkdir()
   for folder in [a,f]:
    result=subprocess.run([sys.executable,'-B',curator_module.__file__,'--aggregate',str(a),'--failure-inventory',str(f),'--cards',str(root/'cards.json'),'--output',str(folder/'output')],capture_output=True,text=True)
    self.assertNotEqual(result.returncode,0);self.assertIn('output is inside sealed input tree',result.stderr);self.assertFalse((folder/'output').exists())
 def test_full_group_identity_and_mandatory_slots_rejected(self):
  base=pathlib.Path(__file__).resolve().parent
  # Fixed actual baseline input, not a duplicate implementation of group rules.
  if not (base/'official-draft-open-foundation-part1-guarded-v1').exists():base=base.parent.parent
  r=json.loads((base/'official-draft-open-foundation-part1-guarded-v1/OFFICIAL-DRAFT.json').read_text());f=json.loads((base/'failure-inventory-open-foundation-part1-guarded-v1/FAILURES.json').read_text());c=json.loads((base/'analysis-foundation-spectre-part1-guarded-v1/OFFICIAL_CARDS.json').read_text())['cards']
  changes=[lambda x:x['groups'].pop(),lambda x:x['groups'].__setitem__(1,copy.deepcopy(x['groups'][0])),lambda x:x['groups'][0].__setitem__('mandatory_variants',99),lambda x:x['groups'][0]['variants'].__setitem__(next(iter(x['groups'][0]['variants'])),'pass'),lambda x:x['groups'][0].__setitem__('status','pass'),lambda x:x['groups'][0].__setitem__('numeric','pass')]
  for change in changes:
   bad=copy.deepcopy(r);change(bad)
   with self.subTest(change=changes.index(change)):
    with self.assertRaises(ValueError):curate(bad,f,c)

if __name__=='__main__':unittest.main()
