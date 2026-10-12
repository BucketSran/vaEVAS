import math
import unittest

from primitives import T, assess, bounds, cards, reference


class Calibration(unittest.TestCase):
    def test_exact_anchors_and_domains(self):
        for f,x,y,e in [('sin',0,0,3),('cos',0,1,3),('exp',0,1,3),
                        ('ln',1,0,3),('sqrt',4,2,3),('pow',-2,-8,3),('pow',4,2,.5)]:
            lo,hi=bounds(f,x,e)
            self.assertLessEqual(lo,y)
            self.assertGreaterEqual(hi,y)
            self.assertLess(hi-lo,1e-13)
        for f,x in [('ln',0),('ln',-1),('sqrt',-1),('sin',14)]:
            with self.assertRaises(ValueError): bounds(f,x)

    def test_trigonometric_symmetry_and_extrema(self):
        for x in (math.pi/2, math.pi, 4*math.pi):
            a,b=bounds('sin',x); c,d=bounds('sin',-x)
            self.assertEqual((a,b),(-d,-c))
            self.assertEqual(bounds('cos',x),bounds('cos',-x))
            self.assertLess(b-a,1e-13)

    def test_independent_nonzero_anchors(self):
        # Fixed constants do not come from the reference under test. Symmetry
        # and oracle-generated controls alone cannot detect a scaled oracle.
        for function,x,value in [('sin',1,0.8414709848078965),
                                  ('cos',1,0.5403023058681397),
                                  ('sin',math.pi/2,1.),('cos',math.pi,-1.),
                                  ('exp',1,2.718281828459045),
                                  ('ln',2,0.6931471805599453),
                                  ('sqrt',2,1.4142135623730951)]:
            lo,hi=bounds(function,x)
            self.assertLess(abs(lo-value),1e-14)
            self.assertLess(abs(hi-value),1e-14)
        lo,hi=bounds('pow',2,.5)
        self.assertLess(abs(lo-1.4142135623730951),1e-14)
        self.assertLess(abs(hi-1.4142135623730951),1e-14)

    def test_trigonometric_tail_range_boundary(self):
        # Independent binary64 library values are calibration anchors, not
        # the oracle used for backend grading. Also calibrate the hard range.
        for function,operation in [('sin',math.sin),('cos',math.cos)]:
            for x in (-13.,-7.5,7.5,13.):
                lo,hi=bounds(function,x)
                self.assertLess(abs(lo-operation(x)),1e-14)
                self.assertLess(abs(hi-operation(x)),1e-14)

    def control(self, card):
        from precision_reference import pwl_exact
        rows=[]
        for i in range(round(card['stop_s']/T)*16+1):
            t=i*T/16; lo,hi=reference(card,t)
            rows.append({'time':t,'u':float(pwl_exact(card['inputs']['u'],t)), 'y':(lo+hi)/2})
        return rows

    def test_accept_all_cards_and_tiers(self):
        for card in cards():
            for tier in ('Q1','Q2','Q3'):
                with self.subTest(card=card['id'],tier=tier):
                    self.assertEqual(assess(card,self.control(card),tier)['status'],'pass')

    def test_reject_wrong_output_and_input(self):
        for card in cards():
            rows=self.control(card); rows[len(rows)//2]['y']+=1e-3
            self.assertEqual(assess(card,rows,'Q3')['status'],'numerical_error')
        card=cards()[0]; rows=self.control(card); rows[2]['u']+=1e-3
        self.assertNotEqual(assess(card,rows,'Q3')['status'],'pass')

    def test_missing_corner_and_observation_gap(self):
        card=cards()[0]; rows=self.control(card)
        self.assertEqual(assess(card,rows[1:],'Q1')['status'],'evidence_insufficient')
        self.assertEqual(assess(card,[rows[0],rows[-1]],'Q1')['status'],'evidence_insufficient')
        self.assertEqual(assess(card,[],'Q1')['status'],'evidence_insufficient')
        for time in (-1e-9,card['stop_s']+T):
            outside=[*rows,dict(rows[-1],time=time)]
            self.assertEqual(assess(card,outside,'Q1')['issues'],['observation outside frozen time range'])

    def test_near_zero_input_error_cannot_hide_sqrt_error(self):
        for card in (c for c in cards() if c['function']=='sqrt' or c['id']=='P-pow-half'):
            rows=self.control(card); rows[0].update(u=7e-15,y=-5e-8)
            self.assertEqual(assess(card,rows,'Q3')['status'],'numerical_error')

    def test_budget_overlap_is_inconclusive(self):
        from primitives import TIERS
        card=cards()[0]; rows=self.control(card)
        zero=next(r for r in rows if r['u']==0.)
        zero['y']=TIERS['Q3']-1e-15
        result=assess(card,rows,'Q3')
        self.assertEqual(result['status'],'evidence_insufficient')
        self.assertLess(result['error_lower_V'],TIERS['Q3'])
        self.assertGreater(result['error_upper_V'],TIERS['Q3'])

    def test_integrated_input_uncertainty_prevents_false_pass(self):
        from primitives import TIERS
        card=next(c for c in cards() if c['function']=='idt');rows=self.control(card)
        for row in rows:
            row['u']-=7e-15;row['y']+=TIERS['Q3']-1e-14
        self.assertEqual(assess(card,rows,'Q3')['status'],'evidence_insufficient')

    def test_integral_signed_area_and_derivative(self):
        card=next(c for c in cards() if c['function']=='idt')
        lo,hi=reference(card,3*T)
        from fractions import Fraction
        expected=Fraction(.125)+sum((Fraction(u)+Fraction(v))*(Fraction(b)-Fraction(a))/(2*Fraction(T))
                                   for (a,u),(b,v) in zip(card['inputs']['u'],card['inputs']['u'][1:]))
        self.assertLessEqual(Fraction(lo),expected); self.assertGreaterEqual(Fraction(hi),expected)
        # Independently hand-integrated half of the first linear ramp.
        lo,hi=reference(card,T/2)
        self.assertLessEqual(lo,.25); self.assertGreaterEqual(hi,.25)
        card=next(c for c in cards() if c['function']=='ddt')
        lo,hi=reference(card,2*T)
        self.assertLessEqual(lo,4.); self.assertGreaterEqual(hi,4.)
