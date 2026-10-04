"""Calibration of the analytic history/calendar checker."""
import copy
import math
import unittest
from history_relocalization import inspect, reference, source, specs


class HistoryReference(unittest.TestCase):
    def rows(self, c):
        times=sorted({*[i*c['maxstep'] for i in range(round(c['stop']/c['maxstep'])+1)],*c['roots']})
        return [dict(time=t,u=t,y=sum(t>=r for r in c['roots']),z=reference(c,t)) for t in times]

    def test_all_exact_answers(self):
        for c in specs():
            with self.subTest(c=c['id']): self.assertTrue(inspect(self.rows(c),c)['pass_'])

    def test_spectre_real_literals_have_a_leading_digit(self):
        for c in specs():
            self.assertNotRegex(source(c), r'(?<![\w.])\.(\d)')

    def test_wrong_history_and_missing_extra_or_shifted_events(self):
        c=specs()[0];good=self.rows(c)
        bad=copy.deepcopy(good);bad[-1]['z']+=1e-3
        self.assertFalse(inspect(bad,c)['pass_'])
        for kind in ['missing','extra','shift','nan','truncated']:
            with self.subTest(kind=kind):
                bad=copy.deepcopy(good)
                if kind=='missing':
                    for row in bad:row['y']=0
                elif kind=='extra':bad[-1]['y']+=1
                elif kind=='shift':
                    for row in bad:row['y']=int(row['time']>=.6)
                elif kind=='nan':bad[1]['z']=math.nan
                else:bad.pop()
                with self.assertRaises(ValueError):inspect(bad,c)


if __name__=='__main__':unittest.main()
