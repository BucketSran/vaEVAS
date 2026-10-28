"""Real Git/CLI plumbing fixtures; stub harnesses are not native Rust science."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import git_fixture

ROOT = Path(__file__).resolve().parents[2]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

fixtures = module('rust_fixture', ROOT/'scripts/tests/test_discover_rust.py')
sys.path.insert(0, str(ROOT/'evas/capabilities'))
registry = module('registry_fixture', ROOT/'evas/capabilities/registry.py')
assets = module('asset_fixture', ROOT/'evas/capabilities/test_asset_catalog.py')
generator = module('rust_generator_fixture', ROOT/'scripts/capabilities/generate_catalog.py')

class RustCatalogReconciliation(unittest.TestCase):
    def setUp(self):
        self.fx = fixtures.RustListingTests('test_compiler_failure_terminal_missing_and_truncated_json_refused')
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        run, self.receipt = self.fx.run_helper()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.root = self.fx.repo
        self.data = self.root/'catalog'
        objects = assets.make_data(self.data)
        archive = self.root/'runs/archive'
        archive.mkdir()
        scratch = Path(self.fx.tmp.name)
        git_fixture.run(['init','-b','main',str(archive)],scratch=scratch,check=True,capture_output=True)
        (archive/'rust.json').write_text(json.dumps(self.receipt))
        self.archive = archive
        for args in [('add','.'),('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','stub receipt')]:
            git_fixture.run(['-C',str(archive),*args],scratch=scratch,check=True,capture_output=True)
        commit = git_fixture.run(['-C',str(archive),'rev-parse','HEAD'],scratch=scratch,
                                 check=True,capture_output=True,text=True).stdout.strip()
        source = dict(schema_version=1,id='source:rust',version='1',kind='source',status='active',
            availability='published-archive',origin='local fixture git archive; not published CI',
            locator=dict(kind='git-object',repository='receipt-archive',revision=commit,path='rust.json'),
            sha256=__import__('hashlib').sha256((archive/'rust.json').read_bytes()).hexdigest(),dependencies=[])
        self.source=source
        self.entries=[]
        for i,binary in enumerate(self.receipt['binaries']):
            self.entries.append(dict(schema_version=1,id='entry:rust:'+str(i),version='1',kind='entrypoint',status='active',
                namespace='rust-tests',collector='binary-listing',listing_profile='fixture-linux',
                rust_target={key:binary[key] for key in ('package','version','target_kind','name')},
                listing_source=registry.reference(source),dependencies=[registry.reference(source)]))
        self.originals=objects
        self.save()

    def save(self):
        assets.write(self.data,'sources.json',dict(schema_version=1,kind='sources',objects=[self.originals[0],self.source]))
        assets.write(self.data,'entrypoints.json',dict(schema_version=1,kind='entrypoints',objects=[self.originals[1],*self.entries]))
        data=json.loads((self.data/'registry.json').read_text())
        data['current']={o['id']:o['version'] for o in [*self.originals,self.source,*self.entries]}
        assets.write(self.data,'registry.json',data)

    def catalog(self):
        return registry.load(self.data,root=self.root,repositories={'receipt-archive':self.archive}).catalog()

    def require(self, receipt=None, profile='fixture-linux'):
        return self.catalog().reconcile_rust_listing(receipt or self.receipt, profile=profile)

    def test_complete_qualified_denominator_preserves_both_actual_hashes(self):
        receipt=copy.deepcopy(self.receipt)
        receipt['binaries'][0]['binary_sha256']='d'*64
        facts=self.require(receipt)
        self.assertEqual(facts['tests_discovered'],3)
        self.assertEqual(facts['ignored_tests_discovered'],1)
        self.assertFalse(facts['binaries'][0]['binary_sha256_equal'])
        self.assertEqual(facts['binaries'][0]['actual_binary_sha256'],'d'*64)
        self.assertTrue(facts['listing_only'])

    def test_missing_extra_duplicate_target_and_unknown_profile_fail_closed(self):
        for change in ('missing','extra','duplicate','profile'):
            with self.subTest(change=change):
                receipt=copy.deepcopy(self.receipt)
                if change=='missing':
                    receipt['binaries'].pop()
                    receipt['tests']=[r for r in receipt['tests'] if r['binary_index']==0]
                    receipt['tests_discovered']=2
                if change=='extra':receipt['binaries'][0]['name']='unknown'
                if change=='duplicate':receipt['binaries'].append(receipt['binaries'][0])
                with self.assertRaises(ValueError):self.require(receipt,profile='unknown' if change=='profile' else 'fixture-linux')
        self.entries.pop();self.save()
        with self.assertRaises(ValueError):self.require()

    def test_source_toolchain_profile_ids_and_ignored_drift_refused(self):
        for change in ('source','tool','profile','target','id','ignored','count','index','incomplete','unknown'):
            with self.subTest(change=change):
                r=copy.deepcopy(self.receipt)
                if change=='source':r['source']['files'][0]['sha256']='f'*64
                if change=='tool':
                    r['toolchain']['rustc']['stdout']+='changed'
                    r['toolchain']['rustc']['stdout_sha256']=__import__('hashlib').sha256(r['toolchain']['rustc']['stdout'].encode()).hexdigest()
                if change=='profile':r['binaries'][0]['cargo_profile']['opt_level']='2'
                if change=='target':r['binaries'][0]['src_sha256']='f'*64
                if change=='id':r['tests'][0]['local_id']='new'
                if change=='ignored':
                    row=r['tests'][0];delta=-1 if row['ignored'] else 1
                    row['ignored']=not row['ignored']
                    r['ignored_tests_discovered']+=delta
                    r['binaries'][row['binary_index']]['ignored_tests_discovered']+=delta
                if change=='count':r['tests_discovered']=904
                if change=='index':r['tests'][0]['binary_index']=True
                if change=='incomplete':r['binaries'][0]['listing_complete']=False
                if change=='unknown':r['schema_version']=2
                with self.assertRaises(ValueError):self.require(r)

    def test_unavailable_unpublished_source_and_duplicate_registration_refused(self):
        self.entries.append(dict(self.entries[0],id='entry:duplicate'));self.save()
        with self.assertRaises(ValueError):self.require()
        self.entries.pop()
        self.source.update(availability='repository-contained',locator=dict(kind='embedded',value=self.receipt),sha256=registry.digest(self.receipt))
        for entry in self.entries:entry.update(listing_source=registry.reference(self.source),dependencies=[registry.reference(self.source)])
        self.save()
        with self.assertRaises(ValueError):self.require()

    def test_cli_opt_in_retains_observation_on_requirement_failure(self):
        argv=[sys.executable,'-B',str(fixtures.HELPER),'--repo',str(self.root),
              '--build-messages',str(self.fx.build),'--build-exit','0','--report',str(self.fx.report),
              '--raw-directory',str(self.fx.raw),'--require-catalog',str(self.data),
              '--listing-profile','fixture-linux','--source-repository','receipt-archive='+str(self.archive)]
        good=subprocess.run(argv,env=self.fx.env,capture_output=True,text=True)
        self.assertEqual(good.returncode,0,good.stderr)
        payload=json.loads(self.fx.report.read_text());self.assertTrue(payload['catalog_reconciliation']['reconciled'])
        bad=subprocess.run([*argv[:-3],'unknown',*argv[-2:]],env=self.fx.env,capture_output=True,text=True)
        self.assertNotEqual(bad.returncode,0)
        payload=json.loads(self.fx.report.read_text())
        self.assertTrue(payload['complete'])
        self.assertFalse(payload['catalog_reconciliation']['reconciled'])
        self.assertEqual(payload['tests_discovered'],3)

    def on_platform(self,receipt,platform):
        receipt=copy.deepcopy(receipt);receipt['environment'].update(platform=platform,machine='x86_64')
        return receipt

    def register(self,receipt):
        # Indented bytes keep the commit nonempty when the runner already reports this platform.
        scratch=Path(self.fx.tmp.name);(self.archive/'rust.json').write_text(json.dumps(receipt,indent=1))
        for args in [('add','.'),('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Linux receipt')]:
            git_fixture.run(['-C',str(self.archive),*args],scratch=scratch,check=True,capture_output=True)
        commit=git_fixture.run(['-C',str(self.archive),'rev-parse','HEAD'],scratch=scratch,check=True,capture_output=True,text=True).stdout.strip()
        self.source.update(locator=dict(self.source['locator'],revision=commit),
                           sha256=__import__('hashlib').sha256((self.archive/'rust.json').read_bytes()).hexdigest())
        for entry in self.entries:entry.update(listing_source=registry.reference(self.source),dependencies=[registry.reference(self.source)])
        self.save()

    def test_runner_image_may_change_only_the_kernel_release(self):
        self.register(self.on_platform(self.receipt,'Linux-6.17.0-1022-azure-x86_64-with-glibc2.39'))
        facts=self.require(self.on_platform(self.receipt,'Linux-7.0.0-1017-azure-x86_64-with-glibc2.39'))
        self.assertTrue(facts['reconciled'])
        self.assertEqual(facts['host_platform_difference'],dict(
            expected_platform='Linux-6.17.0-1022-azure-x86_64-with-glibc2.39',
            actual_platform='Linux-7.0.0-1017-azure-x86_64-with-glibc2.39'))
        self.assertNotIn('host_platform_difference',self.require(self.on_platform(self.receipt,'Linux-6.17.0-1022-azure-x86_64-with-glibc2.39')))
        for platform in ('Linux-7.0.0-1017-azure-x86_64-with-glibc2.40','Linux-7.0.0-1017-azure-aarch64-with-glibc2.39',
                         'Darwin-7.0.0-x86_64-with-glibc2.39'):
            with self.subTest(platform=platform):
                with self.assertRaisesRegex(ValueError,'profile drift'):self.require(self.on_platform(self.receipt,platform))
        changed=self.on_platform(self.receipt,'Linux-7.0.0-1017-azure-x86_64-with-glibc2.39')
        changed['environment']['variables']=dict(changed['environment']['variables'],RUSTFLAGS='-Copt-level=3')
        with self.assertRaisesRegex(ValueError,'profile drift'):self.require(changed)

    def legacy(self, **tools):
        receipt=copy.deepcopy(self.receipt)
        for name,argv in tools.items():receipt['toolchain'][name]['argv']=argv
        return receipt

    STABLE=dict(rustc=['rustc','+stable','-vV'],cargo=['cargo','+stable','--version'])

    def test_legacy_stable_receipt_still_reconciles_and_other_toolchain_requests_fail(self):
        # An archived pre-pin receipt is read back from its bound immutable source; the new observation has no channel.
        self.register(self.legacy(**self.STABLE))
        self.assertTrue(self.require()['reconciled'])
        for argv in (['rustc','+nightly','-vV'],['rustc','+1.99.1','-vV'],['rustc','--version'],['rustc','-vV','--verbose']):
            with self.subTest(argv=argv):
                with self.assertRaisesRegex(ValueError,'toolchain identity'):self.require(self.legacy(rustc=argv))

    def test_current_observation_rejects_the_stable_channel_for_either_or_both_tools(self):
        variants=dict(rustc=dict(rustc=self.STABLE['rustc']),cargo=dict(cargo=self.STABLE['cargo']),both=self.STABLE)
        for registered in ('new','legacy'):
            if registered=='legacy':self.register(self.legacy(**self.STABLE))
            self.assertTrue(self.require()['reconciled'])
            for name,tools in variants.items():
                with self.subTest(registered=registered,variant=name):
                    with self.assertRaisesRegex(ValueError,'toolchain identity'):self.require(self.legacy(**tools))

    def test_historical_allowance_is_for_bound_receipts_only(self):
        listing=module('listing_fixture',ROOT/'evas/capabilities/rust_listing.py')
        stable=self.legacy(**self.STABLE)
        self.assertTrue(listing.checked(self.receipt))
        self.assertTrue(listing.checked(stable,historical=True))
        for receipt in (stable,self.legacy(rustc=self.STABLE['rustc']),self.legacy(cargo=self.STABLE['cargo'])):
            with self.assertRaisesRegex(ValueError,'toolchain identity'):listing.checked(receipt)
        for argv in (['rustc','+nightly','-vV'],['rustc','+1.99.1','-vV'],['rustc','-vV','--verbose'],['rustc','--version']):
            with self.assertRaisesRegex(ValueError,'toolchain identity'):listing.checked(self.legacy(rustc=argv),historical=True)
        # A bound receipt carrying any other channel is refused as the expected side too.
        self.register(self.legacy(rustc=['rustc','+nightly','-vV']))
        with self.assertRaisesRegex(ValueError,'toolchain identity'):self.require()

    def test_generator_applies_the_strict_rules_to_every_new_registration(self):
        # A new actual observation is checked on read, with or without a published source locator.
        locator=dict(kind='git-object',repository='vaevas',revision='0'*40,path='evas/capabilities/observations/rust.json')
        scratch=Path(self.fx.tmp.name)
        def item(name,receipt,published):
            path=scratch/(name+'.json');path.write_text(json.dumps(receipt))
            value=dict(receipt_file=str(path),profile='fixture-linux')
            if published:value['source_locator']=locator
            return value
        for published in (False,True):
            path,raw,profile=generator.read_rust_listing(ROOT,item('good-'+str(published),self.receipt,published))
            self.assertEqual((raw,profile),(self.receipt,'fixture-linux'))
            for name,tools in dict(rustc=dict(rustc=self.STABLE['rustc']),cargo=dict(cargo=self.STABLE['cargo']),both=self.STABLE).items():
                with self.subTest(published=published,stable=name):
                    with self.assertRaisesRegex(ValueError,'toolchain identity'):
                        generator.read_rust_listing(ROOT,item(name+str(published),self.legacy(**tools),published))
            for argv in (['rustc','+nightly','-vV'],['rustc','--version']):
                with self.subTest(published=published,argv=argv):
                    with self.assertRaisesRegex(ValueError,'toolchain identity'):
                        generator.read_rust_listing(ROOT,item('other'+str(published),self.legacy(rustc=argv),published))
            broken=copy.deepcopy(self.receipt);del broken['toolchain']['cargo']
            with self.assertRaisesRegex(ValueError,'incomplete or unknown actual Rust listing structure'):
                generator.read_rust_listing(ROOT,item('broken'+str(published),broken,published))
            with self.assertRaisesRegex(ValueError,'incomplete/unknown actual Rust listing'):
                generator.read_rust_listing(ROOT,item('incomplete'+str(published),dict(self.receipt,complete=False),published))
        # The read happens for every listing before the source is built; publication only picks reconciliation.
        build=next(node for node in ast.parse((ROOT/'scripts/capabilities/generate_catalog.py').read_text()).body
                   if isinstance(node,ast.FunctionDef) and node.name=='build')
        loop=next(node for node in build.body if isinstance(node,ast.For) and isinstance(node.iter,ast.Call)
                  and ast.unparse(node.iter)=="config.get('rust_listings', [])")
        reader=loop.body[0]
        self.assertIsInstance(reader,ast.Assign)
        self.assertEqual(ast.unparse(reader.value),'read_rust_listing(root, item)')
        self.assertNotIn('source_locator',ast.unparse(reader))
        self.assertNotIn('published-archive',ast.unparse(reader))

if __name__=='__main__':unittest.main()
