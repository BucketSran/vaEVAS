import copy,unittest,tempfile,pathlib,json,subprocess,sys
import curate_public_receipt as curator_module
from curate_public_receipt import verify,digest,verify_cards,verify_external_analysis
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
   for folder in [a,f,root]:
    result=subprocess.run([sys.executable,'-B',curator_module.__file__,'--aggregate',str(a),'--failure-inventory',str(f),'--cards',str(root/'cards.json'),'--output',str(folder/'output')],capture_output=True,text=True)
    self.assertNotEqual(result.returncode,0);self.assertIn('output is inside sealed input tree',result.stderr);self.assertFalse((folder/'output').exists())
 def test_full_group_identity_and_mandatory_slots_rejected(self):
  base=pathlib.Path(__file__).resolve().parent
  # Fixed actual baseline input, not a duplicate implementation of group rules.
  if not (base/'official-draft-open-foundation-part1-guarded-v1').exists():base=base.parent.parent
  r=json.loads((base/'official-draft-open-foundation-part1-guarded-v1/OFFICIAL-DRAFT.json').read_text());f=json.loads((base/'failure-inventory-open-foundation-part1-guarded-v1/FAILURES.json').read_text());c=json.loads((base/'analysis-foundation-spectre-part1-guarded-v1/OFFICIAL_CARDS.json').read_text())['cards']
  changes=[lambda x:x['groups'].pop(),lambda x:x['groups'].__setitem__(1,copy.deepcopy(x['groups'][0])),lambda x:x['groups'][0].__setitem__('mandatory_variants',99),lambda x:x['groups'][0]['variants'].__setitem__(next(iter(x['groups'][0]['variants'])),'pass'),lambda x:x['groups'][0].__setitem__('status','pass'),lambda x:x['groups'][0].__setitem__('numeric','pass'),lambda x:x['groups'][0].__setitem__('integrator','qualified')]
  for change in changes:
   bad=copy.deepcopy(r);change(bad)
   with self.subTest(change=changes.index(change)):
    with self.assertRaises(ValueError):curate(bad,f,c)

