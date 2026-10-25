"""Normalize a frozen, independently reviewed source archive into the ledger.

This imports explicit review corrections, retains pending boundaries and does not
approve semantics. The source archive is retained at the canonical task entry;
the public PDF hashes and exact locators remain in data/. No PDF is redistributed.
"""
from pathlib import Path
import argparse
import bisect
import hashlib
import json
import re
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-directory', type=Path, required=True,
                    help='Frozen extraction, merged review index and patch archive')
parser.add_argument('--output-directory', type=Path,
                    default=Path(__file__).resolve().parent / 'data')
args = parser.parse_args()
D = args.source_directory
OUT = args.output_directory
OUT.mkdir(parents=True, exist_ok=True)
merged=json.loads((D/'merged-index.json').read_text()); base,ext=merged['documents']; items=base['items']
# Use independent TOC titles to distinguish headings from numbered prose lists.
norm=lambda s:re.sub(r'[^a-z0-9]','',s.lower())
toc={x['key']:norm(x.get('title','')) for x in items if x.get('kind')=='toc_entry'}
headings=sorted((x['pdf_page_1based'],x['page_line_1based'],x['key']) for x in items if x.get('kind')=='clause_candidate' and x.get('key') in toc and norm(x.get('title',''))==toc[x['key']])
headings += [(x['pdf_page_1based'],x['page_line_1based'],x['key']) for x in items if x.get('kind')=='annex']
headings.sort()
positions=[x[:2] for x in headings]
allowed={'id','kind','key','name','title','pdf_page_1based','page_line_1based','end_pdf_page_1based','end_page_line_1based','extracted_span_sha256','parent_id','bbox_points','source_parts','effective_span_sha256','text_sha256','cell_sequence_sha256','span_sha256','token_sha256','column_index_0based','column_count','row_role','occurrence_ids','normativity','semantic_review_status','boundary_review_status','reason','original_extracted_name','original_table_key','physical_rows_are_logical_rows','caption_source_id'}
normalized=[];dispositions=[]
def policy(obj):
 kind=obj.get('kind','unknown_source_candidate');key=obj.get('key','');owner=None
 if kind in ('toc_entry','toc_annex'):
  return 'excluded','Navigation entry; applicable body source is separately indexed.',key
 if obj.get('disposition')=='excluded':
  return 'excluded','Boundary review identified page furniture, false heading/caption or superseded extraction identity.',None
 if kind in ('grammar_production','production_name_group') or ':grammar_production:' in obj['id']:
  return 'pending','Annex C.15 inherits grammar with subset restrictions; production applicability requires explicit review.',key
 if kind=='reserved_keyword':return 'included','Annex C.3/C.16 reserve all AMS keywords; use of unused keywords remains restricted.', 'B'
 if key.startswith(('C.','D.','E.','F.','G.','H.')):owner=key
 elif kind=='annex':owner=key
 elif kind in ('table','table_grid_fragment','physical_grid_row','physical_grid_cell','logical_table_row','logical_table_cell','logical_table_column'):
  m=re.search(r'(?:table-grid:|table:)([A-H0-9]+)[-.]',obj['id'])
  if m:owner=m[1]
 if owner is None and obj.get('pdf_page_1based'):
  index=bisect.bisect_right(positions,(obj['pdf_page_1based'],obj.get('page_line_1based',0)))-1
  if index>=0:owner=headings[index][2]
 owner=owner or key
 chapter=owner.split('.')[0] if owner else ''
 if chapter=='7':return 'excluded','Annex C.9 excludes mixed-signal Clause 7; source remains indexed.',owner
 if owner.startswith(('3.7','3.8','5.10.5','6.5.3')):
  return 'excluded','Annex C.4/C.7/C.8 excludes this construct; subset error/ignore obligations remain at Annex C.',owner
 if chapter=='8':
  if owner.startswith('8.3'):return 'included','Annex C.10 includes the analog simulation cycle.',owner
  return 'pending','C.10 has a stale 8.2 mixed-cycle cross-reference; do not mechanically exclude initialization or infer a new interpretation.',owner
 if chapter in ('9','11','12'):
  return 'pending','Annex C.11/C.13/C.14 includes only analog context/behavior; row-level context needs review.',owner
 if chapter in ('1','2','3','4','5','6','10'):
  return 'pending','Annex C.1-C.12 applies with explicit exceptions; this physical/structural source still needs fine-grained applicability review.',owner
 if chapter in ('C','D','E','F'):
  return 'pending','Annex C policy, standard definitions, SPICE compatibility or normative dependency retained; item-level exceptions require review.',owner
 if chapter in ('G','H'):return 'excluded','Informative annex retained as a dependency/navigation source; not promoted wholesale to normative semantics.',owner
 return 'pending','Unclassified source boundary or applicability remains explicitly retained.',owner
