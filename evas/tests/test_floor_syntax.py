"""Floor has one real-valued argument at the public source parsing boundary."""
GUARDS = ['LANG']

import unittest
from evas import CompileError, compile_sources, solve
from evas.frontend import parse_sources
from test_affine import model, instance, KERNEL


class FloorSyntax(unittest.TestCase):
    def test_bare_and_system_spelling_keep_one_argument_and_real_type(self):
        for spelling in ('floor', '$floor'):
            with self.subTest(spelling=spelling):
                parsed = parse_sources({'floor.va':model('V(y,r)<+'+spelling+'(V(u,r));')})['m']
                expression = parsed.analog[0].rhs
                self.assertEqual(expression.op, 'floor')
                self.assertEqual(expression.result_type, 'real')
                self.assertEqual(len(expression.args), 1)
                self.assertEqual(expression.args[0].op, 'voltage')

    def test_arity_and_malformed_calls_reject_at_parse(self):
        for spelling in ('floor', '$floor'):
            for suffix in ('()', '(1,2)', '(,1)', '(1,)', '(1'):
                with self.subTest(spelling=spelling,suffix=suffix), self.assertRaises(CompileError):
                    parse_sources({'floor.va':model('V(y,r)<+'+spelling+suffix+';')})

    def test_floor_remains_a_legal_parameter_identifier(self):
        parsed = parse_sources({'floor.va':model('V(y,r)<+floor;').replace('analog begin', 'parameter real floor=0.55; analog begin')})['m']
        self.assertEqual(parsed.analog[0].rhs.op, 'parameter')
        self.assertEqual(parsed.analog[0].rhs.value, 'floor')

    def user_floor_source(self, body, function_body='floor=x+1;', inputs='x', locals='x'):
        declaration = ('analog function real floor; input '+inputs+'; real '+locals+
                       '; begin '+function_body+' end endfunction ')
        return model(body, 'real c;').replace('analog begin', declaration+'analog begin')

    def values(self, source, samples):
        program = compile_sources({'floor.va':source}, [instance()])
        response = solve(program, ['u'], [[value] for value in samples], kernel=KERNEL)
        return [row['voltages'][response['nodes'].index('y')] for row in response['solutions']]

    def test_declared_user_floor_precedes_bare_builtin(self):
        self.assertEqual(self.values(self.user_floor_source('V(y,r)<+floor(V(u,r));'), [.25]), [1.25])

    def test_system_floor_remains_builtin_beside_user_floor(self):
        source = self.user_floor_source('c=V(u,r);if(c< -1)c=-1;if(c>1)c=1;'
                                        'V(y,r)<+floor(V(u,r))+$floor(c);')
        self.assertEqual(self.values(source, [.25,-.25]), [1.25,-.25])
        with self.assertRaises(CompileError):
            compile_sources({'floor.va':self.user_floor_source('V(y,r)<+$floor(V(u,r));')}, [instance()])

    def test_user_floor_keeps_declared_arity(self):
        source = self.user_floor_source('V(y,r)<+floor(V(u,r),2);', 'floor=x+z;', 'x,z', 'x,z')
        self.assertEqual(self.values(source, [.25]), [2.25])
        with self.assertRaises(CompileError):
            compile_sources({'floor.va':self.user_floor_source('V(y,r)<+floor(V(u,r),2);')}, [instance()])

    def test_function_binding_is_forward_visible_and_module_local(self):
        helper = ('analog function real helper; input x; real x; '
                  'begin helper=floor(x); end endfunction ')
        source = self.user_floor_source('V(y,r)<+helper(V(u,r));')
        source = source.replace('analog function real floor;', helper+'analog function real floor;')
        self.assertEqual(self.values(source, [.25]), [1.25])
        other = model('V(y,r)<+floor(0.25);').replace('module m(', 'module other(')
        models = parse_sources({'both.va':source+other})
        self.assertEqual(models['other'].analog[0].rhs.op, 'floor')

    def test_system_name_suffix_does_not_become_floor_call(self):
        with self.assertRaises(CompileError):
            parse_sources({'floor.va':model('V(y,r)<+$floor_extra(1);')})


if __name__ == '__main__':
    unittest.main()
