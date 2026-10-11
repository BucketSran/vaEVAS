import copy
import math
import unittest
from near_timer import CASES, STROBES, assess, clocks, continuous
from fractions import Fraction as F

class NearTimerChecker(unittest.TestCase):
    def rows(self,case):
        return [dict(time=t,y=sum(w for c,w,_ in clocks() if c<=F.from_float(t)),
                     **({**{k:continuous(t,k) for k in 'efi'},'h':sum(d for c,_,d in clocks() if c<=F.from_float(t))} if case['chain'] else {})) for t in STROBES]
    def test_positive_and_negative_controls(self):
        for case in CASES:
            good=self.rows(case)
            self.assertEqual(assess(case,good)['status'],'pass')
            for index,node,value in [(7,'y',51),(4,'y',13),(-1,'y',41),(0,'y',math.nan)]:
                bad=copy.deepcopy(good);bad[index][node]=value
                self.assertEqual(assess(case,bad)['status'],'fail')
            self.assertEqual(assess(case,good[:-1])['status'],'fail')
            if case['chain']:
                for node in 'hefi':
                    bad=copy.deepcopy(good);bad[7][node]+=.01
                    self.assertEqual(assess(case,bad)['status'],'fail')
                for value in [.15,.21]:
                    bad=copy.deepcopy(good);bad[5]['h']=value
                    self.assertEqual(bad[5]['y'],11)
                    self.assertEqual(assess(case,bad)['status'],'fail')
                # Each node retains its own 1 uV allowance around one common
                # discrete state; output measurement errors do not compound.
                valid=copy.deepcopy(good)
                valid[5].update(y=10.9999991,h=.110000999)
                self.assertEqual(assess(case,valid)['status'],'pass')

if __name__=='__main__':unittest.main()
