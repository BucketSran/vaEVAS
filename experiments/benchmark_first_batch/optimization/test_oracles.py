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

    def test_dac_sampled_hold_fixture(self):
        module,cases=oracle('sampled_dac')
        case=dict(cases[1],stop=5e-7)
        rows=[]
        for i in range(10001):
            t=case['stop']*i/10000
            row=dict(time=t,clock=self.clock_voltage(t,case['period']))
            for bit in range(12):
                half=case['period']*(1<<bit)
                phase=(t-half)%(2*half)
                value=0.
                if t>=half:
                    if phase<.1e-9:value=phase/.1e-9
                    elif phase<half:value=1.
                    elif phase<half+.1e-9:value=1-(phase-half)/.1e-9
                row['b'+str(bit)]=.72*value
            sample_index=max(0,math.floor((t-case['first_cross']-.2e-9)/case['period']))
            output_time=case['first_cross']+.2e-9+sample_index*case['period']
            previous=max(0,sample_index-1)
            fraction=min(1.,max(0.,(t-output_time)/.4e-9))
            count=previous+(sample_index-previous)*fraction
            row['out']=case['offset']+case['vref']*count/4095
            rows.append(row)
        self.assertTrue(module.evaluate(rows,case)['passed'])
        wrong=[dict(row,out=case['offset']+.9*(row['out']-case['offset'])) for row in rows]
        self.assertFalse(module.evaluate(wrong,case)['passed'])
        wrong=[dict(row,out=case['offset']+case['vref']*int(row['time']/case['period'])/4095) for row in rows]
        self.assertFalse(module.evaluate(wrong,case)['passed'])

    @staticmethod
    def clock_voltage(t,period):
        if t<1e-9:return 0.
        phase=(t-1e-9)%period
        if phase<.1e-9:return phase/.1e-9
        if phase<period/2:return 1.
        if phase<period/2+.1e-9:return 1-(phase-period/2)/.1e-9
        return 0.

    def test_filter_simultaneous_recurrence_fixture(self):
        module,cases=oracle('sc_coefficients')
        case=dict(cases[1],stop=5e-7)
        samples=module.recurrence_samples(case)
        self.assertEqual([s[1] for s in samples[:3]],[0.,0.,0.])
        self.assertGreater(samples[3][1],0.)
        rows=[]
        for i in range(10001):
            t=case['stop']*i/10000
            index=math.floor((t-case['first_cross'])/case['period'])
            value=0.
            if index>=0:
                previous=0. if index==0 else samples[index-1][1]
                fraction=min(1.,max(0.,(t-samples[index][0])/.4e-9))
                value=previous+(samples[index][1]-previous)*fraction
            rows.append(dict(time=t,clock=self.clock_voltage(t,case['period']),
                             vin=.5+.45*math.sin(2*math.pi*case['sine_frequency']*t),out=value))
        self.assertTrue(module.evaluate(rows,case)['passed'])
        self.assertFalse(module.evaluate([dict(row,out=.9*row['out']) for row in rows],case)['passed'])
        self.assertFalse(module.evaluate([dict(row,out=0.) for row in rows],case)['passed'])

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
