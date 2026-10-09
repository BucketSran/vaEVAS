"""Calibrate every finite oracle, missing evidence and wrong-output rejection."""
import copy
import json
import math
from pathlib import Path
import unittest
from checker import expected, assess, pwl

CARDS=json.loads((Path(__file__).with_name('cases-v1.json')).read_text())['cards']

class Calibration(unittest.TestCase):
    def rows(self,c):
        result=[]
        for i in range(round(c['stop_x']/c['grid_x'])+1):
            x=i*c['grid_x']
            result.append(dict(time=x*c['unit_s'],**{n:pwl(p,x) for n,p in c['inputs'].items()},**expected(c,x)))
        return result

    def test_hand_calculated_anchors(self):
        by={c['id']:c for c in CARDS}
        anchors={'AD-ramp':(5,{'y':0}),'AD-after-stop':(5,{'y':-1}),'SL-catch':(3,{'y':3}),
                 'SL-reverse':(4,{'y':-.8}),'SL-tracking':(2,{'y':-.5}),
                 'DDT-pwl':(2,{'y':-2}),'VR-add':(4,{'y':1.5}),'LANG-preprocess':(4,{'y':1.5}),
                 'LANG-hierarchy':(4,{'y':.5}),'LANG-functions':(3.5,{'y':.75,'z':.25}),
                 'LANG-array-events':(.375,{'y':81,'qzero':40,'qone':41,'qlast':41}),
                 'LANG-vector':(4,{'y':1.5})}
        for name,(x,answer) in anchors.items():
            for n,v in answer.items():self.assertAlmostEqual(expected(by[name],x)[n],v,places=12)
        for name in ['LP-nd','LP-np']:
            self.assertAlmostEqual(expected(by[name],.25)['y'],math.exp(-1)/4,places=15)
        self.assertAlmostEqual(expected(by['NL-cubic'],0)['y'],-.5,places=15)
        self.assertAlmostEqual(expected(by['NL-cubic'],8)['y'],1.5,places=15)

    def test_good_and_bad_outputs_for_every_card(self):
        for c in CARDS:
            with self.subTest(c=c['id']):
                rows=self.rows(c)
                self.assertEqual(assess(c,rows)['status'],'observed_within_target')
                bad=copy.deepcopy(rows)
                for r in bad:r[c['outputs'][0]]+=.01
                self.assertEqual(assess(c,bad)['status'],'observed_difference')
                bad=copy.deepcopy(rows);bad[len(bad)//2][c['outputs'][0]]=float('nan')
                self.assertEqual(assess(c,bad)['status'],'observation_invalid')
                self.assertEqual(assess(c,rows[1:])['status'],'observation_invalid')
                self.assertEqual(assess(c,rows[:-1])['status'],'observation_invalid')
                self.assertEqual(assess(c,rows[::2])['status'],'observation_invalid')
                self.assertEqual(assess(c,rows[:2]+rows[1:])['status'],'observation_invalid')
                bad=copy.deepcopy(rows)
                for r in bad:r[next(iter(c['inputs']))]+=.01
                self.assertEqual(assess(c,bad)['status'],'observation_invalid')

    def test_predeclared_boundaries_remain_ungraded(self):
        for c in CARDS:
            if not c['excluded_centers_x']:continue
            rows=self.rows(c)
            for r in rows:
                if any(abs(r['time']/c['unit_s']-x)<=c['exclusion_radius_x'] for x in c['excluded_centers_x']):
                    r[c['outputs'][0]]+=100
            out=assess(c,rows)
            self.assertEqual(out['status'],'observed_within_target')
            self.assertEqual(out['boundary_status'],'not_graded')
            self.assertTrue(out['boundary_rows'])

if __name__=='__main__':unittest.main()
