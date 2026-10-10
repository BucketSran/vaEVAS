"""Source-polynomial proper filters, checked against independent closed forms."""
from decimal import Decimal, localcontext
import unittest

from evas import KernelError
from test_continuous_dynamics import compile_model, run, rows, values, assert_close

GUARDS = ["DYNAMICS", "COMPOSE"]


class PolynomialDirectFilterContracts(unittest.TestCase):
    def test_original_c4_ramp_with_dc_and_near_zero_observations(self):
        # (s+1)/(s+2) t^2 gives (2t^2+2t-1+exp(-2t))/4.
        program = compile_model("V(y,r)<+laplace_nd(pow(V(u,r),2),'{1,1},'{2,1});")
        times = [0, 2**-20, .125, .5, 1, 2]
        result = run(program, {"u": [[0, 0], [2, 2]]}, times,
                     vabstol=1e-9, reltol=0, max_step=.125)
        with localcontext() as ctx:
            ctx.prec = 60
            for t, actual in zip(times, values(result)):
                t = Decimal(t)
                expected = (2*t*t+2*t-1+(-2*t).exp())/4
                assert_close(self, actual, float(expected), delta=1e-9)

    def test_nonzero_dc_reversal_and_query_grid_preserve_history(self):
        # Integrate the scalar convolution independently on each PWL segment.
        source = [[0, 1], [.5, 2], [1, -1], [2, 1]]
        program = compile_model("V(y,r)<+laplace_nd(pow(V(u,r),2),'{1,1},'{2,1});")
        sparse = [0, .25, .5, .75, 1, 1.5, 2]
        dense = [i/16 for i in range(33)]
        baseline = values(run(program, {"u": source}, sparse, max_step=.125,
                              vabstol=1e-8, reltol=0))
        extended = values(run(program, {"u": source}, dense, max_step=.125,
                              vabstol=1e-8, reltol=0))
        self.assertEqual(baseline, [extended[dense.index(t)] for t in sparse])
        with localcontext() as ctx:
            ctx.prec = 60
            for t, actual in zip(sparse, baseline):
                x = Decimal(source[0][1])**2/2
                for (start, a), (end, end_value) in zip(source, source[1:]):
                    if t < start:
                        break
                    dt = Decimal(min(t, end))-Decimal(start)
                    b = (Decimal(end_value)-Decimal(a))/(Decimal(end)-Decimal(start))
                    a = Decimal(a)
                    u = a+b*dt
                    particular = lambda v: v*v/2-b*v/2+b*b/4
                    x = particular(u)+(x-particular(a))*(-2*dt).exp()
                    if t <= end:
                        break
                assert_close(self, actual, float(u*u-x), delta=1e-8)

    def test_nested_filter_and_unrelated_integral_keep_each_state(self):
        # (s+1)/(s+2) followed by (s+2)/(s+3): y=(s+1)/(s+3) t^2.
        body = "V(y,r)<+laplace_nd(laplace_nd(pow(V(u,r),2),'{1,1},'{2,1}),'{2,1},'{3,1});"
        extra = "V(z,r)<+idt(2,0.25);"
        times = [0, .125, .5, 1]
        answers = []
        for code in (body+extra, extra+body):
            result = run(compile_model(code, 'electrical z;'),
                         {"u": [[0, 0], [1, 1]]}, times, vabstol=1e-9, reltol=0)
            answers.append(values(result))
            with localcontext() as ctx:
                ctx.prec = 60
                for t, row in zip(times, rows(result)):
                    d = Decimal(t)
                    expected = d*d/3+4*d/9-Decimal(4)/27+Decimal(4)/27*(-3*d).exp()
                    assert_close(self, row['y'], float(expected), delta=1e-9)
                    assert_close(self, row['dut:z'], .25+2*t, delta=1e-9)
        for a, b in zip(*answers):
            assert_close(self, a, b, delta=1e-9)

    def test_nondyadic_coefficients_and_voltage_amplification(self):
        # (1+s)/(2+3s), with u=t. Independent inverse transform:
        # y=t²/2-t/2+.75*(1-exp(-2t/3)).
        program = compile_model("V(y,r)<+1000*laplace_nd(pow(V(u,r),2),'{1,1},'{2,3});")
        times = [0, .125, .5, 1]
        result = run(program, {"u": [[0, 0], [1, 1]]}, times, vabstol=1e-7, reltol=0)
        with localcontext() as ctx:
            ctx.prec = 60
            for t, actual in zip(times, values(result)):
                d = Decimal(t)
                expected = 1000*(d*d/2-d/2+Decimal('.75')*(1-(-2*d/3).exp()))
                assert_close(self, actual, float(expected), delta=1e-7)
        with self.assertRaisesRegex(KernelError, 'accuracy|certificate|Krawczyk'):
            run(program, {"u": [[0, 0], [1, 1]]}, times, vabstol=1e-20, reltol=0)

    def test_multiple_direct_terms_and_second_order_filter(self):
        # Independent transfer functions: H1=(s+1)/(s+2),
        # H2=(s²+s+1)/(s+1)². Both receive u², but own distinct history.
        program = compile_model("V(y,r)<+laplace_nd(pow(V(u,r),2),'{1,1},'{2,1})"
                                "+laplace_nd(pow(V(u,r),2),'{1,1,1},'{1,2,1});")
        times = [0, .125, .5, 1]
        result = run(program, {'u': [[0, 0], [1, 1]]}, times, vabstol=1e-9, reltol=0)
        with localcontext() as ctx:
            ctx.prec = 60
            for t, actual in zip(times, values(result)):
                d = Decimal(t)
                first = (2*d*d+2*d-1+(-2*d).exp())/4
                second = d*d-2*d+4-(4+2*d)*(-d).exp()
                assert_close(self, actual, float(first+second), delta=1e-9)

    def test_internal_or_canceled_feedback_and_event_scope_stay_rejected(self):
        for expr in ('pow(V(y,r),2)', 'pow(V(u,r)+0*V(y,r),2)',
                     'pow(V(a,r),2)', 'pow(V(u,r)+0*idt(0,0),2)'):
            with self.subTest(expr=expr):
                program = compile_model(f"V(a,r)<+V(u,r); V(y,r)<+laplace_nd({expr},'{{1,1}},'{{2,1}});",
                                        'electrical a;')
                with self.assertRaisesRegex(KernelError, 'strictly proper'):
                    run(program, {"u": [[0, 0], [1, 1]]}, [0, .5, 1])
        program = compile_model("@(initial_step) q=0; @(timer(0.5)) q=1; "
                                "V(y,r)<+q+laplace_nd(pow(V(u,r),2),'{1,1},'{2,1});", 'integer q;')
        with self.assertRaisesRegex(KernelError, 'event-free'):
            run(program, {"u": [[0, 0], [1, 1]]}, [0, .5, 1])
