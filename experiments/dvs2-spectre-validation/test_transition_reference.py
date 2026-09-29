import copy
import unittest
from transition_reference import cases, check, expected, TTOL, UNIT


def reference(c):
    rows=[]
    for t in c['output_times']:
        x=t/UNIT
        row=dict(time=t,y=expected(c,x),q=c['initial']+sum(d for e,d in zip(c['times'],c['changes']) if x>=e))
        row.update({f'h{i}':c['times'][i-1] if i<=len(c['times']) and x>=c['times'][i-1] else -1 for i in [1,2]})
        rows.append(row)
    return rows


class TransitionChecker(unittest.TestCase):
    def test_common_grid_requires_each_requested_time(self):
        c=cases()[0]; rows=reference(c)
        self.assertEqual(check(c,rows,True)['common_grid_points'],257)
        del rows[3]
        self.assertEqual(check(c,rows)['status'],'finite_consistent')
        with self.assertRaisesRegex(ValueError,'missing common observation time'):
            check(c,rows,True)

    def test_independent_knots_and_reflection(self):
        for c in cases():
            self.assertEqual(check(c,reference(c))['status'],'finite_consistent')
        c=next(c for c in cases() if c['name']=='reverse')
        self.assertAlmostEqual(expected(c,10),.2)
        c=next(c for c in cases() if c['name']=='extend')
        self.assertAlmostEqual(expected(c,10),1.2)

    def test_rejects_amplitude_target_stamp_loss_and_missing_edge(self):
        c=cases()[0]; good=reference(c)
        bads=[]
        for key,delta in [('y',.01),('q',1),('h1',.1)]:
            rows=copy.deepcopy(good); rows[-1][key]+=delta; bads.append(rows)
        bads.extend([good[:-1],list(reversed(good)),[good[0],good[1],good[-1]]])
        for rows in bads:
            with self.assertRaises(ValueError): check(c,rows)

    def test_small_phase_shift_inside_frozen_allowance(self):
        for c in cases():
            rows=reference(c)
            for r in rows: r['y']=expected(c,max(0,(r['time']-TTOL/2)/UNIT))
            check(c,rows)
