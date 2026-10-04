"""DAE/filter composition with independent closed forms and explicit boundaries."""
GUARDS = ['DYNAMICS', 'LAPLACE', 'COMPOSE']

import math
import unittest
from evas import KernelError
from test_continuous_dynamics import compile_model, run, rows, values, assert_close


class ImplicitFilterContracts(unittest.TestCase):
    def test_filter_and_integral_share_the_algebraic_feedback(self):
        # f'=u-f, u=t.  y+y^2=z+f and z'=1+2y-(u-f)
        # imply y'=1; DC f(0)=z(0)=y(0)=0, so y=t.
        program = compile_model(
            'V(f,r)<+laplace_nd(V(u,r),\'{1},\'{1,1}); '
            'V(z,r)<+idt(1+2*V(y,r)-V(u,r)+V(f,r),0); '
            'V(y,r)<+V(z,r)+V(f,r)-pow(V(y,r),2);', 'electrical f,z;')
        times = [0,.125,.5,1,2]
        result = run(program, {'u':[[0,0],[2,2]]}, times, vabstol=1e-9, reltol=0)
        for t,row in zip(times,rows(result)):
            f=t-1+math.exp(-t)
            assert_close(self,row['y'],t,delta=1e-9)
            assert_close(self,row['dut:f'],f,delta=1e-9)
            assert_close(self,row['dut:z'],t+t*t-f,delta=1e-9)

    def test_nonzero_filter_dc_does_not_replace_the_integral_ic(self):
        # u=1+t, f=t+exp(-t); y(0)=1/2 on the selected branch.
        program=compile_model(
            'V(z,r)<+idt(1+2*V(y,r)-V(u,r)+V(f,r),.25); '
            'V(y,r)<+V(z,r)+V(f,r)-.5-pow(V(y,r),2); '
            'V(f,r)<+laplace_nd(V(u,r),\'{1},\'{1,1});', 'electrical f,z;')
        times=[0,.25,.5,1]
        result=run(program,{'u':[[0,1],[1,2]]},times,vabstol=1e-9,reltol=0)
        for t,row in zip(times,rows(result)):
            y=.5+t; f=t+math.exp(-t)
            assert_close(self,row['y'],y,delta=1e-9)
            assert_close(self,row['dut:z'],y+y*y-f+.5,delta=1e-9)

    def test_proper_filter_feedthrough_enters_the_original_constraint(self):
        # f=2t-x, x'=t-x. f'=2-f+t; choose z'=1+2y-f'.
        program=compile_model(
            'V(f,r)<+laplace_nd(V(u,r),\'{1,2},\'{1,1}); '
            'V(y,r)<+idt(-1+2*V(y,r)+V(f,r)-V(u,r),0)'
            '+V(f,r)-pow(V(y,r),2);','electrical f;')
        times=[0,.125,.5,1]
        result=run(program,{'u':[[0,0],[1,1]]},times,vabstol=1e-9,reltol=0)
        for t,row in zip(times,rows(result)):
            assert_close(self,row['y'],t,delta=1e-9)
            assert_close(self,row['dut:f'],t+1-math.exp(-t),delta=1e-9)

    def test_high_order_filter_only_dae_and_query_grid_invariance(self):
        # Two-pole ramp response; y+y^2=f fixes the branch from y(0)=0.
        program=compile_model('V(y,r)<+laplace_nd(V(u,r),\'{1},\'{1,2,1})'
                              '-pow(V(y,r),2);')
        sparse=[0,.25,.5,1,2]
        source={'u':[[0,0],[2,2]]}
        first=values(run(program,source,sparse,vabstol=1e-9,reltol=0))
        dense=[i/16 for i in range(33)]
        second=values(run(program,source,dense,max_step=.0625,vabstol=1e-9,reltol=0))
        self.assertEqual(first,[second[dense.index(t)] for t in sparse])
        for t,actual in zip(sparse,first):
            f=t-2+(t+2)*math.exp(-t)
            assert_close(self,actual,(-1+math.sqrt(1+4*f))/2,delta=1e-9)

    def test_internal_filter_feedback_and_integral_share_the_dc_root(self):
        # f'=u+.5y-f; u=.5+t. With y+y^2=z+f and
        # z'=1+2y-f', DC imposes f=.5+.5y and z(0)=0.
        # The selected root is y(0)=.5, hence y=.5+t and
        # f=.75+1.5*(t-1+exp(-t)). Neither IC can be set independently.
        program=compile_model(
            'V(f,r)<+laplace_nd(V(u,r)+.5*V(y,r),\'{1},\'{1,1}); '
            'V(z,r)<+idt(1+1.5*V(y,r)-V(u,r)+V(f,r),0); '
            'V(y,r)<+V(z,r)+V(f,r)-pow(V(y,r),2);','electrical f,z;')
        times=[0,.125,.5,1]
        result=run(program,{'u':[[0,.5],[1,1.5]]},times,vabstol=1e-9,reltol=0)
        for t,row in zip(times,rows(result)):
            y=.5+t; f=.75+1.5*(t-1+math.exp(-t))
            assert_close(self,row['y'],y,delta=1e-9)
            assert_close(self,row['dut:f'],f,delta=1e-9)
            assert_close(self,row['dut:z'],y+y*y-f,delta=1e-9)

    def test_internal_relay_and_contribution_order_keep_joint_initialization(self):
        pieces=[
            'V(a,r)<+V(u,r)+.5*V(y,r);',
            'V(f,r)<+laplace_nd(V(a,r),\'{1},\'{1,1});',
            'V(z,r)<+idt(1+2*V(y,r)-V(a,r)+V(f,r),0);',
            'V(y,r)<+V(z,r)+V(f,r)-pow(V(y,r),2);',
        ]
        times=[0,.25,.5,1]
        answers=[]
        for body in (''.join(pieces),''.join(reversed(pieces))):
            result=run(compile_model(body,'electrical a,f,z;'),
                       {'u':[[0,.5],[1,1.5]]},times,vabstol=1e-9,reltol=0)
            answers.append(rows(result))
            for t,row in zip(times,answers[-1]):
                assert_close(self,row['y'],.5+t,delta=1e-9)
                assert_close(self,row['dut:a'],.75+1.5*t,delta=1e-9)
        for left,right in zip(*answers):
            for node in left:
                assert_close(self,left[node],right[node],delta=1e-9)

    def test_polynomial_filter_dc_feedback_preserves_nonzero_integral_ic(self):
        # f'=y^2-f; y+y^2=z+f, z(0)=.5 gives y(0)=.5.
        # z'=1+2y-(y^2-f) makes y=.5+t and
        # f=t^2-t+1.25-exp(-t). The nonlinear DC relation cancels
        # y^2 only in the joint system, not within either block alone.
        program=compile_model(
            'V(f,r)<+laplace_nd(pow(V(y,r),2),\'{1},\'{1,1}); '
            'V(y,r)<+idt(1+2*V(y,r)-pow(V(y,r),2)+V(f,r),.5)'
            '+V(f,r)-pow(V(y,r),2);','electrical f;')
        times=[0,.125,.5,1]
        result=run(program,times=times,vabstol=1e-9,reltol=0)
        for t,row in zip(times,rows(result)):
            assert_close(self,row['y'],.5+t,delta=1e-9)
            assert_close(self,row['dut:f'],t*t-t+1.25-math.exp(-t),delta=1e-9)

    def test_nested_proper_filters_keep_dc_feedthrough_and_query_invariance(self):
        # q=.5+t, a=(1+2s)/(1+s) q=.5+t+1-exp(-t),
        # f=a/(1+s)=.5+t-t*exp(-t). y+y^2=f chooses the
        # branch starting at (-1+sqrt(3))/2.
        program=compile_model(
            'V(y,r)<+laplace_nd(laplace_nd(idt(1,.5),\'{1,2},\'{1,1}),'
            '\'{1},\'{1,1})-pow(V(y,r),2);')
        sparse=[0,.25,.5,1]
        first=values(run(program,times=sparse,vabstol=1e-9,reltol=0))
        dense=[i/16 for i in range(17)]
        second=values(run(program,times=dense,max_step=.0625,vabstol=1e-9,reltol=0))
        self.assertEqual(first,[second[dense.index(t)] for t in sparse])
        for t,actual in zip(sparse,first):
            f=.5+t-t*math.exp(-t)
            assert_close(self,actual,(-1+math.sqrt(1+4*f))/2,delta=1e-9)

    def test_singular_filter_dc_feedback_stays_rejected(self):
        program=compile_model('V(y,r)<+laplace_nd(V(y,r),\'{1},\'{1,1})'
                              '-pow(V(y,r),2);')
        # DC implies y^2=0. Its zero residual is not a certificate
        # of an isolated regular initial root.
        with self.assertRaisesRegex(KernelError,'singular|Krawczyk|initialization'):
            run(program,times=[0,.5,1],vabstol=1e-9,reltol=0)

    def test_polynomial_input_with_nonlinear_feedthrough_stays_rejected(self):
        program=compile_model("V(y,r)<+laplace_nd(pow(V(y,r),2),'{1,1},'{1,1})"
                              '-pow(V(y,r),2);')
        with self.assertRaisesRegex(KernelError,'strictly proper'):
            run(program,times=[0,.5,1],vabstol=1e-9,reltol=0)

    def test_call_order_preserves_each_high_order_state_and_integral_ic(self):
        filter_body='V(y,r)<+laplace_nd(V(u,r),\'{1},\'{1,2,1})-pow(V(y,r),2); '
        integral_body='V(z,r)<+idt(1,.25)+idt(2,-.5); '
        times=[0,.25,.5,1]
        answers=[]
        for body in (filter_body+integral_body,integral_body+filter_body):
            result=run(compile_model(body,'electrical z;'),{'u':[[0,0],[1,1]]},
                       times,vabstol=1e-9,reltol=0)
            answers.append(rows(result))
            for t,row in zip(times,answers[-1]):
                assert_close(self,row['dut:z'],3*t-.25,delta=1e-9)
        for left,right in zip(*answers):
            for node in left:
                assert_close(self,left[node],right[node],delta=1e-9)

    def test_filter_history_cannot_bypass_an_impossible_voltage_budget(self):
        program=compile_model('V(y,r)<+laplace_nd(V(u,r),\'{1},\'{1,1})'
                              '-pow(V(y,r),2);')
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            run(program,{'u':[[0,0],[1,1]]},[0,.5,1],vabstol=1e-20,reltol=0)
