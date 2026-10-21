"""Integer conditional prefixes preserve source checks and expanded-tree limits."""
GUARDS = ['LANG', 'ANALOG', 'COMPOSE']

from itertools import product
import unittest

from evas import CompileError, Instance, compile_sources, solve
from test_affine import KERNEL, instance, model


def outputs(response, name='y'):
    return [row['voltages'][response['nodes'].index(name)] for row in response['solutions']]


class IntegerPrefixContracts(unittest.TestCase):
    def test_eight_independent_inputs_count_to_four_bits(self):
        inputs = [f'b{i}' for i in range(8)]
        result_ports = [f'y{i}' for i in range(4)]
        ports = inputs + result_ports
        body = 'count=0;' + ''.join(f'if(V({name})>0.5)count=count+1;' for name in inputs)
        body += ''.join(f'V(y{i})<+((count>>{i})&1);' for i in range(4))
        source = ('`include "disciplines.vams"\nmodule m('+','.join(ports)+'); input '+
                  ','.join(inputs)+'; output '+','.join(result_ports)+'; electrical '+
                  ','.join(ports)+'; integer count; analog begin '+body+' end endmodule')
        program = compile_sources({'count.va':source}, [Instance('d','m',{n:n for n in ports})])
        samples = [list(row) for row in product((0.,1.), repeat=8)] + [[0.5]*8]
        response = solve(program, inputs, samples, kernel=KERNEL)
        for bit in range(4):
            self.assertEqual(outputs(response, f'y{bit}'),
                             [(sum(x>0.5 for x in row)>>bit)&1 for row in samples])

    def test_old_alias_and_each_delta_arm_keep_source_order(self):
        cases = [
            ('code=1;if(V(u,r)>0.5)code=code+2;old=code;code=code+4;V(y,r)<+old*10+code;',
             'integer code,old;', [15,15,37]),
            ('code=5;if(V(u,r)>0.5)code=code+2;else code=code+3;V(y,r)<+code;',
             'integer code;', [8,8,7]),
            ('code=5;if(V(u,r)>0.5)begin end else code=code+3;V(y,r)<+code;',
             'integer code;', [8,8,5]),
        ]
        for body,decl,expected in cases:
            with self.subTest(body=body):
                p=compile_sources({'order.va':model(body,decl)},[instance()])
                self.assertEqual(outputs(solve(p,['u'],[[0],[0.5],[1]],kernel=KERNEL)),expected)

    def test_original_overflow_dead_arms_and_undefined_reads_still_reject(self):
        for body,decl in [
            ('code=2147483647;if(V(u,r)>0.5)code=code+1;code=code-1;V(y,r)<+code;', 'integer code;'),
            ('code=-2147483648;if(V(u,r)>0.5)code=code-1;code=code+1;V(y,r)<+code;', 'integer code;'),
            ('code=0;if(0>1)code=2147483647+1;V(y,r)<+code;', 'integer code;'),
            ('code=0;if(0>1)code=unknown;V(y,r)<+code;', 'integer code;'),
            ('if(V(u,r)>0.5)code=code+1;V(y,r)<+code;', 'integer code;'),
            ('code=0;if(V(u,r)>0.5)code=ddt(V(u,r));V(y,r)<+code;', 'integer code;'),
            ('code=0;if(V(u,r)>0.5)code=code+0.5;V(y,r)<+code;', 'integer code;'),
        ]:
            with self.subTest(body=body),self.assertRaises(CompileError):
                compile_sources({'negative.va':model(body,decl)},[instance()])

    def test_declared_real_merge_keeps_original_select(self):
        from evas.ir import Affine,Binary,Select
        p=compile_sources({'real.va':model(
            'code=1;if(V(u,r)>0.25)code=code+2;if(V(u,r)>0.5)code=code+4;V(y,r)<+code;', 'real code;')},[instance()])
        rhs=p.contributions[0].rhs
        if isinstance(rhs,Binary) and rhs.op=='multiply' and isinstance(rhs.left,Affine):
            rhs=rhs.right
        self.assertIsInstance(rhs,Select)
        self.assertIsInstance(rhs.then_value,Binary)
        self.assertEqual(rhs.then_value.op,'add')
        self.assertIs(rhs.then_value.left,rhs.else_value)
        self.assertEqual(outputs(solve(p,['u'],[[0],[0.5],[1]],kernel=KERNEL)),[1,3,7])

    def test_helper_only_uses_identical_declared_integer_prefixes(self):
        from evas.integer_prefix import factor_integer_prefix
        from evas.ir import Affine, Binary, Origin, Select
        zero,one,two=Affine(0.,()),Affine(1.,()),Affine(2.,())
        prefix=Binary('add',one,two)
        delta=Affine(3.,());origin=Origin('identity.va',1,1,'d')
        yes=Binary('add',prefix,delta)
        checks=[]
        def validate(value, location):
            checks.append(value)
            self.assertIs(location,origin)
        value=factor_integer_prefix('gt',one,zero,yes,prefix,origin,
                                    integer_target=True,validate_integer=validate)
        self.assertIs(value.left,prefix)
        self.assertIs(value.right.then_value,delta)
        self.assertEqual(checks,[yes,prefix])
        self.assertIs(value.right.origin,origin)
        for integer_target,no in [(False,prefix),(True,Binary('add',one,two))]:
            checks.clear()
            raw=factor_integer_prefix('gt',one,zero,yes,no,origin,
                                     integer_target=integer_target,validate_integer=validate)
            self.assertIsInstance(raw,Select)
            self.assertIs(raw.then_value,yes)
            self.assertIs(raw.else_value,no)
            self.assertEqual(checks,[])

    def test_state_operator_and_checked_wrappers_are_not_moved(self):
        from evas.integer_prefix import factor_integer_prefix
        from evas.ir import Affine,Binary,CheckedInteger,EventMath,OperatorRef,Origin,Select,StateRef
        zero,one=Affine(0.,()),Affine(1.,());origin=Origin('scope.va',1,1,'d')
        forbidden=[StateRef(0),OperatorRef(0),CheckedInteger(one,origin),EventMath('abs',(one,),origin)]
        for prefix in forbidden:
            with self.subTest(prefix=prefix):
                yes=Binary('add',prefix,one)
                raw=factor_integer_prefix('gt',one,zero,yes,prefix,origin,
                    integer_target=True,validate_integer=lambda *args:self.fail('excluded tree validated for factoring'))
                self.assertIsInstance(raw,Select)
                self.assertIs(raw.else_value,prefix)
        for guard in forbidden:
            with self.subTest(guard=guard):
                raw=factor_integer_prefix('gt',guard,zero,Binary('add',one,one),one,origin,
                    integer_target=True,validate_integer=lambda *args:self.fail('excluded guard validated for factoring'))
                self.assertIsInstance(raw,Select)

    def test_validation_failure_cannot_be_rewritten_away(self):
        from evas.integer_prefix import factor_integer_prefix
        from evas.ir import Affine,Binary,Origin
        prefix=Affine(2147483647.,());yes=Binary('add',prefix,Affine(1.,()))
        def reject(value,origin):
            raise CompileError('original signed32 overflow')
        with self.assertRaisesRegex(CompileError,'original signed32 overflow'):
            factor_integer_prefix('gt',Affine(1.,()),Affine(0.,()),yes,prefix,Origin('bad.va',1,1,'d'),
                                  integer_target=True,validate_integer=reject)

    def test_wire_expansion_budget_counts_repeated_objects(self):
        from evas.ir import Affine,Binary
        from evas.limits import check_ir
        value=Affine(1.,())
        for _ in range(15):
            value=Binary('add',value,value)
        with self.assertRaisesRegex(CompileError,'100000'):
            check_ir(value)


if __name__=='__main__':
    unittest.main()
