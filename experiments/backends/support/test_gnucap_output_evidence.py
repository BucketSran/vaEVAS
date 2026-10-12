import copy
from fractions import Fraction as F
import math
import unittest
import gnucap_output_evidence as g


class OutputBounds(unittest.TestCase):
    def test_inverse_includes_extremes_and_hidden_zero(self):
        for p in (0., 1e-99, -1e-99, 1., -1., 3e-6):
            radius = g.inverse_radius(p)
            self.assertGreaterEqual(F(g.up(radius)), radius)
            self.assertGreaterEqual(radius, g.RHO*abs(F(p))+g.TINY)
        self.assertGreaterEqual(g.inverse_radius(0.), g.TINY)
        with self.assertRaises(ValueError): g.inverse_radius(math.nan)

    def test_missing_sides_and_ambiguous_ticks_reject(self):
        card={'stop_s':1., 'unit_s':1.}
        contract={'budgets':{'time_serialization_ulps':16,'boundary_distance_s':.3,'global_gap_units':1.}}
        rows=[{'time':0.},{'time':.25},{'time':.5},{'time':.75},{'time':1.}]
        result=g.tick_coverage(card,rows,.25,[{'time_s':.5}],contract)
        self.assertTrue(result['complete'])
        missing=g.tick_coverage(card,[{'time':0.},{'time':1.}],.25,[{'time_s':.5}],contract)
        self.assertFalse(missing['complete'])
        bad=g.tick_coverage(card,rows,2**-69,[],contract)
        self.assertFalse(bad['complete'])

    def test_full_addition_preserves_old_gate_and_detects_budget_failure(self):
        card={'inputs':{'u':[[0.,0.],[1.,1.]]},'outputs':['y'],'input_gain_bound':5.,'output_slope_bound_V_s':5.}
        rows=[{'time':0.,'u':0.,'y':0.},{'time':1.,'u':1.,'y':5.}]
        old={'input_error_upper_V':{'u':0.},'outputs':{'y':{'error_upper_V':1e-12,'unresolved_uncertainty_V':1e-12,'input_uncertainty_V':0.,'reference_uncertainty_V':0.}},'tiers':{'Q3':{'status':'pass','voltage_budget_V':1e-11}}}
        frozen=copy.deepcopy(old)
        result=g.additive_budget(card,rows,old,{'observation':{'input_fraction':.01,'observation_fraction':.1,'reference_fraction':.01}},coverage_complete=True)
        self.assertEqual(old,frozen)
        self.assertGreater(result['outputs']['y']['error_upper_V'],old['outputs']['y']['error_upper_V'])
        self.assertFalse(result['new_additive_tiers']['Q3']['gates']['input_B100'])
        self.assertEqual(result['new_additive_tiers']['Q3']['status'],'pending')
        old['tiers']['Q3']['status']='I'
        self.assertFalse(g.additive_budget(card,rows,old,{'observation':{'input_fraction':.01,'observation_fraction':.1,'reference_fraction':.01}},coverage_complete=True)['new_additive_tiers']['Q3']['gates']['old_all_row_assessment_pass'])

    def test_per_output_gain_and_slope_do_not_use_a_global_max(self):
        card={'inputs':{'u':[[0.,0.],[1.,1.]]},'outputs':['a','b'],
              'input_gain_bound':{'a':0.,'b':3.},
              'output_slope_bound_V_s':{'a':0.,'b':7.}}
        rows=[{'time':0.,'u':0.,'a':0.,'b':0.},
              {'time':1.,'u':1.,'a':1.,'b':2.}]
        old={'input_error_upper_V':{'u':0.},'outputs':{
            n:{'error_upper_V':0.,'unresolved_uncertainty_V':0.,
               'input_uncertainty_V':0.,'reference_uncertainty_V':0.}
            for n in card['outputs']},
            'tiers':{'Q3':{'status':'pass','voltage_budget_V':1e-7}}}
        frozen=copy.deepcopy(old)
        contract={'observation':{'input_fraction':.01,'observation_fraction':.1,'reference_fraction':.01}}
        result=g.additive_budget(card,rows,old,contract,coverage_complete=True)
        d=g.inverse_radius(1.)
        self.assertEqual(result['outputs']['a']['extra_formatter_V'],g.up(d))
        self.assertEqual(result['outputs']['a']['amplified_input_formatter_extra_V'],0.)
        self.assertEqual(result['outputs']['b']['extra_formatter_V'],
                         g.up(g.inverse_radius(2.)+7*d+3*(d+d)))
        self.assertEqual(old,frozen)
        self.assertEqual(result['new_additive_tiers']['Q3']['status'],'pass')
        # Either field may independently use the original scalar form.
        for field in ('input_gain_bound','output_slope_bound_V_s'):
            mixed=copy.deepcopy(card);mixed[field]=2.
            other='output_slope_bound_V_s' if field=='input_gain_bound' else 'input_gain_bound'
            result=g.additive_budget(mixed,rows,old,contract,coverage_complete=True)
            for n in card['outputs']:
                gain=F(2) if field=='input_gain_bound' else F(card['input_gain_bound'][n])
                slope=F(2) if field=='output_slope_bound_V_s' else F(card['output_slope_bound_V_s'][n])
                self.assertEqual(result['outputs'][n]['extra_formatter_V'],
                                 g.up(g.inverse_radius(rows[-1][n])+slope*d+gain*(d+d)))
        missing=copy.deepcopy(card);del missing['input_gain_bound']['b']
        with self.assertRaisesRegex(ValueError,'missing per-output'):
            g.additive_budget(missing,rows,old,contract,coverage_complete=True)

if __name__=='__main__': unittest.main()
