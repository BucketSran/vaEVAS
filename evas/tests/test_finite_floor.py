"""Source-clamped floor keeps real typing and certifies every integer boundary."""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-ORDER']

import math
from fractions import Fraction as F
import unittest

from evas import CompileError, KernelError, compile_sources, solve, transient
from test_affine import KERNEL, instance, model


class FiniteFloor(unittest.TestCase):
    def compile(self, body, declarations='real c; integer q;'):
        return compile_sources({'floor.va':model(body,declarations)}, [instance()])

    def values(self, program, inputs):
        result=solve(program,['u'],[[x] for x in inputs],kernel=KERNEL)
        return [row['voltages'][result['nodes'].index('y')] for row in result['solutions']]

    def test_both_spellings_round_down_at_negative_and_positive_exact_boundaries(self):
        inputs=[-3.,-1.9,-1.,-.2,0.,math.nextafter(1.,-math.inf),1.,math.nextafter(1.,math.inf),3.]
        expected=[]
        for value in inputs:
            exact=max(F(-2),min(F(2),F.from_float(value)))
            expected.append(exact.numerator//exact.denominator)
        for spelling in ('floor','$floor'):
            with self.subTest(spelling=spelling):
                program=self.compile('c=V(u,r);if(c< -2)c=-2;if(c>2)c=2;'
                                     'q='+spelling+'(c);V(y,r)<+q;')
                self.assertEqual(self.values(program,inputs),expected)

    def test_integral_valued_floor_still_has_real_source_type(self):
        program=self.compile('q=floor(1.5)/2;V(y,r)<+q;','real q;')
        self.assertEqual(self.values(program,[0.]),[.5])
        with self.assertRaises(CompileError):
            self.compile('q=floor(1.5)&1;V(y,r)<+q;')

    def test_unbounded_and_only_later_clamped_arguments_remain_rejected(self):
        for body in ['q=floor(V(u,r));if(q<0)q=0;if(q>7)q=7;',
                     'c=V(u,r);if(c<0)c=0;q=floor(8*c);',
                     'c=V(u,r);q=floor(8*c);if(c<0)c=0;if(c>1)c=1;']:
            with self.subTest(body=body),self.assertRaises(CompileError):
                self.compile(body+'V(y,r)<+q;')

    def test_original_dead_arm_and_division_domains_are_not_hidden_by_bounds(self):
        for expression in ['V(u,r)>0?floor(1.5):floor(1/0)', 'floor(1e309)']:
            with self.subTest(expression=expression),self.assertRaises(CompileError):
                self.compile('q='+expression+';V(y,r)<+q;')

    def test_clamps_and_zero_products_preserve_original_overflow_domains(self):
        scale = float.fromhex('0x1p1023')
        for source in [str(scale)+'*V(u,r)', '0*('+str(scale)+'*V(u,r))']:
            with self.subTest(source=source):
                program=self.compile('c='+source+';if(c<0)c=0;if(c>1)c=1;'
                                     'q=floor(c);V(y,r)<+q;')
                with self.assertRaises(KernelError) as failure:
                    self.values(program,[2.])
                self.assertEqual(failure.exception.diagnostic['code'],'kernel.nonfinite_arithmetic')

    def test_integer_storage_and_original_integer_overflow_are_separate_checks(self):
        real_program=self.compile('q=floor(2147483648.0);V(y,r)<+q;','real q;')
        self.assertEqual(self.values(real_program,[0.]),[2147483648.])
        for expression in ['floor(2147483648.0)','floor(2147483647+1)']:
            with self.subTest(expression=expression),self.assertRaises(CompileError):
                self.compile('q='+expression+';V(y,r)<+q;')

    def test_preclamp_partition_limit_is_unchanged(self):
        program=self.compile('c=V(u,r);if(c<0)c=0;if(c>255)c=255;'
                             'q=floor(c);V(y,r)<+q;')
        self.assertEqual(self.values(program,[-1.,255.,300.]),[0.,255.,255.])
        with self.assertRaises(CompileError) as failure:
            self.compile('c=V(u,r);if(c<0)c=0;if(c>256)c=256;'
                         'q=floor(c);V(y,r)<+q;')
        self.assertEqual(failure.exception.diagnostic['code'],'resource_budget')

    def test_input_interval_must_stay_in_one_floor_bin(self):
        program=self.compile('c=V(u,r);if(c<0)c=0;if(c>1)c=1;'
                             'q=$floor(8*c);V(y,r)<+q;')
        # This independent .02 voltage budget admits the .01 input band.
        # The integer value is still exact, and [2.32,2.48] has floor2.
        result=transient(program,{'u':[[0,.3],[1,.3]]},[0,1],stop=1,max_step=1,
                         source_errors={'u':.01},vabstol=.02,reltol=0,kernel=KERNEL)
        self.assertEqual([row['voltages'][result['nodes'].index('y')]
                          for row in result['solutions']],[2.,2.])
        with self.assertRaises(KernelError):
            transient(program,{'u':[[0,.5],[1,.5]]},[0,1],stop=1,max_step=1,
                      source_errors={'u':.01},vabstol=.02,reltol=0,kernel=KERNEL)

    def test_transition_consumer_uses_the_full_sixteen_bin_table(self):
        program=self.compile('c=V(u,r);if(c<0)c=0;if(c>1)c=1;'
                             'q=floor(16*c);V(y,r)<+transition((q>8)?1:0,0,0.0625,0.0625);')
        result=transient(program,{'u':[[0,.25],[.25,.25],[.5,.75],[1,.75]]},
                         [0,.125,.625,1],stop=1,max_step=.125,kernel=KERNEL)
        self.assertEqual([row['voltages'][result['nodes'].index('y')]
                          for row in result['solutions']],[0.,0.,1.,1.])

    def test_residue_and_three_bit_consumers_fit_the_original_wire_budget(self):
        program=self.compile('c=V(u,r);if(c>1)c=1;if(c< -1)c=-1;'
                             'q=floor(4*(c+1)+0.5);if(q>7)q=7;'
                             'V(y,r)<+c-(0.25*q-1);'
                             'V(b0)<+((q&1)?1:0);V(b1)<+(((q>>1)&1)?1:0);'
                             'V(b2)<+(((q>>2)&1)?1:0);',
                             'electrical b0,b1,b2;real c;integer q;')
        inputs=[-1.5,-.875,-.125,.375,1.25]
        result=solve(program,['u'],[[x] for x in inputs],kernel=KERNEL)
        for sample,value in zip(result['solutions'],inputs):
            clipped=max(F(-1),min(F(1),F.from_float(value)))
            argument=4*(clipped+1)+F(1,2)
            code=min(7,argument.numerator//argument.denominator)
            self.assertAlmostEqual(sample['voltages'][result['nodes'].index('y')],
                                   float(clipped-(F(code,4)-1)),places=8)
            for bit in range(3):
                self.assertEqual(sample['voltages'][result['nodes'].index('dut:b'+str(bit))],
                                 (code>>bit)&1)

    def test_table_composition_does_not_discard_original_source_dependencies(self):
        program=self.compile('c=V(u,r);if(c<0)c=0;if(c>1)c=1;'
                             'q=floor(8*c);V(y,r)<+(q&0);')
        with self.assertRaises(KernelError):
            solve(program,[],[[]],kernel=KERNEL)

    def test_instance_clamp_ranges_and_exact_scalar_parameters_are_private(self):
        text=model('c=V(u,r);if(c<0)c=0;if(c>vref)c=vref;'
                   'q=floor(8*c/vref);if(q>7)q=7;V(y,r)<+q;',
                   'parameter real vref=1;real c;integer q;')
        program=compile_sources({'floor.va':text},[
            instance('first',connections={'u':'u','y':'ya','r':'0'}),
            instance('second',connections={'u':'u','y':'yb','r':'0'},parameters={'vref':2})])
        result=solve(program,['u'],[[1.]],kernel=KERNEL)
        for node,expected in [('ya',7.),('yb',4.)]:
            self.assertEqual(result['solutions'][0]['voltages'][result['nodes'].index(node)],expected)
        with self.assertRaises(CompileError):
            compile_sources({'floor.va':text},[instance(parameters={'vref':.9})])


if __name__ == '__main__':
    unittest.main()
