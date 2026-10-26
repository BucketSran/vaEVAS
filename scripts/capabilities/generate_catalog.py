"""Build one Registry from independent actual receipts, without running discovered code."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

PARTS={'catalog-sources.json':'sources','asset-index.json':'assets','method-index.json':'methods','entrypoint-index.json':'entrypoints','historical-index.json':'history'}
GOVERNANCE={'evas/validation/baselines/regression-v1.json','evas/validation/baselines/regression-v1.review.json'}
PREFIXES=['.agents/','.github/','docs/','evas/','experiments/','scripts/']

def canonical(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(obj):return {'id':obj['id'],'version':obj['version'],'sha256':canonical(obj)}
def versioned(obj):
 obj['version']=canonical({k:v for k,v in obj.items() if k!='version'});return obj

def sid(kind,key):return kind+':'+hashlib.sha256(key.encode()).hexdigest()[:24]
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def owned(module,path):
 spec=importlib.util.spec_from_file_location(module,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def source(logical,path,locator=None):
 rawsha=file_sha(path)
 return versioned({'schema_version':1,'id':sid('source',logical),'version':rawsha,'kind':'source','status':'active',
  'origin':logical,'availability':'pending' if locator is None else 'published-archive',
  'locator':locator or {'kind':'pending-archive','repository':'vaevas-evidence','revision':None,'path':'discovery/'+rawsha+'.json'},
  'sha256':rawsha,'dependencies':[]})

def select_audited_method(row,current,previous_objects,current_assets):
 """Bind original path/runtime/bytes before considering current selection."""
 owners={(o['id'],o['version']):o for o in previous_objects if o['kind']=='asset'}
 owners.update({(o['id'],o['version']):o for o in current_assets})
 def identity(method):
  if method is None or method.get('namespace')!='python-regression' or method.get('runtime_id')!=row['id']:return None
  owner=owners.get((method['module']['id'],method['module']['version']))
  return owner if owner and ref(owner)==method['module'] and owner['current_path']==row.get('source_file') else None
 def exact(method):
  owner=identity(method)
  return owner if owner and method['definition']['sha256']==row.get('source_method_sha256') and owner['content'].get('value')==row.get('source_module_sha256') else None
 owner=exact(current)
 if owner is not None:return current,owner,'current-observed-method'
 candidates=[o for o in previous_objects if o['kind']=='method' and o.get('namespace')=='python-regression' and o.get('runtime_id')==row['id']]
 for method in sorted(candidates,key=lambda o:(o['id'],o['version'])):
  owner=exact(method)
  if owner is not None:return method,owner,'retained-original-method-version'
 owner=identity(current)
 if owner is not None:return current,owner,'current-observed-method'
 raise ValueError('historical original source identity unavailable; explicit unbound migration required: '+row['id'])

def entry_inputs(config):
 result=[]
 for item in config['discoveries']:
  if 'entry_file' in item:
   value=json.loads(Path(item['entry_file']).read_text());result.append((value['entry'],value['receipt'],Path(item['entry_file']),item))
  else:
   receipt=json.loads(Path(item['receipt_file']).read_text());result.append((item['entry'],receipt,Path(item['receipt_file']),item))
 return result

def build(config,out):
 root=Path(config['source_root']).resolve();out=Path(out).resolve();data_dir=out/'tree/evas/capabilities/data'
 api=owned('catalog_generation_registry',root/'evas/capabilities/registry.py')
 initial=api.load(root/'evas/capabilities/data',root=root)
 base=copy.deepcopy(initial.data)
 # Preserve every previous version; current comes from this generation, never by mutating old objects.
 previous_dir=Path(config.get('previous_data_dir',root/'evas/capabilities/data'))
 previous_header=json.loads((previous_dir/'registry.json').read_text())
 previous_objects=list(previous_header['objects'])
 for filename in previous_header.get('object_parts',[]):
  previous_objects.extend(json.loads((previous_dir/filename).read_text())['objects'])
 previous_lookup={(o['id'],o['version']):o for o in previous_objects}
 previous_current={name:previous_lookup[(name,version)] for name,version in previous_header['current'].items()}
 normative_header=json.loads((root/'evas/capabilities/data/registry.json').read_text())
 normative_union={(o['id'],o['version']):o for o in [*previous_header['objects'],*normative_header['objects']]}
 base['objects']=list(normative_union.values())
 normative_ids={o['id'] for o in base['objects']}
 base['current']={name:version for name,version in normative_header['current'].items() if name in normative_ids}
 prior_assets={o['current_path']:o for o in previous_current.values() if o['kind']=='asset'}
 prior_methods={(o['namespace'],previous_lookup[(o['module']['id'],o['module']['version'])]['current_path'],o['runtime_id']):o for o in previous_current.values() if o['kind']=='method'}
 moves=config.get('identity_moves',{'assets':{},'methods':{}})

 observation=json.loads(Path(config['asset_receipt']).read_text())
 if observation.get('source_kind')!='immutable-export' or observation.get('content_binding')!='verified-git-blob-oids':raise ValueError('actual immutable export asset receipt required')
 rows=observation['assets'];observed={r['path']:r for r in rows}
 if len(observed)!=len(rows):raise ValueError('duplicate actual asset paths')
 policy=config.get('asset_scope',{'schema_version':1,'id':'EVAS-scope-v1','owner':'evas','included_prefixes':PREFIXES,'root_files':'included','external_components':[{'prefix':'benchmark/','owner':'benchmark'}],'bridges':[]})
 if policy['bridges']:raise ValueError('use bridge_evidence config to bind generated source/consumer refs; do not prefill refs')
 include=[p for p in observed if '/' not in p or any(p.startswith(prefix) for prefix in PREFIXES)]
 unknown=[p for p in observed if p not in include and not p.startswith('benchmark/')]
 if unknown:raise ValueError('unowned source prefixes: '+str(unknown))
 for path in include:
  target=root/path
  if target.is_symlink() or not target.is_file() or file_sha(target)!=observed[path]['sha256'] or (target.stat().st_mode & 0o7777)!=observed[path]['actual_mode']:
   raise ValueError('actual source export differs from asset receipt: '+path)
 sources=[];entries=[];assets={};methods={};histories=[];entry_records=[];pending=[];observation_slots=set()
 locator_map=config.get('discovery_source_locators',{})
 for entry,receipt,path,item in entry_inputs(config):
  if receipt.get('schema_version')!=1 or not receipt.get('complete') or receipt.get('errors') or receipt.get('unresolved_instances'):raise ValueError('incomplete actual discovery input: '+str(path))
  if receipt['namespace']!=entry['namespace']:raise ValueError('entry/receipt namespace mismatch')
  if len(receipt['methods'])!=receipt.get('discovered_instances',len(receipt['methods'])):raise ValueError('receipt instance/source accounting differs')
  identity=entry.get('entry_id',canonical(entry));observation_id=identity+':'+item.get('observation_slot','default')
  if observation_id in observation_slots:raise ValueError('duplicate observation slot; name matrix slots explicitly')
  observation_slots.add(observation_id)
  s=source('actual-discovery:'+observation_id,path,locator_map.get(observation_id,locator_map.get(identity)));sources.append(s)
  # entry_file wraps receipt: source SHA binds original wrapper and pointer to its raw receipt.
  pointer='/receipt' if 'entry_file' in item else ''
  workflow_sha=item.get('workflow_sha256',entry.get('workflow_sha256'))
  if entry.get('workflow'):
   actual_workflow_sha=file_sha(root/entry['workflow'])
   if workflow_sha is not None and workflow_sha!=actual_workflow_sha:raise ValueError('workflow source drift')
   workflow_sha=actual_workflow_sha
  ep={'schema_version':1,'id':sid('entry',observation_id),'version':identity,'kind':'entrypoint','status':'active',
   'namespace':entry['namespace'],'collector':'unittest','start':entry['start'],'pattern':entry['pattern'],
   'ci_entrypoint_ids':[identity] if entry.get('workflow') else [],'workflow_sha256':workflow_sha,
   'provenance':{k:v for k,v in entry.items() if k not in ('environment','command')},
   'command':entry.get('command'),'actual_receipt':ref(s),'receipt_pointer':pointer,
   'receipt_canonical_sha256':canonical(receipt),'collector_sha256':receipt.get('collector',{}).get('sha256'),
   'dependencies':[ref(s)]}
  versioned(ep)
  entries.append(ep);entry_records.append((entry,receipt,ep,s));seen=set()
  for row in receipt['methods']:
   key=(entry['namespace'],row['module_path'],row['runtime_id'])
   if key in seen:raise ValueError('duplicate actual method instance: '+str(key))
   seen.add(key)
   if row['module_path'] not in observed or observed[row['module_path']]['sha256']!=row['module_sha256']:raise ValueError('method owner asset source drift: '+row['module_path'])
   if row['definition']['path'] not in observed:raise ValueError('unregistered method definition asset')
   core={k:row[k] for k in ('module_path','runtime_id','module_sha256','definition','generated')}
   if key in methods and methods[key]['core']!=core:raise ValueError('conflicting owned method source: '+str(key))
   state=methods.setdefault(key,{'core':core,'entries':[],'observations':[]})
   state['entries'].append(ep)
   state['observations'].append({'entrypoint_id':identity,'receipt_source':ref(s),'receipt_pointer':pointer,
    'row_canonical_sha256':canonical(row),'skip_declaration':row.get('skip_declaration'),
    'native_skip_wrapper':row.get('native_skip_wrapper'),'execution_status':'not-executed-by-discovery'})
 rust_records=[]
 for item in config.get('rust_listings',[]):
  path=Path(item['receipt_file']);raw=json.loads(path.read_text());profile=item['profile']
  if not isinstance(profile,str) or not profile or raw.get('schema_version')!=1 or not raw.get('complete') or raw.get('errors') or raw.get('observation_kind')!='rust-test-binary-listing':raise ValueError('incomplete/unknown actual Rust listing')
  logical='actual-rust-listing:'+profile
  src=source(logical,path,item.get('source_locator'));sources.append(src)
  actual_files={r['path']:r for r in raw['source']['files']}
  expected_files={p:r for p,r in observed.items() if p.startswith('evas/rust_core/')}
  if actual_files.keys()!=expected_files.keys() or any(actual_files[p]['sha256']!=expected_files[p]['sha256'] or actual_files[p]['mode']!=expected_files[p]['actual_mode'] for p in actual_files):raise ValueError('Rust conservative source-tree differs from fixed asset observation')
  for binary in raw['binaries']:
   target={k:binary[k] for k in ('package','version','target_kind','name')}
   ep=versioned({'schema_version':1,'id':sid('entry','rust:'+profile+':'+canonical(target)),'version':'1','kind':'entrypoint','status':'active',
    'namespace':'rust-tests','collector':'binary-listing','listing_profile':profile,'rust_target':target,
    'listing_source':ref(src),'observer_sha256':raw['observer']['sha256'],
    'provenance_scope':'actual native listing, original observer; not upgraded to later helper execution',
    'dependencies':[ref(src)]})
   entries.append(ep)
  rust_records.append((item,raw,src))
 bridge_by_path={}
 for bridge in config.get('bridge_evidence',[]):
  path=bridge['path']
  if not path.startswith('benchmark/') or path not in observed or path in bridge_by_path:raise ValueError('bridge must be an actual exact external path')
  consumer_ids=bridge['consumer_entry_ids']
  if not isinstance(consumer_ids,list) or not consumer_ids or any(not isinstance(i,str) or not i for i in consumer_ids):raise ValueError('bridge requires explicit consumer entry IDs')
  chosen=[e for e in entries if any(i in consumer_ids for i in e.get('ci_entrypoint_ids',[])) or e.get('provenance',{}).get('entry_id') in consumer_ids]
  if not chosen:raise ValueError('bridge has no actual declared consumer entrypoint')
  proof=source('reviewed-bridge:'+path,bridge['source_file'],bridge.get('source_locator'));sources.append(proof)
  record={'path':path,'owner':'benchmark','reason':bridge['reason'],'source':ref(proof),'consumers':[ref(e) for e in chosen]}
  policy['bridges'].append(record);bridge_by_path[path]=(proof,chosen)
  include.append(path)
 metadata_paths={'evas/capabilities/data/registry.json',*('evas/capabilities/data/'+name for name in PARTS)}
 generated={'evas/capabilities/registry.json','evas/capabilities/generated/comparison.md','evas/capabilities/generated/paper.md','evas/capabilities/generated/normative.md','evas/docs/development/TRACEABILITY.md'}
 legacy=json.loads((root/'evas/capabilities/data/historical-comparison.json').read_text())
 generated.update('evas/capabilities/'+n['id']+'/README.md' for n in legacy['nodes'])
 readiness={}
 readiness_source=None
 if config.get('readiness_file'):
  prior_rows=json.loads(Path(config['readiness_file']).read_text())['items'];readiness={r['current_path']:{**r,'_row_index':i} for i,r in enumerate(prior_rows)}
  readiness_source=source('prior-limited-readiness-facts',config['readiness_file'],config.get('readiness_source_locator'));sources.append(readiness_source)
 owner_entries={}
 for state in methods.values():
  for ep in state['entries']:owner_entries.setdefault(state['core']['module_path'],{})[ep['id']]=ep
 for item,raw,src in rust_records:
  rust_entries=[e for e in entries if e.get('listing_profile')==item['profile']]
  for path in (r['path'] for r in raw['source']['files']):
   for e in rust_entries:owner_entries.setdefault(path,{})[e['id']]=e
 # Planned metadata paths must exist as objects, even before final capture/stage contains the new files.
 for path in sorted(set(include)|metadata_paths):
  row=observed.get(path);owner=dict(owner_entries.get(path,{}))
  bridge=bridge_by_path.get(path)
  if bridge:owner.update({e['id']:e for e in bridge[1]})
  prior_path=path if path in prior_assets else moves.get('assets',{}).get(path,path)
  previous_asset=prior_assets.get(prior_path)
  if prior_path!=path and previous_asset is None:raise ValueError('asset move lacks previous identity')
  external=path in metadata_paths or path in generated or path in GOVERNANCE
  role='catalog-meta' if path in metadata_paths else 'derived' if path in generated else 'governance' if path in GOVERNANCE else 'cross-component-source-read' if bridge else 'conservative-rust-tree-identity-input' if owner and all(e['collector']=='binary-listing' for e in owner.values()) else 'actual-unittest-owner' if owner else None
  a={'schema_version':1,'id':previous_asset['id'] if previous_asset else readiness.get(path,{}).get('id',sid('asset',path)),'version':'1' if external else row['sha256'],
    'kind':'asset','status':'active','namespace':'EVAS-assets','current_path':path,
    'content':{'algorithm':'external-input-manifest','scope':'actual-execution-inputs','producer':'capabilities.observe-assets-v1'} if external else {'algorithm':'sha256','value':row['sha256']},
    'role':{'status':'confirmed' if role else 'pending','value':role,'reason':'exact Registry/producer/governance path' if external else 'exact source-bound external read; partial consumers only' if bridge else 'conservative native source-tree identity; not compiler read or runtime closure' if role=='conservative-rust-tree-identity-input' else 'actual TestLoader owner module; no semantic qualification' if owner else 'responsibility awaits source review; path does not infer semantics'},
    'consumers':[ref(ep) for ep in sorted(owner.values(),key=lambda e:e['id'])],
    'consumer_status':'partial' if owner else 'pending','location_history':[],
    'location_history_status':'pending-per-file-lineage','semantic_status':'pending','qualification_status':'not-granted',
    'dependencies':[ref(bridge[0])] if bridge else []}
  if previous_asset:a['location_history']=copy.deepcopy(previous_asset.get('location_history',[]))
  if previous_asset and prior_path!=path:a['location_history']=[*previous_asset.get('location_history',[]),{'prior_asset':ref(previous_asset),'reason':'explicit reviewed identity_moves mapping'}]
  if owner:a['role']['facts']=[{'entrypoint':ref(ep),'proof':'source-bound-external-read-partial-consumer' if bridge else 'actual-rust-conservative-source-tree-identity' if ep['collector']=='binary-listing' else 'actual-discovery-owner-module'} for ep in sorted(owner.values(),key=lambda e:e['id'])]
  if not row:a['observation_status']='pending-generation-then-final-capture';pending.append({'kind':'planned-metadata-not-in-capture','path':path})
  old=readiness.get(path)
  if old:
   a['prior_readiness']={'source':ref(readiness_source),'row_pointer':'/items/'+str(old['_row_index']),
      'row_canonical_sha256':canonical({k:v for k,v in old.items() if k!='_row_index'}),
      'source_revision':old['source_revision'],'git_blob':old['git_blob'],'confirmed_fact_count':len(old['confirmed_facts']),
      'current_blob_matches_prior':bool(row and row.get('git_blob_oid')==old['git_blob']),
      'status':'prior limited facts only; underlying evidence availability and current semantic/consumer closure remain unverified'}
   a['dependencies'].append(ref(readiness_source))
  if previous_asset and prior_path!=path:
   a['location_history']=[{'prior_asset':ref(old),'reason':'explicit move; retain every known earlier path version'} for old in previous_objects if old['id']==a['id'] and old.get('current_path')!=path]
  assets[path]=versioned(a)
 for key,state in list(methods.items()):
  namespace,module_path,runtime_id=key;core=state['core'];owner=assets.get(module_path)
  if owner is None:raise ValueError('method owner outside declared asset scope')
  definition_asset=assets.get(core['definition']['path'])
  if definition_asset is None:raise ValueError('method definition outside declared asset scope')
  prior_key=key if key in prior_methods else tuple(moves.get('methods',{}).get('|'.join(key),key))
  previous_method=prior_methods.get(prior_key)
  if prior_key!=key and previous_method is None:raise ValueError('method move lacks previous identity')
  obj={'schema_version':1,'id':previous_method['id'] if previous_method else sid('method','\0'.join(key)),'version':canonical({'namespace':namespace,**core}),
   'version_scope':'full-version-bound-object-v1','kind':'method','status':'active','namespace':namespace,'runtime_id':runtime_id,
   'module':ref(owner),'definition':core['definition'],'generated':core['generated'],
   'entrypoints':[ref(e) for e in sorted(state['entries'],key=lambda e:e['id'])],
   'discovery_observations':state['observations'],'runtime_history':[],
   'semantic_status':'pending','qualification_status':'not-granted','dependencies':[ref(owner)]}
  if definition_asset is not owner:obj['definition_asset']=ref(definition_asset);obj['dependencies'].append(ref(definition_asset))
  if previous_method:obj['runtime_history']=copy.deepcopy(previous_method.get('runtime_history',[]))
  if previous_method and prior_key!=key:obj['runtime_history']=[*previous_method.get('runtime_history',[]),{'prior_method':ref(previous_method),'reason':'explicit reviewed identity_moves mapping'}]
  if previous_method and prior_key!=key:obj['runtime_history']=[{'prior_method':ref(old),'reason':'explicit rename/move; retain every known runtime version'} for old in previous_objects if old['id']==obj['id'] and old.get('runtime_id')!=runtime_id]
  methods[key]=versioned(obj)
 # AST navigation facts do not change the already-bound asset identity. Keep a separate source-bound transition report.
 capindex=root/'evas/docs/development/capability-evidence.md';known={}
 for number,line in enumerate(capindex.read_text().splitlines(),1):
  if line.startswith('|'):
   cells=[x.strip() for x in line.strip().strip('|').split('|')]
   if re.fullmatch('[A-Z][A-Z-]*',cells[0]):known[cells[0]]={'line':number,'row_sha256':hashlib.sha256(line.encode()).hexdigest()}
 guardfacts=[]
 for path in sorted(owner_entries):
  if not path.endswith('.py'):continue
  tree=ast.parse((root/path).read_text());decl=[]
  for node in tree.body:
   targets=node.targets if isinstance(node,ast.Assign) else [node.target] if isinstance(node,ast.AnnAssign) else []
   if any(isinstance(t,ast.Name) and t.id=='GUARDS' for t in targets):decl.append(node)
  for node in decl:
   try:tags=ast.literal_eval(node.value)
   except (ValueError,TypeError):tags=None
   guardfacts.append({'module_path':path,'module_sha256':observed[path]['sha256'],'line':node.lineno,'declared_tags':tags,
      'stable_id_navigation':[{'tag':tag,'mapping':known.get(tag),'status':'source-bound-stable-ID-navigation' if tag in known else 'pending-semantic-or-development-ID'} for tag in (tags or [])],
      'capability_index':{'path':'evas/docs/development/capability-evidence.md','sha256':file_sha(capindex)},
      'historical_node_crosswalk':'pending; no name-based inference','qualification':False})
 guard_payload={'schema_version':1,'facts':guardfacts,'legacy_node_ids':[n['id'] for n in legacy['nodes']],
   'legacy_source':{'path':'evas/capabilities/data/historical-comparison.json','sha256':file_sha(root/'evas/capabilities/data/historical-comparison.json')},
   'crosswalk_status':'pending-explicit-semantic-review','qualification':False}
 sources.append(versioned({'schema_version':1,'id':'source:guards-ast-transition','version':'1','kind':'source','status':'active',
   'origin':'owned-source-AST-GUARDS-navigation-not-semantic-qualification','availability':'repository-contained',
   'locator':{'kind':'embedded','value':guard_payload},'sha256':canonical(guard_payload),'dependencies':[]}))
 # Historical sources are the unchanged published original bytes.
 archive=Path(config['archive_repository']);commit=config['archive_commit'];archive_sources={}
 def original(logical,path):
  raw=subprocess.check_output(['git','--no-optional-locks','-C',str(archive),'show',commit+':'+path])
  s={'schema_version':1,'id':sid('source','published-history:'+path),'version':hashlib.sha256(raw).hexdigest(),'kind':'source','status':'active',
   'origin':logical,'availability':'published-archive','locator':{'kind':'git-object','repository':'vaevas','revision':commit,'path':path},
   'sha256':hashlib.sha256(raw).hexdigest(),'dependencies':[]}
  versioned(s);sources.append(s);archive_sources[logical]=s;return json.loads(raw),s
 prefix='evas/capabilities/history/'
 audit,s=original('original-method-audit-3257',prefix+'method-audit-20261025/original/full3257/audit.json')
 by_runtime={m['runtime_id']:m for m in methods.values() if m['namespace']=='python-regression'}
 for index,row in enumerate(audit['rows']):
  m,owner,alignment_scope=select_audited_method(row,by_runtime.get(row['id']),previous_objects,assets.values())
  matched=row.get('source_method_sha256')==m['definition']['sha256'] and row.get('source_module_sha256')==owner['content'].get('value')
  histories.append({'schema_version':1,'id':sid('history-audit',row['id']),'version':s['sha256'],'kind':'historical-audit-record','status':'active',
   'source':ref(s),'row_pointer':'/rows/'+str(index),'original_row_sha256':canonical(row),'scope_pointer':'/summary/scope','scope_sha256':canonical(audit['summary']['scope']),
   'identity_binding':'bound','history_protocol':'evas-method-audit-3257-v1','method':ref(m),
   'alignment':{'status':'matched' if matched else 'pending','scope':alignment_scope,'reason':'owned method/module bytes compared to original row; not semantic qualification'},
   'original_verdict':row['verdict'],'source_method_sha256':row['source_method_sha256'],'source_module_sha256':row['source_module_sha256'],
   'original_execution_outcome':row.get('execution_outcome'),'qualification_status':'not-granted','dependencies':[ref(s)]})
 specs=[('passing-oracles','evas-passing-oracles-v1','confirmed','/scope'),('passing-negative','evas-passing-negative-v1','findings',''),('passing-raw','evas-passing-raw-v1','findings','')]
 for group,protocol,key,scope_pointer in specs:
  doc,s=original(group,prefix+'passing-detectors-20261025/original/test-scheme-audit/'+group+'/findings.json')
  for index,row in enumerate(doc[key]):
   ids=row.get('test_ids',row.get('methods',[row.get('method_id')]))
   bound_findings={i:by_runtime.get(i) or next((m for m in previous_objects if m['kind']=='method' and m.get('namespace')=='python-regression' and m['runtime_id']==i),None) for i in ids}
   if any(m is None for m in bound_findings.values()):raise ValueError('finding subject needs explicit unbound migration')
   h={'schema_version':1,'id':sid('history-finding',group+':'+row['id']),'version':s['sha256'],'kind':'historical-finding','status':'active',
    'source':ref(s),'row_pointer':'/'+key+'/'+str(index),'original_row_sha256':canonical(row),'scope_pointer':scope_pointer,
    'scope_sha256':canonical(doc['scope'] if scope_pointer else doc),'identity_binding':'bound','history_protocol':protocol,
    'methods':[ref(bound_findings[i]) for i in ids],'subject_coverage':'complete','alignment':{'status':'pending','reason':'original detector has no tested-method SHA; raw module identity is narrower than semantic alignment'},
    'original_finding_id':row['id'],'qualification_status':'not-granted','dependencies':[ref(s)]}
   histories.append(h)
 for h in histories:versioned(h)
 values={'sources':sources,'assets':list(assets.values()),'methods':list(methods.values()),'entrypoints':entries,'history':histories}
 base['asset_scope']=policy;base['object_parts']=list(PARTS)
 oldobjects=base['objects'];merged={(o['id'],o['version']):o for o in [*previous_objects,*oldobjects]}
 migrations=[]
 for objects in values.values():
  for obj in objects:
   key=(obj['id'],obj['version'])
   if key in merged and merged[key]!=obj:raise ValueError('conflicting reused object version')
   merged[key]=obj
   prior=previous_current.get(obj['id'])
   if prior and prior['version']!=obj['version']:migrations.append({'id':obj['id'],'previous':ref(prior),'current':ref(obj),'reason':'version-bound regenerated content; previous object retained'})
   base['current'][obj['id']]=obj['version']
 base['_catalog_metadata_paths']=sorted(metadata_paths)
 actual=copy.deepcopy(base);actual['objects']=list(merged.values())
 reg=api.Registry(actual,root=root,repositories={'vaevas':archive,**config.get('source_repositories',{})});catalog=reg.catalog()
 historical_checked=0
 for obj in histories:catalog.read_history(obj);historical_checked+=1
 for src in sources:
  if src['availability']=='published-archive':
   reg.read_source(src)
 rust_checks=[]
 for item,raw,src in rust_records:
  if src['availability']=='published-archive' and hasattr(catalog,'reconcile_rust_listing'):
   value=catalog.reconcile_rust_listing(raw,profile=item['profile']);status='formal-API-reconciled'
  else:value=None;status='pending-current-Rust-API-in-preview-source' if src['availability']=='published-archive' else 'pending-published-source-locator'
  rust_checks.append({'profile':item['profile'],'actual_tests':raw['tests_discovered'],'actual_binaries':len(raw['binaries']),
   'actual_ignored':raw['ignored_tests_discovered'],'source_receipt_sha256':src['sha256'],'source_availability':src['availability'],
   'observer_sha256_as_actually_recorded':raw['observer']['sha256'],'status':status,'result':value})
 method_checks=[]
 for entry,receipt,ep,s in entry_records:
  # One namespace may contain many disjoint/overlapping entries. Verify each exact entry subset without shrinking the full registry.
  expected={m['runtime_id']:m for m in methods.values() if ref(ep) in m['entrypoints']}
  if len(expected)!=len(receipt['methods']):raise ValueError('entry subset method discrepancy')
  method_checks.append({'entry_id':ep['id'],'namespace':entry['namespace'],'methods':len(expected),'actual_instances':receipt.get('discovered_instances'),'source_sha256':s['sha256']})
 try:asset_report=catalog.reconcile_assets(rows,external_manifest=observed)
 except ValueError as error:
  if not hasattr(error,'report'):raise
  asset_report=error.report
  if asset_report['extra'] or asset_report['unknown'] or asset_report['drift'] or asset_report['external_identity_missing'] or set(asset_report['missing']) != (metadata_paths-observed.keys()):raise
 # Keep all preexisting normative files unchanged. No raw history/discovery payloads go into main parts.
 for path in (root/'evas/capabilities/data').glob('*.json'):data_dir.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,data_dir/path.name)
 kind_for={'sources':{'source'},'assets':{'asset'},'methods':{'method'},'entrypoints':{'entrypoint'},'history':{'historical-audit-record','historical-finding'}}
 base_keys={(o['id'],o['version']) for o in oldobjects}
 for name,kind in PARTS.items():
  objects=[obj for key,obj in merged.items() if key not in base_keys and obj['kind'] in kind_for[kind]]
  write(data_dir/name,{'schema_version':1,'kind':kind,'objects':sorted(objects,key=lambda o:(o['id'],o['version']))})
 for key in ('inventory','dispositions','inventory_identity','target_scope','language_profile','_catalog_metadata_paths'):base.pop(key,None)
 write(data_dir/'registry.json',base)
 write(out/'guards-transition.json',{'schema_version':1,'facts':guardfacts,'legacy_node_ids':[n['id'] for n in legacy['nodes']],
  'legacy_source':{'path':'evas/capabilities/data/historical-comparison.json','sha256':file_sha(root/'evas/capabilities/data/historical-comparison.json')},'crosswalk_status':'pending-explicit-semantic-review','qualification':False})
 report={'schema_version':1,'status':'generated; final source observation and required CI remain separate','source_capture':observation['source_commit'],
  'input_asset_receipt_sha256':file_sha(config['asset_receipt']),'scope_reconciliation':asset_report,'objects':{k:len(v) for k,v in values.items()},
  'namespace_counts':catalog.namespace_counts(),'entry_checks':method_checks,'rust_checks':rust_checks,'historical_rows_read_and_bound':historical_checked,
  'history_alignment_counts':{status:sum(h['alignment']['status']==status for h in histories) for status in ['matched','pending']},
  'role_counts':{status:sum(a['role']['status']==status for a in assets.values()) for status in ['confirmed','pending']},
  'consumer_closure':{'complete':0,'partial':sum(a['consumer_status']=='partial' for a in assets.values()),'pending':sum(a['consumer_status']=='pending' for a in assets.values())},
  'pending':pending+[{'kind':'semantic-role-consumer-and-location-review','paths':[p for p,a in assets.items() if a['role']['status']=='pending']},
    {'kind':'historical-node-guards-crosswalk','guards':sorted({tag for f in guardfacts for tag in (f['declared_tags'] or [])}),'legacy_node_ids':[n['id'] for n in legacy['nodes']]}],
  'migrations':migrations,'previous_object_versions_retained':len(previous_objects),'qualification_added':False,'raw_history_or_discovery_embedded':False,'external_metadata_final_byte_binding':'input capture bytes do not authenticate later generated metadata bytes; verify actual final inputs'}
 write(out/'generation-report.json',report)
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 result=build(json.loads(args.config.read_text()),args.output);print(json.dumps({k:result[k] for k in ['objects','namespace_counts','historical_rows_read_and_bound','history_alignment_counts','role_counts']},indent=2))