class ExternalProvenanceControls(unittest.TestCase):
 def external_fixture(self,root):
  adapter=root/'adapter.py';adapter.write_text('# fixed adapter');execution=root/'execution.json';execution.write_text('{}');sealed={'adapter.py':digest(adapter),'execution.json':digest(execution)}
  identity={'adapter':'adapter.py','proof':None,'approved_adapter_sha256':None,'approved_proof_sha256':None,'execution_input_manifest_sha256':digest(execution),'sealed_files':sealed}
  ip=root/'OPEN_EVIDENCE_IDENTITY.json';ip.write_text(json.dumps(identity));ai=root/'ANALYSIS_IDENTITY.json';ai.write_text(json.dumps({'external_open_evidence_identity_sha256':digest(ip)}))
  manifest=root/'ANALYSIS_MANIFEST.json';manifest.write_text(json.dumps({p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in root.iterdir() if p.is_file()}))
  return {'analysis':str(root),'analysis_manifest_sha256':digest(manifest),'identity_sha256':digest(ai),'external_evidence':{'identity_path':ip.name,'identity_sha256':digest(ip),'adapter_sha256':digest(adapter),'proof_sha256':None,'approved_adapter_sha256':None,'approved_proof_sha256':None,'execution_input_manifest_sha256':digest(execution),'sealed_files':sealed,'proof_metadata':None}}
 def test_external_sealed_positive_and_summary_drift_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   a=self.external_fixture(pathlib.Path(d));verify_external_analysis(a)
   for field,value in [('identity_path','../OPEN_EVIDENCE_IDENTITY.json'),('identity_sha256','0'*64),('adapter_sha256','0'*64),('approved_adapter_sha256','0'*64),('sealed_files',{}),('proof_metadata',{'claims':{'identity':'qualified'}})]:
    bad=copy.deepcopy(a);bad['external_evidence'][field]=value
    with self.subTest(field=field):
     with self.assertRaises(ValueError):verify_external_analysis(bad)
 def test_proof_metadata_bound_to_original_sealed_proof(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);a=self.external_fixture(root);proof=root/'proof.json';proof.write_text(json.dumps({'schema':1,'claims':{'identity':'unknown'},'attachments':{'adapter.py':digest(root/'adapter.py')},'extra':'not projected'}));ip=root/'OPEN_EVIDENCE_IDENTITY.json';identity=json.loads(ip.read_text());identity['proof']=proof.name;identity['evidence_root']='.';identity['sealed_files'][proof.name]=digest(proof);ip.write_text(json.dumps(identity));ai=root/'ANALYSIS_IDENTITY.json';ai.write_text(json.dumps({'external_open_evidence_identity_sha256':digest(ip)}));manifest=root/'ANALYSIS_MANIFEST.json';manifest.write_text(json.dumps({p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in root.iterdir() if p.is_file() and p!=manifest}));a.update(analysis_manifest_sha256=digest(manifest),identity_sha256=digest(ai));a['external_evidence'].update(identity_sha256=digest(ip),proof_sha256=digest(proof),sealed_files=identity['sealed_files'],proof_metadata={'schema':1,'claims':{'identity':'unknown'},'attachments':{'adapter.py':digest(root/'adapter.py')}});verify_external_analysis(a)
   a['external_evidence']['proof_metadata']['claims']['identity']='qualified'
   with self.assertRaisesRegex(ValueError,'metadata'):verify_external_analysis(a)
   forged=json.loads(proof.read_text());forged['attachments']={'missing.json':'0'*64};proof.write_text(json.dumps(forged));identity['sealed_files'][proof.name]=digest(proof);ip.write_text(json.dumps(identity));ai.write_text(json.dumps({'external_open_evidence_identity_sha256':digest(ip)}));manifest.write_text(json.dumps({p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in root.iterdir() if p.is_file() and p!=manifest}));a.update(analysis_manifest_sha256=digest(manifest),identity_sha256=digest(ai));a['external_evidence'].update(identity_sha256=digest(ip),proof_sha256=digest(proof),sealed_files=identity['sealed_files'],proof_metadata={k:forged[k] for k in ['schema','claims','attachments']})
   with self.assertRaisesRegex(ValueError,'attachment'):verify_external_analysis(a)
 def test_external_inventory_hash_and_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);a=self.external_fixture(root);q=root/'unlisted';q.write_text('x')
   with self.assertRaisesRegex(ValueError,'inventory'):verify_external_analysis(a)
   q.unlink();adapter=root/'adapter.py';original=adapter.read_text();adapter.write_text('drift')
   with self.assertRaisesRegex(ValueError,'drift'):verify_external_analysis(a)
   adapter.unlink();other=root/'other';other.write_text(original);adapter.symlink_to(other)
   with self.assertRaisesRegex(ValueError,'unsafe'):verify_external_analysis(a)
 def test_cards_bound_to_sealed_identity_and_probe_override_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);cards=root/'OFFICIAL_CARDS.json';cards.write_text(json.dumps({'cards':[{'id':'F','source':'frozen','support_probe_only':True}]}));manifest=root/'ANALYSIS_MANIFEST.json';manifest.write_text(json.dumps({cards.name:{'sha256':digest(cards),'bytes':cards.stat().st_size}}));sha=digest(cards);r={'official_cards_sha256':sha,'analyses':[{'analysis':str(root),'analysis_manifest_sha256':digest(manifest)}]};self.assertEqual(verify_cards(cards,r),sha)
   cards.write_text(json.dumps({'cards':[{'source':'replacement','support_probe_only':False}]}))
   with self.assertRaisesRegex(ValueError,'approved frozen'):verify_cards(cards,r)
 def test_cards_model_source_must_match_sealed_slots(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'cards.json';p.write_text(json.dumps({'cards':[{'id':'F','source':'frozen'}]}));r={'official_cards_sha256':digest(p),'analyses':[],'slots':[{'variant':'F','source_sha256':'0'*64}]}
   with self.assertRaisesRegex(ValueError,'model source'):verify_cards(p,r)
 def test_old_cards_require_approved_digest(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'cards.json';p.write_text('{"cards":[]}');r={'analyses':[]}
   with self.assertRaises(ValueError):verify_cards(p,r)
   self.assertEqual(verify_cards(p,r,digest(p)),digest(p))
 def test_independent_axis_and_receipts_deduplicate_without_upgrade(self):
  r,f,c=fixture();s=r['slots'][0];s.update(backend='openvaf_r_ngspice',integrator='unknown',integrator_evidence={'status':'unknown','issues':['not proved']},legacy_configuration={'status':'qualified'},settings_provenance={'origin':'legacy'},external_qualification={'identity':{'status':'unknown'},'integrator':{'status':'unknown'}});f['nonpass_slots'][0]['backend']=s['backend']
  clone=copy.deepcopy(s);clone['Q']='Q2';r['slots'].append(clone);ff=copy.deepcopy(f['nonpass_slots'][0]);ff['Q']='Q2';f['nonpass_slots'].append(ff);f['selected_slots']=2
  p=curate(r,f,c,expected_slots=2);self.assertEqual(p['counts']['openvaf_r_ngspice']['integrator'],{'unknown':2});self.assertEqual(p['counts']['openvaf_r_ngspice']['final'],{'evidence_insufficient':2});self.assertEqual(len(p['tables']['external_qualifications']),1);self.assertEqual(len(p['tables']['legacy_configurations']),1);self.assertEqual(p['tables']['settings_provenance'][p['slots'][0]['settings_provenance_ref']],{'origin':'legacy'})
 def test_integrator_status_cannot_claim_wrong_backend_axis(self):
  r,f,c=fixture();r['slots'][0]['integrator']='qualified'
  with self.assertRaisesRegex(ValueError,'integrator'):curate(r,f,c,expected_slots=1)
  r['slots'][0].update(backend='openvaf_r_ngspice',integrator='not_applicable');f['nonpass_slots'][0]['backend']='openvaf_r_ngspice'
  with self.assertRaisesRegex(ValueError,'integrator'):curate(r,f,c,expected_slots=1)
 def test_absent_open_proof_stays_unknown_nonopen_not_applicable(self):
  r,f,c=fixture();p=curate(r,f,c,expected_slots=1);self.assertEqual(p['slots'][0]['integrator'],'not_applicable');r['slots'][0]['backend']='openvaf_r_ngspice';f['nonpass_slots'][0]['backend']='openvaf_r_ngspice';p=curate(r,f,c,expected_slots=1);self.assertEqual(p['slots'][0]['integrator'],'unknown');self.assertEqual(p['tables']['external_qualifications'][p['slots'][0]['external_qualification_ref']],None)

if __name__=='__main__':unittest.main()
