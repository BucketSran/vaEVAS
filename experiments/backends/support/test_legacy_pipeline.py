"""Local acceptance controls for legacy recipes and immutable offline lanes."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import legacy_chain_run as legacy
import transition_integral_run as area
import legacy_pipeline as pipeline
from inputs import sha
save=pipeline.save


class LegacyPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.inputs=self.root/'inputs'
        legacy.freeze(self.inputs,cases=['NT:fixed','NT:held','NT:chain'],tiers=['Q1'])
        self.profile=self.root/'profile.json';save(self.profile,{})

    def reseal_inputs(self):
        save(self.inputs/'MANIFEST.json',{str(p.relative_to(self.inputs)):sha(p) for p in self.inputs.rglob('*')
                                         if p.is_file() and p!=self.inputs/'MANIFEST.json'})

    def test_ground_binding_and_paired_pilot(self):
        before={str(p):sha(p) for p in self.inputs.rglob('*') if p.is_file()}
        for backend,slots in [('evas',1),('spectre',2)]:
            report=legacy.precheck(self.inputs,backend,pilot=True)
            self.assertEqual(report['selected_slots'],slots)
        self.assertEqual(before,{str(p):sha(p) for p in self.inputs.rglob('*') if p.is_file()})
        report=legacy.precheck(self.inputs,'spectre',pilot=True)
        self.assertTrue(all('NT_fixed' in name for name in report['selected_labels']))

    def test_unknown_selectors_fail_before_tools(self):
        for kwargs in ({'cases':['NT:fixed','unknown']},{'tiers':['Q1','bad']},{'variant':'bad'}):
            with patch.object(legacy.execution,'preflight') as tool:
                with self.assertRaises(ValueError):legacy.run(self.inputs,self.root/'absent','evas',self.profile,**kwargs)
                tool.assert_not_called()
                self.assertFalse((self.root/'absent').exists())

    def test_resealed_bad_ground_recipe_blocks_every_invocation(self):
        row=next(r for r in legacy.load(self.inputs/'PLAN.json') if r['backend']=='evas')
        path=self.inputs/row['work']/row['deck'];request=legacy.load(path)
        request['instances'][0]['ports']['r']='r';save(path,request)
        plan=legacy.load(self.inputs/'PLAN.json');plan[0]['deck_sha256']=sha(path);save(self.inputs/'PLAN.json',plan)
        self.reseal_inputs()
        with patch.object(legacy.execution,'preflight') as tool:
            with self.assertRaises(ValueError):legacy.run(self.inputs,self.root/'failed','evas',self.profile)
            tool.assert_not_called()
        records=legacy.load(self.root/'failed'/'EXECUTION.json')
        self.assertEqual(len(records),3)
        self.assertTrue(all(r['status']=='not_run' for r in records))
        self.assertEqual(legacy.load(self.root/'failed'/'ATTEMPTS.json'),[])

    def test_resealed_escaping_label_fails_before_tools(self):
        plan=legacy.load(self.inputs/'PLAN.json');plan[0]['label']='../../escaped'
        save(self.inputs/'PLAN.json',plan);self.reseal_inputs()
        with patch.object(legacy.execution,'preflight') as tool:
            with self.assertRaises(ValueError):legacy.precheck(self.inputs,'evas')
            with self.assertRaises(ValueError):legacy.run(self.inputs,self.root/'lane','evas',self.profile,defer_analysis=True)
            tool.assert_not_called()
        self.assertFalse((self.root/'escaped').exists())

    def simulated(self,backend,tool,env,work):
        (work/'waveform.csv').write_text('time,y\n0,0\n1,0\n')
        return dict(status='waveform_available',waveform='waveform.csv',abort_batch=False,stages=[])

    def lane(self,*,adapter=None,pilot=True,backend="evas"):
        output=self.root/'lane'
        with patch.object(legacy.execution,'preflight',return_value=({'kernel':'unused'},{})),\
             patch.object(legacy.execution,'verify_tool'),\
             patch.object(legacy,'execute_one',side_effect=adapter or self.simulated),\
             patch.object(legacy,'analyze_work',side_effect=AssertionError('deferred analyzer called')):
            legacy.run(self.inputs,output,backend,self.profile,pilot=pilot,defer_analysis=True)
        return output

    def test_deferred_lane_denominator_seal_and_offline_immutability(self):
        lane=self.lane();records=legacy.load(lane/'EXECUTION.json')
        self.assertEqual([r['status'] for r in records],['waveform_available','not_run','not_run'])
        self.assertEqual(records[0]['Q_qualification']['status'],'unknown')
        self.assertFalse(any(lane.rglob('ASSESSMENT.json')))
        timing=legacy.load(lane/'TIMINGS.json')
        for field in ('precheck_s','tool_preflight_s','artifact_sealing_s','total_s'):self.assertGreaterEqual(timing[field],0)
        original=pipeline.file_manifest(lane)
        with patch.object(legacy,'analyze_work',return_value={'assessment':{'status':'control'},'historical_assessment':{'status':'old-control'}}) as checker,\
             patch.object(legacy,'read_native',return_value=[]):
            legacy.analyze([lane],self.root/'analysis.json')
            self.assertFalse(checker.call_args.kwargs['persist'])
            with self.assertRaises(FileExistsError):legacy.analyze([lane],self.root/'analysis.json')
            with self.assertRaises(ValueError):legacy.analyze([lane],lane/'NEW.json')
        self.assertEqual(original,pipeline.file_manifest(lane))
        report=legacy.load(self.root/'analysis.json')
        self.assertEqual(len(report['records']),3)
        self.assertEqual(report['records'][0]['historical_assessment']['status'],'old-control')

    def test_adapter_failure_is_sealed_and_rest_not_run(self):
        def fail(*args):raise RuntimeError('adapter failed')
        lane=self.lane(adapter=fail,pilot=False)
        records=legacy.load(lane/'EXECUTION.json')
        self.assertEqual([r['status'] for r in records],['execution_failed','not_run','not_run'])
        self.assertEqual(legacy.load(lane/'ATTEMPTS.json')[0]['status'],'adapter_error')
        pipeline.verify_lane(lane,legacy.ROOT)

    def test_raw_file_addition_and_size_drift_rejected(self):
        lane=self.lane();(lane/'unexpected').write_text('addition')
        with self.assertRaises(ValueError):legacy.analyze([lane],self.root/'analysis.json')
        (lane/'unexpected').unlink()
        p=next(lane.rglob('waveform.csv'));p.write_text(p.read_text()+'\n')
        with self.assertRaises(ValueError):legacy.analyze([lane],self.root/'analysis.json')

    def test_resealed_missing_or_duplicate_execution_slot_rejected(self):
        lane=self.lane();records=legacy.load(lane/'EXECUTION.json')
        for changed in (records[:-1],records+[records[-1]]):
            save(lane/'EXECUTION.json',changed)
            save(lane/'FILE_MANIFEST.json',pipeline.file_manifest(lane))
            with self.assertRaises(ValueError):pipeline.verify_lane(lane,legacy.ROOT)

    def test_historical_record_cannot_escape_sealed_work_or_waveform(self):
        lane=self.lane();records=legacy.load(lane/'EXECUTION.json')
        for path in lane.glob('FROZEN_*'):path.unlink()
        save(lane/'FILE_MANIFEST.json',pipeline.file_manifest(lane))
        pipeline.verify_lane(lane,legacy.ROOT)
        original=[dict(r) for r in records]
        for field,value in [('label','../../escaped'),('waveform',str(self.root/'outside.csv')),('waveform','../outside.csv')]:
            records=[dict(r) for r in original];records[0][field]=value
            save(lane/'EXECUTION.json',records)
            save(lane/'FILE_MANIFEST.json',pipeline.file_manifest(lane))
            with self.assertRaises(ValueError):pipeline.verify_lane(lane,legacy.ROOT)

    def test_producer_sources_checked_for_spectre_too(self):
        lane=self.lane(backend='spectre')
        pipeline.verify_lane(lane,legacy.ROOT)
        with self.assertRaises(ValueError):pipeline.verify_lane(lane,self.root)


class AreaPipelineTests(unittest.TestCase):
    def test_actual_area_checker_accepts_reference_replay_with_qualification_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);inputs=root/'inputs';area.freeze(inputs)
            profile=root/'profile.json';save(profile,{})
            def fake(backend,tool,env,work):
                c=area.execution.load(work/'condition.json');T=c['unit_s'];a=T;b=1.25*T
                lines=['VALUE']
                for t in area.execution.load(work/'requested_times.json'):
                    values=area.q.reference(t,a,b,T)
                    lines.append('"time" '+format(t,'.17g'))
                    lines.extend('"'+k+'" '+format(float(v),'.17g') for k,v in values.items())
                (work/'waveform.psf').write_text('\n'.join(lines+['END'])+'\n')
                (work/'spectre.log').write_text(f'EDGE_AREA 1 {a:.17g} 1\nEDGE_AREA 2 {b:.17g} 0\n')
                return dict(status='waveform_available',waveform='waveform.psf',abort_batch=False,stages=[])
            with patch.object(area.execution,'preflight',return_value=({},{})),patch.object(area.execution,'verify_tool'),                 patch.object(area.execution,'execute_one',side_effect=fake):
                area.run(inputs,root/'lane','spectre',profile,defer_analysis=True,tiers=['Q1'])
            lane=root/'lane';before=pipeline.file_manifest(lane)
            area.reanalyze([lane],root/'analysis.json')
            report=area.execution.load(root/'analysis.json');pair={r['variant']:r for r in report['records']}
            self.assertEqual(pair['trace']['assessment']['status'],'pass')
            self.assertEqual(pair['original']['assessment']['status'],'evidence_insufficient')
            self.assertEqual(pair['trace']['engineering_verdict'],'evidence_insufficient')
            self.assertEqual(before,pipeline.file_manifest(lane))
            # Reconstruct the historical format in this synthetic control only.
            # Historical EC05 lanes lacked original.va and frozen recipe copies.
            for path in lane.glob('FROZEN_*'):path.unlink()
            for path in lane.rglob('original.va'):path.unlink()
            save(lane/'FILE_MANIFEST.json',pipeline.file_manifest(lane))
            historical=pipeline.file_manifest(lane)
            area.reanalyze([lane],root/'historical-analysis.json')
            old=area.execution.load(root/'historical-analysis.json')
            self.assertIn('limited legacy replay',old['parent_executions'][0]['recipe_binding'])
            self.assertEqual(old['records'][1]['original_source_binding_basis'],'frozen condition.json source text')
            self.assertEqual(historical,pipeline.file_manifest(lane))
            self.assertFalse(any(lane.rglob('original.va')))

    def test_area_freeze_precheck_deferred_and_offline_malformed_raw(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);inputs=root/'inputs';area.freeze(inputs)
            for backend in ('evas','spectre'):
                report=area.precheck(inputs,backend,pilot=True)
                self.assertEqual(report['selected_slots'],3 if backend=='evas' else 6)
            profile=root/'profile.json';save(profile,{})
            def fake(backend,tool,env,work):
                (work/'waveform.psf').write_text('malformed raw retained')
                (work/'spectre.log').write_text('no callback control')
                return dict(status='waveform_available',waveform='waveform.psf',abort_batch=False,stages=[])
            with patch.object(area.execution,'preflight',return_value=({},{})),patch.object(area.execution,'verify_tool'),\
                 patch.object(area.execution,'execute_one',side_effect=fake),\
                 patch.object(area,'analyze_work',side_effect=AssertionError('deferred called')):
                area.run(inputs,root/'lane','spectre',profile,defer_analysis=True,tiers=['Q1'])
            lane=root/'lane';before=pipeline.file_manifest(lane)
            area.reanalyze([lane],root/'analysis.json')
            report=area.execution.load(root/'analysis.json')
            self.assertEqual(len(report['records']),2)
            self.assertTrue(all(r['engineering_verdict']=='evidence_insufficient' for r in report['records']))
            self.assertEqual(before,pipeline.file_manifest(lane))
            self.assertEqual(report['observer_comparison'][0]['comparison']['status'],'evidence_insufficient')


if __name__=='__main__':unittest.main()
