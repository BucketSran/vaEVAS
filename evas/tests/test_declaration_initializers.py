"""Finite scalar declaration seeds at the public compile_sources boundary.

Hand answers follow declaration initialization before initial_step. Rejections
preserve the selected event-state-only contract rather than broaden VA support.
No simulator or kernel build is used by this module.
"""
GUARDS = ["LANG"]

import unittest
from evas import CompileError, compile_sources
from evas.frontend import Instance


def source(declarations, body="", event="x=x+1;", output="x"):
    return ('`include "disciplines.vams"\n'
            'module m(i,o); input i; output o; electrical i,o;\n'
            + declarations + '\nanalog begin\n' + body + '\n'
            + (f'@(cross(V(i)-0.5,+1)) begin {event} end\n' if event else '')
            + f'V(o)<+{output};\nend endmodule\n')


def compile_one(text, parameters=None):
    return compile_sources({'declaration.va': text},
                           [Instance('dut', 'm', {'i': 'i', 'o': 'o'}, parameters or {})])


class DeclarationInitializers(unittest.TestCase):
    def initials(self, program):
        return {(s.instance, s.name): s.initial for s in program.states}

    def test_event_state_seed_and_initial_step_override(self):
        # A declaration supplies 3; initial_step executes later and leaves 7.
        p = compile_one(source('integer x=3;', '@(initial_step) x=7;'))
        self.assertEqual(self.initials(p), {('dut', 'x'): 7})
        p = compile_one(source('integer x=3;'))
        self.assertEqual(self.initials(p), {('dut', 'x'): 3})

    def test_mixed_declarators_real_and_integer_minimum(self):
        # Uninitialized y retains the existing zero default; r is exact binary .5.
        p = compile_one(source('integer x=-2147483648,y; real r=0.5;',
            event='x=0; y=1; r=2;', output='r'))
        self.assertEqual(self.initials(p), {
            ('dut', 'x'): -2147483648, ('dut', 'y'): 0, ('dut', 'r'): .5})

    def test_parameter_override_is_instance_local(self):
        text = source('parameter integer P=3; integer x=P+1;')
        instances = [Instance('a', 'm', {'i':'ia', 'o':'oa'}, {'P':2}),
                     Instance('b', 'm', {'i':'ib', 'o':'ob'}, {'P':5})]
        for order in (instances, instances[::-1]):
            with self.subTest(order=[i.name for i in order]):
                self.assertEqual(self.initials(compile_sources({'m.va':text}, order)),
                                 {('a','x'):3, ('b','x'):6})

    def test_invalid_seed_is_rejected_even_when_overwritten(self):
        for kind, value in [('integer','1.5'), ('integer','2147483648'),
                            ('integer','2147483647+1-1'), ('real','1e308*10'),
                            ('real','1e309'), ('real','missing'), ('real','1/0'),
                            ('real','V(i)'), ('real','$abstime'), ('real','sin(1)')]:
            with self.subTest(kind=kind, value=value), self.assertRaises(CompileError):
                compile_one(source(f'{kind} x={value};', '@(initial_step) x=0;'))

    def test_initializer_cannot_read_another_declared_variable(self):
        for declaration in ('integer a=2; integer x=a;', 'integer x=x;',
                            'integer x=a; integer a=2;'):
            with self.subTest(declaration=declaration), self.assertRaises(CompileError):
                compile_one(source(declaration, event='x=1; a=3;'))

    def test_initializer_cannot_create_a_persistent_role(self):
        cases = [source('integer x=3;', event=''),
                 source('integer x=3;', '@(initial_step) x=7;', event=''),
                 source('real x=3;', 'x=V(i);', event=''),
                 source('real x=3;', event='y=1;', output='x')
                    .replace('real x=3;', 'real x=3; integer y;')]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(CompileError):
                compile_one(text)

    def test_array_illegal_type_and_duplicate_declarations_reject(self):
        for declaration in ('integer x[0:1]=1;', 'real x[0:1]={1,2};',
                            'genvar x=1;', 'string x="a";',
                            'integer x=1; real x;', 'integer x=1,x=2;',
                            'parameter integer x=1; integer x=2;', 'integer i=1;'):
            with self.subTest(declaration=declaration), self.assertRaises(CompileError):
                compile_one(source(declaration))

    def test_compile_failure_does_not_change_later_instance_seeds(self):
        valid = source('parameter real P=2; real x=P;')
        with self.assertRaises(CompileError):
            compile_one(valid, {'P':float('inf')})
        self.assertEqual(self.initials(compile_one(valid, {'P':5})), {('dut','x'):5})
        with self.assertRaises(CompileError):
            compile_one(source('integer x=2147483648;'))
        self.assertEqual(self.initials(compile_one(valid, {'P':2})), {('dut','x'):2})

    def test_source_integer_type_is_preserved_even_for_real_seed(self):
        # Division truncates toward zero before assignment to either target type.
        for expression, expected in [('7/2',3), ('(-7)/2',-3), ('7/2.0',3.5),
                                      ('(-1)>>1',2147483647), ('1<<31',-2147483648),
                                      ('(7&3)+1',4)]:
            text = source(f'real x={expression};')
            with self.subTest(expression=expression):
                self.assertEqual(self.initials(compile_one(text)), {('dut','x'):expected})
        text = source('parameter integer P=5; real x=(P&3);')
        self.assertEqual(self.initials(compile_one(text)), {('dut','x'):1})
        for expression in ('2147483647+1-1', '1.0&1', '(-2147483648)/(-1)', '7%2'):
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                compile_one(source(f'real x={expression};', '@(initial_step) x=0;'))
        # Parameter operand types still determine division before a real seed.
        for declaration, expected in (
            ('parameter integer P=7; real x=P/2;', 3),
            ('parameter integer P=-7; real x=P/2;', -3),
            ('parameter real P=7; real x=P/2;', 3.5),
        ):
            with self.subTest(declaration=declaration):
                self.assertEqual(self.initials(compile_one(source(declaration))),
                                 {('dut', 'x'): expected})

    def test_bad_seed_diagnostic_keeps_its_declaration_location(self):
        with self.assertRaises(CompileError) as caught:
            compile_one(source('real x=V(i);', '@(initial_step) x=0;'))
        self.assertEqual(caught.exception.diagnostic['code'], 'unsupported_initial_event')
        self.assertEqual(caught.exception.diagnostic['location']['source'], 'declaration.va')
        self.assertEqual(caught.exception.diagnostic['location']['line'], 3)

    def test_seed_survives_functions_arrays_and_hierarchy(self):
        leaf = source('''parameter real P=1; real x=twice(P); integer a[0:1];
            analog function real twice; input z; real z; begin twice=2*z; end endfunction''',
            event='a[0]=1; x=2;', output='x')
        top = ('`include "disciplines.vams"\nmodule top(i,o); input i; output o; '
               'electrical i,o; m #(.P(3)) leaf(i,o); endmodule')
        program = compile_sources({'leaf.va':leaf, 'top.va':top},
                                  [Instance('dut','top',{'i':'i','o':'o'})])
        self.assertEqual(self.initials(program), {('dut/leaf','x'):6, ('dut/leaf','a[0]'):0})

    def test_declared_seed_and_initial_step_precede_cross_updates(self):
        # Two triangular rising crossings occur at .5us and 2.5us.
        from evas import transient
        from test_affine import KERNEL
        text = source('integer x=3;')
        for initial, expected in [('', [3,3,4,4,5,5]),
                                  ('@(initial_step) x=7;', [7,7,8,8,9,9])]:
            with self.subTest(initial=initial):
                program = compile_one(text if not initial else source('integer x=3;', initial))
                result = transient(program, {'i':[[0,.4],[1e-6,.6],[2e-6,.4],[3e-6,.6]]},
                    [0,.25e-6,.75e-6,1.75e-6,2.75e-6,3e-6],
                    stop=3e-6, max_step=10e-6, kernel=KERNEL)
                self.assertEqual(result['transient']['states'], [[x] for x in expected])
                y = result['nodes'].index('o')
                self.assertEqual([row['voltages'][y] for row in result['solutions']], expected)

    def test_existing_no_initializer_event_state_keeps_default_zero(self):
        self.assertEqual(self.initials(compile_one(source('integer x;'))), {('dut','x'):0})


if __name__ == '__main__':
    unittest.main(verbosity=2)
