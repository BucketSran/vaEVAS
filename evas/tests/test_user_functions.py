"""Pure functions inline into the same voltage relations and event guards."""
GUARDS = ["LANG", "LIN", "CROSS", "COMPOSE", "case:pure_function"]

from pathlib import Path
import unittest
from evas import CompileError, compile_sources, solve, transient
from test_affine import KERNEL, instance

PREFIX = '''module m(u,y,r); input u; output y; inout r; electrical u,y,r;
parameter real gain=2;
analog function real transfer;
  input x;
  real x,tmp;
  begin tmp=gain*x; transfer=tmp+1; end
endfunction
'''


def compiled(body, prefix=PREFIX, instances=None):
    return compile_sources({'function.va':prefix+'analog begin '+body+' end endmodule'},
                           instances or [instance()])


class PureFunctions(unittest.TestCase):
    def test_parameter_binding_and_noncontractive_voltage_feedback(self):
        path = Path(__file__).resolve().parents[1] / 'validation/cases/pure_function/dut.va'
        p = compile_sources({'function.va':path.read_text()},[instance(module='pure_function')])
        result = solve(p,['u'],[[1],[2]],kernel=KERNEL)
        y = result['nodes'].index('y')
        self.assertEqual([s['voltages'][y] for s in result['solutions']], [1,5/3])

    def test_local_sequential_assignment_and_two_call_sites(self):
        prefix = PREFIX.replace('tmp=gain*x; transfer=tmp+1;',
                                'tmp=x; tmp=tmp+gain; transfer=tmp; transfer=transfer+1;')
        result = solve(compiled('V(y,r)<+transfer(V(u,r))+transfer(2*V(u,r));',prefix),
                       ['u'],[[1]],kernel=KERNEL)
        self.assertEqual(result['solutions'][0]['voltages'][result['nodes'].index('y')],9)

    def test_function_polynomial_guard_keeps_all_roots(self):
        prefix = '''module m(u,y,r); input u; output y; inout r; electrical u,y,r;
integer n;
analog function real guard;
input x; real x;
begin guard=(x-.25)*(x-.75); end
endfunction
'''
        p = compiled('@(initial_step) n=0; @(cross(guard(V(u,r)),0,1e-9,1e-8)) n=n+1; V(y,r)<+n;',prefix)
        r = transient(p,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([e['time'] for e in r['transient']['events']],[.25,.75])

    def test_nested_calls_keep_instance_parameter_isolation(self):
        prefix = PREFIX+'''analog function real twice;
input x; real x; begin twice=transfer(transfer(x)); end endfunction
'''
        instances = [instance('a',connections={'u':'u','y':'a','r':'0'}),
                     instance('b',connections={'u':'u','y':'b','r':'0'},parameters={'gain':3})]
        for order in (instances,instances[::-1]):
            r = solve(compiled('V(y,r)<+twice(V(u,r));',prefix,order), ['u'],[[1]],kernel=KERNEL)
            v=dict(zip(r['nodes'],r['solutions'][0]['voltages']))
            self.assertEqual((v['a'],v['b']),(7,13))

    def test_rejected_scope_and_uninitialized_locals(self):
        for definition,call in (
            ('input x; real x; begin transfer=transfer(x); end','transfer(1)'),
            ('input x; real x; begin transfer=V(u,r); end','transfer(1)'),
            ('input x; real x; begin transfer=idt(x,0); end','transfer(1)'),
            ('input x; real x,t; begin transfer=t; end','transfer(1)'),
            ('input x; real x; begin transfer=x; end','transfer(1,2)'),
            ('input x; real x; begin transfer=x; end','missing(1)'),
            ('input x; real x; begin transfer=x; end','transfer(idt(V(u,r),0))'),
        ):
            prefix=PREFIX[:PREFIX.index('analog function')]+f'analog function real transfer; {definition} endfunction\n'
            with self.subTest(definition=definition,call=call), self.assertRaises(CompileError):
                compiled(f'V(y,r)<+{call};',prefix)

    def test_shared_argument_expansion_has_a_bounded_wire_size(self):
        prefix = PREFIX.replace('tmp=gain*x; transfer=tmp+1;', 'transfer=x+x;')
        call = 'V(u,r)'
        for _ in range(20):
            call = f'transfer({call})'
        with self.assertRaisesRegex(CompileError, 'budget'):
            compiled(f'V(y,r)<+{call};',prefix)

    def test_unknown_call_without_declarations_is_a_compile_diagnostic(self):
        prefix = PREFIX[:PREFIX.index('analog function')]
        for call in ('missing()', 'missing(V(u,r))'):
            with self.subTest(call=call), self.assertRaisesRegex(CompileError, 'unknown analog function'):
                compiled(f'V(y,r)<+{call};',prefix)

    def test_deep_definition_chain_is_a_diagnostic_not_python_recursion_failure(self):
        prefix = PREFIX[:PREFIX.index('analog function')]
        for i in range(64):
            rhs = f'f{i+1}(x)' if i<63 else 'x'
            rhs = '+'.join([rhs]+['0']*12)
            prefix += f'analog function real f{i}; input x; real x; begin f{i}={rhs}; end endfunction\n'
        with self.assertRaisesRegex(CompileError, 'budget'):
            compiled('V(y,r)<+f0(V(u,r));',prefix)


if __name__ == '__main__':
    unittest.main()
