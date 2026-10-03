import copy
import math
import unittest
import timer_settlement as s


class SettlementChecker(unittest.TestCase):
    def case_rows(self,family='chains'):
        c=next(c for c in s.specifications() if c['family']==family)
        _,_,targets=s.design(c)
        rows=[]
        for t in c['output_times']:
            fired=t>=8*s.U
            r=dict(time=t,clock=t/s.U)
            for p in targets:
                r.update({ 'n_'+p['id']:float(fired), 'h_'+p['id']:8. if fired else -1.,
                           'o_'+p['id']:p['expected'] if fired else 0.})
            rows.append(r)
        return c,rows

    def test_analytic_closure_and_finite_time_shift(self):
        for family in ['chains','feedback']:
            c,rows=self.case_rows(family)
            for r in rows:
                for k in r:
                    if k.startswith('h_') and r[k]>0: r[k]-=c['ttol']/s.U/4
            self.assertTrue(all(r['status']=='candidate_consistent' for r in s.inspect(rows,c)['records']))

    def test_old_snapshot_is_a_difference_not_invalid_history(self):
        c,rows=self.case_rows()
        for r in rows: r['o_c']=0.
        result=s.inspect(rows,c)
        self.assertEqual(next(r for r in result['records'] if r['id']=='c')['status'],'candidate_differs')

    def test_duplicate_missing_and_unheld_samples_are_rejected(self):
        c,rows=self.case_rows()
        for field,value in [('n_a',2.),('h_a',9.),('o_a',0.25)]:
            bad=copy.deepcopy(rows); bad[-1][field]=value
            self.assertEqual(s.inspect(bad,c)['records'][0]['status'],'finite_inconsistent')

    def test_bad_input_missing_nonfinite_and_truncated_are_rejected(self):
        c,rows=self.case_rows()
        for field,value in [('clock',0.),('n_a',math.nan)]:
            bad=copy.deepcopy(rows); bad[-1][field]=value
            with self.assertRaises(ValueError): s.inspect(bad,c)
        with self.assertRaises(ValueError): s.inspect(rows[:-1],c)
        del rows[-1]['h_a']
        with self.assertRaises(ValueError): s.inspect(rows,c)

    def test_extended_analytic_candidates_and_wrong_sequence_result(self):
        for c in s.specifications(extended=True)+s.specifications(sequence_controls=True)+s.specifications(counter_rewrite=True):
            _,_,targets=s.design(c)
            rows=[]
            for t in c['output_times']:
                fired=t>=8*s.U
                r=dict(time=t,clock=t/s.U)
                for p in targets:
                    r.update({'n_'+p['id']:float(fired),'h_'+p['id']:8. if fired else -1.,
                              'o_'+p['id']:p['expected'] if fired else 0.})
                rows.append(r)
            self.assertTrue(all(r['status']=='candidate_consistent' for r in s.inspect(rows,c)['records']))
            for row in rows:
                if row['time']>=8*s.U: row['o_'+targets[0]['id']]=1.
            self.assertEqual(s.inspect(rows,c)['records'][0]['status'],'candidate_differs')


if __name__=='__main__': unittest.main()
