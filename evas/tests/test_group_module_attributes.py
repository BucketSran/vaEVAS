"""Restricted module-prefix attributes, with independent public-path answers.

Only the no-value ignore_hidden_state marker is admitted. It affects no EVAS
voltage equation, event state, or history ownership. Unsupported attribute
values/names/positions remain explicit errors; this is not general attribute
semantics or a hidden-state audit exemption.
"""
GUARDS = ['LANG', 'COMPOSE']

import os
from pathlib import Path
import unittest

from evas import CompileError, Instance, compile_sources, solve

EVAS = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('EVAS_TEST_KERNEL',
                           os.environ.get('EVAS_KERNEL',
                                          EVAS / 'rust_core/target/debug/evas-kernel')))


def source(prefix='', body='V(y)<+1.25;', declarations=''):
    return ('`include "disciplines.vams"\n' + prefix
            + 'module m(y); output y; electrical y;\n'
            + declarations + 'analog begin\n' + body + '\nend\nendmodule\n')


def compile_model(text):
    return compile_sources({'attributes.va': text},
                           [Instance('dut', 'm', {'y': 'y'}, {})])


class ModuleAttributeContracts(unittest.TestCase):
    def test_prefix_marker_preserves_constant_equation_and_real_source_location(self):
        # Both forms mean V(y)=5/4, with one equation and no hidden state.
        for prefix, line in [('', 4), ('(* ignore_hidden_state *)\n', 5),
                             ('(* ignore_hidden_state *)(* ignore_hidden_state *)\n', 5)]:
            with self.subTest(prefix=prefix):
                p = compile_model(source(prefix))
                self.assertEqual(len(p.contributions), 1)
                # Unoriented branch normalization sorts ('0', 'y'), so the
                # represented equation is V(0)-V(y)=-5/4, still V(y)=5/4.
                c = p.contributions[0]
                self.assertEqual((p.nodes[c.positive], p.nodes[c.negative]), ('0', 'y'))
                self.assertEqual(c.rhs.constant, -1.25)
                self.assertEqual(p.contributions[0].rhs.terms, ())
                self.assertEqual(p.contributions[0].origin.source, 'attributes.va')
                self.assertEqual(p.contributions[0].origin.line, line)
                self.assertEqual(p.contributions[0].origin.instance, 'dut')
                self.assertEqual(p.states, ())
                self.assertEqual(p.events, ())

    def test_attributed_equation_reaches_actual_kernel_without_changing_voltage(self):
        for prefix in ['', '(* ignore_hidden_state *)\n']:
            with self.subTest(prefix=prefix):
                p = compile_model(source(prefix))
                r = solve(p, [], [[]], kernel=KERNEL)
                self.assertEqual(r['solutions'][0]['voltages'][p.nodes.index('y')], 1.25)

    def test_default_transition_tokens_survive_attribute_boundary(self):
        prefix = '`default_transition 10p\n(* ignore_hidden_state *)\n'
        p = compile_model(source(prefix, 'V(y)<+transition(1.25);'))
        self.assertEqual(len(p.operators), 1)
        self.assertEqual(p.operators[0].rise, 10e-12)
        self.assertEqual(p.operators[0].fall, 10e-12)
        self.assertEqual(p.operators[0].origin.line, 6)
        self.assertEqual(p.operators[0].origin.source, 'attributes.va')

    def test_comment_and_string_delimiters_are_not_attribute_blocks(self):
        p = compile_model(source('// (* unsupported = V(no_such_node) *)\n',
                                 '@(timer(0.5)) $display("(* literal *)"); V(y)<+1.25;'))
        self.assertEqual(p.contributions[0].rhs.constant, -1.25)
        self.assertEqual(p.contributions[0].rhs.terms, ())
        # The string must remain a display argument, not vanish during filtering.
        self.assertEqual(p.events[0].body[0].format, '(* literal *)')

    def test_unsupported_or_malformed_attributes_are_not_silently_skipped(self):
        for prefix in [
            '(* ignore_hidden_state\n',
            '(* *)\n',
            '(* unknown_annotation *)\n',
            '(* ignore_hidden_state = 1 *)\n',
            '(* ignore_hidden_state = V(missing) *)\n',
            '(* ignore_hidden_state, unknown_annotation *)\n',
            '(* ignore_hidden_state (* ignore_hidden_state *) *)\n',
            '( * ignore_hidden_state * )\n',
            '*)\n',
        ]:
            with self.subTest(prefix=prefix), self.assertRaises(CompileError):
                compile_model(source(prefix))

    def test_marker_does_not_hide_illegal_prefix_position_or_original_expression(self):
        for text in [
            source('garbage (* ignore_hidden_state *)\n'),
            source('(* ignore_hidden_state *) garbage\n'),
            source('', '(* ignore_hidden_state *) V(y)<+1.25;'),
            source('', 'V(y)<+1.25;', '(* ignore_hidden_state *) real x;\n'),
        ]:
            with self.subTest(text=text), self.assertRaises(CompileError):
                compile_model(text)
        # Exact source line remains the original contribution's location.
        with self.assertRaises(CompileError) as caught:
            compile_model(source('(* ignore_hidden_state *)\n', 'V(y)<+V(missing);'))
        self.assertEqual(caught.exception.diagnostic['code'], 'undeclared_node')
        self.assertEqual(caught.exception.diagnostic['location']['source'], 'attributes.va')
        self.assertEqual(caught.exception.diagnostic['location']['line'], 5)
        with self.assertRaises(CompileError):
            compile_model(source('`default_transition 0\n(* ignore_hidden_state *)\n',
                                 'V(y)<+transition(1.25);'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
