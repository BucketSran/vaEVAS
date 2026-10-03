"""Compiler resource failures must be bounded, diagnostic, and transportable."""
GUARDS = ["LANG", "COMPOSE"]

import json
import unittest
from evas import CompileError, compile_sources, solve
from evas.ir import Affine, Binary, BranchIdentity, Contribution, Origin, Program
from test_affine import KERNEL, instance, model


class FrontendLimits(unittest.TestCase):
    def compile(self, source):
        return compile_sources({'limits.va': source}, [instance()])

    def test_deep_syntax_and_flat_expression_have_source_diagnostics(self):
        bodies = [
            'V(y,r)<+' + '('*1500+'1'+')'*1500+';',
            'V(y,r)<+' + '+'.join(['1']*1500)+';',
            'V(y,r)<+' + '-'*1500+'1;',
            'begin '*1500 + 'x=1;' + 'end '*1500 + 'V(y,r)<+x;',
        ]
        for body in bodies:
            with self.subTest(body=body[:30]), self.assertRaisesRegex(CompileError, r'limits.va:\d+:\d+: .*limit'):
                self.compile(model(body, 'real x;'))

    def test_parameter_chain_limit_and_short_hand_answer(self):
        for count in (12, 400):
            declarations = ' '.join(f'parameter real p{i}=' + ('1;' if i == count-1 else f'p{i+1}+1;') for i in range(count))
            source = model('V(y,r)<+p0;', declarations)
            if count == 400:
                with self.assertRaisesRegex(CompileError, r'limits.va:\d+:\d+: .*limit'):
                    self.compile(source)
            else:
                p=self.compile(source)
                row=solve(p,['u'],[[0]],kernel=KERNEL)['solutions'][0]['voltages']
                self.assertEqual(row[p.nodes.index('y')],count)

    def test_parameter_depth_does_not_depend_on_declaration_order(self):
        declarations = [f'parameter real p{i}=' + ('1;' if i == 69 else f'p{i+1}+1;') for i in range(70)]
        for ordered in (declarations, list(reversed(declarations))):
            with self.subTest(order=ordered[0]), self.assertRaisesRegex(CompileError, 'parameter dependency depth limit'):
                self.compile(model('V(y,r)<+p0;', ' '.join(ordered)))

    def test_expression_and_parameter_depth_do_not_multiply_the_stack(self):
        declarations = ' '.join(f'parameter real p{i}=' + ('1;' if i == 39 else '+'*40+f'p{i+1}+1;') for i in range(40))
        p = self.compile(model('V(y,r)<+p0;', declarations))
        result = solve(p, ['u'], [[0]], kernel=KERNEL)
        self.assertEqual(result['solutions'][0]['voltages'][p.nodes.index('y')], 40)

    def test_sequential_selects_are_bounded_before_predicate_analysis(self):
        source = model('x=0;' + 'if(V(u,r)>0) x=1;'*1500 + 'if(x>0) x=2; V(y,r)<+x;', 'real x;')
        with self.assertRaisesRegex(CompileError, r'limits.va:\d+:\d+: .*limit'):
            self.compile(source)

    def test_shared_expression_expansion_is_rejected_before_serialization(self):
        source=model('x=V(u,r);'+'x=x+x;'*30+'V(y,r)<+x;', 'real x;')
        with self.assertRaisesRegex(CompileError, r'limits.va:\d+:\d+: .*limit'):
            self.compile(source)

    def test_direct_program_serialization_also_has_expansion_guard(self):
        expr=Affine(1,())
        for _ in range(16):
            expr=Binary('add',expr,expr)
        p=Program(('0','y'),(Contribution(BranchIdentity('dut','0','y'),0,1,expr,Origin('direct.va',3,4,'dut')),))
        with self.assertRaisesRegex(CompileError, 'limit'):
            p.to_dict()

    def test_unused_local_does_not_move_rejection_to_rust(self):
        for count in (16, 120):
            expression='+'.join(['V(y,r)']*count)+'+1'
            outcomes=[]
            for local in (False,True):
                source=model(('x=1;' if local else '')+'V(y,r)<+'+expression+';', 'real x;' if local else '')
                try:
                    p=self.compile(source)
                except CompileError as error:
                    self.assertIn('limit',str(error)); outcomes.append('compile_limit')
                else:
                    result=solve(p,['u'],[[0]],kernel=KERNEL)
                    self.assertAlmostEqual(result['solutions'][0]['voltages'][p.nodes.index('y')],1/(1-count))
                    outcomes.append('success')
            self.assertEqual(outcomes[0],outcomes[1])
            if count == 16:
                self.assertEqual(outcomes,['success','success'])

    def test_small_shared_expression_preserves_value_and_ir(self):
        p=self.compile(model('x=V(u,r);'+'x=x+x;'*8+'V(y,r)<+x;', 'real x;'))
        self.assertEqual(json.loads(json.dumps(p.to_dict()))['schema_version'],16)
        result=solve(p,['u'],[[.125]],kernel=KERNEL)
        self.assertEqual(result['solutions'][0]['voltages'][p.nodes.index('y')],32)
