"""Checker calibration with independently constructed trajectories, not VA execution."""
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('checker',ROOT/'benchmark/checkers/first_batch_model_repair.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

def fixture(case,targets):
    # Piecewise linear fixture encodes event targets; no reference source read.
    nodes=list(targets);ts={0.,case['stop']}
    for events in targets.values():
        for t,v in events:ts|={t,t+case['tr']/2,t+case['tr'],max(0,t-2e-10),min(case['stop'],t+2e-10)}
    ts|={case['stop']*i/2000 for i in range(2001)}
    rows=[]
    for t in sorted(ts):
        if t>case['stop']:continue
        row={'time':t}
        for node,events in targets.items():
            v=events[0][1]
            for start,new in events[1:]:
                if t<start:break
                if t<start+case['tr']:v+=(new-v)*(t-start)/case['tr'];break
                v=new
            row[node]=v
        rows.append(row)
    return rows

class ComparatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cases=json.loads((ROOT/'benchmark/tasks/spec-latched-comparator/tests/cases.json').read_text())
    def test_analytic_event_trajectories_pass(self):
        for c in self.cases:self.assertTrue(checker.evaluate(fixture(c,checker.comparator_targets(c)),c)['passed'])
    def test_swapped_decision_fails(self):
        for c in self.cases:
            targets=checker.comparator_targets(c);targets['outp'],targets['outn']=targets['outn'],targets['outp']
            self.assertFalse(checker.evaluate(fixture(c,targets),c)['passed'])
    def test_constant_delay_fails(self):
        c=self.cases[0];wrong=dict(c,tau=0)
        self.assertFalse(checker.evaluate(fixture(c,checker.comparator_targets(wrong)),c)['passed'])
    def test_low_phase_spurious_ready_fails(self):
        c=self.cases[1];targets=checker.comparator_targets(c);targets['ready'] += [(8e-9,1),(10e-9,0)];targets['ready'].sort()
        self.assertFalse(checker.evaluate(fixture(c,targets),c)['passed'])
    def test_hold_glitch_fails_even_if_final_value_correct(self):
        c=self.cases[0];targets=checker.comparator_targets(c);targets['outp'] += [(4e-9,0),(4.4e-9,1)];targets['outp'].sort()
        self.assertFalse(checker.evaluate(fixture(c,targets),c)['passed'])
    def test_reset_cycle_has_no_decision(self):
        c=self.cases[0];targets=checker.comparator_targets(c);e=c['events'][-1];targets['ready'] += [(e['rise']+1e-9,1),(e['fall'],0)]
        self.assertFalse(checker.evaluate(fixture(c,targets),c)['passed'])
    def test_async_reset_before_decision_cancels_even_after_release(self):
        c=self.cases[0];e=c['events'][2];targets=checker.comparator_targets(c)
        self.assertFalse(any(e['rise']<t<e['fall'] and v for t,v in targets['ready']))
        # Missing reset event handling leaves the timer armed. Reset releases
        # before its deadline, so a timer-level rst check cannot mask the bug.
        wrong=dict(c,resets=[(t,v) for t,v in c['resets'] if not e['rise']<t<e['fall']])
        self.assertFalse(checker.evaluate(fixture(c,checker.comparator_targets(wrong)),c)['passed'])
    def test_async_reset_after_decision_clears_both_polarities_and_ready(self):
        c=self.cases[0];targets=checker.comparator_targets(c)
        for index,node in [(0,'outp'),(3,'outn')]:
            e=c['events'][index];assertion=e['rise']+2e-9
            self.assertIn((assertion,0.),targets['ready'])
            self.assertIn((assertion,0.),targets[node])
            self.assertEqual(checker.level_at(0,targets['ready'],e['rise']+4e-9),0.)
            wrong=dict(c,resets=[(t,v) for t,v in c['resets'] if not e['rise']<t<e['fall']])
            self.assertFalse(checker.evaluate(fixture(c,checker.comparator_targets(wrong)),c)['passed'])

class AdditionalContracts(unittest.TestCase):
    def cases(self,task):return json.loads((ROOT/'benchmark/tasks'/task/'tests/cases.json').read_text())
    def test_phase_pulses_and_semantic_faults(self):
        for c in self.cases('spec-cdr-phase-detector'):
            targets=checker.bbpd_targets(c);self.assertTrue(checker.evaluate(fixture(c,targets),c)['passed'])
            targets['up'],targets['down']=targets['down'],targets['up'];self.assertFalse(checker.evaluate(fixture(c,targets),c)['passed'])
    def test_sigma_charge_balance_and_falling_phase(self):
        for c in self.cases('spec-sigma-delta'):
            targets=checker.sigma_targets(c);self.assertTrue(checker.evaluate(fixture(c,targets),c)['passed'])
            targets['bitout']=[(t+(.8e-9 if t else 0),v) for t,v in targets['bitout']]
            self.assertFalse(checker.evaluate(fixture(c,targets),c)['passed'])
    def test_hold_analytic_exponential_and_bandwidth(self):
        for c in self.cases('spec-sample-hold-acquisition'):
            rows=[{'time':c['stop']*i/2000,'vout':checker.hold_value(c,c['stop']*i/2000)} for i in range(2001)]
            self.assertTrue(checker.evaluate(rows,c)['passed'])
            wrong=dict(c,tau=2*c['tau']);rows=[{'time':r['time'],'vout':checker.hold_value(wrong,r['time'])} for r in rows]
            self.assertFalse(checker.evaluate(rows,c)['passed'])
    def test_hold_has_static_hold_even_when_input_changes(self):
        c=self.cases('spec-sample-hold-acquisition')[0]
        self.assertAlmostEqual(checker.hold_value(c,11e-9),checker.hold_value(c,13e-9))

class UVLOTests(unittest.TestCase):
    def test_supply_crossing_qualification(self):
        cases=json.loads((ROOT/'benchmark/tasks/spec-uvlo-deglitch/tests/cases.json').read_text())
        for c in cases:
            targets=checker.uvlo_targets(c);self.assertTrue(checker.evaluate(fixture(c,targets),c)['passed'])
            self.assertGreater(targets['pgood'][1][0],7e-9)
            wrong=dict(c,tgood=1e-12,tbad=1e-12)
            self.assertFalse(checker.evaluate(fixture(c,checker.uvlo_targets(wrong)),c)['passed'])
    def test_cancelled_startup_glitch_rejected(self):
        c=json.loads((ROOT/'benchmark/tasks/spec-uvlo-deglitch/tests/cases.json').read_text())[0]
        targets=checker.uvlo_targets(c);targets['pgood'] += [(4e-9,1),(5e-9,0)];targets['pgood'].sort()
        self.assertFalse(checker.evaluate(fixture(c,targets),c)['passed'])

class SARZoomTests(unittest.TestCase):
    def cases(self,task):return json.loads((ROOT/'benchmark/tasks'/task/'tests/cases.json').read_text())
    def test_sar_four_decisions_abort_and_restart(self):
        for c in self.cases('repair-sar-abort'):
            targets=checker.sar_targets(c);self.assertTrue(checker.evaluate(fixture(c,targets),c)['passed'])
            # First completion belongs to conversion two, never the aborted attempt.
            rises=[t for t,v in targets['valid'] if v]
            self.assertAlmostEqual(rises[0],30e-9+c['tvalid'])
            for block,time in enumerate([30e-9+c['tvalid'],46e-9+c['tvalid']],1):
                code=sum(int(checker.level_at(0,targets['d'+str(bit)],time+1e-10))<<bit for bit in range(4))
                self.assertEqual(code,int(16*checker.pwl_value(c['vin'],time)))
    def test_sar_stale_valid_and_latency_rejected(self):
        c=self.cases('repair-sar-abort')[0];targets=checker.sar_targets(c)
        targets['valid'] += [(14.8e-9,1),(15.5e-9,0)];targets['valid'].sort()
        self.assertFalse(checker.evaluate(fixture(c,targets),c)['passed'])
        wrong=dict(c,tvalid=1e-12)
        self.assertFalse(checker.evaluate(fixture(c,checker.sar_targets(wrong)),c)['passed'])
    def test_zoom_independent_calendar(self):
        for c in self.cases('repair-zoom-sequencer'):
            targets=checker.zoom_targets(c);self.assertTrue(checker.evaluate(fixture(c,targets),c)['passed'])
            targets['clk_zoom']=targets['clk_zoom'][:3]
            self.assertFalse(checker.evaluate(fixture(c,targets),c)['passed'])
    def test_zoom_nbit_and_reset_are_separate_obligations(self):
        c=self.cases('repair-zoom-sequencer')[1];targets=checker.zoom_targets(c);targets['rst_zoom']=[(0.,0.)]
        self.assertFalse(checker.evaluate(fixture(c,targets),c)['passed'])

if __name__=='__main__':unittest.main()
