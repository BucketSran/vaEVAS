"""Curate a compact receipt from immutable local aggregate/failure evidence.

No qualification recomputation: retain every selected slot and each separate layer.
"""
import argparse,collections,hashlib,json,pathlib
PROOF_METADATA_FIELDS=('schema','backend','image_id','binary_hashes','environment_sha256','argv_sha256','claims','run_scopes','attachments','reviews')
LAYERS=('final','numeric','behavior','evidence','config','native','runtime','original_execution','integrator')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verify(base, *, required=()):
 base=base.resolve();manifest=base/'MANIFEST.json'
 if manifest.is_symlink():raise ValueError('unsafe receipt manifest')
 entries=json.loads(manifest.read_text())
 if not isinstance(entries,dict) or not set(required).issubset(entries):raise ValueError('required receipt payload absent from manifest')
 for rel,e in entries.items():
  p=base/rel
  if p.is_symlink() or not p.resolve().is_relative_to(base):raise ValueError('unsafe receipt artifact')
  if isinstance(e,dict) and 'sha256' not in e:raise ValueError('receipt digest absent: '+rel)
  if digest(p)!=(e['sha256'] if isinstance(e,dict) else e):raise ValueError('receipt drift: '+rel)
  if isinstance(e,dict) and 'bytes' in e and (type(e['bytes']) is not int or p.stat().st_size!=e['bytes']):raise ValueError('receipt size drift: '+rel)
 return digest(manifest)
def integrator_status(row):
 is_open=row['backend'] in ('openvaf_r_ngspice','gnucap_modelgen');status=row.get('integrator','unknown' if is_open else 'not_applicable')
 if status not in (('qualified','unknown') if is_open else ('not_applicable',)):raise ValueError('invalid integrator status for backend')
 return status
def verify_external_analysis(a):
 external=a.get('external_evidence')
 if external is None:return
 root=pathlib.Path(a['analysis'])
 if root.is_symlink():raise ValueError('unsafe external analysis root')
 root=root.resolve();manifest=root/'ANALYSIS_MANIFEST.json'
 if manifest.is_symlink() or digest(manifest)!=a['analysis_manifest_sha256']:raise ValueError('external analysis manifest drift')
 entries=json.loads(manifest.read_text());files={}
 for path in root.rglob('*'):
  if path.is_symlink():raise ValueError('unsafe external analysis artifact')
  if path.is_file() and path!=manifest:files[str(path.relative_to(root))]=path
 if set(files)!=set(entries):raise ValueError('external analysis inventory drift')
 for rel,e in entries.items():
  path=root/rel
  if not path.resolve().is_relative_to(root) or not isinstance(e,dict) or 'sha256' not in e or 'bytes' not in e:raise ValueError('unsafe external analysis entry')
  if digest(path)!=e['sha256'] or type(e['bytes']) is not int or path.stat().st_size!=e['bytes']:raise ValueError('external analysis artifact drift')
 identity_path=external['identity_path']
 if identity_path!='OPEN_EVIDENCE_IDENTITY.json' or identity_path not in entries:raise ValueError('external identity membership mismatch')
 if digest(root/identity_path)!=external['identity_sha256']:raise ValueError('external identity digest mismatch')
 identity=json.loads((root/'ANALYSIS_IDENTITY.json').read_text())
 if digest(root/'ANALYSIS_IDENTITY.json')!=a['identity_sha256'] or identity.get('external_open_evidence_identity_sha256')!=external['identity_sha256']:raise ValueError('external analysis identity mismatch')
 sealed=json.loads((root/identity_path).read_text())
 if sealed['sealed_files']!=external['sealed_files']:raise ValueError('external sealed file selection mismatch')
 for rel,sha in sealed['sealed_files'].items():
  path=root/rel
  if rel not in entries or path.is_symlink() or not path.resolve().is_relative_to(root) or entries[rel]['sha256']!=sha or digest(path)!=sha:raise ValueError('external sealed file digest mismatch')
 for field in ['approved_adapter_sha256','approved_proof_sha256','execution_input_manifest_sha256']:
  if external.get(field)!=sealed.get(field):raise ValueError('external approval or execution identity mismatch')
 for field in ['adapter','proof']:
  rel=sealed.get(field);expected=external.get(field+'_sha256')
  if (rel is None and expected is not None) or (rel is not None and (rel not in sealed['sealed_files'] or sealed['sealed_files'][rel]!=expected)):raise ValueError('external source digest mismatch')
 proof=sealed.get('proof')
 original=None if proof is None else json.loads((root/proof).read_text())
 metadata=None if original is None else {k:v for k,v in original.items() if k in PROOF_METADATA_FIELDS}
 if original is not None:
  for attachment,sha in original.get('attachments',{}).items():
   rel=str(pathlib.Path(sealed['evidence_root'])/attachment)
   if sealed['sealed_files'].get(rel)!=sha:raise ValueError('external proof attachment missing from sealed files')
 if external.get('proof_metadata')!=metadata:raise ValueError('external proof metadata mismatch')
