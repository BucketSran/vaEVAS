"""Post-reset joint closure with independent piecewise IVP answers."""
# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["DYNAMICS"]

import math
import unittest
from fractions import Fraction as Q
from evas.runtime import KernelError

from test_continuous_dynamics import compile_model, run, rows, assert_close


class LifecycleClosureContracts(unittest.TestCase):
    def test_transition_sampling_uses_the_existing_ramp_over_the_window(self):
        # A timer starts a four-second ramp at 1/4. Sampling at sqrt(2)
        # gives (sqrt(2)-1/4)/4, independent of output sampling density.
        body = ('@(initial_step) begin q=0; target=0; end '
            '@(timer(0.25,0,1e-12)) target=1; '
            '@(cross(pow(V(u,r),2)-2,1,TTOL,ETOL)) q=V(z,r); '
            'V(z,r)<+transition(target,0,4,4); V(y,r)<+q;')
        for ttol, etol in [('1e-5','1e-4'), ('1e-10','1e-9')]:
            program = compile_model(body.replace('TTOL',ttol).replace('ETOL',etol),
                                    'real q; integer target; electrical z;')
            with self.subTest(ttol=ttol):
                result = run(program, {'u': [[0,0],[2,2]]}, [0,2], stop=2,
                             vabstol=1e-7, reltol=1e-7)
                assert_close(self, rows(result)[-1]['y'], (math.sqrt(2)-.25)/4, delta=2e-7)
                if ttol == '1e-5':
                    lo, hi = result['transient']['events'][-1]['observation_time_bounds']
                    self.assertLessEqual(lo, math.sqrt(2))
                    self.assertGreaterEqual(hi, math.sqrt(2))
                    self.assertLess(hi-lo, 1e-12)
                    with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
                        run(program, {'u': [[0,0],[2,2]]}, [0,2], stop=2,
                            vabstol=1e-20, reltol=0)

    def test_direct_integral_release_keeps_the_same_event_sample(self):
        program = compile_model('@(initial_step) begin rst=1; q=0; end '
            '@(cross(pow(V(u,r),2)-2,1,1e-10,1e-9)) begin rst=0; q=V(z,r); end '
            'V(z,r)<+idt(V(u,r),3,rst); V(y,r)<+q;', 'integer rst; real q; electrical z;')
        result = run(program, {'u': [[0,0],[2,2]]}, [0,2], stop=2,
                     vabstol=1e-7, reltol=1e-7)
        assert_close(self, rows(result)[-1]['y'], 3, delta=2e-7)
        assert_close(self, rows(result)[-1]['dut:z'], 4, delta=2e-7)

    def test_uncertified_history_window_is_explicitly_rejected(self):
        for history in ['absdelay(V(u,r),0.25)', 'slew(V(u,r),2,-2)',
                        'idtmod(V(u,r),0,8,0)']:
            with self.subTest(history=history):
                body = ('@(initial_step) q=0; @(TRIGGER) q=V(z,r); '
                        f'V(z,r)<+{history}; V(y,r)<+q;')
                uncertain = compile_model(body.replace('TRIGGER', 'cross(pow(V(u,r),2)-2,1,1e-10,1e-9)'),
                                          'real q; electrical z;')
                with self.assertRaisesRegex(KernelError, 'event_resolution.*certified observation'):
                    run(uncertain, {'u': [[0,0],[2,2]]}, [0,2], stop=2)
                exact = compile_model(body.replace('TRIGGER', 'timer(1,0,1e-12)'),
                                      'real q; electrical z;')
                result = run(exact, {'u': [[0,0],[2,2]]}, [0,2], stop=2)
                expected = .75 if history.startswith('absdelay') else 1 if history.startswith('slew') else .5
                assert_close(self, rows(result)[-1]['y'], expected)

    def test_immutable_history_sampling_keeps_the_root_window(self):
        # u=t, tau=sqrt(2). z=t^2/2 or t^3/3, independently of q.
        # A disconnected identically-zero integral cannot change this obligation.
        for nonlinear in [False, True]:
            for zero_component in [False, True]:
                for wrapped in [False, True]:
                    with self.subTest(nonlinear=nonlinear, zero=zero_component, wrapped=wrapped):
                        integrand = 'pow(V(u,r),2)' if nonlinear else 'V(u,r)'
                        history = f'idt({integrand},0)'
                        if wrapped:
                            history = f"laplace_nd({history},'{{1,1}},'{{1,1}})"
                        body = ('@(initial_step) q=0; '
                            '@(cross(pow(V(u,r),2)-2,1,TTOL,ETOL)) q=V(z,r); '
                            f'V(y,r)<+q; V(z,r)<+{history};')
                        declarations = 'real q; electrical z;'
                        if zero_component:
                            body += 'V(aux,r)<+idt(0*q,0);'
                            declarations += 'electrical aux;'
                        wide = compile_model(body.replace('TTOL', '1e-5').replace('ETOL', '1e-4'), declarations)
                        result = run(wide, {'u': [[0,0],[2,2]]}, [0,1.75,2], stop=2,
                                     vabstol=1e-7, reltol=1e-7)
                        expected = 2*math.sqrt(2)/3 if nonlinear else 1
                        assert_close(self, rows(result)[-1]['y'], expected, delta=2e-7)
                        lo, hi = result['transient']['events'][0]['observation_time_bounds']
                        self.assertLessEqual(lo, math.sqrt(2))
                        self.assertGreaterEqual(hi, math.sqrt(2))
                        self.assertLess(hi-lo, 1e-12)
                        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
                            run(wide, {'u': [[0,0],[2,2]]}, [0,1.75,2], stop=2,
                                vabstol=1e-20, reltol=0)
                        narrow = compile_model(body.replace('TTOL', '1e-10').replace('ETOL', '1e-9'), declarations)
                        result = run(narrow, {'u': [[0,0],[2,2]]}, [0,1.75,2], stop=2,
                                     vabstol=1e-7, reltol=1e-7)
                        expected = 2*math.sqrt(2)/3 if nonlinear else 1
                        assert_close(self, rows(result)[-1]['y'], expected, delta=2e-7)

    def test_derivative_restores_instantaneous_event_feedback(self):
        # Every encoding gives y=q at positive time; q+=y+ has no unique solution.
        bodies = [
            'V(y,r)<+ddt(idt(q,0));',
            "V(y,r)<+laplace_nd(ddt(idt(q,0)),'{1,1},'{1,1});",
            'V(z,r)<+idt(q,0); V(y,r)<+ddt(V(z,r));',
            # x'+x=q, so x'+x=q also exposes the input instantaneously.
            "V(z,r)<+laplace_nd(q,'{1},'{1,1}); V(y,r)<+ddt(V(z,r))+V(z,r);",
        ]
        for body in bodies:
            with self.subTest(body=body):
                program = compile_model('@(initial_step) q=1; '
                    '@(timer(0.5,0,1e-12)) q=V(y,r); '+body, 'real q; electrical z;'
                    if 'V(z,r)' in body else 'real q;')
                with self.assertRaisesRegex(KernelError, 'unsupported_operator.*instantaneous'):
                    run(program, times=[0,.25,.5,1], stop=1, vabstol=1e-7, reltol=1e-7)

    def test_derivative_without_event_feedback_accepts_input_updates(self):
        program = compile_model('@(initial_step) q=1; '
            '@(timer(0.5,0,1e-12)) q=q+1; V(y,r)<+ddt(idt(q,0));', 'real q;')
        result = run(program, times=[0,.25,.5,1], stop=1, vabstol=1e-8, reltol=1e-8)
        for row, expected in zip(rows(result), [0,1,2,2]):
            assert_close(self, row['y'], expected, delta=1e-8)

    def test_derivative_preserves_remaining_dynamic_state(self):
        # ddt removes one integration, not every state on its input path.
        program = compile_model('@(initial_step) q=1; '
            '@(timer(0.5,0,1e-12)) begin q=V(y,r); q=q+1; end '
            'V(y,r)<+ddt(idt(idt(q,0),0));', 'real q;')
        result = run(program, times=[0,.5,1], stop=1, vabstol=1e-8, reltol=1e-8)
        assert_close(self, rows(result)[-1]['y'], 1.25, delta=1e-8)
        # H=1/(1+s)^2 has relative degree 2: its first derivative remains
        # continuous. A 2->1 step at .5 gives y'=-h*exp(-h).
        program = compile_model('@(initial_step) q=2; '
            '@(timer(0.5,0,1e-12)) q=V(y,r)+1; '
            "V(y,r)<+ddt(laplace_nd(q,'{1},'{1,2,1}));", 'real q;')
        result = run(program, times=[0,.5,1], stop=1, vabstol=1e-8, reltol=1e-8)
        assert_close(self, rows(result)[-1]['y'], -.5*math.exp(-.5), delta=1e-8)

    def test_direct_filter_event_fixed_point_is_explicitly_rejected(self):
        # H(s)=1: q+=y+=q+ admits every q, not a unique event solution.
        program=compile_model('@(initial_step) q=1; '
            "@(timer(0.5,0,1e-12)) q=V(y,r); V(y,r)<+laplace_nd(q,'{1,1},'{1,1});",
            'real q;')
        with self.assertRaisesRegex(KernelError,'unsupported_operator.*instantaneous'):
            run(program,times=[0,.5,1],stop=1)

    def test_direct_filter_without_event_voltage_feedback_keeps_order(self):
        program=compile_model('@(initial_step) q=1; '
            "@(timer(0.5,0,1e-12)) q=q+1; V(y,r)<+laplace_nd(q,'{1,1},'{1,1});",
            'real q;')
        result=run(program,times=[0,.5,1],stop=1)
        for row,expected in zip(rows(result),[1,2,2]):
            assert_close(self,row['y'],expected,delta=1e-8)

    def test_strictly_proper_filter_cuts_instantaneous_event_feedback(self):
        program=compile_model('@(initial_step) q=1; '
            "@(timer(0.5,0,1e-12)) begin q=V(z,r); q=q+1; end "
            "V(y,r)<+laplace_nd(q,'{1,1},'{1,1}); "
            "V(z,r)<+laplace_nd(V(y,r),'{1},'{1,1});",'real q; electrical z;')
        result=run(program,times=[0,.5,1],stop=1)
        assert_close(self,rows(result)[-1]['y'],2,delta=1e-8)
        assert_close(self,rows(result)[-1]['dut:z'],2-math.exp(-.5),delta=1e-8)

    def test_reset_sample_release_preserves_other_history(self):
        for nonlinear in [False, True]:
            for reverse in [False, True]:
                for cross in [False, True]:
                    with self.subTest(nonlinear=nonlinear, reverse=reverse, cross=cross):
                        trigger = 'cross(V(u,r)-0.5,1,1e-8,1e-8)' if cross else 'timer(0.5,0,1e-12)'
                        assignments = 'q=V(z,r); rst=1;' if reverse else 'rst=1; q=V(z,r);'
                        body = (f'@(initial_step) begin q=1; rst=0; end '
                            f'@({trigger}) begin {assignments} end '
                            '@(timer(0.75,0,1e-12)) rst=0; '
                            "V(z,r)<+idt(q,1,rst); V(y,r)<+laplace_nd(V(z,r),'{1},'{1,1}); "
                            'V(held,r)<+q;')
                        declarations = 'real q; integer rst; electrical z;'
                        if nonlinear:
                            body += 'V(aux,r)<+idt(pow(V(u,r),2),0);'
                            declarations += 'electrical aux;'
                        program=compile_model(body,declarations,ports='u,y,held,r',
                            directions='input u; output y,held; inout r;')
                        for times,step in [([0,.25,.5,.625,.75,.875,1],1),
                                           ([i/32 for i in range(33)],1/32)]:
                            result=run(program,{'u':[[0,0],[1,1]]},times,stop=1,max_step=step,
                                       vabstol=1e-7,reltol=1e-7)
                            at_reset=.5+math.exp(-.5)
                            at_release=1+(at_reset-1)*math.exp(-.25)
                            for t,row in zip(times,rows(result)):
                                z=1+t if t<.5 else 1 if t<=.75 else 1+t-.75
                                y=(t+math.exp(-t) if t<.5 else
                                   1+(at_reset-1)*math.exp(-(t-.5)) if t<=.75 else
                                   (t-.75)+(at_release)*math.exp(-(t-.75)))
                                assert_close(self,row['dut:z'],z,delta=1e-7)
                                assert_close(self,row['y'],y,delta=1e-7)
                                assert_close(self,row['held'],1,delta=1e-7)

    def test_reset_sample_keeps_local_assignment_order(self):
        # Local q=q+1 follows the post-reset q=z+=1, hence future slope 2.
        program=compile_model('@(initial_step) begin q=1; rst=0; end '
            '@(timer(0.5,0,1e-12)) begin rst=1; q=V(y,r); q=q+1; end '
            '@(timer(0.75,0,1e-12)) rst=0; V(y,r)<+idt(q,1,rst);',
            'real q; integer rst;')
        result=run(program,times=[0,.5,.75,1],stop=1,vabstol=1e-9,reltol=1e-9)
        assert_close(self,rows(result)[-1]['y'],1.5,delta=1e-9)
        self.assertTrue(all('observation_time_bounds' not in e
                            for e in result['transient']['events']))

    def test_trace_binds_reset_sample_and_future_flow_to_one_root(self):
        root = (Q(.5)-Q(.2))/(Q(.8)-Q(.2))
        program = compile_model(
            '@(initial_step) begin q=1; rst=0; h=0; end '
            '@(cross(V(u,r)-0.5,1,1e-9,1e-8)) begin '
            'rst=1; q=V(z,r); h=V(clock,r); end '
            '@(timer(0.75,0,1e-12)) rst=0; '
            'V(z,r)<+idt(q,1,rst); V(y,r)<+q; V(stamp,r)<+h;',
            'real q,h; integer rst; electrical z;', ports='u,clock,y,stamp,r',
            directions='input u,clock; output y,stamp; inout r;')
        result=run(program,{'u':[[0,.2],[1,.8]],'clock':[[0,0],[1,1]]},
                   [0,.625,.75,1],stop=1,vabstol=1e-8,reltol=1e-8)
        event=result['transient']['events'][0]
        lo,hi=event['observation_time_bounds']
        self.assertLessEqual(Q(lo),root)
        self.assertGreaterEqual(Q(hi),root)
        self.assertEqual(event['time'],hi)
        self.assertTrue(lo<=rows(result)[1]['stamp']<=hi)
        assert_close(self,rows(result)[1]['y'],1,delta=1e-8)
        assert_close(self,rows(result)[-1]['dut:z'],1.25,delta=1e-8)


if __name__=='__main__':
    unittest.main()
