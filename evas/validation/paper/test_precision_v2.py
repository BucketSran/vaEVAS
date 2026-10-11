"""Calibration against constructed answers and deliberate faults, not DUT output."""
import copy
import math
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from precision_v2 import assess, load_contract, observation_plan, error_bounds, rows_digest
from precision_reference import FirstOrder, pwl_range

CONTRACT = load_contract()
CARDS = {c['id']: c for c in CONTRACT['cards']}


def sample_rows(card, shift=50e-12):
    # Independent hand-derived triangle and plateau. A sparse synthetic native
    # trace meets the obligations without reproducing the production generator.
    ts = {0., card['stop_s']}
    ts.update(i * card['unit_s']/32 for i in range(math.ceil(card['stop_s']/card['unit_s']*32)))
    centers = {t for pts in card['inputs'].values() for t, _ in pts}
    for t in card['events_s']:
        centers.update((t, t-card['event_early_s'], t+card['event_late_s']))
        ts.update((t+shift-1e-14, t+shift+1e-14))
    for t in centers:
        ts.update((t-1e-12, t, t+1e-12))
    events = [t+shift for t in card['events_s']]
    rows = []
    for t in sorted(t for t in ts if 0 <= t <= card['stop_s']):
        n = sum(e <= t for e in events)
        def triangle(t):
            x = t/1e-6
            return card['scale_V']*((-.4+.2*x) if x<=4 else (1.2-.2*x) if x<=8 else (-.4+.2*(x-8)))
        u = .2 if card['id']=='SH-T-LONG' else triangle(t)
        y = card['initial_V'] if not n else .2 if card['id']=='SH-T-LONG' else triangle(events[n-1])
        row = {'time': t, 'u': u, 'y': y, 'count': float(n)}
        if 'clk' in card['inputs']:
            # Clock is periodic: rise .9..1.1 us, high to 1.4, fall to 1.5.
            x = (t/1e-6) % 1
            row['clk'] = min(1., max(0., (x+.1)/.2 if x<=.4 else (0.5-x)/.1 if x<=.9 else (x-.9)/.2))
            if t < .9e-6: row['clk'] = 0.
        rows.append(row)
    return rows


