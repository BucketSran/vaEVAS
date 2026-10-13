"""Independent hand anchors and corrupt evidence for EC05-Q-v2."""
GUARDS = ['QUALIFICATION', 'TRANSITION', 'DYNAMICS']
import copy
from decimal import localcontext
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'validation/paper'))
import transition_integral_precision as q


def fixture():
    c=q.card();T=c['unit_s'];ts=set(c['times'])
    for t in [T,1.25*T,1.75*T]:ts.update([t-1e-12,t,t+1e-12])
    with localcontext() as ctx:
        ctx.prec=80
        rows=[{'time':t,**{n:float(v) for n,v in q.reference(t,T,1.25*T,T).items()}} for t in sorted(ts)]
    events=[dict(index=i,time_s=t,target=v,bounds=[t,t]) for i,t,v in [(1,T,1),(2,1.25*T,0)]]
    return c,rows,events


class TransitionIntegralPrecision(unittest.TestCase):
    def test_hand_triangular_area_anchors(self):
        c=q.card();T=c['unit_s']
        for x,e,y in [(0,0,.1),(1,0,.1),(1.125,.25,.115625),(1.25,.5,.1625),
                      (1.5,.25,.25625),(1.75,0,.2875),(3,0,.2875)]:
            a=q.reference(x*T,T,1.25*T,T)
            self.assertAlmostEqual(float(a['edge_v']),e,delta=1e-15)
            self.assertAlmostEqual(float(a['y']),y,delta=1e-15)
    def test_three_tiers_and_wrong_full_fall_area(self):
        c,rows,events=fixture()
        for tier in q.TIERS:self.assertEqual(q.assess(c,rows,events,tier)['status'],'pass')
        rows[-1]['y']=.4125
        self.assertEqual(q.assess(c,rows,events,'Q1')['status'],'numerical_error')
    def test_budget_and_evidence_failures_remain_distinct(self):
        c,rows,events=fixture()
        broken=copy.deepcopy(rows);broken[-1]['y']+=2e-6
        self.assertEqual(q.assess(c,broken,events,'Q1')['status'],'pass')
        self.assertEqual(q.assess(c,broken,events,'Q2')['status'],'numerical_error')
        self.assertEqual(q.assess(c,rows,events[:1],'Q1')['status'],'evidence_insufficient')
        self.assertEqual(q.assess(c,[rows[0],*rows],events,'Q1')['status'],'evidence_insufficient')
        wrong=copy.deepcopy(events);wrong[0]['time_s']-=2e-10;wrong[0]['bounds']=[wrong[0]['time_s']]*2
        self.assertEqual(q.assess(c,rows,wrong,'Q1')['status'],'behavior_error')
    def test_time_box_propagates_to_future_area(self):
        c,rows,events=fixture()
        events[0]['bounds']=[events[0]['time_s']-1e-12,events[0]['time_s']+1e-12]
        verdict=q.assess(c,rows,events,'Q3')
        self.assertEqual(verdict['status'],'evidence_insufficient')
        self.assertIn('influence',verdict['reason'])

    def test_observation_plan_covers_full_allowed_interruption_end(self):
        import tempfile
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments/backends/support'))
        import transition_integral_run as runner
        with tempfile.TemporaryDirectory() as tmp:
            inputs=Path(tmp)/'inputs';runner.freeze(inputs)
            plan=runner.execution.load(inputs/'PLAN.json')
            row=next(r for r in plan if r['backend']=='spectre' and r['tier']=='Q3' and r['variant']=='trace')
            times=runner.execution.load(inputs/row['work']/'requested_times.json')
            c=q.card();T=c['unit_s']
            for da in (-1e-10,1e-10):
                for db in (-1e-10,1e-10):
                    for boundary in (T+da,1.25*T+db,3*(1.25*T+db)-2*(T+da)):
                        self.assertLessEqual(min(abs(t-boundary) for t in times),2.1e-12)
                        self.assertTrue(any(0<boundary-t<=2.1e-12 for t in times))
                        self.assertTrue(any(0<t-boundary<=2.1e-12 for t in times))
            deck=(inputs/row['work']/row['deck']).read_text()
            self.assertEqual(deck.count('precision="%.17g"'),1)
            self.assertEqual(deck.count('transres=1e-20'),1)
            self.assertEqual(set(c['inputs']),set())

    def test_bad_observer_waveform_keeps_original_receipts_and_manifest(self):
        import tempfile
        from unittest.mock import patch
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments/backends/support'))
        import transition_integral_run as runner
        with tempfile.TemporaryDirectory() as tmp:
            inputs=Path(tmp)/'inputs';profile=Path(tmp)/'profile.json'
            runner.freeze(inputs);runner.save(profile,{})
            def simulate(backend,tool,env,work):
                (work/'waveform.psf').write_text('VALUE\n"time" 0\n"y" 0\n"y" 0\nEND\n')
                (work/'spectre.log').write_text('')
                return dict(status='waveform_available',waveform='waveform.psf',abort_batch=False,stages=[])
            output=Path(tmp)/'lane'
            with patch.object(runner.execution,'preflight',return_value=({},{})),                 patch.object(runner.execution,'verify_tool'),                 patch.object(runner.execution,'execute_one',side_effect=simulate):
                runner.run(inputs,output,'spectre',profile,tiers=['Q1'])
            records=runner.execution.load(output/'EXECUTION.json')
            self.assertEqual(len(records),2)
            self.assertEqual({r['variant'] for r in records},{'original','trace'})
            self.assertTrue(all(r['engineering_verdict']=='evidence_insufficient' for r in records))
            self.assertTrue(all('PSF time missing or repeated signal' in r['analysis_error'] for r in records))
            comparison=runner.execution.load(output/'OBSERVER_COMPARISON.json')[0]['comparison']
            self.assertEqual(comparison['status'],'evidence_insufficient')
            manifest=runner.execution.load(output/'FILE_MANIFEST.json')
            self.assertIn('EXECUTION.json',manifest);self.assertIn('OBSERVER_COMPARISON.json',manifest)
            for record in records:self.assertIn('runs/'+record['label']+'/RESULT.json',manifest)
            self.assertEqual(manifest,runner.pipeline.file_manifest(output))
            runner.pipeline.verify_lane(output,runner.ROOT)
            runner.reanalyze([output],Path(tmp)/'analysis.json')
            self.assertEqual(manifest,runner.pipeline.file_manifest(output))




if __name__=='__main__':unittest.main()