def verify_cards(path,r,expected=None):
 actual=digest(path);bound=r.get('official_cards_sha256')
 if bound is None:bound=expected
 if bound is None or actual!=bound or (expected is not None and expected!=bound):raise ValueError('cards do not match approved frozen identity')
 # Baseline compatibility: the explicitly approved digest must also match a sealed analysis copy.
 for a in r['analyses']:
  root=pathlib.Path(a['analysis']);manifest=root/'ANALYSIS_MANIFEST.json'
  if root.is_symlink() or manifest.is_symlink():raise ValueError('unsafe cards analysis identity')
  entries=json.loads(manifest.read_text())
  if digest(manifest)!=a['analysis_manifest_sha256']:raise ValueError('cards analysis manifest drift')
  if 'OFFICIAL_CARDS.json' in entries:
   entry=entries['OFFICIAL_CARDS.json'];saved=root/'OFFICIAL_CARDS.json'
   if not isinstance(entry,dict) or 'sha256' not in entry:raise ValueError('cards manifest digest absent')
   if 'bytes' in entry and (type(entry['bytes']) is not int or saved.stat().st_size!=entry['bytes']):raise ValueError('cards manifest size drift')
   if saved.is_symlink() or not saved.resolve().is_relative_to(root.resolve()) or entry['sha256']!=actual or digest(saved)!=actual:raise ValueError('cards sealed analysis identity mismatch')
 cards=json.loads(path.read_text()).get('cards',[])
 sources={c['id']:hashlib.sha256(c['source'].encode()).hexdigest() for c in cards}
 for slot in r.get('slots',[]):
  if slot.get('source_sha256') is not None and sources.get(slot['variant'])!=slot['source_sha256']:raise ValueError('cards model source differs from sealed slot')
 return actual
def validate_groups(slots,cards,groups):
 backs=('evas','spectre','openvaf_r_ngspice','gnucap_modelgen');qs=('Q1','Q2','Q3')
 cardmap={c['id']:c for c in cards};groupmap={}
 for c in cards:groupmap.setdefault(c['group_id'],set()).add(c['id'])
 if len(cards)!=71 or len(cardmap)!=71 or len(groupmap)!=44:raise ValueError('official card identity mismatch')
 expected={(b,v,q) for b in backs for v in cardmap for q in qs}
 slotmap={(s['backend'],s['variant'],s['Q']):s for s in slots}
 if set(slotmap)!=expected:raise ValueError('official slot identity mismatch')
 gkeys=[(g['backend'],g['group'],g['Q']) for g in groups]
 if len(gkeys)!=528 or len(set(gkeys))!=528 or set(gkeys)!={(b,g,q) for b in backs for g in groupmap for q in qs}:raise ValueError('group denominator or identity mismatch')
 for g in groups:
  variants=groupmap[g['group']];cells=[slotmap[g['backend'],v,g['Q']] for v in variants]
  if type(g['mandatory_variants']) is not int or g['mandatory_variants']!=len(variants) or g['variants']!={v:slotmap[g['backend'],v,g['Q']]['final'] for v in variants}:raise ValueError('group mandatory slot mismatch')
  states=[c['final'] for c in cells]
  status='pass' if all(x=='pass' for x in states) else next((x for x in ('execution_failed','behavior_error','numerical_error') if x in states),'evidence_insufficient')
  if g['status']!=status:raise ValueError('group final status mismatch')
  expected_integrator='qualified' if all(integrator_status(c)=='qualified' for c in cells) else 'not_applicable' if all(integrator_status(c)=='not_applicable' for c in cells) else 'unknown'
  if integrator_status(g)!=expected_integrator:raise ValueError('group integrator status mismatch')
  for field,passed,failure in [('numeric','pass','numerical_error'),('behavior','pass','behavior_error'),('evidence','complete',None),('config','qualified',None),('native','qualified',None),('runtime','qualified',None)]:
   states=[c.get(field,'unknown') for c in cells]
   value=failure if failure and failure in states else passed if all(x==passed for x in states) else 'evidence_insufficient' if field=='evidence' else 'unknown'
   if g[field]!=value:raise ValueError('group layer status mismatch: '+field)