class TierCalibration(unittest.TestCase):
    def check(self, card, rows):
        return assess(card, rows, CONTRACT)

    def test_valid_timer_all_tiers(self):
        for key in ('SH-T-RAMP','SH-T-SMALL','SH-T-LONG'):
            result = self.check(CARDS[key], sample_rows(CARDS[key]))
            self.assertEqual([v['status'] for v in result['tiers'].values()], ['pass']*3, result)

    def test_window_partial_overlap_is_not_a_pass(self):
        c=CARDS['SH-T-RAMP']
        for shift in (-100.5e-12,100.5e-12):
            rows=sample_rows(c, shift)
            # A wide counter bracket intersects the legal window: the old leak.
            rows=[r for r in rows if all(not t-102e-12 < r['time'] < t-99e-12 for t in c['events_s'])] if shift<0 else [r for r in rows if all(not t+99e-12 < r['time'] < t+102e-12 for t in c['events_s'])]
            self.assertTrue(all(v['status']!='pass' for v in self.check(c,rows)['tiers'].values()))

    def test_confirmed_outside_window_and_missing_event(self):
        c=CARDS['SH-T-RAMP']
        self.assertEqual(self.check(c,sample_rows(c,4e-10))['behavior']['status'],'behavior_error')
        rows=sample_rows(c)
        for r in rows:
            if r['count']>=3:r['count']+=1
        self.assertEqual(self.check(c,rows)['behavior']['status'],'behavior_error')

    def test_initial_hold_drift_includes_both_extrema(self):
        c=CARDS['SH-T-RAMP'];rows=sample_rows(c);initial=[r for r in rows if not r['count']]
        initial[1]['y']-=.7*1.01e-6;initial[-1]['y']+=.7*1.01e-6
        r=self.check(c,rows)
        self.assertEqual(r['tiers']['Q1']['status'],'pass')
        self.assertEqual(r['tiers']['Q2']['status'],'numerical_error')

    def test_all_holding_stages_and_stale_value(self):
        c=CARDS['SH-T-LONG']
        for stage in range(33):
            rows=sample_rows(c);group=[r for r in rows if r['count']==stage]
            group[0]['y']-=1e-6;group[-1]['y']+=1e-6
            self.assertEqual(self.check(c,rows)['tiers']['Q2']['status'],'numerical_error')
        c=CARDS['SH-T-RAMP'];rows=sample_rows(c)
        next(r for r in rows if r['count']==2)['y']=-.2
        self.assertTrue(all(v['status']=='numerical_error' for v in self.check(c,rows)['tiers'].values()))

    def test_tiers_share_reference_and_do_not_hide_input_error(self):
        c=CARDS['SH-T-RAMP'];rows=sample_rows(c)
        for r in rows:r['y']+=2e-6
        out=self.check(c,rows)
        self.assertEqual([r['status'] for r in out['tiers'].values()],['pass','numerical_error','numerical_error'])
        rows=sample_rows(c);rows[5]['u']+=1e-3
        self.assertTrue(all(v['status']=='input_mismatch' for v in self.check(c,rows)['tiers'].values()))

    def test_missing_boundaries_including_legal_window_ends(self):
        c=CARDS['SH-T-RAMP'];rows=sample_rows(c)
        t=c['events_s'][0]-c['event_early_s']
        rows=[r for r in rows if abs(r['time']-t)>3e-12]
        self.assertTrue(all(v['status']=='evidence_insufficient' for v in self.check(c,rows)['tiers'].values()))

    def test_bounds_never_negative_and_threshold_overlap(self):
        self.assertEqual(error_bounds(1.,1.,1.,.1),(0.,.1))
        c=CARDS['SH-T-LONG'];rows=sample_rows(c)
        for r in rows:r['y']+=1.01e-6
        self.assertEqual(self.check(c,rows)['tiers']['Q2']['status'],'evidence_insufficient')

    def test_plan_preserves_critical_identity_and_does_not_change_models(self):
        c=CARDS['SH-T-RAMP'];before=copy.deepcopy(c);plan=observation_plan(c,CONTRACT)
        self.assertEqual(c,before)
        self.assertGreater(len(plan['times_s']),40000)
        self.assertTrue(all(p['time_s'] in plan['times_s'] for p in plan['critical']))
        self.assertEqual(plan['target_tier'],'Q3')

    def test_cross_positive_early_and_expression_tolerance(self):
        c=CARDS['SH-X-RAMP']
        self.assertTrue(all(v['status']=='pass' for v in self.check(c,sample_rows(c))['tiers'].values()))
        self.assertEqual(self.check(c,sample_rows(c,-.5e-12))['behavior']['status'],'behavior_error')
        c=copy.deepcopy(c);c['cross_expression_tolerance_V']=1e-9
        self.assertEqual(self.check(c,sample_rows(c))['behavior']['status'],'behavior_error')

    def test_exact_timer_boundary_needs_bound_independent_evidence(self):
        c=CARDS['SH-T-RAMP'];rows=sample_rows(c,-100e-12)
        self.assertTrue(all(v['status']!='pass' for v in self.check(c,rows)['tiers'].values()))
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);artifact=base/'independent.txt';artifact.write_text('synthetic calibration, not actual backend evidence')
            data={'method':'independent_callback_trace','waveform_rows_sha256':rows_digest(rows),
                  'artifact':artifact.name,'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
                  'events':[{'index':k,'time_bounds_s':[str(Fraction(t-100e-12))]*2} for k,t in enumerate(c['events_s'],1)]}
            path=base/'proof.json';path.write_text(json.dumps(data))
            result=assess(c,rows,CONTRACT,event_evidence_path=path)
            self.assertTrue(all(v['status']=='pass' for v in result['tiers'].values()),result)
            valid=copy.deepcopy(data)
            data['events'].append({'index':c['expected_events']+1,'time_bounds_s':['0','0']})
            path.write_text(json.dumps(data))
            self.assertTrue(all(v['status']!='pass' for v in assess(c,rows,CONTRACT,event_evidence_path=path)['tiers'].values()))
            data=copy.deepcopy(valid);data['events'][0]['time_bounds_s']=['0','0'];path.write_text(json.dumps(data))
            conflict=assess(c,rows,CONTRACT,event_evidence_path=path)
            self.assertIn('event 1 independent time conflicts', '\n'.join(conflict['observation_issues']))
            self.assertTrue(all(v['status']!='pass' for v in conflict['tiers'].values()))
            data=valid
            data['waveform_rows_sha256']='bad';path.write_text(json.dumps(data))
            self.assertTrue(all(v['status']!='pass' for v in assess(c,rows,CONTRACT,event_evidence_path=path)['tiers'].values()))

    def test_first_order_grades_independent_closed_form_trajectories(self):
        for key in ('LP-RAMP','LP-NONZERO','LP-SMALL','LP-IDT'):
            c=CARDS[key];points=c['inputs']['u'];rows=[]
            def reference(t):
                y=c['initial_V'];tau=c['tau_s']
                for (a,u),(b,v) in zip(points,points[1:]):
                    h=min(t,b)-a
                    if h<0:break
                    slope=(v-u)/(b-a);w=-math.expm1(-h/tau)
                    y=y*(1-w)+u*w+slope*(h-tau*w)
                    if t<=b:return y
                return y
            for t in observation_plan(c,CONTRACT)['times_s']:
                # Independent linear interpolation for the synthetic stimulus.
                for (a,u),(b,v) in zip(points,points[1:]):
                    if t<=b:break
                rows.append({'time':t,'u':u+(v-u)*(t-a)/(b-a),'y':reference(t)})
            r=self.check(c,rows)
            self.assertEqual([v['status'] for v in r['tiers'].values()],['pass']*3,r)
            for row in rows:row['y']+=2*(1e-8+1e-6*c['scale_V'])
            self.assertEqual([v['status'] for v in self.check(c,rows)['tiers'].values()],['pass','numerical_error','numerical_error'])

    def test_reference_and_export_uncertainty_cannot_qualify(self):
        c=copy.deepcopy(CARDS['LP-NONZERO']);c['inputs']={'u':[[0.,.25],[c['stop_s'],.25]]}
        rows=[{'time':t,'u':.25,'y':.25} for t in observation_plan(c,CONTRACT)['times_s']]
        with patch('precision_v2.FirstOrder.bounds',return_value=(.25-1e-8,.25+1e-8)):
            result=self.check(c,rows)
            self.assertEqual(result['tiers']['Q2']['status'],'evidence_insufficient')
            self.assertIn('reference uncertainty exceeds tier limit',result['tiers']['Q2']['reasons'])
        contract=copy.deepcopy(CONTRACT);contract['budgets']['voltage_serialization_ulps']=10**10
        self.assertTrue(all(v['status']!='pass' for v in assess(c,rows,contract)['tiers'].values()))


