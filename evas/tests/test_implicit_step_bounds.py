"""Implicit DAE model mesh requests, checked against y=t by substitution."""
GUARDS = ["DYNAMICS"]

import unittest
from evas.runtime import KernelError
from test_continuous_dynamics import compile_model, run, values, assert_close


class ImplicitStepBounds(unittest.TestCase):
    def test_dynamic_voltage_bound_is_applied_to_internal_accepted_mesh(self):
        body = 'V(y,r)<+idt(1+2*V(y,r),0)-pow(V(y,r),2);'
        ordinary = run(compile_model(body), times=[0, 1], stop=1,
                       vabstol=1e-9, reltol=0)
        bounded = compile_model(body + '$bound_step(0.015625/(1+V(y,r)));')
        sparse = run(bounded, times=[0, .5, 1], stop=1, vabstol=1e-9, reltol=0)
        self.assertGreater(sparse['transient']['accepted_steps'],
                           ordinary['transient']['accepted_steps'])
        dense = run(bounded, times=[i/32 for i in range(33)], stop=1,
                    vabstol=1e-9, reltol=0)
        for t, actual in zip([0, .5, 1], values(sparse)):
            assert_close(self, actual, t, delta=1e-9)
        self.assertEqual(values(sparse), [values(dense)[i] for i in [0, 16, 32]])
        self.assertEqual(sparse['transient']['accepted_steps'],
                         dense['transient']['accepted_steps'])

    def test_conditional_bound_uses_implicit_operator_and_driven_frame(self):
        # On y=t, z=idt(1+2y,0)=t+t^2. The bound is only active
        # after the exact source corner at t=1/2.
        body = ('z=idt(1+2*V(y,r),0); V(y,r)<+z-pow(V(y,r),2);'
                'if(V(u,r)>0.5) $bound_step(0.015625/(1+z));')
        result = run(compile_model(body, 'real z;'), {'u': [[0,0],[.5,.5],[1,1]]},
                     [0, .5, 1], stop=1, vabstol=1e-9, reltol=0)
        for t, actual in zip([0, .5, 1], values(result)):
            assert_close(self, actual, t, delta=1e-9)
        self.assertGreater(result['transient']['accepted_steps'], 32)

    def test_inactive_invalid_bound_is_not_evaluated_but_active_invalid_rejects(self):
        base = 'V(y,r)<+idt(1+2*V(y,r),0)-pow(V(y,r),2);'
        inactive = compile_model(base + 'if(V(u,r)>2) $bound_step(-1-V(y,r));')
        run(inactive, times=[0, 1], stop=1)
        invalid = compile_model(base + '$bound_step(-1-V(y,r));')
        with self.assertRaises(KernelError) as error:
            run(invalid, times=[0, 1], stop=1)
        self.assertEqual(error.exception.detail['kind'], 'invalid_bound_step')