def curate(r, failures, cards, *, expected_slots=852):
 slots=r['slots'];keys=[(s['backend'],s['variant'],s['Q']) for s in slots]
 if len(slots)!=expected_slots or len(set(keys))!=len(keys):raise ValueError('slot denominator or identity mismatch')
 cardmap={c['id']:c for c in cards};fmap={(x['backend'],x['variant'],x['Q']):x for x in failures['nonpass_slots']}
 if len(fmap)!=len(failures['nonpass_slots']):raise ValueError('duplicate failure slot')
 if set(fmap)!={k for k,s in zip(keys,slots) if s['final']!='pass'}:raise ValueError('failure inventory selection mismatch')
 if failures['selected_slots']!=len(slots) or failures['full_pass']!=sum(s['final']=='pass' for s in slots):raise ValueError('failure count mismatch')
 if expected_slots==852:validate_groups(slots,cards,r['groups'])
 tables={'analyses':{},'models':{},'settings':{},'reasons':{},'external_proofs':{},'external_qualifications':{},'legacy_configurations':{},'settings_provenance':{}};intern={k:{} for k in tables}
 def put(table,value):
  canonical=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
  if canonical in intern[table]:return intern[table][canonical]
  key=table[0]+str(len(tables[table]));tables[table][key]=value;intern[table][canonical]=key;return key
 analysis_refs={}
 for a in r['analyses']:
  path=a['analysis'];entry={k:a[k] for k in ['batch','checker_revision','analysis_manifest_sha256','identity_sha256','tool_identity_sha256','contract_relation','raw_manifest'] if k in a}
  entry['retention_id']=pathlib.Path(path).name
  if a.get('external_evidence') is not None:entry['external_evidence_ref']=put('external_proofs',a['external_evidence'])
  analysis_refs[path]=put('analyses',entry)
 modelrefs={}
 for v in dict.fromkeys(s['variant'] for s in slots):
  c=cardmap[v];modelrefs[v]=put('models',{'variant':v,'group':c['group_id'],'title':c['title'],'top':c['top'],'unit_s':c['unit_s'],'stop_s':c['stop_s'],'declared_source_sha256':hashlib.sha256(c['source'].encode()).hexdigest(),'probe_only':bool(c.get('probe_only') or c.get('support_probe_only'))})
 out=[]
 for s,k in zip(slots,keys):
  x={'backend':s['backend'],'variant':s['variant'],'Q':s['Q'],'model_ref':modelrefs[s['variant']],'selected_batch':s['selected_batch'],**{f:s.get(f,'unknown') for f in LAYERS}}
  x['integrator']=integrator_status(s)
  x['integrator_evidence']=s.get('integrator_evidence')
  x['legacy_configuration_ref']=put('legacy_configurations',s.get('legacy_configuration'))
  x['settings_provenance_ref']=put('settings_provenance',s.get('settings_provenance'))
  x['external_qualification_ref']=put('external_qualifications',s.get('external_qualification'))
  if x['final']=='pass' and tables['models'][x['model_ref']]['probe_only']:raise ValueError('probe cannot pass')
  if s.get('analysis'):
   if s['analysis'] not in analysis_refs:raise ValueError('unknown analysis identity')
   x['analysis_ref']=analysis_refs[s['analysis']]
  x['settings_ref']=put('settings',{'requested':s.get('requested_settings',{}),'actual':s.get('actual_settings',{}),'status':s.get('config','unknown'),'binding_status':s.get('profile_binding',{}).get('status','unknown')})
  for field in ['error_lower_V','error_upper_V','voltage_budget_V','original_result_sha256','kernel_or_binary_sha256','tool_identity_sha256','source_compatibility','source_sha256']:
   x[field]=s.get(field)
  x['input_identity_sha256']=s.get('raw_artifact_hashes',{}).get('INPUT_IDENTITY.json')
  f=fmap.get(k,{});reasons=[]
  for layer,field in [('behavior','behavior_errors'),('evidence','evidence_issues')]:
   for issue in s.get(field,[]):reasons.append({'layer':layer,'text':issue})
  ef=f.get('execution_failure')
  if ef:reasons.append({'layer':'execution','status':ef.get('status'),'reason':ef.get('reason'),'detail':ef.get('detail'),'attribution':ef.get('attribution')})
  for origin,value in f.get('unknown_by_origin',{}).items():
   # Do not publish bulk logs, private paths or repeat complete adapter receipts.
   if isinstance(value,dict):
    value={**{z:value[z] for z in ['status','reason','issues','origin_gap','scope','limit'] if z in value},**({'origin_gap':value['facts']['origin_gap']} if 'origin_gap' in value.get('facts',{}) else {})}
   reasons.append({'layer':'unknown','origin':origin,'facts':value})
  if f.get('behavior_attribution'):reasons.append({'layer':'behavior_attribution','facts':f['behavior_attribution']})
  x['reason_refs']=[put('reasons',v) for v in reasons]
  witnesses=s.get('output_witnesses',{})
  if x['final']!='pass' and witnesses:
   chosen=max(witnesses,key=lambda n:(witnesses[n].get('error_lower_V',0) if x['numeric']=='numerical_error' else witnesses[n].get('error_upper_V',0)) or 0)
   w=witnesses[chosen];x['key_failure_witness']={'output':chosen,**{z:w[z] for z in ['worst','error_lower_V','error_upper_V','unresolved_uncertainty_V','unqualified_observations'] if z in w}}
  out.append(x)
 # Independent counts must equal the expanded aggregate, including failed/probe unknown slots.
 counts={b:{f:dict(collections.Counter(s[f] for s in out if s['backend']==b)) for f in LAYERS} for b in dict.fromkeys(s['backend'] for s in out)}
 availability={
  'original_raw':{'status':'local-only','claim':'Raw logs, waveforms and execution artifacts are retained locally; no public download is supplied. Hashes identify artifacts but do not make them publicly retrievable.'},
  'analysis_artifacts':{'status':'local-only','locator':'tables.analyses retention_id and artifact hashes'},
  'model_and_checker_source':{'status':'repository-contained','model_sources':['evas/validation/paper/precision_breadth_foundation.py','evas/validation/paper/precision_breadth_composition.py'],'checker_revisions':list(dict.fromkeys(a['checker_revision'] for a in r['analyses'])),'claim':'Versioned model and checker definitions are distinct from original execution artifacts; a source revision does not prove historical binary provenance or public raw availability.'},
  'reexecution':{'status':'requires-backend-environment','claim':'New execution requires the recorded backend, settings and stimuli, including licensed tools where applicable. Repository source is not a claim that historical binaries or execution artifacts are redistributable.'}}
 return {'schema_version':1,'availability':availability,'claim':'curated immutable receipt; no new qualification or best-of selection','selected_slots':len(out),'collected_slots':sum(s['original_execution'] not in ('not_run','not_collected') for s in out),'aggregate_source_sha256':r['aggregate_source_sha256'],'tool_source_hashes':r['tool_source_hashes'],'selection_sha256':r['selection_sha256'],'official_input_manifest_sha256':r['official_input_manifest_sha256'],'tables':tables,'slots':out,'counts':counts,'groups':[{k:g[k] for k in ['group','backend','Q','status','numeric','behavior','evidence','config','native','runtime','mandatory_variants','variants']}|{'integrator':integrator_status(g)} for g in r['groups']]}
