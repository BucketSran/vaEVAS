"""Effective parameter values and set membership, not parser acceptance alone."""
GUARDS = ["LANG"]

import unittest
from evas import CompileError, Instance, compile_sources
from test_affine import execute, instance, model


class ParameterConstraints(unittest.TestCase):
    def test_literal_integer_defaults_ranges_and_child_overrides_are_checked(self):
        # 3/2*2 is 2 with integer division, 3 after real lowering. The bounded
        # frontend must reject it, even when no integer parameter is referenced.
        for declaration in ('parameter integer n=3/2*2;',
                            'parameter integer n=2147483647*2/2;',
                            'parameter integer n=3 from [0:3/2*2];',
                            'parameter real n=3 from [0:3/2*2];'):
            with self.subTest(declaration=declaration):
                with self.assertRaises(CompileError) as caught:
                    compile_sources({'p.va':model('V(y)<+n;',declaration)},[instance()])
                self.assertEqual(caught.exception.diagnostic['code'],'unsupported_integer_arithmetic')
        source=model('V(y)<+n;', 'parameter integer n=3/2*2;')
        self.assertEqual(execute(source,[instance(parameters={'n':4})])[0]['y'],4)
        self.assertEqual(execute(model('V(y)<+n;','parameter integer n=3/2.0*2;'))[0]['y'],3)
        for value in (-2147483648,2147483647):
            self.assertEqual(execute(model('V(y)<+n;',f'parameter integer n={value};'))[0]['y'],value)
        source='''module child(y); output y; electrical y;
            parameter integer n=1; analog begin V(y)<+n; end endmodule
            module parent(y); output y; electrical y;
            child #(.n(3/2*2)) c(y); endmodule'''
        with self.assertRaises(CompileError) as caught:
            compile_sources({'p.va':source},[Instance('p','parent',{'y':'y'})])
        self.assertEqual(caught.exception.diagnostic['code'],'unsupported_integer_arithmetic')

    def test_integer_semantics_survive_genvar_substitution_in_node_indices(self):
        source = '''module m(y); output y; electrical y; electrical [3:0] x;
            parameter integer n=3; genvar i;
            analog begin
                for(i=1;i<2;i=i+1) V(x[n/(i+1)*2])<+1;
                V(y)<+V(x[3]);
            end
            endmodule'''
        # Integer arithmetic selects bit 2; real arithmetic would select bit 3.
        with self.assertRaises(CompileError) as caught:
            compile_sources({'p.va':source},[Instance('a','m',{'y':'y'})])
        self.assertEqual(caught.exception.diagnostic['code'],'unsupported_integer_arithmetic')

    def test_integer_division_and_overflow_are_not_silently_real_arithmetic(self):
        for rhs in ('n/2','n+1/2','n*2147483647'):
            with self.subTest(rhs=rhs), self.assertRaises(CompileError) as caught:
                compile_sources({'p.va':model('V(y)<+'+rhs+';', 'parameter integer n=3;')},[instance()])
            self.assertEqual(caught.exception.diagnostic['code'],'unsupported_integer_arithmetic')
        self.assertEqual(execute(model('V(y)<+n/2.0;', 'parameter integer n=3;'))[0]['y'],1.5)
        with self.assertRaises(CompileError):
            compile_sources({'p.va':model('V(y)<+gain;', 'parameter integer n=3; parameter real gain=n/2;')},[instance()])
        with self.assertRaises(CompileError):
            compile_sources({'p.va':model('for(i=1;i<3;i=i+1) V(y)<+n/i;', 'parameter integer n=3; genvar i;')},[instance()])

    def test_comma_declarations_bind_each_value_and_range(self):
        source = model('V(y,r)<+a+b;', 'parameter integer a=2 from [1:3], b=a+1 from (a:5);')
        self.assertEqual(execute(source)[0]['y'],5)
        with self.assertRaisesRegex(CompileError,'range'):
            compile_sources({'p.va':source},[instance(parameters=dict(b=2))])

    def test_integer_parameters_and_instance_isolation(self):
        source = model('V(y,r)<+n;', 'parameter integer n=4 from [1:8];')
        instances = [instance('a', connections=dict(u='u',y='a',r='0')),
                     instance('b', connections=dict(u='u',y='b',r='0'), parameters=dict(n=7))]
        row = execute(source, instances)[0]
        self.assertEqual((row['a'],row['b']), (4,7))
        for bad in (2.5, 2147483648, -2147483649):
            with self.assertRaises(CompileError) as caught:
                compile_sources({'p.va':source}, [instance(parameters=dict(n=bad))])
            self.assertEqual(caught.exception.diagnostic['code'], 'parameter_type')

    def test_interval_union_exclusions_and_effective_overrides(self):
        source = model('V(y,r)<+p;', 'parameter real p=-1 from [0:1] from (2:4) exclude .5 exclude [3:3.5);')
        for good in (0,1,2.25,3.5):
            self.assertEqual(execute(source, [instance(parameters=dict(p=good))])[0]['y'], good)
        for bad in (-1,.5,2,3,3.25,4):
            with self.subTest(bad=bad), self.assertRaises(CompileError) as caught:
                compile_sources({'p.va':source}, [instance(parameters=dict(p=bad))])
            self.assertEqual(caught.exception.diagnostic['code'], 'parameter_range')

    def test_infinity_and_parameter_dependent_bounds(self):
        source = model('V(y,r)<+p;', 'parameter real p=2 from (lo:inf); parameter real lo=1 exclude 0;')
        self.assertEqual(execute(source)[0]['y'],2)
        for overrides in (dict(lo=2),dict(lo=0)):
            with self.assertRaisesRegex(CompileError,'range'):
                compile_sources({'p.va':source},[instance(parameters=overrides)])
        self.assertEqual(execute(model('V(y,r)<+p;', 'parameter real p=-2 from (-inf:0);'))[0]['y'],-2)

    def test_invalid_bounds_cannot_hide_behind_override(self):
        for constraint in ('from [3:2]', 'from [2:2]', 'from [V(u):4]', 'from [missing:4]', 'exclude 1/0'):
            with self.subTest(constraint=constraint), self.assertRaises(CompileError):
                compile_sources({'p.va':model('V(y,r)<+p;', 'parameter real p=1 '+constraint+';')}, [instance(parameters=dict(p=3))])
