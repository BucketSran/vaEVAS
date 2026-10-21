"""Bound finite parameters share the literal held-target contract."""
GUARDS = ["LANG", "TRANSITION", "EVENT-ORDER", "COMPOSE"]
import unittest
from evas import Instance, compile_sources, transient, CompileError
from test_affine import KERNEL
from test_native_integer_events import model


def program(target, *, declaration='parameter real supply=0.9;', overrides=None):
    text=model('n=n+1;',decl=declaration+'integer n;real out;',initial='n=0;out=0;')
    text=text.replace('V(y,r)<+out;',f'V(y,r)<+transition({target},0,0.1,0.1);')
    return compile_sources({'held-parameter.va':text},[Instance('dut','m',dict(y='y',r='0'),overrides or {})])


def values(p):
    r=transient(p,{},[0,.5,1.2,2.2],stop=2.2,max_step=.1,kernel=KERNEL)
    return [s['voltages'][r['nodes'].index('y')] for s in r['solutions']]


class HeldTargetParameters(unittest.TestCase):
    def test_parameter_true_arm_follows_actual_callback(self):
        self.assertEqual(values(program('(n&1)?supply:0.0')),[0,0,.9,0])

    def test_parameter_false_arm_and_bound_alias_override(self):
        p=program('(n&1)?0.0:rail',declaration='parameter real supply=0.9;parameter real rail=supply;',overrides={'supply':.3})
        self.assertEqual(values(p),[.3,.3,0,.3])

    def test_direct_literal_keeps_old_successful_path(self):
        self.assertEqual(values(program('(n&1)?0.9:0.0')),[0,0,.9,0])

    def test_nonfinite_and_divide_by_zero_parameters_still_reject(self):
        for value in [float('nan'),float('inf'),-float('inf')]:
            with self.subTest(value=value),self.assertRaises(CompileError):
                program('(n&1)?supply:0.0',overrides={'supply':value})
        with self.assertRaises(CompileError):
            program('(n&1)?supply:0.0',declaration='parameter real supply=1.0/0.0;')

    def test_real_state_and_hidden_input_dependencies_still_reject(self):
        for target in ['(n&1)?supply:out','(n&1)?supply:0.0*V(y,r)',
                       '(n&1)?supply:0.0*$abstime']:
            with self.subTest(target=target),self.assertRaises(CompileError):program(target)

    def test_input_dependent_parameter_binding_still_rejects(self):
        with self.assertRaises(CompileError):
            program('(n&1)?supply:0.0',declaration='parameter real supply=V(y,r);')
