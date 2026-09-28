"""Calibration of analytical anchors, discriminating faults, and malformed observations."""
import copy
import math
import unittest

from analyze import analyze
from suite import conditions, events, pwl, reference, T

CASES={c['id']:c for c in conditions()}


def samples(case, transform=None, offsets=None):
    result=[]
    for i in range(4001):
        t=i*1e-9
        row={'time':t,**{n:pwl(p,t) for n,p in case['inputs'].items()},**reference(case,t,offsets)}
        if transform: transform(row,t/T)
        result.append(row)
    return result


class Calibration(unittest.TestCase):
    def test_fifteen_correct_finite_traces(self):
        for case in CASES.values():
            with self.subTest(case=case['id']):
                self.assertEqual(analyze(samples(case),case)['status'],'observations_within_targets')

    def test_independent_anchors(self):
        anchors=[('v1-main',.5,'vout',-.625),('v1-main',1,'vout',.125),
                 ('v2-main',3,'op',.85),('v2-main',3,'on',1.05),
                 ('v3-main',1,'vout',.1),('v3-main',3,'vout',.9),
                 ('v4-c0',1.75,'vout',.425),('v4-c1',1.75,'vout',.1),
                 ('v4-c1',1.95,'vout',.1),('v4-c1',2.75,'vout',.575),
                 ('v5-main',.575,'vout',.5),('v5-main',1.275,'vout',.5),
                 ('v6-main',1.5,'vout',.3/math.e),
                 ('v6-main',2,'vout',.3*(1+math.exp(-2))),
                 ('v7-linear-main',2,'outa',.8),('v7-linear-main',2,'outb',1/3)]
        for name,x,node,value in anchors:
            self.assertAlmostEqual(reference(CASES[name],x*T)[node],value,places=12)

    def test_nonlinear_closed_form_and_wrong_interpolation(self):
        for cubic in [.5,2.]:
            case=CASES['v7-nonlinear-'+str(cubic)]
            for x in [.125,.5,1.5,2.5,3.875]:
                u=pwl(case['inputs']['vin'],x*T)
                closed=2/math.sqrt(3*cubic)*math.sinh(math.asinh(3*math.sqrt(3*cubic)*u/2)/3)
                self.assertAlmostEqual(reference(case,x*T)['vout'],closed,places=14)
        case=CASES['v7-nonlinear-2.0']
        self.assertGreater(abs(reference(case,.5*T)['vout']-(-.375)),9/640)

    def test_v2_correlated_wrong_model_requires_oat(self):
        def wrong(row,x):
            h=row['vdd']-row['vref'];d=row['vip']-row['vin']
            row.update(op=1.5*h+d-1,on=1.5*h-d-1)
        case=CASES['v2-main']
        self.assertEqual(analyze(samples(case,wrong),case)['status'],'observations_within_targets')
        for name in ['v2-reference-zero','v2-supply-fixed']:
            case=CASES[name]
            self.assertEqual(analyze(samples(case,wrong),case)['status'],'observed_violation')

    def test_behavior_faults(self):
        faults=[
            ('v1-main',lambda r,x:r.update(vout=1.5*r['vin']+.125)),
            ('v3-main',lambda r,x:r.update(vout=.9 if r['vin']>=.5 else .1)),
            ('v4-c1',lambda r,x:r.update(vout=.425) if 1.525<x<2.5 else None),
            ('v4-c1',lambda r,x:r.update(vout=.4775) if 1.875<x<2.5 else None),
            ('v4-c1',lambda r,x:r.update(vout=.1) if x>2.5 else None),
            ('v4-c0',lambda r,x:r.update(vout=r['vin'])),
            ('v5-main',lambda r,x:r.update(vout=.1)),
            ('v6-main',lambda r,x:r.update(vout=r['vin'])),
            ('v7-linear-main',lambda r,x:r.update(outb=r['outa'])),
            ('v7-nonlinear-2.0',lambda r,x:r.update(vout=-.5+.25*x)),
        ]
        for name,mutate in faults:
            with self.subTest(case=name,mutation=str(mutate)):
                case=CASES[name]
                self.assertEqual(analyze(samples(case,mutate),case)['status'],'observed_violation')

    def test_allowed_event_offsets(self):
        for name in ['v3-main','v4-c0','v4-c1','v5-main']:
            case=CASES[name]
            offsets=[(e[3]+e[4])/2 for e in events(case)]
            self.assertEqual(analyze(samples(case,offsets=offsets),case)['status'],'observations_within_targets')

    def test_voltage_threshold_sensitivity(self):
        case=CASES['v1-main']
        for error,expected in [(.0005,'observations_within_targets'),(.002,'observed_violation')]:
            self.assertEqual(analyze(samples(case,lambda r,x:r.update(vout=r['vout']+error)),case)['status'],expected)

    def test_bad_observations(self):
        case=CASES['v1-main'];valid=samples(case)
        bad=[]
        row=copy.deepcopy(valid);row[5].pop('vout');bad.append(row)
        row=copy.deepcopy(valid);row[5]['vout']=math.nan;bad.append(row)
        row=copy.deepcopy(valid);row[5]['time']=row[4]['time'];bad.append(row)
        bad.extend([valid[:-1],valid[1:],valid[::2]])
        for rows in bad:
            with self.assertRaises(ValueError): analyze(rows,case)

    def test_input_error_is_not_dut_failure(self):
        case=CASES['v1-main']
        self.assertEqual(analyze(samples(case,lambda r,x:r.update(vin=r['vin']+.01)),case)['status'],'input_mismatch')

    def test_unobserved_pulse_remains_unqualified(self):
        # A pulse entirely between export points has no representation in this file.
        # The analyzer must retain I even when all observed values pass.
        case=CASES['v1-main']
        self.assertEqual(analyze(samples(case),case)['formal_dvs_qualification'],'I')


if __name__=='__main__':
    unittest.main()
