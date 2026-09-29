"""Adapter controls using current frozen conditions, without a private old archive."""
import unittest
import re
from matrix import conditions, PROFILES, T, netlists


class MatrixAdapters(unittest.TestCase):
    def test_all_physical_inputs_and_fixed_denominator(self):
        cases=conditions()
        self.assertEqual(len(cases)*len(PROFILES)*4,248)
        for c in cases:
            for p in PROFILES.values():
                decks=netlists(c,dict(p,stop=c['stop_x']*T,maxstep=p['step']))
                for deck in decks.values():
                    for name,points in c['inputs'].items():
                        m=re.search(r'^V'+name+r' '+name+r' 0 PWL\(([^)]+)\)$',deck,re.M)
                        self.assertIsNotNone(m)
                        self.assertEqual(list(map(float,m[1].split())),[v for t,y in points for v in (t*T,y)])
                    self.assertNotIn('uic',deck.lower())
                    self.assertNotIn('linearize',deck.lower())
                self.assertIn('short=1e-9',decks['tb.gc'])
                self.assertIn('v(bench_ref)',decks['tb.gc'])

    def test_modules_and_parameters_preserved(self):
        cases={c['id']:c for c in conditions()}
        p=dict(PROFILES['base'],stop=4*T,maxstep=PROFILES['base']['step'])
        decks=netlists(cases['c2-main'],p)
        for text in ['N0 vin z 0 model0','N1 z clk rst vout 0 model1','.model model0 dvs_v6','.model model1 dvs_sampler']:
            self.assertIn(text,decks['tb.cir'])
        self.assertIn('filter(vin,z,bench_ref);',decks['tb.gc'])
        self.assertIn('sampler(z,clk,rst,vout,bench_ref);',decks['tb.gc'])
        self.assertIn('.g1(-0.5)',netlists(cases['s1-override'],p)['tb.gc'])

    def test_variable_reference_preserved(self):
        c=next(c for c in conditions() if c['id']=='v2-main')
        deck=netlists(c,dict(PROFILES['base'],stop=4*T,maxstep=PROFILES['base']['step']))['tb.gc']
        self.assertIn('dut(vip,vin,vdd,vref,op,on);',deck)
        self.assertIn('Vvref vref 0 PWL(',deck)
        self.assertIn('Vbench_ref bench_ref 0 0',deck)


if __name__=='__main__':unittest.main()