def main():
 a=argparse.ArgumentParser();a.add_argument('--aggregate',type=pathlib.Path,required=True);a.add_argument('--failure-inventory',type=pathlib.Path,required=True);a.add_argument('--cards',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True);a.add_argument('--expected-cards-sha256');o=a.parse_args()
 if any(o.output.resolve().is_relative_to(p.resolve()) for p in [o.aggregate,o.failure_inventory,o.cards.parent]):raise ValueError('output is inside sealed input tree')
 agsha=verify(o.aggregate,required=('OFFICIAL-DRAFT.json',));fsha=verify(o.failure_inventory,required=('FAILURES.json',));r=json.loads((o.aggregate/'OFFICIAL-DRAFT.json').read_text());f=json.loads((o.failure_inventory/'FAILURES.json').read_text())
 if pathlib.Path(f['aggregate']).resolve()!=o.aggregate.resolve() or f['aggregate_manifest_sha256']!=agsha:raise ValueError('wrong failure inventory aggregate')
 cards_sha=verify_cards(o.cards,r,o.expected_cards_sha256)
 for analysis in r['analyses']:verify_external_analysis(analysis)
 result=curate(r,f,json.loads(o.cards.read_text())['cards']);result['official_cards_sha256']=cards_sha;result.update(curation_source_sha256=digest(pathlib.Path(__file__)),aggregate_manifest_sha256=agsha,failure_manifest_sha256=fsha,cards_sha256=digest(o.cards))
 encoded=json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n'
 if '/Users/' in encoded or '/home/' in encoded:raise ValueError('private absolute path leaked')
 o.output.mkdir(exist_ok=False);target=o.output/'PUBLIC-RECEIPT.json';target.write_text(encoded)
 check=json.loads(target.read_text());assert check['counts']==result['counts'] and len(check['slots'])==852
 (o.output/'MANIFEST.json').write_text(json.dumps({'PUBLIC-RECEIPT.json':{'sha256':digest(target),'bytes':target.stat().st_size}},indent=2)+'\n')
 print(json.dumps({'output':str(o.output),'slots':852,'collected':result['collected_slots'],'bytes':target.stat().st_size,'sha256':digest(target)}))
if __name__=='__main__':main()
