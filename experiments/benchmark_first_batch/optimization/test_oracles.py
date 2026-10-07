"""Pure oracle calibration fixtures. These do not execute Verilog-A."""
import importlib.util
import json
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).parent


def oracle(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/name/'evaluate.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases=json.loads((ROOT/name/'cases.json').read_text())
    return module,cases


class Oracles(unittest.TestCase):
    def test_vco_phase_clamps_and_complete_cycles(self):
        module,cases=oracle('vco_boundstep')
        self.assertAlmostEqual(module.phase_cycles(cases[0]['stop'],cases[0]),159.2)
        self.assertAlmostEqual(module.phase_cycles(cases[2]['stop'],cases[2]),77.624)
        clamped=dict(cases[0],controls=[[0,-.5],[1e-6,-.5],[2e-6,1.5]])
        # First microsecond is 4 cycles. During the ramp the quarter intervals
        # are at fmin and fmax, and the middle half has their mean frequency.
        self.assertAlmostEqual(module.phase_cycles(2e-6,clamped),206.)

    def test_vco_waveform_and_errors(self):
        module,cases=oracle('vco_boundstep')
        case=cases[2]
        n=8192
        rows=[{'time':case['stop']*i/n,'out':module.expected(case['stop']*i/n,case)} for i in range(n+1)]
        self.assertTrue(module.evaluate(rows,case)['passed'])
        for factor in (0,.9,-1):
            wrong=[dict(row,out=case['offset']+factor*(row['out']-case['offset'])) for row in rows]
            self.assertFalse(module.evaluate(wrong,case)['passed'])
        sparse=rows[::512]
        self.assertFalse(module.evaluate(sparse,case)['passed'])
        rows[-1]['out']=float('nan')
        self.assertFalse(module.evaluate(rows,case)['passed'])

    def test_flash_threshold_order_and_boundary(self):
        module,cases=oracle('flash_thresholds')
        for skew in (-.3,0,.3):
            thresholds=[k/256+skew*(k/256)*(1-k/256) for k in range(1,256)]
            self.assertTrue(all(b>a for a,b in zip(thresholds,thresholds[1:])))
        ideal=dict(cases[0],skew=0)
        self.assertEqual(module.expected_code(0,ideal),128)
        self.assertEqual(module.expected_code(1/(4*1370000),ideal),255)
        self.assertEqual(module.expected_code(3/(4*1370000),ideal),0)

    def test_supervisor_independent_edge_fixtures(self):
        module,cases=oracle('power_monitor')
        known=[[(25.0000075e-6,1),(80.0000025e-6,-1)],
               [(13.000075e-6,1),(16.0000625e-6,-1)],
               [(3e-6,1),(10.00005e-6,-1)]]
        for case,edges in zip(cases,known):
            calculated=module.expected_edges(case)
            self.assertEqual(len(edges),len(calculated))
            for (t,d),(ct,cd) in zip(edges,calculated):
                self.assertAlmostEqual(t,ct,places=14)
                self.assertEqual(d,cd)
            times=sorted(set([0,case['stop']]+[i*case['stop']/1000 for i in range(1001)]+
                             [t+delta for t,d in edges for delta in (-.25e-9,0,.25e-9)]))
            rows=[]
            for t in times:
                value=0.
                for et,d in edges:
                    fraction=min(1.,max(0.,(t-et+.25e-9)/.5e-9))
                    value+=d*fraction
                rows.append(dict(time=t,supply=0.,enable=value))
            self.assertTrue(module.evaluate(rows,case)['passed'])
            inverted=[dict(row,enable=1-row['enable']) for row in rows]
            self.assertFalse(module.evaluate(inverted,case)['passed'])
            self.assertFalse(module.evaluate([dict(row,enable=0.) for row in rows],case)['passed'])


if __name__=='__main__':
    unittest.main()
