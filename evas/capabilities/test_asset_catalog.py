"""Catalog maintenance fixtures only; no scientific tests, simulator or network."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from registry import load,RegistryError,digest,reference

def write(root,path,value):
    target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(value));return target

def make_data(root):
    source=dict(schema_version=1,id='source:fixture',version='1',kind='source',status='active',origin='fixture-only',availability='repository-contained',locator={'kind':'embedded','value':{'data':'fixture'}},sha256=digest({'data':'fixture'}),dependencies=[])
    entry=dict(schema_version=1,id='entry:python',version='1',kind='entrypoint',status='active',namespace='python-regression',collector='unittest',start='evas/tests',pattern='test*.py',dependencies=[])
    asset=dict(schema_version=1,id='asset:stable',version='1',kind='asset',status='active',namespace='EVAS-assets',current_path='evas/tests/test_demo.py',content={'algorithm':'sha256','value':'a'*64},role={'status':'pending','reason':'fixture role not reviewed'},consumers=[reference(entry)],consumer_status='pending',location_history=[],dependencies=[reference(source)])
    method=dict(schema_version=1,id='method:stable',version='1',kind='method',status='active',namespace='python-regression',runtime_id='test_demo.Case.test_one',module=reference(asset),definition={'path':asset['current_path'],'sha256':'b'*64,'line':1,'name':'test_one'},generated=False,entrypoints=[reference(entry)],runtime_history=[],semantic_status='pending',dependencies=[reference(asset)])
    objects=[source,entry,asset,method]
    write(root,'registry.json',{'schema_version':1,'objects':[],'object_parts':['sources.json','entrypoints.json','assets.json','methods.json'],'current':{o['id']:o['version'] for o in objects}})
    for name,kind,rows in [('sources.json','sources',[source]),('entrypoints.json','entrypoints',[entry]),('assets.json','assets',[asset]),('methods.json','methods',[method])]:write(root,name,{'schema_version':1,'kind':kind,'objects':rows})
    write(root,'source-inventory.json',{'items':[]});write(root,'dispositions.json',{'items':[]});write(root,'boundary-audit.json',{'normalized_inventory_identity':digest([])});write(root,'target-scope.json',{});write(root,'language-profile.json',{'base':'2.4','selected_changes':[],'changes':{}})
    return objects

class CatalogIntegration(unittest.TestCase):
    def test_part_files_join_the_existing_Registry_current_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);objects=make_data(root)
            reg=load(root,root=root)
            self.assertEqual(set(reg.objects),{(o['id'],o['version']) for o in objects})
            self.assertEqual(reg.catalog().namespace_counts()['python-regression']['methods'],1)
            self.assertFalse(reg.qualified('method:stable'))
            self.assertFalse(reg.qualified('asset:stable'))

if __name__=='__main__':unittest.main()

class ReconcileBehaviors(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.objects = make_data(self.root)

    def reg(self):
        return load(self.root, root=self.root)

    def part(self, name, obj):
        write(self.root, name+'.json', {'schema_version': 1, 'kind': name, 'objects': [obj]})

    def observation(self):
        return {'path': 'evas/tests/test_demo.py', 'sha256': 'a'*64, 'git_mode': '100644', 'actual_mode': 420}

    def test_asset_exact_and_seed_external_detection(self):
        c=self.reg().catalog(); row=self.observation()
        self.assertTrue(c.reconcile_assets([row]))
        for rows in ([], [row,dict(row,path='scripts/new_outside_seed.py')], [row,row], [dict(row,sha256='c'*64)]):
            with self.assertRaises(ValueError): c.reconcile_assets(rows)

    def test_external_manifest_avoids_self_hash_cycle(self):
        asset=self.objects[2]
        asset['role']={'status':'confirmed','value':'catalog-meta','reason':'producer metadata definition'}
        asset['content']={'algorithm':'external-input-manifest','scope':'actual-execution-inputs','producer':'capabilities.observe-assets-v1'}
        self.part('assets',asset)
        method=self.objects[3];method['module']=reference(asset);method['dependencies']=[reference(asset)];self.part('methods',method)
        c=self.reg().catalog();row=self.observation()
        with self.assertRaises(ValueError): c.reconcile_assets([row])
        self.assertTrue(c.reconcile_assets([row],external_manifest={row['path']:row}))
        asset['content']={'algorithm':'sha256','value':'a'*64};self.part('assets',asset)
        with self.assertRaises(RegistryError): self.reg()

    def test_derived_support_paths_reject_self_hash_and_accept_external_manifest(self):
        for path in ('evas/capabilities/generated/support-facts.json','evas/capabilities/generated/support.md'):
            with self.subTest(path=path):
                asset=copy.deepcopy(self.objects[2])
                asset['current_path']=path
                asset['role']={'status':'confirmed','value':'derived','reason':'exact generated support view'}
                asset['content']={'algorithm':'sha256','value':'a'*64}
                self.part('assets',asset)
                method=copy.deepcopy(self.objects[3])
                method['definition']=dict(method['definition'],path=path)
                method['module']=reference(asset);method['dependencies']=[reference(asset)]
                self.part('methods',method)
                with self.assertRaises(RegistryError): self.reg()
                asset['content']={'algorithm':'external-input-manifest','scope':'actual-execution-inputs','producer':'capabilities.observe-assets-v1'}
                self.part('assets',asset)
                method['module']=reference(asset);method['dependencies']=[reference(asset)]
                self.part('methods',method)
                row={'path':path,'sha256':'d'*64,'git_mode':'100644','actual_mode':420}
                catalog=self.reg().catalog()
                with self.assertRaises(ValueError): catalog.reconcile_assets([row])
                self.assertTrue(catalog.reconcile_assets([row],external_manifest={path:row}))
                current=catalog.current('asset')[0]
                self.assertEqual(current['content']['algorithm'],'external-input-manifest')
                self.assertNotIn('value',current['content'])
                self.assertNotEqual(current.get('version'),row['sha256'])
                self.assertFalse(self.reg().qualified(asset['id']))

    def test_unknown_part_schema_and_second_current_rejected(self):
        for update in ({'schema_version':2},{'current':{}},{'kind':'qualifications'}):
            value={'schema_version':1,'kind':'assets','objects':[self.objects[2]]};value.update(update)
            write(self.root,'assets.json',value)
            with self.assertRaises(RegistryError): self.reg()

    def test_broken_content_bound_reference_rejected(self):
        method=copy.deepcopy(self.objects[3]);method['module']['sha256']='c'*64;self.part('methods',method)
        with self.assertRaises(RegistryError): self.reg()

    def test_namespace_and_factory_reconcile_exact(self):
        method=self.objects[3]
        row={'module_path':'evas/tests/test_demo.py','runtime_id':method['runtime_id'],
             'module_sha256':'a'*64,'definition':method['definition'],'generated':False}
        receipt={'schema_version':1,'namespace':'python-regression','complete':True,'errors':[],'methods':[row]}
        c=self.reg().catalog();self.assertTrue(c.reconcile_methods('python-regression',receipt))
        for changed in (dict(receipt,methods=[]),dict(receipt,methods=[row,row]),dict(receipt,errors=['import failed']),dict(receipt,complete=False),dict(receipt,namespace='maintenance'),dict(receipt,schema_version=2),dict(receipt,methods=[dict(row,generated=True)]),dict(receipt,methods=[dict(row,module_sha256='c'*64)])):
            with self.assertRaises(ValueError):c.reconcile_methods('python-regression',changed)
        maintenance=dict(receipt,namespace='maintenance',methods=[])
        self.assertTrue(c.reconcile_methods('maintenance',maintenance))

    def test_rename_requires_prior_version_and_preserves_identity(self):
        old=self.objects[2];new=copy.deepcopy(old);new['version']='2';new['current_path']='evas/tests/test_moved.py'
        write(self.root,'assets.json',{'schema_version':1,'kind':'assets','objects':[old,new]})
        data=json.loads((self.root/'registry.json').read_text());data['current'][old['id']]='2';write(self.root,'registry.json',data)
        with self.assertRaises(RegistryError):self.reg()
        new['location_history']=[{'prior_asset':reference(old),'reason':'reviewed move'}]
        write(self.root,'assets.json',{'schema_version':1,'kind':'assets','objects':[old,new]})
        reg=self.reg();self.assertEqual(reg.catalog().current('asset')[0]['id'],old['id'])
        self.assertIn((old['id'],'1'),reg.objects)

    def test_historical_module_mismatch_cannot_be_claimed_matched(self):
        row={'schema_version':1,'id':'audit:original','version':'1','kind':'historical-audit-record','status':'active',
          'source':reference(self.objects[0]),'row_pointer':'','scope_pointer':'','original_row_sha256':'a'*64,'scope_sha256':'b'*64,
          'identity_binding':'unbound','alignment':{'status':'matched'},'method':reference(self.objects[3]),
          'source_method_sha256':'b'*64,'source_module_sha256':'c'*64,'original_verdict':'no_defect_found','dependencies':[]}
        data=json.loads((self.root/'registry.json').read_text());data['object_parts'].append('history.json');data['current'][row['id']]='1';write(self.root,'registry.json',data)
        self.part('history',row)
        with self.assertRaises(RegistryError):self.reg()
        row['alignment']={'status':'pending','reason':'unbound historical fixture'};row.pop('method');row.pop('source_method_sha256');row.pop('source_module_sha256');self.part('history',row)
        reg=self.reg();self.assertFalse(reg.qualified(row['id']))
        self.assertEqual(reg.objects[(row['id'],'1')]['original_verdict'],'no_defect_found')

    def test_sources_are_data_and_pending_archives_are_unavailable(self):
        from source_reader import read_source,historical_row
        value={'verdict':'passed','scope':'historical fixture'}
        source=dict(self.objects[0],locator={'kind':'embedded','value':value},sha256=digest(value))
        self.assertEqual(historical_row(source,'',digest(value)),value)
        for changed in (dict(source,sha256='a'*64),dict(source,availability='pending',locator={'kind':'git-object','repository':'archive','revision':None,'path':'audit.json'}),dict(source,locator={'kind':'repository-relative','path':'../escape'})):
            with self.assertRaises(ValueError):read_source(changed,root=self.root)

    def test_traceability_uses_same_registry_without_qualification(self):
        import importlib.util
        path=Path(__file__).resolve().parents[2]/'scripts/traceability.py'
        spec=importlib.util.spec_from_file_location('traceability_preview',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        text=mod.render_catalog_navigation(self.reg())
        self.assertIn('python-regression: 1 registered methods',text)
        self.assertIn('Pending asset roles: 1',text)
        self.assertIn('No normative coverage',text)

class ActualDiscovery(unittest.TestCase):
    def test_factory_discovery_never_executes_test_body_and_import_failure_is_retained(self):
        import importlib.util
        path=Path(__file__).resolve().parents[2]/'scripts/capabilities/discover_methods.py'
        spec=importlib.util.spec_from_file_location('discovery_preview',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);tests=root/'checks';tests.mkdir()
            (tests/'test_factory.py').write_text('import unittest\ndef factory():\n def generated(self):\n  raise RuntimeError("BODY MUST NOT RUN")\n return generated\nclass Case(unittest.TestCase):\n test_generated = factory()\n def test_plain(self):\n  raise RuntimeError("BODY MUST NOT RUN")\n')
            receipt=mod.discover(root,'checks',namespace='maintenance')
            self.assertTrue(receipt['complete'],receipt['errors']);self.assertEqual(len(receipt['methods']),2)
            self.assertEqual(sum(r['generated'] for r in receipt['methods']),1)
            (tests/'test_broken.py').write_text('raise ImportError("fixture import failure")\n')
            failed=mod.discover(root,'checks',namespace='maintenance')
            self.assertFalse(failed['complete']);self.assertTrue(failed['errors']);self.assertEqual(len(failed['methods']),2)

class ObserverAndSourceSchemas(unittest.TestCase):
    def test_independent_observer_keeps_catalog_and_governance_paths_with_real_modes(self):
        import importlib.util
        from unittest.mock import patch
        path=Path(__file__).resolve().parents[2]/'scripts/capabilities/observe_assets.py'
        spec=importlib.util.spec_from_file_location('observer_preview',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            paths=['evas/capabilities/data/assets.json','evas/validation/baselines/regression-v1.json','scripts/new_seed_external.py']
            for name in paths:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(name)
            def git(args, **kwargs):
                if '--show-object-format' in args:return b'sha1\n'
                if '--show-toplevel' in args:return (str(root)+'\n').encode()
                if 'status' in args:return b''
                if 'ls-files' in args:
                    return b''.join(('100644 '+'a'*40+' 0\t'+name+'\0').encode() for name in paths)
                return ('b'*40+'\n').encode()
            with patch.object(mod.subprocess,'check_output',side_effect=git):receipt=mod.observe(root)
            self.assertEqual([r['path'] for r in receipt['assets']],paths)
            self.assertEqual(receipt['relation_to_ci_input_key'],'unproven-independent-observation')
            self.assertTrue(all('git_mode' in r and 'actual_mode' in r for r in receipt['assets']))

    def test_archive_pending_is_explicit_and_absolute_source_paths_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);objects=make_data(root);source=objects[0]
            source.update(availability='pending',locator={'kind':'pending-archive','repository':'validation-archive','revision':None,'path':'audit/result.json'})
            write(root,'sources.json',{'schema_version':1,'kind':'sources','objects':[source]})
            # Rebind dependencies after changing the source object; content pins are exact.
            asset=objects[2];asset['dependencies']=[reference(source)];write(root,'assets.json',{'schema_version':1,'kind':'assets','objects':[asset]})
            method=objects[3];method['module']=reference(asset);method['dependencies']=[reference(asset)];write(root,'methods.json',{'schema_version':1,'kind':'methods','objects':[method]})
            registry=load(root,root=root)
            with self.assertRaises(ValueError):registry.read_source(source)
            source['locator']={'kind':'repository-relative','path':'/private/absolute.json'};write(root,'sources.json',{'schema_version':1,'kind':'sources','objects':[source]})
            with self.assertRaises(RegistryError):load(root,root=root)

class SeparateRustAndHistoricalSource(unittest.TestCase):
    def test_rust_listing_has_its_own_actual_binary_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);objects=make_data(root)
            actual={'schema_version':1,'namespace':'rust-tests','complete':True,'errors':[],
                    'binary_sha256':'c'*64,'runtime_ids':['crate::one','crate::two']}
            source=dict(objects[0],id='source:rust-listing',locator={'kind':'embedded','value':actual},sha256=digest(actual))
            entry={'schema_version':1,'id':'entry:rust','version':'1','kind':'entrypoint','status':'active',
                   'namespace':'rust-tests','collector':'binary-listing','listing_source':reference(source),'dependencies':[reference(source)]}
            write(root,'sources.json',{'schema_version':1,'kind':'sources','objects':[objects[0],source]})
            write(root,'entrypoints.json',{'schema_version':1,'kind':'entrypoints','objects':[objects[1],entry]})
            data=json.loads((root/'registry.json').read_text());data['current'].update({source['id']:'1',entry['id']:'1'});write(root,'registry.json',data)
            c=load(root,root=root).catalog()
            self.assertEqual(c.reconcile_listing(reference(entry),actual),2)
            self.assertEqual(c.namespace_counts()['rust-tests']['methods'],0)
            for changed in (dict(actual,runtime_ids=['crate::one']),dict(actual,runtime_ids=['crate::one','crate::one']),dict(actual,binary_sha256='d'*64)):
                with self.assertRaises(ValueError):c.reconcile_listing(reference(entry),changed)

    def test_historical_row_scope_and_original_verdict_are_byte_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);objects=make_data(root)
            original={'scope':{'denominator':3257,'name':'fixture representation only'},'rows':[{'id':'test.original','verdict':'no_defect_found'}]}
            source=dict(objects[0],id='source:original',locator={'kind':'embedded','value':original},sha256=digest(original))
            history={'schema_version':1,'id':'history:original','version':'1','kind':'historical-audit-record','status':'active',
                'source':reference(source),'row_pointer':'/rows/0','scope_pointer':'/scope',
                'original_row_sha256':digest(original['rows'][0]),'scope_sha256':digest(original['scope']),
                'identity_binding':'unbound','alignment':{'status':'pending','reason':'fixture has no tested-module identity'},'dependencies':[reference(source)]}
            write(root,'sources.json',{'schema_version':1,'kind':'sources','objects':[objects[0],source]})
            write(root,'history.json',{'schema_version':1,'kind':'history','objects':[history]})
            data=json.loads((root/'registry.json').read_text());data['object_parts'].append('history.json');data['current'].update({source['id']:'1',history['id']:'1'});write(root,'registry.json',data)
            reg=load(root,root=root);c=reg.catalog()
            self.assertEqual(c.read_history(history),original['rows'][0]);self.assertFalse(reg.qualified(history['id']))
            with self.assertRaises(ValueError):c.read_history(dict(history,scope_sha256='c'*64))

class CurrentIdentityIndex(unittest.TestCase):
    """Rename boundaries already enforced by Catalog.validate.

    Outcomes are the existing error text and current selection. These cases
    also pass on the unindexed scan; they lock that observable result.
    """

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.objects = make_data(self.root)

    def reg(self):
        return load(self.root, root=self.root)

    def set_current(self, updates):
        data = json.loads((self.root / 'registry.json').read_text())
        data['current'].update(updates)
        write(self.root, 'registry.json', data)

    def test_asset_rename_without_prior_identity_keeps_rejection_text(self):
        old = self.objects[2]
        new = copy.deepcopy(old)
        new['version'] = '2'
        new['current_path'] = 'evas/tests/test_moved.py'
        write(self.root, 'assets.json', {'schema_version': 1, 'kind': 'assets', 'objects': [old, new]})
        self.set_current({old['id']: '2'})
        with self.assertRaises(RegistryError) as caught:
            self.reg()
        self.assertEqual(str(caught.exception), 'rename/move lost known historical identity')

    def test_asset_rename_with_prior_identity_keeps_current_version(self):
        old = self.objects[2]
        new = copy.deepcopy(old)
        new['version'] = '2'
        new['current_path'] = 'evas/tests/test_moved.py'
        new['location_history'] = [{'prior_asset': reference(old), 'reason': 'reviewed move'}]
        write(self.root, 'assets.json', {'schema_version': 1, 'kind': 'assets', 'objects': [old, new]})
        self.set_current({old['id']: '2'})
        reg = self.reg()
        current = reg.catalog().current('asset')
        self.assertEqual([(item['id'], item['version'], item['current_path']) for item in current],
                         [(old['id'], '2', 'evas/tests/test_moved.py')])
        self.assertEqual(reg.objects[(old['id'], '1')]['location_history'], [])

    def test_method_rename_without_and_with_prior_identity(self):
        old = self.objects[3]
        new = copy.deepcopy(old)
        new['version'] = '2'
        new['runtime_id'] = 'test_demo.Case.test_moved'
        write(self.root, 'methods.json', {'schema_version': 1, 'kind': 'methods', 'objects': [old, new]})
        self.set_current({old['id']: '2'})
        with self.assertRaises(RegistryError) as caught:
            self.reg()
        self.assertEqual(str(caught.exception), 'rename/move lost known historical identity')
        new['runtime_history'] = [{'prior_method': reference(old), 'reason': 'reviewed rename'}]
        write(self.root, 'methods.json', {'schema_version': 1, 'kind': 'methods', 'objects': [old, new]})
        reg = self.reg()
        current = reg.catalog().current('method')
        self.assertEqual([(item['id'], item['version'], item['runtime_id']) for item in current],
                         [(old['id'], '2', 'test_demo.Case.test_moved')])
        self.assertEqual(reg.objects[(old['id'], '1')]['runtime_history'], [])

    def test_multiple_old_asset_versions_keep_every_distinct_path(self):
        old = self.objects[2]
        middle = copy.deepcopy(old)
        middle['version'] = '2'
        middle['current_path'] = 'evas/tests/test_middle.py'
        current = copy.deepcopy(old)
        current['version'] = '3'
        current['current_path'] = 'evas/tests/test_current.py'
        current['location_history'] = [{'prior_asset': reference(middle), 'reason': 'covers only the middle path'}]
        write(self.root, 'assets.json', {'schema_version': 1, 'kind': 'assets', 'objects': [middle, old, current]})
        self.set_current({old['id']: '3'})
        with self.assertRaises(RegistryError) as caught:
            self.reg()
        self.assertEqual(str(caught.exception), 'rename/move lost known historical identity')
        current['location_history'] = [
            {'prior_asset': reference(middle), 'reason': 'middle path'},
            {'prior_asset': reference(old), 'reason': 'first path'}]
        write(self.root, 'assets.json', {'schema_version': 1, 'kind': 'assets', 'objects': [middle, old, current]})
        self.assertEqual(self.reg().catalog().current('asset')[0]['version'], '3')

    def test_multiple_old_method_versions_keep_every_distinct_runtime(self):
        old = self.objects[3]
        middle = copy.deepcopy(old)
        middle['version'] = '2'
        middle['runtime_id'] = 'test_demo.Case.test_middle'
        current = copy.deepcopy(old)
        current['version'] = '3'
        current['runtime_id'] = 'test_demo.Case.test_current'
        current['runtime_history'] = [{'prior_method': reference(middle), 'reason': 'covers only the middle id'}]
        write(self.root, 'methods.json', {'schema_version': 1, 'kind': 'methods', 'objects': [middle, old, current]})
        self.set_current({old['id']: '3'})
        with self.assertRaises(RegistryError) as caught:
            self.reg()
        self.assertEqual(str(caught.exception), 'rename/move lost known historical identity')
        current['runtime_history'] = [
            {'prior_method': reference(middle), 'reason': 'middle id'},
            {'prior_method': reference(old), 'reason': 'first id'}]
        write(self.root, 'methods.json', {'schema_version': 1, 'kind': 'methods', 'objects': [middle, old, current]})
        self.assertEqual(self.reg().catalog().current('method')[0]['runtime_id'], 'test_demo.Case.test_current')

    def test_unrelated_id_version_does_not_force_history(self):
        asset = self.objects[2]
        previous = copy.deepcopy(asset)
        previous['id'] = 'asset:unrelated'
        previous['version'] = '0'
        previous['current_path'] = 'evas/tests/test_other_old.py'
        other = copy.deepcopy(previous)
        other['version'] = '1'
        other['current_path'] = 'evas/tests/test_other.py'
        other['location_history'] = [{'prior_asset': reference(previous), 'reason': 'unrelated move'}]
        write(self.root, 'assets.json', {'schema_version': 1, 'kind': 'assets', 'objects': [asset, previous, other]})
        self.set_current({other['id']: '1'})
        paths = sorted(item['current_path'] for item in self.reg().catalog().current('asset'))
        self.assertEqual(paths, ['evas/tests/test_demo.py', 'evas/tests/test_other.py'])

    def test_history_on_noncurrent_asset_does_not_satisfy_current(self):
        prior = copy.deepcopy(self.objects[2])
        current = copy.deepcopy(self.objects[2])
        current['version'] = '2'
        current['current_path'] = 'evas/tests/test_moved.py'
        prior['location_history'] = [{'prior_asset': reference(current), 'reason': 'recorded only on the old version'}]
        method = copy.deepcopy(self.objects[3])
        method['module'] = reference(prior)
        method['dependencies'] = [reference(prior)]
        write(self.root, 'assets.json', {'schema_version': 1, 'kind': 'assets', 'objects': [prior, current]})
        write(self.root, 'methods.json', {'schema_version': 1, 'kind': 'methods', 'objects': [method]})
        self.set_current({prior['id']: '2'})
        with self.assertRaises(RegistryError) as caught:
            self.reg()
        self.assertEqual(str(caught.exception), 'rename/move lost known historical identity')

    def test_mismatched_history_digest_keeps_reference_rejection(self):
        old = self.objects[2]
        new = copy.deepcopy(old)
        new['version'] = '2'
        new['current_path'] = 'evas/tests/test_moved.py'
        stale = reference(old)
        stale['sha256'] = 'c' * 64
        new['location_history'] = [{'prior_asset': stale, 'reason': 'digest does not match the retained object'}]
        write(self.root, 'assets.json', {'schema_version': 1, 'kind': 'assets', 'objects': [old, new]})
        self.set_current({old['id']: '2'})
        with self.assertRaises(RegistryError) as caught:
            self.reg()
        self.assertEqual(str(caught.exception), 'missing, changed or wrong-kind catalogue reference')

    def test_same_catalog_revalidates_after_input_changes(self):
        old = self.objects[2]
        new = copy.deepcopy(old)
        new['version'] = '2'
        new['current_path'] = 'evas/tests/test_moved.py'
        new['location_history'] = [{'prior_asset': reference(old), 'reason': 'reviewed move'}]
        write(self.root, 'assets.json', {'schema_version': 1, 'kind': 'assets', 'objects': [old, new]})
        self.set_current({old['id']: '2'})
        reg = self.reg()
        catalog = reg.catalog()
        self.assertIsNone(catalog.validate())
        added = copy.deepcopy(old)
        added['version'] = '0'
        added['current_path'] = 'evas/tests/test_earlier.py'
        reg.objects[(added['id'], added['version'])] = added
        with self.assertRaises(ValueError) as caught:
            catalog.validate()
        self.assertEqual(str(caught.exception), 'rename/move lost known historical identity')
        del reg.objects[(added['id'], added['version'])]
        self.assertIsNone(catalog.validate())
        same = copy.deepcopy(reg.objects[(old['id'], '2')])
        same['version'] = '9'
        same['location_history'] = []
        reg.objects[(same['id'], same['version'])] = same
        self.assertIsNone(catalog.validate())
        same['current_path'] = 'evas/tests/test_mutated.py'
        with self.assertRaises(ValueError) as caught:
            catalog.validate()
        self.assertEqual(str(caught.exception), 'rename/move lost known historical identity')
        same['current_path'] = 'evas/tests/test_moved.py'
        self.assertIsNone(catalog.validate())

    def test_duplicate_and_unknown_identity_rejections_stay_after_the_scan(self):
        asset = copy.deepcopy(self.objects[2])
        other = copy.deepcopy(asset)
        other['id'] = 'asset:duplicate-path'
        write(self.root, 'assets.json', {'schema_version': 1, 'kind': 'assets', 'objects': [asset, other]})
        self.set_current({other['id']: '1'})
        with self.assertRaises(RegistryError) as caught:
            self.reg()
        self.assertEqual(str(caught.exception), 'duplicate current asset path')
        write(self.root, 'assets.json', {'schema_version': 1, 'kind': 'assets', 'objects': [self.objects[2]]})
        self.set_current({other['id']: None})
        data = json.loads((self.root / 'registry.json').read_text())
        del data['current'][other['id']]
        write(self.root, 'registry.json', data)
        method = copy.deepcopy(self.objects[3])
        duplicate = copy.deepcopy(method)
        duplicate['id'] = 'method:duplicate-runtime'
        write(self.root, 'methods.json', {'schema_version': 1, 'kind': 'methods', 'objects': [method, duplicate]})
        self.set_current({duplicate['id']: '1'})
        with self.assertRaises(RegistryError) as caught:
            self.reg()
        self.assertEqual(str(caught.exception), 'duplicate current runtime identity')
        changed = copy.deepcopy(self.objects[2])
        changed['content'] = {'algorithm': 'md5', 'value': 'a' * 64}
        rebound = copy.deepcopy(self.objects[3])
        rebound['module'] = reference(changed)
        rebound['dependencies'] = [reference(changed)]
        write(self.root, 'assets.json', {'schema_version': 1, 'kind': 'assets', 'objects': [changed]})
        write(self.root, 'methods.json', {'schema_version': 1, 'kind': 'methods', 'objects': [rebound]})
        data = json.loads((self.root / 'registry.json').read_text())
        del data['current'][duplicate['id']]
        write(self.root, 'registry.json', data)
        with self.assertRaises(RegistryError) as caught:
            self.reg()
        self.assertEqual(str(caught.exception), 'unknown content identity')
