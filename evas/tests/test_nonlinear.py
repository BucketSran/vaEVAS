"""Independent polynomial contracts; these controls are development regressions.

Known roots are constructed algebraically, without using EVAS to define answers.
The original 31-condition contracts and checkers remain unchanged.
"""
import copy
import unittest

from evas import CompileError, KernelError, compile_sources, solve
from test_affine import KERNEL, execute, instance, model
import test_contracts as contracts
from test_contracts import wire_request


class PolynomialContracts(unittest.TestCase):
    def test_cubic_known_roots_references_scales_and_sample_order(self):
        source = model('V(y,r)<+V(u,r)-c*pow(V(y,r),3)/(s*s);',
                       'parameter real c=.5; parameter real s=1;')
        for c in (.125, .5, 2, 8):
            for scale, reference in ((.01, -.7), (1, 0), (10, 2)):
                targets = [-3, -.5, 0, .25, 2, -3]
                samples = [[reference+scale*(q+c*q**3), reference] for q in targets]
                rows = execute(source, [instance(connections=dict(u='u', y='y', r='r'),
                    parameters=dict(c=c, s=scale))], ['u', 'r'], samples)
                for row, q in zip(rows, targets):
                    self.assertAlmostEqual(row['y'], reference+scale*q, delta=2e-8*scale)
                self.assertEqual(rows[0], rows[-1])

    def test_products_and_powers_have_independent_forward_answers(self):
        source = model('V(y,r)<+V(u,r)*V(v,r)+pow(V(u,r)+1,4)/2;',
                       ports='u,v,y,r', directions='input u,v; output y; inout r;')
        rows = execute(source, [instance(connections=dict(u='u',v='v',y='y',r='r'))],
                       ['u','v','r'], [[-.5,.7,-.2],[2,-1,.3],[0,0,0]])
        for row in rows:
            u,v,r = row['u'],row['v'],row['r']
            self.assertAlmostEqual(row['y'], r+(u-r)*(v-r)+(u-r+1)**4/2, places=10)

    def test_reverse_additive_contributions_and_parameter_exponent(self):
        source = model('V(y,r)<+V(u,r); V(r,y)<+c*pow(V(y,r),p);',
                       'parameter real p=3; parameter real c=.5;')
        for power in (1,3,5,9):
            q=.75
            row=execute(source,[instance(parameters=dict(p=power))],samples=[[q+.5*q**power]])[0]
            self.assertAlmostEqual(row['y'],q,places=9)
        constant=model('V(y,r)<+a;', 'parameter real a=pow(-2,3);')
        self.assertEqual(execute(constant)[0]['y'],-8)

    def test_coupled_nonlinear_instances_and_declaration_order(self):
        # The symmetric Jacobian has diagonal >= 1 and off-diagonal .25.
        # Construct the RHS from q=(.5,-.25), not from an EVAS run.
        source=model('V(y,r)<+bias-.25*V(u,r)-pow(V(y,r),3);', 'parameter real bias=0;')
        a,b=.5,-.25
        instances=[instance('a',connections=dict(u='b',y='a',r='0'),parameters=dict(bias=a+a**3+.25*b)),
                   instance('b',connections=dict(u='a',y='b',r='0'),parameters=dict(bias=b+b**3+.25*a))]
        rows=[]
        for order in (instances,instances[::-1]):
            program=compile_sources({'coupled.va':source},order)
            result=solve(program,[],[[]],kernel=KERNEL)
            rows.append(dict(zip(result['nodes'],result['solutions'][0]['voltages'])))
        self.assertEqual(rows[0],rows[1])
        self.assertAlmostEqual(rows[0]['a'],a,places=9)
        self.assertAlmostEqual(rows[0]['b'],b,places=9)

    def test_expanded_products_and_nested_powers_match_known_roots(self):
        for expression in ('V(y,r)*V(y,r)*V(y,r)', 'pow(V(y,r),3)',
                           'pow(pow(V(y,r),2),2)*V(y,r)'):
            power = 5 if 'pow(pow' in expression else 3
            source = model('V(y,r)<+V(u,r)-' + expression + ';')
            roots = [-2, -.25, 0, .5, 3]
            rows = execute(source, samples=[[q+q**power] for q in roots])
            for row, q in zip(rows, roots):
                self.assertAlmostEqual(row['y'], q, places=8)

    def test_parallel_nonlinear_constraints_remain_separate(self):
        source=model('V(y,r)<+V(u,r)-c*pow(V(y,r),3);','parameter real c=1;')
        self.assertAlmostEqual(execute(source,[instance('a'),instance('b')],samples=[[2]])[0]['y'],1,places=9)
        with self.assertRaises(KernelError):
            execute(source,[instance('a'),instance('b',parameters=dict(c=2))],samples=[[2]])

    def test_nonconvergence_singular_jacobian_and_nonfinite(self):
        cases=[('V(y,r)<+V(y,r)-pow(V(y,r),2)-1;', 'singular_jacobian'),
               ('V(y,r)<+V(y,r)-(pow(V(y,r),3)-2*V(y,r)+2);','nonconvergence'),
               ('V(y,r)<+pow(V(u,r),3);','nonfinite_arithmetic')]
        for body,kind in cases:
            with self.subTest(kind=kind), self.assertRaises(KernelError) as error:
                execute(model(body),samples=[[1e200]] if kind=='nonfinite_arithmetic' else [[0]])
            self.assertEqual(error.exception.detail['kind'],kind)
            self.assertEqual(error.exception.detail['sample'],0)
            self.assertIn('test.va:',error.exception.detail['message'])

    def test_all_driven_constraints_and_batch_failure(self):
        source=model('V(y,r)<+pow(V(u,r),3);')
        program=compile_sources({'driven.va':source},[instance()])
        with self.assertRaises(KernelError) as error:
            solve(program,['u','y'],[[2,8],[2,9]],kernel=KERNEL)
        self.assertEqual(error.exception.detail['sample'],1)
        self.assertEqual(error.exception.detail['kind'],'residual_failure')

    def test_unsupported_exponents_divisors_and_calls_are_explicit(self):
        for expression in ('pow(V(u,r),0)','pow(V(u,r),-1)','pow(V(u,r),.5)',
                           'pow(V(u,r),33)','pow(V(u,r),V(u,r))','1/V(u,r)',
                           'sin(V(u,r))','pow(V(u,r))','pow(V(u,r),2,3)'):
            with self.subTest(expression=expression),self.assertRaises(CompileError):
                compile_sources({'bad.va':model('V(y,r)<+'+expression+';')},[instance()])


class PolynomialWireContracts(unittest.TestCase):
    request = contracts.BranchContracts.request

    def test_handwritten_polynomial_and_nested_validation(self):
        request=wire_request()
        rhs=dict(op='power',base=dict(op='affine',constant=-2,terms=[]),exponent=3)
        request['program']['contributions'][0]['rhs']=rhs
        self.assertEqual(self.request(request)['solutions'][0]['voltages'],[0,8])
        mutations=[(dict(exponent=0),'invalid_ir'),(dict(exponent=33),'invalid_ir'),
                   (dict(exponent=-1),'invalid_request'),(dict(exponent=2.5),'invalid_request'),
                   (dict(op='sin'),'invalid_request'),(dict(extra=True),'invalid_request'),
                   (dict(base=dict(op='affine',constant=0,terms=[dict(node=2,coefficient=1)])),'invalid_ir')]
        for fields,kind in mutations:
            changed=copy.deepcopy(request); changed['program']['contributions'][0]['rhs'].update(fields)
            with self.subTest(fields=fields): self.request(changed,kind)


if __name__=='__main__':
    unittest.main()
