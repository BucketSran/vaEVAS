"""Synthetic physical-provider controls; no original model/checker execution."""
GUARDS=['LANG','ANALOG','EVENT-ORDER','TIMED-OPERATOR','COMPOSE']
from pathlib import Path
from fractions import Fraction as Q
import os
import json
import tempfile
from unittest.mock import patch
import unittest
from evas import Instance,compile_sources,transient
from evas.scs_sources import voltage_points
from test_history_forcing import KERNEL as DEFAULT_KERNEL, SOURCE

KERNEL=Path(os.environ.get('FORCING_SHAPE_KERNEL',DEFAULT_KERNEL))

class PhysicalForcing(unittest.TestCase):
    def run_shape(self,source=SOURCE,shaped=True,foreign=False,pulse=None):
        sources={'physical_mixer.va':source}
        instances=[Instance('one','mixer',dict(u='u',lo='lo',rst='rst',y='y',metric='metric'),{})]
        if foreign:
            sources['observer.va']='''`include "disciplines.vams"
module observer(a,z); input a; output z; electrical a,z; real discarded;
analog begin discarded=0.0*V(a); V(z)<+0.0; end endmodule'''
            instances.append(Instance('observer','observer',dict(a='lo',z='z'),{}))
        p=compile_sources(sources,instances)
        def fail(message,**kw):raise AssertionError(message)
        points,_,proof=voltage_points(pulse or dict(type='pulse',val0=0.,val1=1.,delay=.13,
            rise=.07,fall=.08,width=.13,period=.41),1.,fail)
        self.assertGreater(proof['voltage_error_bound_V'],0)
        return transient(p,dict(u=[[0,.25],[1,.25]],lo=points,rst=[[0,0],[1,0]]),
            [0,.15,.18,.3,.36,.38,.6,.9,1],stop=1,max_step=.1,kernel=KERNEL,
            source_errors=dict(lo=proof['voltage_error_bound_V']),
            source_shapes=dict(lo=proof['source_shape']) if shaped else None)

    def test_original_physical_pulse_predicate_and_independent_transition(self):
        r=self.run_shape(); i=r['nodes'].index('y')
        for t,row,box in zip(r['saved']['times'] if 'saved'in r else [0,.15,.18,.3,.36,.38,.6,.9,1],r['solutions'],r['observation_evidence']['voltage_bounds_V']):
            phase=(Q(t)-Q(.13))%Q(.41)
            high=(Q(.07)/2<phase<Q(.07)+Q(.13)+Q(.08)/2) and Q(t)>=Q(.13)
            want=Q(3,16) if high else Q(13,16)
            self.assertAlmostEqual(row['voltages'][i],float(want),places=10)
            self.assertLessEqual(Q(box[i][0]),want); self.assertGreaterEqual(Q(box[i][1]),want)

    def test_unknown_band_still_rejected(self):
        with self.assertRaisesRegex(Exception,'unsupported_source_uncertainty'):
            self.run_shape(shaped=False)

    def test_numeric_raw_discarded_and_zero_terms_rejected(self):
        for extra in ['mix=V(lo);','mix=0.0*V(lo);','for(i=0;i<0;i=i+1) mix=V(lo);', 'if(V(rst)>2.0) mix=V(lo);', 'mix=(V(rst)>2.0)?V(lo):0.0;']:
            source=SOURCE.replace('real z,pol,mix; integer q;','real z,pol,mix; integer q,i;').replace('if(V(rst)>0.5)',extra+'\n  if(V(rst)>0.5)')
            with self.subTest(extra=extra),self.assertRaisesRegex(Exception,'unsupported_forcing_scope'):
                self.run_shape(source)

    def test_numeric_foreign_discarded_read_rejected(self):
        with self.assertRaisesRegex(Exception,'unsupported_forcing_scope'):
            self.run_shape(foreign=True)

    def physical_request(self,source=SOURCE,times=None,physical_end=1.):
        p=compile_sources({'explicit_physical.va':source},[
            Instance('one','mixer',dict(u='u',lo='lo',rst='rst',y='y',metric='metric'),{})])
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'diagnostics.json'
            with patch.dict(os.environ,{'EVAS_DIAGNOSTICS_PATH':str(log)}):
                result=transient(p,dict(u=[[0,.25],[1,.25]],lo=[[0,0],[1,.875]],rst=[[0,0],[1,0]]),
                    times or [0,.25,.5,.55,1],stop=1,max_step=.125,kernel=KERNEL,
                    source_errors=dict(lo=.125),source_shapes=dict(lo=[
                        dict(time_numerator='0',time_denominator='1',value_V=0.),
                        dict(time_numerator='1',time_denominator='1',value_V=physical_end)]))
            self.last_diagnostics=json.loads(log.read_text())
            return result

    def test_physical_curve_not_nominal_selects_branch_including_exact_root(self):
        times=[0,.25,.5,.55,1];r=self.physical_request(times=times);i=r['nodes'].index('y')
        for t,row in zip(times,r['solutions']):
            self.assertEqual(row['voltages'][i],.1875 if t>.5 else .8125)
        # At .55 nominal lo=.48125 is below threshold; physical lo=.55 is above.
        c=self.last_diagnostics['counters']
        self.assertGreater(c.get('forcing_curve_actual_point_calls',0)+c.get('forcing_owned_point_success',0),0)
        self.assertGreater(c.get('forcing_curve_reserved_work',0)+c.get('forcing_owned_reserved_work',0),0)
        # 3/4*binary64(.4) lies strictly above binary64(.3), while its
        # enclosure includes that threshold. Fraction decides the exact side.
        times=[0,.25,.4,.625,1]
        r=self.physical_request(source=SOURCE.replace('V(lo)>0.5','V(lo)>0.3'),
                                times=times,physical_end=.75)
        i=r['nodes'].index('y')
        for t,row in zip(times,r['solutions']):
            high=Q.from_float(t)*Q(3,4)>Q.from_float(.3)
            self.assertEqual(row['voltages'][i],.1875 if high else .8125)
        c=self.last_diagnostics['counters']; actual=c['forcing_actual_exact_calls']
        self.assertGreater(actual,0)
        self.assertEqual(actual,c['selected_ln_exact_calls'])
        self.assertEqual(actual,c['selected_ln_exact_reservations'])
        self.assertEqual(actual*200000,c['selected_ln_exact_debit'])
        self.assertGreater(c['forcing_predicate_curve_reads_prepaid'],0)
        print('physical_exact_and_read_accounting',c)

    def test_physical_cross_updates_real_independent_transition(self):
        source=SOURCE.replace('@(timer(0.25)) q=1;','@(cross(V(lo)-0.5,+1)) q=1;')
        times=[0,.25,.49,.51,.5625,.625,1];r=self.physical_request(source,times)
        i=r['nodes'].index('metric')
        for t,row in zip(times,r['solutions']):
            self.assertAlmostEqual(row['voltages'][i],min(1,max(0,(t-.5)*8)),places=9)


    def test_many_knot_physical_predicate_uses_global_values_without_derivatives(self):
        pulse=dict(type='pulse',val0=0.,val1=1.,delay=.013,
                   rise=.007,fall=.008,width=.013,period=.041)
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'diagnostics.json'
            with patch.dict(os.environ,{'EVAS_DIAGNOSTICS_PATH':str(log)}):
                r=self.run_shape(pulse=pulse)
            counters=json.loads(log.read_text())['counters']
        i=r['nodes'].index('y')
        for time,row in zip([0,.15,.18,.3,.36,.38,.6,.9,1],r['solutions']):
            phase=(Q(time)-Q(.013))%Q(.041)
            high=(Q(.007)/2<phase<Q(.007)+Q(.013)+Q(.008)/2) and Q(time)>=Q(.013)
            self.assertAlmostEqual(row['voltages'][i],float(Q(3,16) if high else Q(13,16)),places=10)
        self.assertEqual(counters.get('forcing_curve_actual_range_calls',0),0)
        self.assertGreater(counters['forcing_global_value_knots'],80)
        self.assertGreater(counters.get('forcing_curve_actual_point_calls',0)+counters.get('forcing_owned_point_success',0),0)
        print('global_value_no_derivative_accounting',counters)

if __name__=='__main__':unittest.main()
