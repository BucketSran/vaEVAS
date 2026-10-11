from pathlib import Path
import json,hashlib,collections
R=Path(__file__).resolve().parents[1]
def rd(p):return json.loads(p.read_text())
def sh(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def manifest(d):
 for n,v in rd(d/'MANIFEST.json').items():assert sh(d/n)==v['sha256'] and (d/n).stat().st_size==v['bytes'],n
A=R/'official-final-v3-ng-f03-guarded-v1';C=R/'public-receipt-final-v3-ng-f03-852-v2';F=R/'failure-inventory-final-v3-ng-f03-guarded-v2'
for p in [A,C,F]:manifest(p)
a=rd(A/'OFFICIAL-DRAFT.json');c=rd(C/'PUBLIC-RECEIPT.json');old=rd(R/'official-draft-complete-v2-baseline-guarded-v1/OFFICIAL-DRAFT.json');selection=rd(A/'SELECTION.json')
assert sh(A/'SELECTION.json')==sh(R/'FINAL-SELECTION-v3-ng-f03-v1.json')==a['selection_sha256']==c['selection_sha256']
key=lambda x:(x['backend'],x['variant'],x['Q']);am={key(x):x for x in a['slots']};om={key(x):x for x in old['slots']};cm={key(x):x for x in c['slots']};assert len(am)==len(om)==len(cm)==852 and am.keys()==om.keys()==cm.keys()
axes=['final','numeric','behavior','evidence','config','native','runtime','integrator','original_execution'];science=['final','numeric','behavior','evidence','config','native','runtime','original_execution','error_lower_V','error_upper_V','voltage_budget_V','source_sha256','original_result_sha256','kernel_or_binary_sha256','tool_identity_sha256'];unchanged=0;new=0;counts={}; reasons=0
analyses={x['analysis']:x for x in a['analyses']}
for k,s in am.items():
 cs=cm[k]
 for name in axes+['selected_batch','source_compatibility','source_sha256','original_result_sha256','kernel_or_binary_sha256','tool_identity_sha256','error_lower_V','error_upper_V','voltage_budget_V']:assert s.get(name)==cs.get(name),(k,name)
 for ref,tab,name in [('legacy_configuration_ref','legacy_configurations','legacy_configuration'),('settings_provenance_ref','settings_provenance','settings_provenance'),('external_qualification_ref','external_qualifications','external_qualification')]:assert c['tables'][tab][cs[ref]]==s[name],(k,ref)
 settings=c['tables']['settings'][cs['settings_ref']];assert settings['requested']==s['requested_settings'] and settings['actual']==s['actual_settings']
 for ref in cs['reason_refs']:assert ref in c['tables']['reasons'];reasons+=1
 spec=selection['slot_selection'][s['backend']];assert s['selected_batch']==spec['group_batches'].get(s['group'],spec['default_batch'])
 if s['backend']!='evas' and not(s['backend']=='openvaf_r_ngspice' and s['group']=='F03'):
  for name in science:assert s.get(name)==om[k].get(name),(k,name)
  unchanged+=1
 else:
  new+=1;ar=next(x for x in rd(Path(s['analysis'])/'REANALYSIS.json') if x['label']==s['label']);assert s['original_result_sha256']==ar['identity']['original_result_sha256'];assert s['final']==ar['qualified_tiers'][s['Q']]
  raw=Path(analyses[s['analysis']]['raw_lane'])/'runs'/s['label'];assert sh(raw/'RESULT.json')==s['original_result_sha256']
  if s['backend']=='evas':assert s['kernel_or_binary_sha256']=='ae8e012c97abc166b33dbb2b0ccd7f9ed4a1d28543d2e1bd1c1f083c47fbf602'
  else:assert s['final']=='evidence_insufficient' and s['config']==s['native']==s['runtime']=='unknown'
 assert not(s.get('probe_only') and s['final']=='pass')
 if s['backend'] in ('openvaf_r_ngspice','gnucap_modelgen'):assert s['native']==s['runtime']==s['integrator']=='unknown' and s['final']!='pass'
for backend in {s['backend'] for s in a['slots']}:
 counts[backend]={axis:dict(collections.Counter(s[axis] for s in a['slots'] if s['backend']==backend)) for axis in axes}
assert counts==c['counts'];assert unchanged==603 and new==249
assert len(a['groups'])==len(c['groups'])==528
cg={(g['backend'],g['group'],g['Q']):g for g in c['groups']}
for g in a['groups']:
 cc=cg[g['backend'],g['group'],g['Q']]
 for k,v in cc.items():assert g[k]==v,(g['group'],k)
assert not c['tables']['external_proofs'];assert c['curation_source_sha256']=='d9f20088929e7fe1e5ef18ddfa77fbb5ca69b4b8a0c3f21d0b6d255f3b0e773b'
result={'aggregate_sha256':sh(A/'OFFICIAL-DRAFT.json'),'compact_sha256':sh(C/'PUBLIC-RECEIPT.json'),'compact_bytes':(C/'PUBLIC-RECEIPT.json').stat().st_size,'failure_inventory_sha256':sh(F/'FAILURES.json'),'selection_sha256':sh(A/'SELECTION.json'),'slots':852,'groups':528,'unchanged_scientific_slots':unchanged,'new_selected_slots':new,'reasons_checked':reasons,'counts':counts,'overall_final':dict(collections.Counter(s['final'] for s in a['slots'])),'failures':[]}
(R/'review/astra-final-852-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='counts'},indent=2))
