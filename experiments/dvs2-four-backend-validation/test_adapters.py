"""Adapter calibration: physical stimuli, multi-module wiring and ground mapping."""
import json
from pathlib import Path
import re
import unittest
from build_inputs import ROOT, netlists, selected

SOURCE=ROOT/'runs/dvs2-spectre-20260928-01'
CASES=json.loads((SOURCE/'conditions.json').read_text())

class AdapterCalibration(unittest.TestCase):
    def test_budget_and_exact_unchanged_inputs(self):
        self.assertEqual([sum(selected(c,b) for c in CASES)*2 for b in ['evas','openvaf_ngspice','gnucap']],[34,34,62])
        for c in CASES:
            for setting in ['base','fine']:
                p=json.loads((SOURCE/'runs'/c['id']/setting/'requested_settings.json').read_text())
                decks=netlists(c,p)
                for deck in decks.values():
                    for name,points in c['inputs'].items():
                        match=re.search(r'^V'+name+r' '+name+r' 0 PWL\(([^)]+)\)$',deck,re.M)
                        self.assertIsNotNone(match)
                        numbers=list(map(float,match[1].split()))
                        self.assertEqual(numbers,[v for x,y in points for v in (x*1e-6,y)])
                    self.assertNotIn('uic',deck.lower())
                    self.assertNotIn('linearize',deck.lower())
                self.assertIn('short=1e-9',decks['tb.gc'])
                self.assertIn('v(bench_ref)',decks['tb.gc'])
    def test_multi_module_and_parameter_binding(self):
        c=next(c for c in CASES if c['id']=='c2-main')
        p=json.loads((SOURCE/'runs/c2-main/base/requested_settings.json').read_text())
        decks=netlists(c,p)
        self.assertIn('N0 vin z 0 model0',decks['tb.cir'])
        self.assertIn('N1 z clk rst vout 0 model1',decks['tb.cir'])
        self.assertIn('.model model0 dvs_v6',decks['tb.cir'])
        self.assertIn('.model model1 dvs_sampler',decks['tb.cir'])
        self.assertIn('filter(vin,z,bench_ref);',decks['tb.gc'])
        self.assertIn('sampler(z,clk,rst,vout,bench_ref);',decks['tb.gc'])
        c=next(c for c in CASES if c['id']=='s1-override')
        self.assertIn('.g1(-0.5)',netlists(c,p)['tb.gc'])
        self.assertIn('g1=-0.5',netlists(c,p)['tb.cir'])
    def test_dynamic_reference_is_not_replaced(self):
        c=next(c for c in CASES if c['id']=='v2-main')
        p=json.loads((SOURCE/'runs/v2-main/base/requested_settings.json').read_text())
        gc=netlists(c,p)['tb.gc']
        self.assertIn('dut(vip,vin,vdd,vref,op,on);',gc)
        self.assertIn('Vvref vref 0 PWL(',gc)
        self.assertIn('Vbench_ref bench_ref 0 0',gc)

if __name__=='__main__':unittest.main()
