"""Public freeze/run receipts using a tiny independent constant card."""
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SUPPORT = ROOT / 'experiments/backends/support'
import sys
sys.path.insert(0, str(SUPPORT))
import precision_breadth_run as runner


def fixture():
    return {'cards': [{'id':'F01_constant','group_id':'F01','family':'foundation',
        'title':'constant','source':'module dut(u,y); inout u,y; electrical u,y; analog V(y)<+V(u); endmodule',
        'top':'dut','ports':['u','y'],'parameters':{},'inputs':{'u':[[0,1],[1e-6,1]]},
        'outputs':['y'],'scale_V':1,'unit_s':1e-6,'stop_s':1e-6}],
        'profiles':[{'id':n,'reltol':r,'vabstol_V':1e-9,'iabstol_A':1e-12,'step_units':1/32}
                    for n,r in [('base',1e-3),('both',1e-6),('deep',1e-8)]],
        'tiers':[{'id':q,'factor':f} for q,f in [('Q1',10),('Q2',1),('Q3',.1)]],
        'budgets':{'absolute_V':1e-8,'relative':1e-6}}


class BreadthRunner(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.inputs=self.base/'inputs'
        self.patches=[patch.object(runner,'load_contract',return_value=fixture()),
                      patch.object(runner,'observation_plan',return_value={'times_s':[0,5e-7,1e-6]}),
                      patch.object(runner,'source_files',return_value=[Path(runner.__file__)])]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def freeze(self):runner.freeze(self.inputs)

    def test_freeze_binds_allfour_same_source_and_tier_settings(self):
        self.freeze();plan=runner.load(self.inputs/'PLAN.json')
        self.assertEqual(len(plan),12)
        self.assertEqual({r['tier']:r['profile'] for r in plan if r['backend']=='evas'},{'Q1':'base','Q2':'both','Q3':'deep'})
        self.assertEqual({r['tier']:r['profile'] for r in plan if r['backend']=='spectre'},{'Q1':'base','Q2':'both','Q3':'deep_bound'})
        self.assertEqual(len({r['source_sha256'] for r in plan}),1)
        runner.verify(self.inputs)
        self.assertIn('SOURCE_IDENTITY.json',runner.load(self.inputs/'MANIFEST.json'))
        with self.assertRaises(FileExistsError):runner.freeze(self.inputs)

    def test_backend_profile_binding_is_frozen_before_execution(self):
        self.freeze();bindings=runner.load(self.inputs/'PROFILE_BINDINGS.json')
        self.assertEqual(bindings['schema_version'],'breadth-v2')
        for row in runner.load(self.inputs/'PLAN.json'):
            settings=runner.load(self.inputs/row['work']/'requested_settings.json')
            special=row['backend']=='spectre' and row['tier']=='Q3'
            expected=0.0004 if special else fixture()['profiles'][['base','both','deep'].index(runner.TIER_PROFILES[row['tier']])]['step_units']
            self.assertEqual(settings['step_units'],expected)
            if row['tier']=='Q3':self.assertEqual(settings['reltol'],fixture()['profiles'][2]['reltol'])
            self.assertEqual(bindings['backend_tier_profiles'][row['backend']][row['tier']],row['profile'])
        self.assertIn('PROFILE_BINDINGS.json',runner.load(self.inputs/'MANIFEST.json'))
        self.assertIn('experiments/backends/support/precision_binding_run.py',runner.load(self.inputs/'SOURCE_IDENTITY.json'))
        old=self.base/'old'
        runner.freeze(old,backend_tier_profiles={b:dict(runner.TIER_PROFILES) for b in runner.BACKENDS})
        self.assertTrue(all(r['profile']=='deep' for r in runner.load(old/'PLAN.json') if r['tier']=='Q3'))
        with self.assertRaises(ValueError):runner.freeze(self.base/'bad',backend_tier_profiles={'spectre':{'Q3':'invented'}})
        self.assertFalse((self.base/'bad').exists())

    def test_legacy_plan_runs_without_new_binding_metadata(self):
        runner.freeze(self.inputs,backend_tier_profiles={b:dict(runner.TIER_PROFILES) for b in runner.BACKENDS})
        (self.inputs/'PROFILE_BINDINGS.json').unlink()
        manifest=runner.load(self.inputs/'MANIFEST.json');del manifest['PROFILE_BINDINGS.json']
        runner.checkpoint(self.inputs/'MANIFEST.json',manifest)
        profile=self.base/'profile.json';profile.write_text('{}')
        with patch.object(runner,'preflight',side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):runner.run(self.inputs,self.base/'out','spectre',profile,'foundation',tiers=['Q3'])
        started=runner.load(self.base/'out/STARTED.json')
        self.assertEqual(started['schema_version'],'breadth-v1')
        self.assertEqual(started['selected'][0]['profile'],'deep')

    def test_drift_rejected_and_fixed_plan_retained(self):
        self.freeze();(self.inputs/'cards.json').write_text('{}')
        profile=self.base/'profile.json';profile.write_text('{}')
        with self.assertRaises(ValueError):runner.run(self.inputs,self.base/'out','evas',profile,'foundation')
        records=runner.load(self.base/'out/EXECUTION.json')
        self.assertEqual(len(records),3)
        self.assertTrue(all(r['status']=='not_run' for r in records))
        self.assertTrue((self.base/'out/FILE_MANIFEST.json').exists())

    def test_failed_invocation_has_attempt_and_unrun_slots(self):
        self.freeze();profile=self.base/'profile.json';profile.write_text('{}')
        with patch.object(runner,'preflight',return_value=({},{})), patch.object(runner,'verify_tool'), \
             patch.object(runner,'execute_one',side_effect=RuntimeError('adapter failed')):
            with self.assertRaises(RuntimeError):runner.run(self.inputs,self.base/'out','evas',profile,'foundation')
        records=runner.load(self.base/'out/EXECUTION.json')
        self.assertEqual([r['status'] for r in records],['execution_failed','not_run','not_run'])
        receipt=runner.load(self.base/'out/ATTEMPTS.json')
        self.assertEqual(receipt['backend_invocations'],1)
        self.assertEqual(receipt['stage_invocations'],0)
        self.assertEqual(receipt['attempts'][0]['status'],'adapter_error')

    def test_deferred_export_retains_raw_without_calling_analysis(self):
        self.freeze();profile=self.base/'profile.json';profile.write_text('{}')
        def export(backend,tool,env,work):
            (work/'waveform.csv').write_text('time,y\n0,1\n0.000001,1\n')
            (work/'raw-response.json').write_text('{"sample_origins":["accepted"]}')
            return {'status':'waveform_available','waveform':'waveform.csv','stages':[{'stage':'simulate'}],'abort_batch':False}
        with patch.object(runner,'preflight',return_value=({},{})),patch.object(runner,'verify_tool'), \
             patch.object(runner,'execute_one',side_effect=export),patch.object(runner,'read_native') as native, \
             patch.object(runner,'assess') as assess,patch.object(runner,'effective_settings') as settings, \
             patch.object(runner,'qualification') as qualification,patch.object(runner,'native_observation_evidence') as provenance:
            results=runner.run(self.inputs,self.base/'out','evas',profile,'foundation',tiers=['Q1'],defer_analysis=True)
        for analysis in (native,assess,settings,qualification,provenance):analysis.assert_not_called()
        result=results[0]
        self.assertEqual(result['analysis_status'],'pending')
        self.assertEqual(result['qualification']['status'],'unknown')
        self.assertNotIn('assessment',result)
        self.assertTrue(all(t['status']=='unknown' for t in result['qualified_tiers'].values()))
        self.assertTrue(runner.load(self.base/'out/STARTED.json')['defer_analysis'])
        manifest=runner.load(self.base/'out/FILE_MANIFEST.json')
        self.assertIn('runs/'+result['label']+'/waveform.csv',manifest)
        self.assertIn('runs/'+result['label']+'/raw-response.json',manifest)
        self.assertEqual(runner.load(self.base/'out/ATTEMPTS.json')['stage_invocations'],1)

    def test_deferred_failed_invocation_retains_failure_and_unrun_slots(self):
        self.freeze();profile=self.base/'profile.json';profile.write_text('{}')
        with patch.object(runner,'preflight',return_value=({},{})),patch.object(runner,'verify_tool'), \
             patch.object(runner,'execute_one',side_effect=RuntimeError('adapter failed')),patch.object(runner,'assess') as assess:
            with self.assertRaises(RuntimeError):runner.run(self.inputs,self.base/'out','evas',profile,'foundation',defer_analysis=True)
        assess.assert_not_called()
        records=runner.load(self.base/'out/EXECUTION.json')
        self.assertEqual([r['status'] for r in records],['execution_failed','not_run','not_run'])
        self.assertEqual(records[0]['analysis_status'],'not_available')
        self.assertEqual(records[0]['qualification']['status'],'unknown')
        self.assertEqual(runner.load(self.base/'out/ATTEMPTS.json')['backend_invocations'],1)
        self.assertTrue((self.base/'out/FILE_MANIFEST.json').exists())
        with patch.object(runner,'preflight',return_value=({},{})),patch.object(runner,'verify_tool'), \
             patch.object(runner,'execute_one',return_value={'status':'compile_failed','stages':[],'abort_batch':False}):
            returned=runner.run(self.inputs,self.base/'compile-out','evas',profile,'foundation',tiers=['Q1'],defer_analysis=True)
        self.assertEqual(returned[0]['status'],'compile_failed')
        self.assertEqual(returned[0]['analysis_status'],'not_available')
        self.assertTrue(all(q['status']=='unknown' for q in returned[0]['qualified_tiers'].values()))

    def test_numerical_pass_cannot_qualify_without_actual_settings(self):
        self.freeze();profile=self.base/'profile.json';profile.write_text('{}')
        outcome={'status':'waveform_available','waveform':'fake.csv','stages':[{'command':['fake']}],'abort_batch':False}
        with patch.object(runner,'preflight',return_value=({},{})), patch.object(runner,'verify_tool'), \
             patch.object(runner,'execute_one',return_value=outcome), patch.object(runner,'read_native',return_value=[]), \
             patch.object(runner,'assess',return_value={'tiers':{'Q1':{'status':'pass'}}}), \
             patch.object(runner,'effective_settings',side_effect=ValueError('absent actual controls')):
            records=runner.run(self.inputs,self.base/'out','evas',profile,'foundation',tiers=['Q1'])
        self.assertEqual(records[0]['assessment']['tiers']['Q1']['status'],'pass')
        self.assertFalse(runner.load(self.base/'out/STARTED.json')['defer_analysis'])
        self.assertEqual(records[0]['qualified_tiers']['Q1']['status'],'evidence_insufficient')
        self.assertEqual(runner.load(self.base/'out/ATTEMPTS.json')['stage_invocations'],1)

    def test_analysis_failure_retains_every_frozen_tier(self):
        self.freeze();profile=self.base/'profile.json';profile.write_text('{}')
        outcome={'status':'waveform_available','waveform':'fake.csv','stages':[],'abort_batch':False}
        with patch.object(runner,'preflight',return_value=({},{})), patch.object(runner,'verify_tool'), \
             patch.object(runner,'execute_one',return_value=outcome), \
             patch.object(runner,'read_native',side_effect=ValueError('missing column')):
            records=runner.run(self.inputs,self.base/'out','evas',profile,'foundation',tiers=['Q1'])
        result=records[0]
        self.assertIn('missing column',result['analysis_error'])
        self.assertEqual(set(result['qualified_tiers']),{'Q1','Q2','Q3'})
        self.assertTrue(all(q['status']=='evidence_insufficient' for q in result['qualified_tiers'].values()))

    def test_accepted_row_count_alone_cannot_prove_native_origins(self):
        work=self.base/'case';work.mkdir()
        (work/'spectre.log').write_text('Number of accepted tran steps = 2\n')
        (work/'tb.scs').write_text('tran tran strobeoutput=all skipcount=1 compression=no\n')
        rows=[{'time':0},{'time':.5},{'time':1}]
        evidence=runner.native_observation_evidence(work,'spectre',{'status':'qualified'},rows)
        self.assertEqual(evidence['status'],'unknown')
        self.assertTrue(evidence['facts']['rows_equal_accepted_steps_plus_initial'])

    def test_spectre_each_accepted_time_matches_raw_export(self):
        work=self.base/'case';work.mkdir()
        (work/'spectre.log').write_text('precision = %.17g\ntran: time = 500 ns (50 %), step = 500 ns\n'
            'tran: time = 1 us (100 %), step = 500 ns\nNumber of accepted tran steps = 2\n')
        (work/'tb.scs').write_text('tran tran strobeoutput=all skipcount=1 compression=no annotate=steps annotatedigits=16\n')
        (work/'requested_times.json').write_text('[0, 0.0000005, 0.000001]')
        rows=[{'time':0.},{'time':5e-7},{'time':1e-6}]
        tool={'version':'sub-version  21.1.0.509.isr12',
              'binary_sha256':'72fe7e6e958b514d9a0f8bf85e7a08807ea9b34ecbd0ef5ae0586618d549889f'}
        evidence=runner.native_observation_evidence(work,'spectre',{'status':'qualified'},rows,tool=tool,card={'stop_s':1e-6},contract={'budgets':{'time_serialization_ulps':16}})
        self.assertEqual(evidence['status'],'qualified')
        self.assertEqual(evidence['facts']['matched_accepted_rows'],2)
        wrong=[{'time':0.},{'time':6e-7},{'time':1e-6}]
        self.assertEqual(runner.native_observation_evidence(work,'spectre',{'status':'qualified'},wrong,tool=tool,card={'stop_s':1e-6},contract={'budgets':{'time_serialization_ulps':16}})['status'],'unknown')
        (work/'spectre.log').write_text('precision = %.17g\ntran: time = 500 ns (50 %), step = 500 ns\n'
            'tran: time = 500 ns (50 %), step = 500 ns\nNumber of accepted tran steps = 2\n')
        self.assertEqual(runner.native_observation_evidence(work,'spectre',{'status':'qualified'},rows,tool=tool,card={'stop_s':1e-6},contract={'budgets':{'time_serialization_ulps':16}})['status'],'unknown')

    def test_spectre_strobe_uses_frozen_stop_time_budget_without_retiming(self):
        work=self.base/'case';work.mkdir()
        (work/'tb.scs').write_text('tran tran strobeoutput=all skipcount=1 compression=no annotate=steps annotatedigits=16\n')
        requested=1.75e-6;stop=4e-6;actual=1.749999999999998e-6
        (work/'requested_times.json').write_text(json.dumps([0,requested,stop]))
        tool={'version':'sub-version  21.1.0.509.isr12',
              'binary_sha256':'72fe7e6e958b514d9a0f8bf85e7a08807ea9b34ecbd0ef5ae0586618d549889f'}
        def evidence(times):
            (work/'spectre.log').write_text('precision = %.17g\n'+''.join(
                'tran: time = %.16g us (50 %%), step = 1 ns\n' % (t*1e6) for t in times[1:])+
                'Number of accepted tran steps = %d\n' % (len(times)-1))
            rows=[{'time':t} for t in times]
            result=runner.native_observation_evidence(work,'spectre',{'status':'qualified'},rows,
                tool=tool,card={'stop_s':stop},contract={'budgets':{'time_serialization_ulps':16}})
            self.assertEqual([r['time'] for r in rows],times)
            return result
        self.assertGreater(abs(actual-requested),8*math.ulp(requested))
        self.assertLess(abs(actual-requested),16*math.ulp(stop))
        positive=evidence([0.,actual,stop])
        self.assertEqual(positive['status'],'qualified')
        self.assertEqual(positive['facts']['strobe_time_uncertainty_s'],16*math.ulp(stop))
        self.assertEqual(evidence([0.,requested-32*math.ulp(stop),stop])['status'],'unknown')
        # Two accepted rows inside the same request window are ambiguous.
        self.assertEqual(evidence([0.,requested-8*math.ulp(stop),requested+8*math.ulp(stop),stop])['status'],'unknown')
        # Two critical requests must not be collapsed onto one accepted row.
        (work/'requested_times.json').write_text(json.dumps([0,requested,math.nextafter(requested,math.inf),stop]))
        self.assertEqual(evidence([0.,actual,stop])['status'],'unknown')

    def test_runtime_control_evidence_requires_actual_applied_step(self):
        settings={'actual':{'stop':1e-6,'maxstep':1e-9},
                  'requested':{'stop':1e-6,'maxstep':1e-9},'max_step_applied':False}
        self.assertEqual(runner.runtime_control_evidence('evas',settings)['status'],'unknown')
        settings.update(sample_origin_summary={'stateless_working_point':3},observed_response={'accepted_steps':0})
        evidence=runner.runtime_control_evidence('evas',settings)
        self.assertEqual(evidence['status'],'qualified')
        self.assertEqual(evidence['maxstep_application'],'not_applicable')
        settings['max_step_applied']=True
        self.assertEqual(runner.runtime_control_evidence('evas',settings)['status'],'qualified')
        settings['actual']['maxstep']='unknown'
        self.assertEqual(runner.runtime_control_evidence('spectre',settings)['status'],'unknown')

    def test_current_source_drift_rejected(self):
        self.freeze()
        identities=runner.load(self.inputs/'SOURCE_IDENTITY.json')
        identities['experiments/backends/support/precision_breadth_run.py']='0'*64
        runner.checkpoint(self.inputs/'SOURCE_IDENTITY.json',identities)
        manifest=runner.load(self.inputs/'MANIFEST.json')
        manifest['SOURCE_IDENTITY.json']=runner.sha(self.inputs/'SOURCE_IDENTITY.json')
        runner.checkpoint(self.inputs/'MANIFEST.json',manifest)
        with self.assertRaisesRegex(ValueError,'source drift'):runner.verify(self.inputs)

    def test_subset_keeps_tier_binding(self):
        self.freeze();profile=self.base/'profile.json';profile.write_text('{}')
        with patch.object(runner,'preflight',side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):runner.run(self.inputs,self.base/'out','evas',profile,'foundation',tiers=['Q2'])
        records=runner.load(self.base/'out/EXECUTION.json')
        self.assertEqual([(r['tier'],r['profile'],r['status']) for r in records],[('Q2','both','not_run')])


if __name__=='__main__':unittest.main()
