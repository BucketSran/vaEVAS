"""Calibrate engineering checks with deliberately correct and faulty traces."""
import copy
import json
import math
from pathlib import Path
import unittest

from precision_checker import FirstOrder, assess, pwl

DATA=json.loads(Path(__file__).with_name('precision-v1.json').read_text())
CARDS={c['id']:c for c in DATA['cards']}
BUDGETS=DATA['budgets']


def points(card):
    step=card['unit_s']/32
    ts={0.,card['stop_s'],*(i*step for i in range(math.ceil(card['stop_s']/step)))}
    for pts in card['inputs'].values():
        for t,v in pts:ts.update([t-1e-12,t,t+1e-12])
    for t in card.get('events_s',[]):
        ts.update(t+i*1e-12 for i in range(-105,106))
    return sorted(t for t in ts if 0<=t<=card['stop_s'])


def sample_rows(card, shift=5e-11):
    events=[t+shift for t in card['events_s']]
    rows=[]
    for t in points(card):
        n=sum(e<=t for e in events)
        # Direct piecewise answer, independent of the checker's event bracket logic.
        if not n:y=card['initial_V']
        elif card['id']=='SH-T-LONG':y=.2
        else:
            x=events[n-1]/card['unit_s']
            y=card['scale_V']*((-.4+.2*x) if x<=4 else (1.2-.2*x) if x<=8 else (-.4+.2*(x-8)))
        rows.append({'time':t,'count':float(n),'y':y,**{k:pwl(v,t) for k,v in card['inputs'].items()}})
    return rows


class PrecisionChecks(unittest.TestCase):
    def test_sample_hold_legal_late_callbacks_and_near_zero(self):
        for c in DATA['cards'][:4]:
            with self.subTest(c=c['id']):
                self.assertEqual(assess(c,sample_rows(c),BUDGETS)['status'],'pass')

    def test_early_timer_and_illegal_cross(self):
        c=CARDS['SH-T-RAMP']
        self.assertEqual(assess(c,sample_rows(c,shift=-5e-11),BUDGETS)['status'],'pass')
        c=copy.deepcopy(CARDS['SH-X-RAMP']);c['cross_expression_tolerance_V']=1e-9
        self.assertEqual(assess(c,sample_rows(c,shift=5e-11),BUDGETS)['status'],'behavior_error')

    def test_missing_filter_corner(self):
        c=CARDS['LP-RAMP'];ref=FirstOrder(c)
        rows=[{'time':t,'u':pwl(c['inputs']['u'],t),'y':ref.value(t)} for t in points(c) if abs(t-2e-6)>3e-12]
        self.assertEqual(assess(c,rows,BUDGETS)['status'],'evidence_insufficient')

    def test_pwl_corners_and_hold(self):
        pts=[[0.,-.4],[4e-6,.4],[8e-6,-.4]]
        for t,v in [(0,-.4),(2e-6,0.),(4e-6,.4),(6e-6,0.),(9e-6,-.4)]:
            self.assertAlmostEqual(pwl(pts,t),v,places=15)

    def test_missing_or_repeated_event_rejected(self):
        c=CARDS['SH-T-RAMP']; rows=sample_rows(c)
        for r in rows:
            if r['count']>=3:r['count']+=1
        self.assertEqual(assess(c,rows,BUDGETS)['status'],'behavior_error')

    def test_previous_sample_and_tracking_input_rejected(self):
        c=CARDS['SH-T-RAMP']
        for kind in ('old','tracking'):
            rows=sample_rows(c)
            for r in rows:
                if r['count']:
                    r['y']=r['u'] if kind=='tracking' else -.123
            self.assertEqual(assess(c,rows,BUDGETS)['status'],'numerical_error')

    def test_output_before_counter_is_not_excused_by_time_window(self):
        c=CARDS['SH-T-RAMP']; rows=sample_rows(c)
        for r in rows:
            if c['events_s'][0]<=r['time']<c['events_s'][0]+5e-11:r['y']=-.2
        self.assertEqual(assess(c,rows,BUDGETS)['status'],'behavior_error')

    def test_outside_event_window_rejected(self):
        c=CARDS['SH-T-RAMP']; rows=sample_rows(c,shift=4e-10)
        self.assertEqual(assess(c,rows,BUDGETS)['status'],'behavior_error')

    def test_wide_callback_bracket_is_inconclusive(self):
        c=CARDS['SH-T-RAMP']; rows=sample_rows(c)
        t=c['events_s'][0]
        rows=[r for r in rows if not t+1e-11<r['time']<t+9e-11]
        self.assertEqual(assess(c,rows,BUDGETS)['status'],'evidence_insufficient')

    def test_input_failure_not_blended_into_output_budget(self):
        c=CARDS['SH-T-RAMP']; rows=sample_rows(c)
        rows[len(rows)//2]['u']+=1e-5
        self.assertEqual(assess(c,rows,BUDGETS)['status'],'input_mismatch')

    def test_first_order_against_unit_ramp_closed_form(self):
        c=copy.deepcopy(CARDS['LP-RAMP']);c.update(unit_s=1.,stop_s=8.,tau_s=1.,scale_V=8.)
        c['inputs']={'u':[[0.,0.],[8.,8.]]}
        reference=FirstOrder(c)
        for t in [0.,.125,1.,4.,8.]:
            self.assertAlmostEqual(reference.value(t),t-1+math.exp(-t),places=14)
        rows=[{'time':i/32,'u':i/32,'y':i/32-1+math.exp(-i/32)} for i in range(257)]
        self.assertEqual(assess(c,rows,BUDGETS)['status'],'pass')
        for r in rows:r['y']+=1e-3
        self.assertEqual(assess(c,rows,BUDGETS)['status'],'numerical_error')

    def test_nonzero_dc_and_incomplete_extent(self):
        c=copy.deepcopy(CARDS['LP-NONZERO']);c['inputs']={'u':[[0.,.25],[c['stop_s'],.25]]}
        rows=[{'time':t,'u':.25,'y':.25} for t in points(c)]
        self.assertEqual(assess(c,rows,BUDGETS)['status'],'pass')
        self.assertEqual(assess(c,rows[:-1],BUDGETS)['status'],'evidence_insufficient')
        rows[0]['y']=0.
        self.assertEqual(assess(c,rows,BUDGETS)['status'],'numerical_error')


if __name__=='__main__':unittest.main()
