"""Independent accept/reject controls for the new finite observation checker."""
import copy
import unittest
from operators import Q, specs, interpolate, check, TARGET


class CheckerCalibration(unittest.TestCase):
    def rows(self,c):
        return [dict(time=t, **{n:float(interpolate(points,Q(t)/Q(c['unit'])))
                for n,points in {**c['inputs'],**c['answers']}.items()}) for t in c['output_times']]

    def test_correct_all_profiles(self):
        for c in specs(): self.assertEqual(check(c,self.rows(c))['status'],'observations_within_targets')

    def test_hand_computed_anchors(self):
        cases={c['name']:c for c in specs()}
        for name,t,y in [('ad-ramp',5,0),('ad-after-stop',7,-1),('ad-affine-reference',2,6),
                         ('sl-catch',3,3),('sl-reverse',3,Q(6,5)),('sl-reflected',3,Q(-6,5)),
                         ('sl-affine-reference',2,6),('sl-corner-catch',5,3)]:
            self.assertEqual(interpolate(cases[name]['answers']['y'],t),y)

    def test_wrong_delayed_history_rejected(self):
        c=specs()[0]; rows=self.rows(c)
        for r in rows:r['y']=float(interpolate(c['inputs']['u'],Q(r['time'])/Q(c['unit'])))
        self.assertEqual(check(c,rows)['status'],'observed_violation')

    def test_wrong_reverse_restart_rejected(self):
        c=next(c for c in specs() if c['name']=='sl-reverse');rows=self.rows(c)
        for r in rows:
            x=Q(r['time'])/Q(c['unit'])
            r['y']=float(x if x<=2 else max(Q(-4),2-2*(x-2)))
        self.assertEqual(check(c,rows)['status'],'observed_violation')

    def test_fixed_threshold_sides(self):
        c=specs()[0]
        for delta,status in [(TARGET/2,'observations_within_targets'),(2*TARGET,'observed_violation')]:
            rows=self.rows(c)
            for r in rows:r['y']+=delta
            self.assertEqual(check(c,rows)['status'],status)

    def test_input_error_is_observation_failure(self):
        c=specs()[0];rows=self.rows(c);rows[7]['u']+=.01
        self.assertEqual(check(c,rows)['status'],'observation_invalid')

    def test_missing_grid_duplicate_and_nan(self):
        c=specs()[0];rows=self.rows(c)
        bad=[rows[:7]+rows[8:],rows[:7]+[rows[6]]+rows[7:]]
        nan=copy.deepcopy(rows);nan[7]['y']=float('nan');bad.append(nan)
        for r in bad:
            with self.assertRaises(ValueError):check(c,r)


if __name__=='__main__':unittest.main()
