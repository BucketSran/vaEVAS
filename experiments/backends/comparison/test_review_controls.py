"""Independent controls for the frozen CMP review findings; no simulator launch."""
import copy
import hashlib
import subprocess
import unittest
from unittest.mock import patch

import records
from records import ROOT, common_errors, load, validate

SNAPSHOT = ROOT/'experiments/backends/comparison/snapshot-20261006-accounted.json'

class ReviewControls(unittest.TestCase):
    def test_reused_verdict_is_bound_to_named_matrix_observation(self):
        data=load(SNAPSHOT)
        row=next(r for r in data['records'] if r['dataset']=='development31-20260928' and r['case']=='v3-main' and r['backend']=='evas' and r['profile']=='fine')
        self.assertEqual(row['verdict'],'F')
        row['verdict']='P'
        with self.assertRaisesRegex(ValueError,'observation'):
            validate(data)

    def test_metric_is_bound_to_receipt_observation_and_budget(self):
        for field,value in [('observed',123),('budget',.002),('property','another property')]:
            with self.subTest(field=field):
                data=load(SNAPSHOT)
                row=next(r for r in data['records'] if r['dataset']=='cmp8-base' and r['case']=='v1-main' and r['backend']=='evas')
                row['metrics']['voltage'][field]=value
                with self.assertRaisesRegex(ValueError,'metric'):
                    validate(data)

    def test_v2_differential_and_common_mode_have_separate_budgets(self):
        # e_op=1.8mV, e_on=0: differential=1.8mV, common=0.9mV.
        from records import voltage_metrics
        analysis={'v1_screen':{'differential_error_v':.0018,'common_mode_error_v':.0009,
            'max_observed_error':{'op':{'error_v':.0018},'on':{'error_v':0}}}}
        metrics=voltage_metrics('v2-main',analysis,2)
        components=metrics['voltage']
        self.assertEqual([m['budget'] for m in components],[.002,.001])
        self.assertAlmostEqual(max(m['observed']/m['budget'] for m in components),.9)
        self.assertEqual([m['observed'] for m in components],[.0018,.0009])

    def test_historical_candidate_survives_real_checker_fix_blob(self):
        data=load(SNAPSHOT)
        target=ROOT/'benchmark/checkers/triangle_evas.py'
        changed=hashlib.sha256(subprocess.check_output(['git','show','1006c3d5:benchmark/checkers/triangle_evas.py'],cwd=ROOT)).hexdigest()
        original=records.sha
        with patch('records.sha',side_effect=lambda p:changed if p.resolve()==target.resolve() else original(p)):
            validate(data)

    def test_v2_independent_differential_and_common_mode_failures(self):
        from records import voltage_metrics
        # Opposing 1.1mV port errors exceed differential 2mV only.
        # Equal 1.1mV port errors exceed common-mode 1mV only.
        for differential,common,expected in [(.0022,0,1.1),(0,.0011,1.1)]:
            with self.subTest(differential=differential,common=common):
                analysis={'v1_screen':{'differential_error_v':differential,'common_mode_error_v':common,
                    'max_observed_error':{'op':{'error_v':.0011},'on':{'error_v':.0011}}}}
                components=voltage_metrics('v2-main',analysis,2)['voltage']
                self.assertAlmostEqual(max(m['observed']/m['budget'] for m in components),expected)

    def test_legacy_v2_metric_is_explicitly_excluded_from_rendered_common_subset(self):
        from records import render
        data=load(SNAPSHOT)
        result=common_errors(data,'development31-20260928','base','voltage')
        self.assertNotIn('v2-main',result['cases'])
        self.assertIn('legacy schema1 V2 metric invalid',result['excluded']['v2-main'])
        self.assertIn('V2 单端1mV归一化指标已失效',render(data))

    def test_schema2_binds_every_actual_observation_and_retains_launch_count(self):
        data=load(SNAPSHOT.with_name('snapshot-20261006-accounted-v2.json'))
        validate(data)
        old=load(SNAPSHOT)
        executed=[r for r in data['records'] if r['accounting']=='executed']
        self.assertEqual(len(executed),16)
        for row in data['records']:
            prior=next(r for r in old['records'] if tuple(r[k] for k in ('dataset','case','backend','profile'))==tuple(row[k] for k in ('dataset','case','backend','profile')))
            for key in ('verdict','measurement','accounting','execution_receipt'):
                self.assertEqual(row.get(key),prior.get(key))
        v2=next(r for r in executed if r['backend']=='evas' and r['case']=='v2-main')
        self.assertEqual([m['observed'] for m in v2['metrics']['voltage']],[4.440892098500626e-16,2.220446049250313e-16])
        self.assertEqual([m['budget'] for m in v2['metrics']['voltage']],[.002,.001])

    def test_schema2_mutations_cannot_change_normalized_properties(self):
        path=SNAPSHOT.with_name('snapshot-20261006-accounted-v2.json')
        for field,value in [('observed',.123),('budget',.001),('property','single ended')]:
            data=load(path)
            row=next(r for r in data['records'] if r['dataset']=='cmp8-base' and r['case']=='v2-main' and r['backend']=='evas')
            row['metrics']['voltage'][0][field]=value
            with self.assertRaisesRegex(ValueError,'metric'):
                validate(data)
        data=load(path)
        row=next(r for r in data['records'] if r['accounting']=='reused')
        row['observation_binding']['selector']['condition']='v3-main'
        with self.assertRaisesRegex(ValueError,'observation selector'):
            validate(data)

    def test_old_and_derived_snapshots_survive_base1006_combination(self):
        target=ROOT/'benchmark/checkers/triangle_evas.py'
        changed=hashlib.sha256(subprocess.check_output(['git','show','1006c3d5:benchmark/checkers/triangle_evas.py'],cwd=ROOT)).hexdigest()
        original=records.sha
        snapshots=sorted(SNAPSHOT.parent.glob('snapshot*.json'))
        before={p:original(p) for p in snapshots}
        with patch('records.sha',side_effect=lambda p:changed if p.resolve()==target.resolve() else original(p)):
            for p in snapshots:
                with self.subTest(snapshot=p.name):
                    validate(load(p))
        self.assertEqual(before,{p:original(p) for p in snapshots})
        data=load(SNAPSHOT.with_name('snapshot-20261006-accounted-v2.json'))
        candidate=next(d for d in data['datasets'] if d['id']=='application-reference')['candidates'][0]
        self.assertNotEqual(candidate['adapter_checker_sha256'],changed)

    def test_archived_source_is_bound_to_original_revision_and_hash(self):
        data=load(SNAPSHOT.with_name('snapshot-20261006-accounted-v2.json'))
        candidate=next(d for d in data['datasets'] if d['id']=='application-reference')['candidates'][0]
        ref=candidate['sources'][0]
        original=records.sha
        target=(ROOT/ref['path']).resolve()
        with patch('records.sha',side_effect=lambda p:'corrupt' if p.resolve()==target else original(p)):
            with self.assertRaisesRegex(ValueError,'changed compact evidence'):
                validate(data)
        candidate['revision']='1006c3d5'
        with self.assertRaisesRegex(ValueError,'fixed 40-hex revision'):
            validate(data)
        candidate['revision']='d06581f92628ab9e94a2d16bf600b0225174bb6d'
        ref['original_path']='../outside'
        with self.assertRaisesRegex(ValueError,'escapes repository'):
            validate(data)

    def test_common_aggregate_uses_maximum_of_both_v2_normalized_properties(self):
        data=load(SNAPSHOT.with_name('snapshot-20261006-accounted-v2.json'))
        dataset=next(d for d in data['datasets'] if d['id']=='development31-20260928')
        dataset['cases']=[c for c in dataset['cases'] if c['id']=='v2-main']
        rows=[r for r in data['records'] if r['dataset']==dataset['id'] and r['case']=='v2-main' and r['profile']=='base']
        for row in rows:
            row['metrics']['voltage'][0]['observed']=.0018
            row['metrics']['voltage'][1]['observed']=.0009
        result=common_errors(data,dataset['id'],'base','voltage')
        self.assertEqual(result['cases'],['v2-main'])
        for maximum in result['maxima'].values():
            self.assertAlmostEqual(maximum['normalized'],.9)
            self.assertEqual([m['budget'] for m in maximum['original']],[.002,.001])

    def test_static_derivation_cannot_relabel_original_execution_identity(self):
        data=load(SNAPSHOT.with_name('snapshot-20261006-accounted-v2.json'))
        row=next(r for r in data['records'] if r['accounting']=='reused')
        row['measurement']['revision']='new-candidate'
        with self.assertRaisesRegex(ValueError,'static derivation changed historical execution identity'):
            validate(data)
