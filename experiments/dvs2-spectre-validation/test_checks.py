"""Calibration against hand anchors, injected semantic faults and invalid exports."""
import copy
import math
import unittest
from check_results import check, histories, integrator_check, lowpass, reference
from run_suite import conditions, netlist, v1, T

CASES={c['id']:c for c in conditions()}


def rows(name):
    c=CASES[name]
    result=[]
    for i in range(int(c['stop_x']*1000)+1):
        x=i/1000; t=x*T
        result.append(dict(time=t,**{n:v1.pwl(p,t) for n,p in c['inputs'].items()},**reference(c,x)))
    return result


class Calibration(unittest.TestCase):
    def test_manifest_identity_and_real_parameter_override(self):
        self.assertEqual(len(CASES),31)
        self.assertEqual(sum(c['kind']!='v1' for c in CASES.values()),16)
        self.assertNotIn('v6-main',CASES)
        self.assertIn('v6-standard',CASES)
        self.assertNotIn('g1=',netlist(CASES['s1-default'],'base'))
        self.assertIn('g1=-0.5',netlist(CASES['s1-override'],'base'))
        a=CASES['c1-main']; b=CASES['c1-swapped']
        self.assertEqual(a['inputs'],b['inputs'])
        self.assertEqual(a['instances'],list(reversed(b['instances'])))

    def test_hand_anchors(self):
        for name,expected in [('s1-default',[.225,.825,.575,-.325,-.125]),
                              ('s1-override',[-.65,-.85,.15,.45,-.35]),
                              ('d1-free',[.25,.4,.45,.4,.25]),
                              ('d1-reset',[.25,.4,.25,.2125,.0625])]:
            for x,y in enumerate(expected): self.assertAlmostEqual(reference(CASES[name],x)['vout'],y,places=12)
        for x,y in [(1.5,.1103638324),(2.5,.5045722882),(3.5,.5870852636)]:
            self.assertAlmostEqual(lowpass(x),y,places=9)
        for name,expected in [('d2-constant',[.125,.625,1.125,1.625,2.125]),
                              ('d2-chirp',[.125,.75,1.625,2.75,4.125])]:
            for x,y in enumerate(expected): self.assertAlmostEqual(reference(CASES[name],x)['accumulated'],y,places=12)
        for x,expected in [(.25,(0,0)),(.75,(.1,0)),(1.75,(.1,.1)),(2.75,(.2,.1))]:
            r=reference(CASES['e1-aligned'],x)
            self.assertAlmostEqual(r['up'],expected[0]); self.assertAlmostEqual(r['down'],expected[1])
        for name,expected in [('e2-low',[.1,.75,.65,.1,.1,.45]),
                              ('e2-clock-high',[.1,.75,.65,.1,.1,.45]),
                              ('e2-reset-high',[.1,.1,.65,.1,.1,.45])]:
            for x,y in zip([.25,.75,1.75,2.75,3.05,3.75],expected):
                self.assertAlmostEqual(reference(CASES[name],x)['vout'],y)
        for name in ['c1-main','c1-swapped','c1-no-reset-a']:
            for x,y in zip([1,2,3,3.95],[.275,.375,.475,.575]):
                self.assertAlmostEqual(reference(CASES[name],x)['outb'],y)
            self.assertAlmostEqual(reference(CASES[name],2.75)['outa'],.55 if name.endswith('no-reset-a') else .1)

    def test_all_new_positive_and_missing_observation_controls(self):
        for name,c in CASES.items():
            if c['kind']=='v1': continue
            with self.subTest(name=name):
                data=rows(name)
                self.assertEqual(check(data,c)['status'],'observations_within_targets')
                self.assertEqual(check(data[:-1],c)['status'],'observation_invalid')

    def test_seven_distinguishing_semantic_faults(self):
        faults={
            'e1-aligned':lambda r:r.update(up=r['up']-.1) if r['time']>2.6*T else None,
            'e2-clock-high':lambda r:r.update(vout=.8) if r['time']<.3*T else None,
            'c1-main':lambda r:r.update(outb=.1) if 2.2*T<r['time']<2.7*T else None,
            'c2-main':lambda r:r.update(vout=.3) if 1.6*T<r['time']<2.4*T else None,
            'd1-reset':lambda r:r.update(vout=.25+.2*(r['time']/T)-.05*(r['time']/T)**2),
            'd2-chirp':lambda r:r.update(accumulated=.125+(.5+.25*r['time']/T)*r['time']/T),
            's1-override':lambda r:r.update(vout=-.25),
        }
        for name,fault in faults.items():
            with self.subTest(name=name):
                data=rows(name)
                for r in data: fault(r)
                self.assertEqual(check(data,CASES[name])['status'],'observed_violation')

    def test_phase_range_and_whole_cycle_not_hidden_by_sine(self):
        data=rows('d2-constant')
        for r in data: r['wrapped']+=1
        self.assertEqual(check(data,CASES['d2-constant'])['status'],'observed_violation')
        data=rows('d2-constant')
        for r in data: r['accumulated']+=1
        self.assertEqual(check(data,CASES['d2-constant'])['status'],'observed_violation')

    def test_nonfinite_time_order_density_and_input(self):
        original=rows('s1-default'); c=CASES['s1-default']
        for field,value in [('time',original[9]['time']),('u',9),('vout',float('nan'))]:
            data=copy.deepcopy(original); data[10][field]=value
            self.assertEqual(check(data,c)['status'],'observation_invalid')
        data=original[:10]+original[12:]
        self.assertEqual(check(data,c)['status'],'observation_invalid')

    def test_uncertainty_is_not_forced_to_pass_or_fail(self):
        data=rows('e1-aligned')
        for r in data: r['down']+=.0009
        result=check(data,CASES['e1-aligned'])['history']['down']
        self.assertEqual(result['exact_export_assumption']['status'],'P')
        self.assertEqual(result['candidate_budget_sensitivity']['status'],'I')
        data=rows('d1-free')
        for r in data: r['vout']+=.0009
        self.assertEqual(integrator_check(data,CASES['d1-free'],.00025)['status'],'I')

    def test_c2_linearization_reserve(self):
        for event in histories(CASES['c2-main'])['vout'][1]:
            for delta in [0,.00001,.00002,.00004]:
                error=abs(lowpass(float(event.start)+delta)-(float(event.target)+float(event.sample_slope)*delta))
                self.assertLessEqual(error,9.6e-10+1e-14)


if __name__=='__main__': unittest.main()
