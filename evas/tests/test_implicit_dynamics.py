"""Index-one polynomial DAE answers derived by substitution, not a solver oracle."""
# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["DYNAMICS"]

import unittest
from evas.runtime import KernelError
from test_continuous_dynamics import compile_model, run, rows, values, assert_close


class ImplicitDynamicsContracts(unittest.TestCase):
    def test_nonlinear_algebraic_integral_feedback_has_exact_linear_voltage(self):
        # y+y^2=z, z'=1+2y, z(0)=0. Differentiation gives y'=1
        # on the branch starting at y=0; hence y=t, z=t+t^2.
        program = compile_model("V(y,r)<+idt(1+2*V(y,r),0)-pow(V(y,r),2);")
        times = [0,.125,.5,1,2]
        result = run(program, times=times, stop=2, vabstol=1e-10, reltol=0)
        for t, actual in zip(times, values(result)):
            assert_close(self, actual, t, delta=1e-10)

    def test_algebraic_relay_and_contribution_splitting_preserve_the_dae(self):
        models = [
            "V(z,r)<+idt(1+2*V(y,r),0); V(y,r)<+V(z,r)-pow(V(y,r),2);",
            "V(y,r)<+-pow(V(y,r),2); V(y,r)<+V(z,r); V(z,r)<+idt(1+2*V(y,r),0);",
        ]
        times = [0,.25,.5,1,2]
        for body in models:
            result = run(compile_model(body,"electrical z;"), times=times, stop=2,
                         vabstol=1e-10,reltol=0)
            for t, row in zip(times, rows(result)):
                assert_close(self,row["y"],t,delta=1e-10)
                assert_close(self,row["dut:z"],t+t*t,delta=1e-10)

    def test_coupled_algebraic_nodes_are_jointly_continued(self):
        program = compile_model(
            "V(a,r)<+idt(1+2*V(a,r),0)-pow(V(a,r),2); "
            "V(y,r)<+pow(V(a,r),2)+idt(1,0);", "electrical a;")
        times = [0,.25,.5,1]
        result=run(program,times=times,stop=1,vabstol=1e-10,reltol=0)
        for t,row in zip(times,rows(result)):
            assert_close(self,row["dut:a"],t,delta=1e-10)
            assert_close(self,row["y"],t*t+t,delta=1e-10)

    def test_piecewise_source_derivative_uses_each_physical_segment(self):
        # y+y^2=z+u, z'=0; y=(-1+sqrt(1+4u))/2, continuous
        # across the PWL corner; algebraic derivative changes sides there.
        import math
        program=compile_model("V(y,r)<+idt(0,0)+V(u,r)-pow(V(y,r),2);")
        source={"u":[[0,0],[.5,.5],[1,0]]}
        times=[0,.125,.5,.75,1]
        result=run(program,source,times,stop=1,vabstol=1e-9,reltol=0)
        for t,actual in zip(times,values(result)):
            u=t if t<=.5 else 1-t
            assert_close(self,actual,(-1+math.sqrt(1+4*u))/2,delta=1e-9)

    def test_query_grid_does_not_change_the_implicit_branch_or_history(self):
        program=compile_model("V(y,r)<+idt(1+2*V(y,r),0)-pow(V(y,r),2);")
        sparse=[0,.25,.5,1]
        first=values(run(program,times=sparse,stop=1,vabstol=1e-10,reltol=0))
        dense=[i/16 for i in range(17)]
        second=values(run(program,times=dense,stop=1,max_step=.0625,vabstol=1e-10,reltol=0))
        self.assertEqual(first,[second[dense.index(t)] for t in sparse])

    def test_singular_algebraic_jacobian_cannot_silently_switch_branches(self):
        program=compile_model("V(y,r)<+idt(-1,0)-pow(V(y,r),2);")
        with self.assertRaises(KernelError):
            run(program,times=[0,.125,.3],stop=.3,vabstol=1e-8,reltol=0)

    def test_implicit_history_is_not_accepted_under_impossible_precision(self):
        program=compile_model("V(y,r)<+idt(1+2*V(y,r),0)-pow(V(y,r),2);")
        with self.assertRaisesRegex(KernelError,"waveform_accuracy"):
            run(program,times=[0,.5,1],stop=1,vabstol=1e-20,reltol=0)
