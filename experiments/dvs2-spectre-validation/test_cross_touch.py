"""Synthetic calibration; no EVAS or Spectre execution."""
import copy
from fractions import Fraction as Q
import unittest
from cross_touch import audit_settings, classify, inspect, inspect_arrivals, monitors, pwl, roots, specifications


def observations(case, touch='none'):
    rows=[]
    rate=Q(case['inputs']['clock'][-1][1])/Q(case['stop'])
    for t in case['output_times']:
        row={name:float(pwl(points,Q(t))) for name,points in case['inputs'].items()}
        row['time']=t
        for m in monitors():
            events=[r for r,w in roots(case,m)]
            if m['valley']=='touch':
                dirs=[]
                if touch in ['arrival','both']: dirs.append(-m['polarity'])
                if touch in ['departure','both']: dirs.append(m['polarity'])
                events=[Q(case['center']) for d in dirs if not m['direction'] or d==m['direction']]
            elapsed=[r for r in events if r<=Q(t)]
            key=m['id'];row['n_'+key]=len(elapsed)
            row['t_'+key]=float(elapsed[-1]*rate) if elapsed else 0.
            row['g_'+key]=0.
        rows.append(row)
    return rows


class TouchCalibration(unittest.TestCase):
    def test_arrival_contract_accepts_both_polarities(self):
        for case in specifications():
            result=inspect_arrivals(observations(case,'arrival'),case)
            self.assertEqual(sum(m['status']=='control_pass' for m in result['monitors']),12)
            self.assertEqual(sum(m['status']=='arrival_pass' for m in result['monitors']),6)

    def test_arrival_contract_rejects_other_touch_hypotheses(self):
        for style in ['none','departure','both']:
            case=specifications()[0]
            with self.subTest(style=style):
                result=inspect_arrivals(observations(case,style),case)
                self.assertTrue(any(m['status']=='failed' for m in result['monitors']))

    def test_arrival_contract_checks_touch_history_and_samples(self):
        case=specifications()[0]
        for fault in ['premature_count','delayed_count','early_stamp','late_stamp','bad_guard','decreasing_count']:
            rows=observations(case,'arrival');i=next(i for i,r in enumerate(rows) if r['time']==case['center'])
            key='touch_pos_both'
            if fault=='premature_count':
                for prefix in ['n_','t_','g_']: rows[i-1][prefix+key]=rows[i][prefix+key]
            if fault=='delayed_count':
                for j in [i,i+1]:
                    for prefix in ['n_','t_','g_']: rows[j][prefix+key]=0.
            if fault=='early_stamp': rows[i]['t_'+key]-=.001
            if fault=='late_stamp': rows[i]['t_'+key]+=.001
            if fault=='bad_guard': rows[i]['g_'+key]=.01
            if fault=='decreasing_count': rows[-1]['n_'+key]=0
            with self.subTest(fault=fault):
                self.assertTrue(any(m['status']=='failed' for m in inspect_arrivals(rows,case)['monitors']))

    def test_rounded_stop_log_requires_matching_waveform_endpoint(self):
        case=specifications()[6]
        log='vabstol = 1e-10\niabstol = 1e-14\nreltol = 1e-8\nstop = 3.00004 us\nstep = 100 ns\nmaxstep = 100 ns\nmethod = traponly\n'
        _,audit=audit_settings(log,case,observations(case))
        self.assertFalse(audit['exact_log_match'])
        self.assertTrue(audit['waveform_matches_requested'])
        rows=observations(case);rows[-1]['time']=3.00004e-6
        with self.assertRaisesRegex(ValueError,'waveform stop mismatch'): audit_settings(log,case,rows)

    def test_metadata_repair_does_not_accept_wrong_settings(self):
        case=specifications()[6]
        log='vabstol = 1e-10\niabstol = 1e-14\nreltol = 1e-8\nstop = 3.00004 us\nstep = 100 ns\nmaxstep = 100 ns\nmethod = traponly\n'
        for bad in [log.replace('3.00004','3.00005'),log.replace('maxstep = 100','maxstep = 200'),
                    log.replace('traponly','gear2only'),log.replace('vabstol = 1e-10','vabstol = 1e-6')]:
            with self.subTest(log=bad),self.assertRaises(ValueError): audit_settings(bad,case,observations(case))

    def test_hand_answers_and_root_separation(self):
        specs=specifications();self.assertEqual(len(specs),12);self.assertEqual(len(monitors()),18)
        case=specs[0]
        probe=next(m for m in monitors() if m['id']=='below_pos_both')
        r=roots(case,probe)
        self.assertAlmostEqual(float(r[0][0]),1.5e-6*100/101,delta=1e-19)
        self.assertAlmostEqual(float(r[1][0]),3e-6-1.5e-6*100/101,delta=1e-19)
        for case in specs:
            r=roots(case,probe)
            self.assertGreater(r[1][0]-r[0][0],100*Q(case['ttol']))
            for m in monitors():
                self.assertEqual(len(roots(case,m)),(2 if m['direction']==0 else 1) if m['valley']=='below' else 0)

    def test_touch_hypotheses_are_classified_without_selecting_a_winner(self):
        for case in specifications():
            for style,label in [('none','no_touch_event'),('arrival','arrival_direction_once'),
                                ('departure','departure_direction_once'),('both','both_directions')]:
                with self.subTest(case=case['id'],style=style):
                    result=inspect(observations(case,style),case)
                    self.assertEqual(set(result['touch_classification'].values()),{label})
                    self.assertFalse(any(m['status']=='failed' for m in result['monitors']))
        self.assertEqual(classify([3,1,2],1),'other')

    def test_wrong_histories_and_timing_fail(self):
        case=specifications()[0]
        for fault in ['extra_above','missing_below','early_stamp','late_stamp','bad_guard','decreasing_count']:
            rows=observations(case,'arrival');i=next(i for i,r in enumerate(rows) if r['time']==case['center'])
            if fault=='extra_above': rows[-1]['n_above_pos_both']=1
            if fault=='missing_below': rows[i]['n_below_pos_both']=0
            if fault=='early_stamp': rows[i]['t_below_pos_both']-=.001
            if fault=='late_stamp': rows[i]['t_below_pos_both']+=.001
            if fault=='bad_guard': rows[i]['g_below_pos_both']=.01
            if fault=='decreasing_count': rows[-1]['n_below_pos_both']=0
            with self.subTest(fault=fault):
                self.assertTrue(any(m['status']=='failed' for m in inspect(rows,case)['monitors']))

    def test_invalid_observation_sets_fail(self):
        case=specifications()[0]
        for fault in ['empty','truncated','nan','reordered','missing','wrong_input']:
            rows=copy.deepcopy(observations(case))
            if fault=='empty': rows=[]
            if fault=='truncated': rows.pop()
            if fault=='nan': rows[2]['n_above_pos_both']=float('nan')
            if fault=='reordered': rows[2],rows[3]=rows[3],rows[2]
            if fault=='missing': rows[2].pop('clock')
            if fault=='wrong_input': rows[2]['touch']+=.01
            with self.subTest(fault=fault),self.assertRaises(ValueError): inspect(rows,case)
