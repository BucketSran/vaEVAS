"""Display arguments retain name checks before dead loops/branches are erased."""
GUARDS = ['LANG', 'EVENT-ORDER']

import unittest

from evas import CompileError, compile_sources
from test_affine import instance, model


class DisplayNodeDeclarations(unittest.TestCase):
    def compile(self, statement):
        return compile_sources(
            {'display-names.va': model('@(timer(0.5)) begin ' + statement
                                      + ' end V(y,r)<+0;', 'integer i;')},
            [instance()],
        )

    def test_declared_display_node_in_zero_trip_loop_is_admitted(self):
        self.compile('for(i=0;i<0;i=i+1) $display("u=%g",V(u,r));')

    def test_undeclared_display_node_in_zero_trip_loop_is_rejected(self):
        with self.assertRaises(CompileError) as caught:
            self.compile('for(i=0;i<0;i=i+1) $display("u=%g",V(missing,r));')
        self.assertEqual(caught.exception.diagnostic['code'], 'undeclared_node')

    def test_undeclared_display_node_in_dead_conditional_is_rejected(self):
        with self.assertRaises(CompileError) as caught:
            self.compile('if(0>1) $display("u=%g",V(u,missing));')
        self.assertEqual(caught.exception.diagnostic['code'], 'undeclared_node')