for obj in items:
 out={k:v for k,v in obj.items() if k in allowed}
 out['kind']=out.get('kind','unknown_source_candidate');out['source_document']='lrm24';out['source_treatment']=obj['disposition']
 decision,reason,owner=policy(obj)
 if owner:out['owner_clause_candidate']=owner
 normalized.append(out)
 dispositions.append({'source_id':obj['id'],'decision':decision,'reason':reason,'evas_target_scope':'pending-fine-grained-mapping'})
for obj in ext['g7_changes']+ext['selected_source_containers_and_atoms']:
 out={k:v for k,v in obj.items() if k in allowed or k in ('mantis','selection','description_status','selection_unit','note')};out['source_document']='lrm2023';out.setdefault('kind','change-index');out['source_treatment']='included';normalized.append(out)
 selected=obj.get('selection')=='selected' or obj.get('kind')=='selected_atom_candidate'
 dispositions.append({'source_id':obj['id'],'decision':'included' if selected else 'pending','reason':'Only selected 7780/7920 atoms override 2.4; containers are navigation, never wholesale replacement.','evas_target_scope':'not-conferred'})
normalized.append({'id':'lrm24:table:B.1','kind':'logical_table_group','source_document':'lrm24','key':'B.1','source_treatment':'included','boundary_review_status':'two-page-keyword-table-reviewed'})
dispositions.append({'source_id':'lrm24:table:B.1','decision':'included','reason':'Annex C.3/C.16 reserve the 212 B.1 keywords; use restrictions are separate.','evas_target_scope':'pending-fine-grained-mapping'})
ids=[x['id'] for x in normalized]
assert len(ids)==len(set(ids)), 'duplicate index identity'
# Keep one canonical object; boundary tasks reference IDs instead of repeating objects.
boundary_tasks=[]
for u in merged['unresolved_boundaries']:
 if u.get('resolution')=='review-attached' or u.get('kind')=='source_boundary_pending':continue
 boundary_tasks.append(u)
patch=json.loads((D/'merged-index-patch.json').read_text())
audit={'schema_version':1,'merged_source_sha256':hashlib.sha256((D/'merged-index.json').read_bytes()).hexdigest(),'operations':patch['operations'],'review_receipts':patch['review_receipts'],'boundary_tasks':boundary_tasks,'claims':{k:v for k,v in merged['claims'].items() if k != 'pr1_complete'}}
source={'schema_version':1,'documents':[{'id':x['version'],'pdf_sha256':x['pdf_sha256']} for x in merged['documents']],'reconciliation':json.loads((D/'source-inventory.json').read_text())['documents'][0]['reconciliation'],'items':sorted(normalized,key=lambda x:x['id'])}
def write_rows(name,data,key):
 rows=data.pop(key);prefix=json.dumps(data,ensure_ascii=False,sort_keys=True)[:-1]
 text=prefix+',"'+key+'":[\n'+',\n'.join(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')) for r in rows)+'\n]}\n';(OUT/name).write_text(text)
audit['normalized_inventory_identity'] = hashlib.sha256(json.dumps(source['items'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
write_rows('source-inventory.json',source,'items')
write_rows('dispositions.json',{'schema_version':1,'items':sorted(dispositions,key=lambda x:x['source_id'])},'items')
(OUT/'boundary-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
(OUT/'annex-c-policy.json').write_text(json.dumps({'schema_version':1,'items':merged['annex_c_applicability_policy']},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'items':len(ids),'dispositions':len(dispositions),'boundary_tasks':len(boundary_tasks)}))
