"""Nested continuous predicates must retain every possible mode boundary."""
GUARDS = ["DYNAMICS", "COMPOSE"]
from pathlib import Path
import unittest
import math
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
    def test_adjacent_cuts_reject_for_both_linear_and_nonlinear_consumers(self):
        # u rises from 0 to 1 over one ULP above 1. Its nonlinear area is
        # atan(1) after scaling by 2**52, not zero. There is no binary64
        # observation strictly inside this interval, so freezing at an edge
        # cannot prove the mode used throughout it.
        stop=math.nextafter(1.,math.inf)
        for rate in ('4503599627370496.0', '4503599627370496.0/(1.0+V(u)*V(u))'):
            source='`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;analog begin V(y)<+idt(((V(u)>0.0?1.0:0.0)>0.5)?(%s):0.0,0.0);end endmodule'%rate
            p=compile_sources({'adjacent.va':source},[Instance('dut','m',{'u':'u','y':'y'})])
            with self.subTest(rate=rate),self.assertRaisesRegex(KernelError,'condition_precision'):
                transient(p,{'u':[[0.,0.],[1.,0.],[stop,1.]]},[0.,1.,stop],stop=stop,max_step=1.,kernel=KERNEL)

    def test_possible_parent_root_inside_child_root_box_is_not_ignored(self):
        # rate is 2**54 on (binary64(1/3), exact(1/3)], area exactly 1/3.
        # In this first extension overlapping root boxes are refused, never
        # replaced by the zero modes observed on either side of the box.
        with self.assertRaisesRegex(KernelError,'condition_precision'):
            run('(3.0*V(u)>1.0?0.0:V(u))>0.3333333333333333',gain='18014398509481984.0')

if __name__=='__main__':unittest.main()
