"""Component ownership is an explicit scope; observations retain every tracked row."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from registry import load, RegistryError, reference
from test_asset_catalog import make_data, write

def policy():
    return {'schema_version':1,'id':'EVAS-scope-v1','owner':'evas',
        'included_prefixes':['.agents/','.github/','docs/','evas/','experiments/','scripts/'],
        'root_files':'included','external_components':[{'prefix':'benchmark/','owner':'benchmark'}],
        'bridges':[]}

def row(path,sha='a'*64):
    return {'path':path,'sha256':sha,'git_mode':'100644','actual_mode':420}

class AssetScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.objects=make_data(self.root)
        self.data=json.loads((self.root/'registry.json').read_text())

    def catalog(self,scope=True):
        if scope:self.data['asset_scope']=policy()
        write(self.root,'registry.json',self.data)
        return load(self.root,root=self.root).catalog()

    def test_legacy_without_scope_remains_all_tracked_strict(self):
        c=self.catalog(False)
        with self.assertRaises(ValueError):c.reconcile_assets([row('evas/tests/test_demo.py'),row('benchmark/task.py')])
        self.assertEqual(c.partition_assets([row('benchmark/task.py')])['scope_id'],'legacy-all-tracked-v1')

    def test_external_benchmark_owner_is_counted_without_becoming_evas_coverage(self):
        observations=[row('evas/tests/test_demo.py'),row('benchmark/task.py'),row('benchmark/data.txt')]
        c=self.catalog();report=c.reconcile_assets(observations)
        self.assertTrue(report['ok']);self.assertEqual(report['observed_total'],3)
        self.assertEqual(report['in_scope_count'],1)
        self.assertEqual(report['external_owners']['benchmark']['count'],2)
        self.assertEqual(len(observations),3)

    def test_new_inscope_and_root_source_are_extra_while_unknown_prefix_is_unowned(self):
        c=self.catalog()
        for path in ('scripts/new.py','new_root.py','.new-root-dotfile'):
            with self.assertRaises(ValueError) as caught:c.reconcile_assets([row('evas/tests/test_demo.py'),row(path)])
            self.assertIn(path,caught.exception.report['extra'])
        rows=[row('evas/tests/test_demo.py'),row('new_component/new.py')]
        part=c.partition_assets(rows)
        self.assertEqual(part['unknown'],['new_component/new.py'])
        with self.assertRaises(ValueError) as caught:c.reconcile_assets(rows)
        self.assertEqual(caught.exception.report['unknown'],['new_component/new.py'])

    def test_catalog_cannot_register_outscope_benchmark_without_bridge(self):
        asset=copy.deepcopy(self.objects[2]);asset.update(id='asset:benchmark',current_path='benchmark/task.py')
        write(self.root,'assets.json',{'schema_version':1,'kind':'assets','objects':[self.objects[2],asset]})
        self.data['current'][asset['id']]='1'
        with self.assertRaises(RegistryError):self.catalog()

    def bridge(self):
        asset=copy.deepcopy(self.objects[2]);asset.update(id='asset:bridge',current_path='benchmark/shared.py',consumer_status='partial')
        write(self.root,'assets.json',{'schema_version':1,'kind':'assets','objects':[self.objects[2],asset]})
        self.data['current'][asset['id']]='1'
        p=policy();p['bridges']=[{'path':'benchmark/shared.py','owner':'benchmark','reason':'fixture explicit cross-component edge only',
            'source':reference(self.objects[0]),'consumers':[reference(self.objects[1])]}]
        self.data['asset_scope']=p
        write(self.root,'registry.json',self.data)
        return asset,p

    def test_exact_source_bound_bridge_has_separate_boundary_denominator(self):
        self.bridge();c=load(self.root,root=self.root).catalog()
        rows=[row('evas/tests/test_demo.py'),row('benchmark/shared.py'),row('benchmark/unrelated.py')]
        report=c.reconcile_assets(rows)
        self.assertEqual(report['bridge_count'],1);self.assertEqual(report['in_scope_count'],2)
        self.assertEqual(report['external_owners']['benchmark']['paths'],['benchmark/unrelated.py'])
        self.assertEqual(report['bridge_paths'],['benchmark/shared.py'])
        with self.assertRaises(ValueError) as caught:c.reconcile_assets(rows[:1])
        self.assertIn('benchmark/shared.py',caught.exception.report['missing'])

    def test_bridge_requires_source_bound_partial_consumers_and_exact_external_path(self):
        asset,p=self.bridge()
        for mutation in ('complete','unbound-source','empty-consumers','unknown-prefix','duplicate'):
            broken=copy.deepcopy(p);changed=copy.deepcopy(asset)
            if mutation=='complete':changed['consumer_status']='complete'
            elif mutation=='unbound-source':broken['bridges'][0]['source']['sha256']='c'*64
            elif mutation=='empty-consumers':broken['bridges'][0]['consumers']=[]
            elif mutation=='unknown-prefix':broken['bridges'][0]['path']='other/shared.py'
            else:broken['bridges'].append(copy.deepcopy(broken['bridges'][0]))
            self.data['asset_scope']=broken;write(self.root,'registry.json',self.data)
            write(self.root,'assets.json',{'schema_version':1,'kind':'assets','objects':[self.objects[2],changed]})
            with self.assertRaises(RegistryError):load(self.root,root=self.root)

    def test_scope_schema_is_closed_and_versioned(self):
        for key,value in [('schema_version',2),('id','EVAS-scope-v2'),('included_prefixes',['evas/']),('root_files','excluded'),('external_components',[{'prefix':'benchmark/','owner':'evas'}]),('extra_exclusions',['scripts/'])]:
            broken=policy();broken[key]=value;self.data['asset_scope']=broken;write(self.root,'registry.json',self.data)
            with self.assertRaises(RegistryError):load(self.root,root=self.root)

    def test_outscope_duplicates_and_invalid_paths_are_not_silently_dropped(self):
        c=self.catalog()
        for rows in ([row('benchmark/same'),row('benchmark/same')],[row('../benchmark/task.py')]):
            with self.assertRaises(ValueError):c.partition_assets(rows)

    def test_cli_returns_machine_readable_owner_boundary_on_success_and_unknown_rejection(self):
        import shutil
        import subprocess
        import sys
        code=Path(__file__).resolve().parent
        for name in ('registry.py','asset_catalog.py','asset_scope.py','source_reader.py'):
            destination=self.root/'evas/capabilities'/name;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(code/name,destination)
        self.catalog()
        observer=self.root/'observation.json'
        receipt={'schema_version':1,'producer':'capabilities.observe-assets-v1',
            'scope':{'kind':'all-tracked-regular-checkout-files','untracked':'excluded-explicitly'},
            'assets':[row('evas/tests/test_demo.py'),row('benchmark/external.py')]}
        command=[sys.executable,'-B',str(code.parents[1]/'scripts/capabilities/reconcile.py'),
                 '--root',str(self.root),'--registry-data',str(self.root),'--assets',str(observer)]
        for path,exit_code in [(None,0),('unowned/new.py',1)]:
            value=copy.deepcopy(receipt)
            if path:value['assets'].append(row(path))
            observer.write_text(json.dumps(value))
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,exit_code,result.stderr)
            actual=json.loads(result.stdout)
            self.assertEqual(actual['reconciled'],exit_code==0)
            self.assertEqual(actual['assets']['external_owners']['benchmark']['count'],1)
            self.assertEqual(actual['assets']['unknown'],[path] if path else [])