class IndependentReferences(unittest.TestCase):
    def test_pwl_exact_corners_and_interior_extremum(self):
        lo,hi,u=pwl_range([[0.,0.],[1.,1.],[2.,0.]],.5,1.5)
        self.assertEqual((lo,hi),(.5,1.));self.assertLess(u,1e-15)

    def test_filter_known_constant_ramp_and_nonzero(self):
        c=copy.deepcopy(CARDS['LP-RAMP']);c.update(tau_s=1.,initial_V=0.)
        c['inputs']={'u':[[0.,0.],[8.,8.]]};ref=FirstOrder(c)
        for t in (0.,.125,1.,4.,8.):
            lo,hi=ref.bounds(t);answer=t-1+math.exp(-t)
            self.assertLess(abs((lo+hi)/2-answer),2e-15)
            self.assertLess(hi-lo,3e-14)
        c['inputs']={'u':[[0.,.25],[8.,.25]]};c['initial_V']=.25;ref=FirstOrder(c)
        for t in (0.,1.,8.):self.assertEqual(ref.bounds(t),(.25,.25))

    def test_filter_initial_state_does_not_reset_at_corner(self):
        c=copy.deepcopy(CARDS['LP-NONZERO']);ref=FirstOrder(c)
        for t,_ in c['inputs']['u'][1:-1]:
            left=ref.bounds(math.nextafter(t,-math.inf));right=ref.bounds(math.nextafter(t,math.inf))
            self.assertLess(abs(left[0]-right[1]),1e-14)


if __name__=='__main__': unittest.main()
