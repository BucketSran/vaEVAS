"""Synthetic integration identities exercise refresh without any backend launch."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import records
from records import ROOT, load, sha, validate, render
from freeze import SELECTED, freeze, save


class RefreshControls(unittest.TestCase):
    def setUp(self):
        directory=ROOT/'runs/cmp-refresh-controls'
        directory.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name)
        self.old=self.work/'old-inputs';freeze(self.old)
        self.new=self.work/'new-inputs';shutil.copytree(self.old,self.new)
        provenance=load(self.new/'provenance.json');provenance['evas_runtime_identity']='synthetic-new-runtime'
        (self.new/'provenance.json').write_text(json.dumps(provenance))
        manifest=load(self.new/'INPUT_MANIFEST.json')
        manifest['provenance.json']={'sha256':sha(self.new/'provenance.json'),'bytes':(self.new/'provenance.json').stat().st_size}
        (self.new/'INPUT_MANIFEST.json').write_text(json.dumps(manifest))
        original=load(ROOT/'experiments/backends/comparison/snapshot-20261006-accounted-v2.json')
        self.parent=copy.deepcopy(original);self.parent.pop('derivation',None)
        self.fresh=copy.deepcopy(self.parent)
        self.fresh['targets']['evas']={'revision':'f'*40,'runtime_identity':'synthetic-new-runtime'}
        for data,label,inputs in [(self.parent,'parent',self.old),(self.fresh,'fresh',self.new)]:
            for row in data['records']:
                if row['dataset']!='cmp8-base':continue
                if label=='fresh' and row['backend']!='evas':
                    row.update(accounting='unrun',verdict='T',stage='launch',reason='synthetic no launch',measurement=None,metrics={},evidence=[])
                    row.pop('execution_receipt',None)
                    continue
                if row['backend'] not in ('evas','spectre'):continue
                receipt=load(ROOT/row['execution_receipt']['path'])
                receipt['input_manifest_sha256']=sha(inputs/'INPUT_MANIFEST.json')
                receipt['checker_identity']=load(inputs/'provenance.json')['checker_identity']
                row['checker_identity']=receipt['checker_identity']
                if label=='fresh':
                    receipt.update(source_revision='f'*40,runtime_identity='synthetic-new-runtime',kernel_sha256='synthetic-new-kernel',run_id='synthetic-refresh')
                    row['measurement'].update(revision='f'*40,runtime_identity='synthetic-new-runtime',kernel_sha256='synthetic-new-kernel',run_id='synthetic-refresh')
                p=self.work/(label+'-'+row['backend']+'-'+row['case']+'-receipt.json');save(p,receipt)
                ref={'path':str(p.relative_to(ROOT)),'sha256':sha(p)}
                row['execution_receipt']=ref
                row['evidence']=[e for e in row['evidence'] if e['kind']!='receipt']+[dict(ref,kind='receipt')]
        self.parent_path=self.work/'parent.json';save(self.parent_path,self.parent)
        self.fresh_path=self.work/'fresh.json';save(self.fresh_path,self.fresh)
        validate(self.parent);validate(self.fresh)
        self.before={p:sha(p) for p in (ROOT/'experiments/backends/comparison').rglob('*.json')}

    def test_named_receipt_reuse_is_a_valid_refresh_observation(self):
        # Assemble an expected refresh directly, before invoking the producer.
        result=copy.deepcopy(self.parent)
        result['targets']['evas']=copy.deepcopy(self.fresh['targets']['evas'])
        fresh={(r['dataset'],r['case'],r['backend'],r['profile']):r for r in self.fresh['records']}
        for index,row in enumerate(result['records']):
            if row['dataset']!='cmp8-base':continue
            if row['backend']=='evas':
                result['records'][index]=copy.deepcopy(fresh[tuple(row[k] for k in ('dataset','case','backend','profile'))])
            elif row['backend']=='spectre':
                row.update(accounting='reused',reuse_justification='Original Spectre receipt retained; physical inputs, checker and runtime match the refreshed target.')
        ref=lambda p:{'path':str(p.relative_to(ROOT)),'sha256':sha(p)}
        result['refresh']={'parent':ref(self.parent_path),'fresh':ref(self.fresh_path),
            'old_manifest':ref(self.old/'INPUT_MANIFEST.json'),'new_manifest':ref(self.new/'INPUT_MANIFEST.json'),
            'old_provenance':ref(self.old/'provenance.json'),'new_provenance':ref(self.new/'provenance.json')}
        validate(result)

    def make(self):
        from refresh import refresh
        return refresh(self.parent_path,self.fresh_path,self.old,self.new,self.work/'proof')

    def test_new_receipt_reuse_and_current_evas_render_and_derive(self):
        from derive import derive
        result=self.make();validate(result)
        rows=[r for r in result['records'] if r['dataset']=='cmp8-base']
        self.assertEqual({b:sum(r['backend']==b for r in rows) for b in records.BACKENDS},{b:8 for b in records.BACKENDS})
        for row in rows:
            self.assertEqual(row['accounting'],{'evas':'executed','spectre':'reused','gnucap':'unrun','openvaf_ngspice':'unrun'}[row['backend']])
            if row['backend']=='evas':self.assertEqual(records.freshness(row,result['targets']),'current')
        self.assertIn('current; reused',render(result))
        output=self.work/'refreshed.json';save(output,result)
        derived=derive(output);validate(derived)
        self.assertEqual(result['records'],derived['records'])
        self.assertEqual(self.before,{p:sha(p) for p in self.before})

    def rebind_fresh_manifest(self):
        # Update the coherent synthetic new receipt hashes so the physical-byte
        # guard, rather than a stale manifest hash, must catch the fault.
        for row in self.fresh['records']:
            if row['dataset']!='cmp8-base' or row['backend']!='evas':continue
            path=ROOT/row['execution_receipt']['path']
            receipt=load(path);receipt['input_manifest_sha256']=sha(self.new/'INPUT_MANIFEST.json')
            path.write_text(json.dumps(receipt))
            ref={'path':str(path.relative_to(ROOT)),'sha256':sha(path)}
            row['execution_receipt']=ref
            row['evidence']=[e for e in row['evidence'] if e['kind']!='receipt']+[dict(ref,kind='receipt')]
        self.fresh_path.write_text(json.dumps(self.fresh))

    def test_physical_deck_request_source_and_condition_changes_are_rejected(self):
        for name in ['tb.scs','requested_settings.json','dut.va','condition.json']:
            with self.subTest(name=name):
                path=self.new/'runs/spectre'/SELECTED[0]/'base'/name
                original=path.read_bytes();manifest=load(self.new/'INPUT_MANIFEST.json')
                path.write_bytes(original+b'\nchanged')
                manifest[str(path.relative_to(self.new))]={'sha256':sha(path),'bytes':path.stat().st_size}
                (self.new/'INPUT_MANIFEST.json').write_text(json.dumps(manifest))
                self.rebind_fresh_manifest()
                with self.assertRaisesRegex(ValueError,'Spectre reuse changed physical input'):self.make()
                path.write_bytes(original)
                manifest[str(path.relative_to(self.new))]={'sha256':sha(path),'bytes':path.stat().st_size}
                (self.new/'INPUT_MANIFEST.json').write_text(json.dumps(manifest))
                self.rebind_fresh_manifest()

    def test_checker_drift_and_manifest_tampering_are_rejected(self):
        provenance=load(self.new/'provenance.json');provenance['checker_identity']='different-checker'
        (self.new/'provenance.json').write_text(json.dumps(provenance))
        manifest=load(self.new/'INPUT_MANIFEST.json');manifest['provenance.json']['sha256']=sha(self.new/'provenance.json')
        manifest['provenance.json']['bytes']=(self.new/'provenance.json').stat().st_size
        (self.new/'INPUT_MANIFEST.json').write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):self.make()

    def test_refreshed_snapshot_mutations_fail_full_validation(self):
        original=self.make()
        mutations=[('missing row',lambda d:d['records'].pop()),
                   ('duplicate',lambda d:d['records'].append(copy.deepcopy(d['records'][-1]))),
                   ('false reuse',lambda d:next(r for r in d['records'] if r['dataset']=='cmp8-base' and r['backend']=='spectre').update(measurement={'revision':'f'*40,'runtime_identity':'different','run_id':'wrong'})),
                   ('wrong metric',lambda d:next(r for r in d['records'] if r['dataset']=='cmp8-base' and r['backend']=='spectre' and r['case']=='v1-main')['metrics']['voltage'][0].update(observed=.9)),
                   ('false T observation',lambda d:next(r for r in d['records'] if r['dataset']=='cmp8-base' and r['backend']=='gnucap').update(accounting='reused',verdict='P')),
                   ('missing reuse source',lambda d:d.pop('refresh')),
                   ('wrong target',lambda d:d['targets']['evas'].update(runtime_identity='old-runtime'))]
        for label,mutate in mutations:
            with self.subTest(label=label):
                data=copy.deepcopy(original);mutate(data)
                with self.assertRaises(ValueError):validate(data)

    def test_parent_and_fresh_exact_configuration_boundaries(self):
        for label in ['duplicate','external observed','old evas']:
            with self.subTest(label=label):
                fresh=copy.deepcopy(self.fresh)
                if label=='duplicate':fresh['records'].append(copy.deepcopy(fresh['records'][-1]))
                elif label=='external observed':
                    row=next(r for r in fresh['records'] if r['dataset']=='cmp8-base' and r['backend']=='spectre')
                    old=next(r for r in self.parent['records'] if tuple(r[k] for k in ('dataset','backend','case','profile'))==tuple(row[k] for k in ('dataset','backend','case','profile')))
                    row.update(copy.deepcopy(old))
                else:
                    fresh['targets']['evas']=copy.deepcopy(self.parent['targets']['evas'])
                    for row in fresh['records']:
                        if row['dataset']=='cmp8-base' and row['backend']=='evas':
                            row.update(copy.deepcopy(next(r for r in self.parent['records'] if r['dataset']=='cmp8-base' and r['backend']=='evas' and r['case']==row['case'])))
                self.fresh_path.write_text(json.dumps(fresh))
                with self.assertRaises(ValueError):self.make()
                self.fresh_path.write_text(json.dumps(self.fresh))

    def test_archived_manifest_and_receipt_run_id_cannot_drift(self):
        result=self.make()
        path=ROOT/result['refresh']['old_manifest']['path']
        content=path.read_bytes();path.write_bytes(content+b' ')
        with self.assertRaises(ValueError):validate(result)
        path.write_bytes(content)
        spectre=next(r for r in result['records'] if r['dataset']=='cmp8-base' and r['backend']=='spectre')
        spectre['measurement']['run_id']='different-run'
        with self.assertRaises(ValueError):validate(result)

    def test_mixed_new_execution_identity_and_failed_grade_boundaries(self):
        fresh=copy.deepcopy(self.fresh)
        row=next(r for r in fresh['records'] if r['dataset']=='cmp8-base' and r['backend']=='evas')
        receipt=load(ROOT/row['execution_receipt']['path']);receipt['run_id']='another-synthetic-run'
        p=self.work/'mixed-receipt.json';save(p,receipt)
        row['measurement']['run_id']=receipt['run_id']
        ref={'path':str(p.relative_to(ROOT)),'sha256':sha(p)}
        row['execution_receipt']=ref
        row['evidence']=[e for e in row['evidence'] if e['kind']!='receipt']+[dict(ref,kind='receipt')]
        self.fresh_path.write_text(json.dumps(fresh))
        validate(fresh)
        with self.assertRaises(ValueError):self.make()
        # A synthetic timeout receipt remains X within the same eight-case batch.
        fresh=copy.deepcopy(self.fresh)
        row=next(r for r in fresh['records'] if r['dataset']=='cmp8-base' and r['backend']=='evas' and r['case']=='v1-main')
        receipt=load(ROOT/row['execution_receipt']['path'])
        obs=self.work/'failed-observation.json';save(obs,{'status':'timeout','formal_dvs_qualification':'I'})
        obsref={'path':str(obs.relative_to(ROOT)),'sha256':sha(obs)}
        receipt.update(observation=obsref,execution_status='timeout',waveform_sha256=None,effective_settings=None)
        receipt['commands'][0].update(exit_code=-9,timed_out=True)
        p=self.work/'failed-receipt.json';save(p,receipt);ref={'path':str(p.relative_to(ROOT)),'sha256':sha(p)}
        row.update(verdict='X',reason='timeout',stage='simulate',metrics={},execution_receipt=ref,
                   evidence=[dict(obsref,kind='analysis'),dict(ref,kind='receipt')])
        row['measurement']['output_sha256']=None
        self.fresh_path.write_text(json.dumps(fresh))
        result=self.make();validate(result)
        self.assertEqual(sum(r['dataset']=='cmp8-base' for r in result['records']),32)
        self.assertEqual(next(r for r in result['records'] if r['dataset']=='cmp8-base' and r['backend']=='evas' and r['case']=='v1-main')['verdict'],'X')

    def test_original_snapshots_and_matrix_reuse_stay_valid(self):
        for p in (ROOT/'experiments/backends/comparison').glob('snapshot*.json'):validate(load(p))

if __name__=='__main__':unittest.main()
