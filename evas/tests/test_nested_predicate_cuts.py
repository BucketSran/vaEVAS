"""Nested continuous predicates must retain every possible mode boundary."""
GUARDS = ["DYNAMICS", "COMPOSE"]
from pathlib import Path
import unittest
import math
from fractions import Fraction as F
from evas import Instance, KernelError, compile_sources, transient
KERNEL=Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel'

def run(predicate, times=(0.,.25,.5,.75,1.), gain='1.0'):
    source='''`include "disciplines.vams"
module m(u,y); input u; output y; electrical u,y;
analog begin V(y)<+idt((%s)?%s:0.0,0.0); end endmodule'''%(predicate,gain)
    program=compile_sources({'nested.va':source},[Instance('dut','m',{'u':'u','y':'y'})])
    return transient(program,{'u':[[0.,0.],[1.,1.]]},list(times),stop=1.,max_step=1.,
                     kernel=KERNEL,vabstol=1e-9,reltol=0.)

class NestedPredicateCuts(unittest.TestCase):
    def test_parent_crossing_inside_child_mode_is_not_lost(self):
        for p in ('(V(u)>0.25?V(u):0.0)>0.5',
                  '((V(u)>0.25?V(u):0.0)+0.125)>0.625'):
            with self.subTest(predicate=p):
                result=run(p)
                values=[s['voltages'][result['nodes'].index('y')] for s in result['solutions']]
                for actual,wanted in zip(values,[0.,0.,0.,.25,.5],strict=True):
                    self.assertLessEqual(abs(actual-wanted),1e-9)
    def test_arithmetic_boolean_selection_changes_at_all_child_cuts(self):
        r=run('((V(u)>0.25?1.0:0.0)+(V(u)>0.75?2.0:0.0))>0.5')
        values=[s['voltages'][r['nodes'].index('y')] for s in r['solutions']]
        for actual,wanted in zip(values,[0.,0.,.25,.5,.75],strict=True):
            self.assertLessEqual(abs(actual-wanted),1e-9)
    def test_adjacent_cuts_linear_area_uses_the_certified_open_side(self):
        # No binary64 point lies in (1, stop), but its real open side is
        # root-free and the exact-source rational witness proves u>0 there.
        stop=math.nextafter(1.,math.inf)
        rate='4503599627370496.0'
        self.assertEqual(F(rate)*(F(stop)-1),1)
        for predicate in ('V(u)>0.0', '(V(u)>0.0?1.0:0.0)>0.5'):
            source='`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;analog begin V(y)<+idt((%s)?(%s):0.0,0.0);end endmodule'%(predicate,rate)
            p=compile_sources({'adjacent.va':source},[Instance('dut','m',{'u':'u','y':'y'})])
            with self.subTest(predicate=predicate,rate=rate):
                times=[0.,1.,stop]
                result=transient(p,{'u':[[0.,0.],[1.,0.],[stop,1.]]},times,stop=stop,max_step=1.,kernel=KERNEL)
                evidence=result['observation_evidence']
                controls=evidence['effective_controls']
                self.assertEqual(controls['absolute_V'],1e-12)
                self.assertEqual(controls['relative'],1e-10)
                index=result['nodes'].index('y')
                bound_index=evidence['nodes'].index('y')
                for t,row,bounds in zip(times,result['solutions'],evidence['voltage_bounds_V'],strict=True):
                    wanted=F(rate)*max(F(0),F(t)-1)
                    value=F(row['voltages'][index])
                    budget=F(controls['absolute_V'])+F(controls['relative'])*abs(value)
                    lo,hi=map(F,bounds[bound_index])
                    self.assertLessEqual(abs(value-wanted),budget)
                    self.assertLessEqual(lo,wanted);self.assertLessEqual(wanted,hi)
                    self.assertLessEqual(max(abs(lo-value),abs(hi-value)),budget)

    def test_adjacent_cuts_nonlinear_consumer_keeps_the_trial_limit(self):
        # The same certified open side does not certify the nonlinear tube.
        # Its exact area is atan(1)=pi/4, so a frozen zero is not an answer.
        stop=math.nextafter(1.,math.inf)
        rate='4503599627370496.0/(1.0+V(u)*V(u))'
        for predicate in ('V(u)>0.0', '(V(u)>0.0?1.0:0.0)>0.5'):
            source='`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;analog begin V(y)<+idt((%s)?(%s):0.0,0.0);end endmodule'%(predicate,rate)
            p=compile_sources({'adjacent.va':source},[Instance('dut','m',{'u':'u','y':'y'})])
            with self.subTest(predicate=predicate,rate=rate):
                with self.assertRaises(KernelError) as caught:
                    transient(p,{'u':[[0.,0.],[1.,0.],[stop,1.]]},[0.,1.,stop],stop=stop,max_step=1.,kernel=KERNEL)
                self.assertEqual(caught.exception.detail['kind'],'waveform_accuracy')
                self.assertRegex(caught.exception.detail['message'],r'^cannot refine nonlinear trajectory within 64 trials: tube or user-budget Taylor remainder not certified$')

    def test_possible_parent_root_inside_child_root_box_is_not_ignored(self):
        # rate is 2**54 on (binary64(1/3), exact(1/3)], area exactly 1/3.
        # In this first extension overlapping root boxes are refused, never
        # replaced by the zero modes observed on either side of the box.
        with self.assertRaisesRegex(KernelError,'condition_precision'):
            run('(3.0*V(u)>1.0?0.0:V(u))>0.3333333333333333',gain='18014398509481984.0')

if __name__=='__main__':unittest.main()
