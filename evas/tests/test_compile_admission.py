"""Public compilation admission, independently specified by VAMS 2.4 §2.6."""
GUARDS = ['LANG']

import unittest
from evas import CompileError, Instance, compile_sources

BODY = 'module m(y); output y; electrical y; analog begin V(y)<+VALUE; end endmodule'
INSTANCE = Instance('dut', 'm', {'y': 'y'})

class CompileAdmission(unittest.TestCase):
    def compile(self, value='0.5', prefix='`include "disciplines.vams"\n', headers=None):
        return compile_sources({'dut.va': prefix + BODY.replace('VALUE', value), **(headers or {})}, [INSTANCE])

    def test_real_literal_requires_digits_on_both_sides_of_point(self):
        for literal in ('.25', '.5', '.875', '1.', '1.e2', '.5u'):
            with self.subTest(literal=literal), self.assertRaisesRegex(CompileError, r'dut.va:2:.*real literal'):
                self.compile(literal)
        for literal in ('0.25', '0.5', '0.875', '1.0', '1e2', '0.5u'):
            with self.subTest(literal=literal):
                self.compile(literal)

    def test_electrical_requires_a_preceding_supported_definition(self):
        with self.assertRaisesRegex(CompileError, r'dut.va:1:.*electrical.*not declared'):
            self.compile(prefix='')
        self.compile()
        definition = ('nature Voltage; units="V"; access=V; abstol=1u; endnature\n'
                      'nature Current; units="A"; access=I; abstol=1p; endnature\n'
                      'discipline electrical; potential Voltage; flow Current; domain continuous; enddiscipline\n')
        self.compile(prefix=definition)
        self.compile(prefix='`include "custom.vams"\n', headers={'custom.vams': definition})
        with self.assertRaises(CompileError):
            self.compile(prefix='`include "disciplines.vams"\n', headers={'disciplines.vams': ''})
        with self.assertRaises(CompileError):
            self.compile(prefix='', headers={'later.va':definition})

    def test_preprocessing_only_checks_active_expanded_tokens(self):
        self.compile(prefix='`ifdef NEVER\n`include "missing.vams"\n'+BODY.replace('VALUE','.5')+'\n`endif\n`include "disciplines.vams"\n')
        self.compile('`IGNORE(.5)', prefix='`include "disciplines.vams"\n`define IGNORE(x) 0.5\n')
        self.compile('`GOOD', prefix='`include "disciplines.vams"\n`define BAD .5\n`define GOOD 0.5\n')
        with self.assertRaisesRegex(CompileError, r'dut.va:3:.*real literal'):
            self.compile('`BAD', prefix='`include "disciplines.vams"\n`define BAD .5\n')
        with self.assertRaisesRegex(CompileError, r'dut.va:1:.*electrical.*not declared'):
            self.compile(prefix='', headers={'unused.vams':'`include "disciplines.vams"\n'})
        self.compile(prefix='`include "custom.vams"\n', headers={'custom.vams':'`include "disciplines.vams"\n'})

    def test_supplied_headers_are_authoritative_and_redefinitions_reject(self):
        definition = ('nature Voltage; units="V"; access=V; abstol=1u; endnature\n'
                      'nature Current; units="A"; access=I; abstol=1p; endnature\n'
                      'discipline electrical; potential Voltage; flow Current; domain continuous; enddiscipline\n')
        self.compile(prefix='`include "disciplines.vams"\n', headers={'disciplines.vams':definition})
        for invalid in (definition.replace('domain continuous', 'domain discrete'),
                        definition.replace('access=V', 'access=X'),
                        definition + definition,
                        definition.replace('abstol=1u', 'abstol=0')):
            with self.subTest(header=invalid), self.assertRaisesRegex(CompileError, r'disciplines.vams:'):
                self.compile(prefix='`include "disciplines.vams"\n', headers={'disciplines.vams':invalid})
        program = self.compile('`M_PI', prefix='`include "constants.vams"\n`include "disciplines.vams"\n',
                               headers={'constants.vams':'`define M_PI 3\n'})
        self.assertEqual(program.contributions[0].rhs.constant, -3)
        with self.assertRaisesRegex(CompileError, r'undefined or unsupported macro'):
            self.compile('`M_PI')
        with self.assertRaisesRegex(CompileError, r'dut.va:1:.*was not provided'):
            self.compile(prefix='`include "missing.vams"\n')

    def test_override_cannot_hide_invalid_source_and_unused_include_is_inactive(self):
        source = '`include "disciplines.vams"\n'+BODY.replace('analog begin','parameter real p=.5; analog begin').replace('VALUE','p')
        with self.assertRaisesRegex(CompileError, r'real literal'):
            compile_sources({'dut.va':source}, [Instance('dut','m',{'y':'y'},{'p':1})])
        with self.assertRaisesRegex(CompileError, r'not declared'):
            self.compile(prefix='`ifdef NEVER\n`include "disciplines.vams"\n`endif\n')

    def test_frozen_invalid_sources_reject_and_explicit_successors_compile(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        for case, reason in (('event_relocalization', 'real literal'),
                             ('projected_history', 'real literal'),
                             ('pure_function', 'not declared')):
            binding = Instance('dut', case, {'u':'u', 'y':'y', 'r':'0'})
            original = root/'validation/cases'/case/'dut.va'
            with self.subTest(case=case), self.assertRaisesRegex(CompileError, reason):
                compile_sources({str(original):original.read_text()}, [binding])
            successor = root/'tests/fixtures'/f'{case}.va'
            compile_sources({str(successor):successor.read_text()}, [binding])

    def test_independent_roots_do_not_share_disciplines_or_macros(self):
        a = '`include "disciplines.vams"\n`define ROOT_VALUE 1\n'+BODY.replace('module m(', 'module A(').replace('VALUE','1')
        b = BODY.replace('module m(', 'module B(').replace('VALUE','2')
        bindings = [Instance('a','A',{'y':'a'}), Instance('b','B',{'y':'b'})]
        for roots in ({'a.va':a,'b.va':b}, {'b.va':b,'a.va':a}):
            with self.subTest(order=list(roots)), self.assertRaisesRegex(CompileError, r'b.va:1:.*electrical.*not declared'):
                compile_sources(roots, bindings)
        b = '`include "disciplines.vams"\n'+b.replace('<+2', '<+`ROOT_VALUE')
        for roots in ({'a.va':a,'b.va':b}, {'b.va':b,'a.va':a}):
            with self.subTest(order=list(roots)), self.assertRaisesRegex(CompileError, r'b.va:2:.*undefined or unsupported macro'):
                compile_sources(roots, bindings)

    def test_each_root_keeps_its_include_graph_and_standard_guards(self):
        a = '`include "disciplines.vams"\n'+BODY.replace('module m(', 'module A(').replace('VALUE','1')
        b = '`include "disciplines.vams"\n`include "disciplines.vams"\n'+BODY.replace('module m(', 'module B(').replace('VALUE','2')
        bindings = [Instance('a','A',{'y':'a'}), Instance('b','B',{'y':'b'})]
        for roots in ({'a.va':a,'b.va':b}, {'b.va':b,'a.va':a}):
            with self.subTest(order=list(roots)):
                program = compile_sources(roots, bindings)
                from evas.query import static_index
                self.assertEqual({m['name'] for m in static_index(program, bindings, roots)['modules']}, {'A','B'})
        self.compile('`HEADER_VALUE', prefix='`include "custom.vams"\n', headers={
            'custom.vams':'`include "disciplines.vams"\n`define HEADER_VALUE 3\n'})
        # Two module definitions in one textual include graph share its environment.
        compile_sources({'top.va':a+'\n`include "child.vams"\n', 'child.vams':b.split('\n',2)[2]}, bindings)

    def test_frozen_smoke_refusals_and_versioned_manifest_successors(self):
        from pathlib import Path
        from evas.lint import lint_manifest
        root = Path(__file__).resolve().parents[1]
        for case, reason in (('absdelay','not declared'), ('timer_counter','not declared'),
                             ('cross_counter','real literal')):
            with self.subTest(case=case):
                with self.assertRaisesRegex(CompileError, reason):
                    lint_manifest(root/'validation/smoke'/f'{case}.json')
                self.assertEqual(lint_manifest(root/'tests/fixtures/smoke-admission-v1'/f'{case}.json')['status'], 'lint_passed')
