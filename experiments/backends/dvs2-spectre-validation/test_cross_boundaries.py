"""Synthetic calibration of the frozen boundary candidate, no simulator calls."""
import copy
from fractions import Fraction as Q
import unittest
from cross_boundaries import expected, inspect, monitors, pwl, shapes, specifications


def observations(case):
    rows=[];rate=Q(case['inputs']['clock'][-1][1])/Q(case['stop'])
    for t in case['output_times']:
        row={name:float(pwl(points,Q(t))) for name,points in case['inputs'].items()}
        row['time']=t
        for m in monitors():
            elapsed=[r for r,w in expected(case,m) if r<=Q(t)]
            key=m['id'];row['n_'+key]=len(elapsed)
            row['t_'+key]=float(elapsed[-1]*rate) if elapsed else 0.
            row['g_'+key]=0.
        rows.append(row)
    return rows


class BoundaryCalibration(unittest.TestCase):
    def test_hand_counts_and_full_candidate(self):
        self.assertEqual(len(specifications()),6)
        self.assertEqual(len(shapes()),21)
        self.assertEqual(len(monitors()),63)
        for case in specifications():
            result=inspect(observations(case),case)
            self.assertEqual(result['summary'],dict(candidate_consistent=45,control_pass=18))
            answers={m['id']:m['expected_count'] for m in result['monitors']}
            self.assertEqual([answers['terminal_pos_'+d] for d in ['both','rising','falling']],[1,0,1])
            self.assertEqual([answers['plateau_cross_neg_'+d] for d in ['both','rising','falling']],[1,1,0])

    def test_missing_extra_wrong_direction_and_departure_are_visible(self):
        case=specifications()[0]
        for fault in ['missing_terminal','extra_departure','initial_event','wrong_direction','all_zero_event','missing_control']:
            rows=observations(case)
            if fault=='missing_terminal': rows[-1]['n_terminal_pos_both']=0
            if fault=='extra_departure': rows[-1]['n_plateau_return_pos_both']=2
            if fault=='initial_event': rows[0]['n_initial_plateau_pos_both']=1
            if fault=='wrong_direction': rows[-1]['n_terminal_pos_rising']=1
            if fault=='all_zero_event': rows[-1]['n_all_zero_both']=1
            if fault=='missing_control': rows[-1]['n_ordinary_pos_both']=0
            with self.subTest(fault=fault):
                self.assertTrue(any(m['status'] in ['candidate_inconsistent','control_failed'] for m in inspect(rows,case)['monitors']))

    def test_samples_and_history_are_checked(self):
        case=specifications()[0];key='plateau_return_pos_both'
        for fault in ['early','late','guard','decrease','fractional','premature','delayed','held_change']:
            rows=observations(case);i=next(i for i,r in enumerate(rows) if r['time']==1e-6)
            if fault=='early': rows[i]['t_'+key]-=.001
            if fault=='late': rows[i]['t_'+key]+=.001
            if fault=='guard': rows[i]['g_'+key]=.01
            if fault=='decrease': rows[-1]['n_'+key]=0
            if fault=='fractional': rows[i]['n_'+key]=.5
            if fault=='premature': rows[i-1]['n_'+key]=1
            if fault=='delayed':
                for j in [i,i+1]:
                    for p in ['n_','t_','g_']: rows[j][p+key]=0
            if fault=='held_change': rows[-1]['t_'+key]+=.001
            with self.subTest(fault=fault):
                self.assertTrue(any(m['status']=='candidate_inconsistent' for m in inspect(rows,case)['monitors']))

    def test_invalid_observations_fail(self):
        case=specifications()[0]
        for fault in ['empty','truncated','nonfinite','missing','reordered','input']:
            rows=copy.deepcopy(observations(case))
            if fault=='empty': rows=[]
            if fault=='truncated': rows.pop()
            if fault=='nonfinite': rows[1]['n_all_zero_both']=float('nan')
            if fault=='missing': rows[1].pop('clock')
            if fault=='reordered': rows[1],rows[2]=rows[2],rows[1]
            if fault=='input': rows[1]['terminal_pos']+=.01
            with self.subTest(fault=fault),self.assertRaises(ValueError): inspect(rows,case)
