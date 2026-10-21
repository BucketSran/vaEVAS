"""LRM 2.4 §§4.5.8/10.3: ordered defaults through public compilation/runtime."""
GUARDS = ['LANG', 'TRANSITION']
import unittest
from evas import CompileError, compile_sources, transient
from test_affine import KERNEL, instance, model


class DefaultTransitionDirective(unittest.TestCase):
    def compile(self, prefix, call='transition(a)', headers=None, declarations=''):
        return compile_sources({'dut.va': prefix + '\n' + model(
            '@(initial_step) a=0; @(timer(1)) a=1; V(y,r)<+'+call+';',
            'real a;'+declarations), **(headers or {})}, [instance()])

    def test_missing_edges_use_directive_in_actual_kernel(self):
        p = self.compile('`default_transition 2')
        r = transient(p, {'u':[[0,0],[4,0]]}, [0,1,2,3,4], stop=4, max_step=.25, kernel=KERNEL)
        for row, expected in zip(r['solutions'], [0,0,.5,1,1], strict=True):
            self.assertAlmostEqual(row['voltages'][p.nodes.index('y')], expected, delta=2e-12)

    def test_explicit_edges_and_zero_parameter_edges(self):
        for call, declarations, expected in [
            ('transition(a,0,3)', '', (3,3)),
            ('transition(a,0,3,4)', '', (3,4)),
            ('transition(a,0,0)', '', (2,2)),
            ('transition(a,0,z,4)', 'parameter real z=0;', (2,4)),
            ('transition(a,0,3,z)', 'parameter real z=0;', (3,2)),
            ('transition(a,1)', '', (2,2))]:
            with self.subTest(call=call):
                op = self.compile('`default_transition 2', call, declarations=declarations).operators[0]
                self.assertEqual((op.rise,op.fall), expected)

    def test_include_order_macro_expression_and_latest_default(self):
        prefix='`define T 2\n`default_transition (`T/2.0)\n`include "settings.vams"\n'
        p=self.compile(prefix, headers={'settings.vams':'`default_transition (`T+1)\n'})
        self.assertEqual(p.operators[0].rise, 3)
        # A later directive must not change an earlier module's call sites.
        first='`default_transition 1\n'+model('V(y,r)<+transition(0);')
        second='`default_transition 3\n'+model('V(y,r)<+transition(0);').replace('module m(', 'module n(')
        p=compile_sources({'both.va':first+'\n'+second}, [instance(),instance('two','n')])
        self.assertEqual([op.rise for op in p.operators], [1,3])

    def test_independent_roots_do_not_leak_defaults(self):
        other='`default_transition 2\n'+model('V(y,r)<+transition(0);').replace('module m(', 'module n(')
        for inventory in ({'other.va':other,'dut.va':model('V(y,r)<+transition(0);')},
                          {'dut.va':model('V(y,r)<+transition(0);'),'other.va':other}):
            with self.assertRaises(CompileError) as caught:
                compile_sources(inventory,[instance()])
            self.assertEqual(caught.exception.diagnostic['code'], 'unsupported_transition_default_edges')

    def test_instance_parameter_overrides_preserve_default_and_explicit_edges(self):
        source='`default_transition 2\n'+model('V(y,r)<+transition(0,0,t);', 'parameter real t=0;')
        p=compile_sources({'dut.va':source}, [instance('zero'), instance('positive',parameters={'t':4})])
        self.assertEqual([(op.rise,op.fall) for op in p.operators], [(2,2),(4,4)])
        with self.assertRaises(CompileError):
            compile_sources({'dut.va':source}, [instance(parameters={'t':-1})])

    def test_bad_directives_and_unknown_macros_remain_errors(self):
        for prefix in ['`default_transition', '`default_transition -1', '`default_transition 0',
                       '`default_transition 1e999', '`default_transition unknown',
                       '`default_transition `UNKNOWN', '`default_transition 2 trailing',
                       '`default_transition .2', '`default_transition 1/0',
                       '`default_transition 3/2', '`default_transition 2147483647*2']:
            with self.subTest(prefix=prefix), self.assertRaises(CompileError):
                self.compile(prefix, 'transition(a,0,1)')
        with self.assertRaisesRegex(CompileError, 'outside module'):
            self.compile('', declarations='\n`default_transition 2\n')
        with self.assertRaisesRegex(CompileError, 'outside module'):
            self.compile('', headers={'bad.vams':'`default_transition 2\n'}, declarations='\n`include "bad.vams"\n')
        with self.assertRaisesRegex(CompileError, 'UNKNOWN'):
            self.compile('`default_transition 2', 'transition(`UNKNOWN,0,1)')

    def test_no_directive_keeps_existing_boundary_and_inactive_branch(self):
        op=self.compile('', 'transition(a,0,3)').operators[0]
        self.assertEqual((op.rise,op.fall),(3,3))
        for call in ['transition(a)', 'transition(a,0)', 'transition(a,0,0)']:
            with self.subTest(call=call), self.assertRaises(CompileError):
                self.compile('',call)
        p=self.compile('`ifdef ABSENT\n`default_transition -1\n`endif\n`default_transition 2')
        self.assertEqual(p.operators[0].rise,2)
        with self.assertRaises(CompileError):
            self.compile('`default_transition 2','transition(a,0,-1)')
