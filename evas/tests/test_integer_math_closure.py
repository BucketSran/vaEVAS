"""Signed division ranges and public modulo-counter closure.

Expected residues use independent quotient enumeration over small domains;
public execution has a fixed counter sequence rather than a helper oracle.
"""
GUARDS = ["LANG", "TIMER", "EVENT-ORDER", "EVENT-CONDITIONS"]

import unittest
from fractions import Fraction

from evas import CompileError, Instance, KernelError, compile_sources, transient
from evas.integer_arithmetic import bounds
from test_affine import KERNEL, execute, instance, model


class IntegerMathClosure(unittest.TestCase):
    def test_runtime_divisor_signed_sequences(self):
        cases=[(10,8,9,'n+1','%',[10,3,4,5,6]),
               (-10,-8,-9,'n-1','%',[-10,-3,-4,-5,-6]),
               (-7,-2,-3,'n','/',[-7,3,-1,0,0])]
        for start,divisor,changed,update,operator,expected in cases:
            source=model('@(initial_step)begin n='+str(start)+';d='+str(divisor)+';end '
                '@(timer(0.25,0.25,1e-12))begin n='+update+';n=n'+operator+'d;end '
                '@(timer(0.375))d='+str(changed)+';V(y,r)<+n;','integer n,d;')
            program=compile_sources({'runtime-divisor.va':source},[instance()])
            result=transient(program,{'u':[[0,0],[1,0]]},[0,.25,.5,.75,1],
                             stop=1,max_step=.25,kernel=KERNEL)
            y=result['nodes'].index('y')
            self.assertEqual([row['voltages'][y] for row in result['solutions']],expected)

    def test_runtime_divisor_joint_budget_and_original_arithmetic_guards(self):
        for last,accepted in ((16,True),(17,False)):
            source=model('@(initial_step)begin n=0;d=1;end '
                '@(timer(0.125))if(V(u,r)>0)n=15;else n=0; '
                '@(timer(0.25))if(V(u,r)>0)d='+str(last)+';else d=1; '
                '@(timer(0.375))q=n%d;V(y,r)<+q;','integer n,d;real q;')
            if accepted:
                compile_sources({'joint256.va':source},[instance()])
            else:
                with self.assertRaises(CompileError):
                    compile_sources({'joint272.va':source},[instance()])
        for declarations,body in [
                ('integer n,d;real q;', '@(initial_step)begin n=3;d=1;end '
                 '@(timer(0.125))if(V(u,r)>0)d=0;@(timer(0.25))q=n/d;V(y,r)<+q;'),
                ('integer n,d;real q;', '@(initial_step)begin n=3;d=1;end '
                 '@(timer(0.25))q=n/(d&0);V(y,r)<+q;'),
                ('integer n,d;real q;', '@(initial_step)begin n=-2147483648;d=-1;end '
                 '@(timer(0.25))q=n/d;V(y,r)<+q;'),
                ('integer n,d;real q;', '@(initial_step)begin n=1;d=2;end '
                 '@(timer(0.25))q=((n+2147483647)-2147483647)%d;V(y,r)<+q;'),
                ('integer n,d;real q;parameter integer take=0;',
                 '@(initial_step)begin n=3;d=0;end '
                 '@(timer(0.25))if(take)q=n/d;else q=2;V(y,r)<+q;')]:
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_sources({'invalid-runtime-divisor.va':model(body,declarations)},[instance()])

    def test_runtime_divisor_singleton_preserves_same_batch_read(self):
        source=model('@(initial_step)begin n=3;d=1;end '
            '@(timer(0.25))d=1;@(timer(0.25))q=n/d;','integer n,d;real q;')
        source+=' module fixed(y);output y;electrical y;analog begin V(y)<+1;end endmodule'
        program=compile_sources({'singleton-divisor.va':source},
                                [instance(),Instance('source','fixed',{'y':'y'})])
        with self.assertRaisesRegex(KernelError,'cannot read state written'):
            transient(program,{'u':[[0,0],[1,0]]},[0,.25,.5],stop=1,max_step=.25,kernel=KERNEL)

    def test_finite_power_signed_counter_and_reciprocal(self):
        for expression, expected in [('pow(2.0,n)', [.5,1,2,4,4]),
                                     ('1.0/pow(2.0,n)', [2,1,.5,.25,.25])]:
            source=model('@(initial_step)begin n=-1;q='+str(expected[0])+';end '
                '@(timer(0.25,0.25,1e-12))begin if(n<2)n=n+1;q='+expression+';end V(y,r)<+q;',
                'integer n; real q;')
            program=compile_sources({'finite-power.va':source},[instance()])
            result=transient(program,{'u':[[0,0],[1,0]]},[0,.25,.5,.75,1],
                             stop=1,max_step=.25,kernel=KERNEL)
            y=result['nodes'].index('y')
            self.assertEqual([row['voltages'][y] for row in result['solutions']],expected)

    def test_finite_power_weighted_feedback_and_counter_guard(self):
        cases=[(1,'n<=4','n+1','1.0/pow(2.0,n)',[0,.5,.75,.875,.9375]),
               (2,'n>=0','n-1','pow(2.0,n)',[0,4,6,7,7])]
        for initial,guard,update,weight,expected in cases:
            source=model('@(initial_step)begin n='+str(initial)+';q=0;end '
                '@(timer(0.25,0.25,1e-12))begin if('+guard+')begin '
                'if(V(u,r)>0)q=q+'+weight+';n='+update+';end end V(y,r)<+q;',
                'integer n;real q;')
            program=compile_sources({'weighted-power.va':source},[instance()])
            for data in (0,1):
                result=transient(program,{'u':[[0,data],[1,data]]},[0,.25,.5,.75,1],
                                 stop=1,max_step=.25,kernel=KERNEL)
                y=result['nodes'].index('y')
                self.assertEqual([row['voltages'][y] for row in result['solutions']],
                                 expected if data else [0,0,0,0,0])

    def test_finite_power_preserves_type_domain_and_original_intermediates(self):
        for declarations, update, expression in [
                ('integer n; real q;', 'n=n+1;', 'pow(2.0,n)'),
                ('integer n; real q;', 'if(n<33)n=n+1;', 'pow(2.0,n)'),
                ('real n,q;', 'if(n<2)n=n+1;', 'pow(2.0,n)'),
                ('integer n; real q;', 'if(n<2)n=n+1;', 'pow(3.0,n)'),
                ('integer n; real q;', 'if(n<2)n=n+1;', 'pow(0.0,n-1)'),
                ('integer n; real q;', 'if(n<2)n=n+1;', 'pow(2.0,(n+2147483647)-2147483647)'),
                ('integer n; real q;', 'if(n<2)n=n+1;', 'pow(2.0,n)&1'),
                ('integer n; real q;', 'if(n<2)n=n+1;', 'pow(1.7976931348623157e308,n)'),
                ('integer n; real q;', 'if(n<2)n=n+1;', 'pow(8.98846567431158e307,n)'),
                ('integer n; real q;', 'if(n<2)n=n+1;', 'pow(2.2250738585072014e-308,n)')]:
            source=model('@(initial_step)n=0; @(timer(0.25))begin '+update+'q='+expression+';end V(y,r)<+q;',declarations)
            with self.subTest(expression=expression,update=update), self.assertRaises(CompileError):
                compile_sources({'bad-finite-power.va':source},[instance()])

    def test_unused_power_keeps_pure_math_domain_and_static_obligations(self):
        source=model('@(initial_step)n=0; @(timer(0.5)) '
            'if(active)q=pow(0.0,n-1);else q=2; V(y,r)<+q;',
            'parameter integer active=0;integer n;real q;')
        program=compile_sources({'unused-power.va':source},[instance()])
        result=transient(program,{'u':[[0,0],[1,0]]},[0,.75,1],
                         stop=1,max_step=.25,kernel=KERNEL)
        y=result['nodes'].index('y')
        self.assertEqual([row['voltages'][y] for row in result['solutions']],[0,2,2])
        # The old pure unused-domain policy does not permit an illegal typed
        # integer intermediate to disappear from an unselected math argument.
        invalid=source.replace('n=0','n=1').replace('pow(0.0,n-1)',
                                                  'pow(2.0,(n+2147483647)-2147483647)')
        with self.assertRaises(CompileError):
            compile_sources({'unused-overflow-power.va':invalid},[instance()])

    def test_finite_power_counts_actual_decisions_even_in_parameter_dead_code(self):
        for gate in (0,1):
            source=model('@(initial_step)begin n=0;m=0;k=0;end '
                '@(timer(0.25))begin if(n<32)n=n+1;if(m<32)m=m+1;if(k<32)k=k+1;'
                'if(gate)q=pow(2.0,n)*pow(2.0,m)*pow(2.0,k);end V(y,r)<+q;',
                'integer n,m,k; real q; parameter integer gate='+str(gate)+';')
            with self.subTest(gate=gate), self.assertRaises(CompileError) as caught:
                compile_sources({'finite-power-budget.va':source},[instance()])
            self.assertEqual(caught.exception.diagnostic['code'],'resource_budget')

    def test_finite_power_singleton_keeps_same_batch_read_dependency(self):
        source=model('@(timer(0.25))n=0; @(timer(0.25))q=pow(2.0,n);','integer n; real q;')
        source+=' module fixed(y);output y;electrical y;analog begin V(y)<+1;end endmodule'
        program=compile_sources({'singleton-power.va':source},
                                [instance(),Instance('source','fixed',{'y':'y'})])
        with self.assertRaisesRegex(KernelError,'cannot read state written'):
            transient(program,{'u':[[0,0],[1,0]]},[0,.25,.5],stop=1,max_step=.25,kernel=KERNEL)

    def test_typed_parameter_division_defaults_ranges_and_real_operands(self):
        cases = [('parameter integer seed=9; parameter integer q=seed/2;', 4),
                 ('parameter integer seed=-9; parameter integer q=seed/2;', -4),
                 ('parameter integer q=9/2;', 4),
                 ('parameter integer q=-9/2;', -4),
                 ('parameter real q=9.0/2;', 4.5),
                 ('parameter integer seed=9; parameter real q=seed/2;', 4),
                 ('parameter integer q=4 from [9/2:5];', 4),
                 ('parameter integer q=-4 from [-5:-9/2];', -4)]
        for declarations, expected in cases:
            with self.subTest(declarations=declarations):
                self.assertEqual(execute(model('V(y,r)<+q;', declarations))[0]['y'], expected)

    def test_typed_parameter_division_overrides_and_instance_isolation(self):
        declarations = 'parameter integer seed=9; parameter integer q=seed/2;'
        source = model('V(y,r)<+q;', declarations)
        row = execute(source, [instance('a', connections=dict(u='u',y='a',r='0')),
                               instance('b', connections=dict(u='u',y='b',r='0'),
                                        parameters={'seed':-9})])[0]
        self.assertEqual((row['a'], row['b']), (4,-4))
        # Overriding this default removes its arithmetic dependency, as before.
        source = model('V(y,r)<+q;', 'parameter integer q=1/0;')
        self.assertEqual(execute(source, [instance(parameters={'q':7})])[0]['y'], 7)

    def test_typed_child_override_uses_parent_type_in_each_instance(self):
        source = '''`include "disciplines.vams"
module child(y); output y; electrical y; parameter integer q=0;
analog begin V(y)<+q; end endmodule
module parent(u,y); input u; output y; electrical u,y; parameter integer seed=9;
child #(.q(seed/2)) c(y); endmodule'''
        row = execute(source, [Instance('a','parent',{'u':'u','y':'a'}),
                               Instance('b','parent',{'u':'u','y':'b'},{'seed':-9})])[0]
        self.assertEqual((row['a'], row['b']), (4,-4))
        for expression in ('(seed+2147483647)/2', 'seed/0'):
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                compile_sources({'bad-child-division.va':source.replace('seed/2',expression)},
                                [Instance('a','parent',{'u':'u','y':'a'})])

    def test_typed_parameter_division_preserves_invalid_originals(self):
        for declarations, body in [
                ('parameter integer q=9/0;', 'V(y,r)<+q;'),
                ('parameter integer q=(2147483647+1)/2;', 'V(y,r)<+q;'),
                ('parameter integer q=(-2147483648)/(-1);', 'V(y,r)<+q;'),
                ('parameter integer n=1;', 'V(y,r)<+(1?n:(n+2147483647)/2);'),
                ('parameter integer seed=1; genvar i,j;',
                 'for(i=0;i<2;i=i+1) for(j=0;j<(i+2147483647-2147483647)/2;j=j+1) V(y,r)<+0; V(y,r)<+seed;')]:
            with self.subTest(declarations=declarations, body=body), self.assertRaises(CompileError):
                compile_sources({'bad-parameter-division.va':model(body,declarations)}, [instance()])

    def test_remainder_interval_matches_independent_finite_results(self):
        for divisor in (-7, -3, -1, 1, 3, 7):
            for low in range(-12, 13):
                for high in range(low, 13):
                    values = []
                    for value in range(low, high + 1):
                        # Select the quotient with smallest absolute residual,
                        # among those leaving the dividend's sign unchanged.
                        quotients = range(-13, 14)
                        residues = [value-divisor*q for q in quotients
                                    if abs(value-divisor*q)<abs(divisor)
                                    and (value-divisor*q)*value>=0]
                        self.assertEqual(len(residues), 1)
                        values.extend(residues)
                    self.assertEqual(bounds('%', [(low, high), (divisor, divisor)]),
                                     (min(values), max(values)))
        for numerator in ((-7,-3),(-2,2),(0,8)):
            for divisor in ((-4,-1),(1,4)):
                quotients,remainders=[],[]
                for n in range(numerator[0],numerator[1]+1):
                    for d in range(divisor[0],divisor[1]+1):
                        quotient=int(Fraction(n,d))
                        quotients.append(quotient)
                        remainders.append(n-d*quotient)
                self.assertEqual(bounds('/',[numerator,divisor]),(min(quotients),max(quotients)))
                self.assertEqual(bounds('%',[numerator,divisor]),(min(remainders),max(remainders)))
        self.assertEqual(bounds('%', [(-2147483648,2147483647),(8,8)]), (-7,7))
        self.assertIsNone(bounds('%', [(0,8),(0,0)]))
        self.assertEqual(bounds('%', [(0,8),(1,2)]), (0,1))
        self.assertIsNone(bounds('%', [(0,8),(-1,1)]))
        self.assertIsNone(bounds('%', [(0,8),(1,257)]))

    def test_modulo_counter_closes_and_preserves_signed_remainder(self):
        for initial, delta, expected in [(7, 1, [7,0,1,2,3]),
                                         (-7, -1, [-7,0,-1,-2,-3])]:
            source = model('@(initial_step)n='+str(initial)+'; '
                '@(timer(0.25,0.25,1e-12))n=(n+('+str(delta)+'))%8; V(y,r)<+n;',
                'integer n;')
            program = compile_sources({'modulo-counter.va':source}, [instance()])
            result = transient(program, {'u':[[0,0],[1,0]]}, [0,.25,.5,.75,1],
                               stop=1,max_step=.25,kernel=KERNEL)
            y = result['nodes'].index('y')
            self.assertEqual([s['voltages'][y] for s in result['solutions']], expected)

    def test_modulo_cannot_erase_invalid_original_intermediate_or_dead_arm(self):
        for expression in ('(n+2147483647)%8', 'n%0',
                           '1 ? n%8 : (2147483647+1)%8', '(-2147483648)%(-1)'):
            source = model('@(initial_step)n=1; @(timer(0.25))n='+expression+'; V(y,r)<+n;',
                           'integer n;')
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                compile_sources({'invalid-modulo.va':source}, [instance()])


if __name__ == '__main__':
    unittest.main()
