"""Fixed-clock development probes, independent of any backend timestamps.

Nominal answers use exact Fraction arithmetic on the submitted binary64 values.
The t=0/stop counts below test EVAS's explicit convention, not universal LRM
qualification. These tests do not change the original 31-condition denominator.
"""
import copy
from fractions import Fraction as Q
import json
import math
import subprocess
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from evas.ir import SCHEMA_VERSION
from test_affine import KERNEL, instance, model


def timer_source(arguments="2,5,0.001", initial=0):
    return model(f'''@(initial_step) n={initial};
      @(timer({arguments})) n=n+1; V(y,r)<+n;''', 'integer n;')


def run_timer(source=None, *, stop=19, times=None, step=100, instances=None):
    program = compile_sources({'timer.va': source or timer_source()}, instances or [instance()])
    return transient(program, {'u': [[0, 0], [stop, stop]]},
                     times or [0, 1, 3, 8, 13, 18, stop],
                     stop=stop, max_step=step, kernel=KERNEL)


class TimerContracts(unittest.TestCase):
    def test_representable_pwl_roots_coincide_despite_rounded_division(self):
        for exponent in [-30, 0, 20]:
            unit = 2.0**exponent
            for threshold in [1, 3, 8, 11, 17]:
                start, stop = threshold*unit, 19*unit
                # Fraction anchors the expected equality, independently of Rust.
                root = Q(stop)*Q(threshold)/19
                self.assertEqual(root, Q(start))
                source = model(f'''@(initial_step) begin n=0; m=0; end
                  @(timer({start!r},0,{unit/1024!r})) n=n+1;
                  @(cross(V(u,r)-{threshold},1,{unit/1024!r},0.001)) m=m+1;
                  V(y,r)<+n+m;''', 'integer n,m;')
                program=compile_sources({'timer.va':source},[instance()])
                result=transient(program,{'u':[[0,0],[stop,19]]},[0,stop],
                                 stop=stop,max_step=stop,kernel=KERNEL)
                self.assertEqual([e['time'] for e in result['transient']['events']], [start,start])
                self.assertEqual(result['transient']['states'][-1], [1,1])

    def test_representable_root_outside_three_rounded_guesses_is_found(self):
        # 22*(15/22) rounds down; neither outward endpoint equals the exact 15.
        self.assertNotEqual(22*(15/22),15)
        self.assertEqual(Q(22)*Q(15)/22,15)
        source=model('''@(initial_step) begin n=0; m=0; end
            @(timer(15,0,0.01)) n=n+1;
            @(cross(V(u,r)-15,1,0.01,0.01)) m=m+1;
            V(y,r)<+n+m;''','integer n,m;')
        result=run_timer(source,stop=22,times=[0,22])
        self.assertEqual([e['time'] for e in result['transient']['events']],[15.,15.])

    def test_one_ulp_neighbors_of_certified_root_remain_distinct(self):
        for start in [math.nextafter(8.,0.), math.nextafter(8.,math.inf)]:
            source=model(f'''@(initial_step) begin n=0; m=0; end
              @(timer({start!r},0,0.1)) n=n+1;
              @(cross(V(u,r)-8,1,0.1,0.1)) m=m+1;
              V(y,r)<+n+m;''','integer n,m;')
            result=run_timer(source,stop=19,times=[0,19])
            self.assertEqual([e['time'] for e in result['transient']['events']],sorted([8.,start]))
            self.assertEqual(result['transient']['states'][-1], [1,1])

    def test_periodic_independent_count_answers_and_typed_records(self):
        result = run_timer()
        self.assertEqual(result['schema_version'], SCHEMA_VERSION)
