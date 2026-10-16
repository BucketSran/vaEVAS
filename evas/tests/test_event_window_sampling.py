"""Certify callback samples and their use in later history at the execution time."""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["EVENT-CONDITIONS", "DYNAMICS"]

import math
import unittest

from evas.runtime import KernelError
from test_continuous_dynamics import compile_model, run, rows, values, assert_close


class EventWindowSamplingContracts(unittest.TestCase):
    def test_matching_fired_guard_uses_strict_post_crossing_side(self):
        from fractions import Fraction as Q
        root = (Q(.5)-Q(.2))/(Q(.8)-Q(.2))
        for relation, expected_state in [('>=', 2), ('<=', 3), ('>', 2), ('<', 3)]:
            program = compile_model(
                "@(initial_step) q=0; @(cross(V(u,r)-0.5,1,1e-9,1e-8)) "
                f"if (V(u,r){relation}0.5) q=2; else q=3; V(y,r)<+idt(q*q,0);",
                "integer q;")
            with self.subTest(relation=relation):
                sources = {"u": [[0,.2],[1,.8]]}
                result = run(program, sources, [0,1], stop=1,
                             vabstol=1e-8, reltol=0)
                event,=result['transient']['events']
                te=event['time']
                self.assertGreater(Q(te),root)
                self.assertLessEqual(Q(te)-root,Q(1e-9))
                self.assertEqual(event['after'], [expected_state])
                self.assertEqual(result['transient']['states'],[[0],[expected_state]])
                self.assertEqual(values(result)[0],0)
                assert_close(self, values(result)[-1], float(expected_state**2*(1-Q(te))), delta=1e-8)
                dense = run(program, sources, [0,.25,.5,1], stop=1,
                            vabstol=1e-8, reltol=0)
                self.assertEqual(result['transient']['events'],dense['transient']['events'])
                self.assertEqual(result['solutions'],[dense['solutions'][i] for i in (0,3)])

    def test_or_guard_that_did_not_fire_cannot_certify_a_condition(self):
        from fractions import Fraction as Q
        root = (Q(.5)-Q(.2))/(Q(.8)-Q(.2))
        program = compile_model(
            "@(initial_step) q=0; @(cross(V(u,r)-0.5,1,1e-9,1e-8) "
            "or cross(V(c,r)-0.5,1,1e-9,1e-8)) "
            "if (V(c,r)>=0.5) q=2; else q=3; V(y,r)<+idt(q*q,0);",
            "integer q;", ports="u,c,y,r", directions="input u,c; output y; inout r;")
        result = run(program, {"u": [[0,.2],[1,.8]], "c": [[0,.25],[1,.25]]}, [0,1],
                     stop=1, vabstol=1e-8, reltol=0)
        self.assertEqual(result['transient']['events'][0]['after'], [3])
        assert_close(self, values(result)[-1], float(9*(1-root)), delta=1e-8)

    def test_linear_input_sample_retains_time_error_in_future_integral(self):
        program = compile_model(
            "@(initial_step) q=0; @(cross(pow(V(u,r),2)-2,1,1e-9,1e-8)) q=V(u,r); "
            "V(y,r)<+idt(q,0);", "real q;")
        result = run(program, {"u": [[0,0],[2,2]]}, [0,1,1.75,2], stop=2,
                     vabstol=1e-7, reltol=1e-7)
        for t, actual in zip([0,1,1.75,2], values(result)):
            assert_close(self, actual, 0 if t<math.sqrt(2) else math.sqrt(2)*(t-math.sqrt(2)), delta=3e-7)

    def test_nonlinear_sample_controls_polynomial_flow_with_full_time_enclosure(self):
        program = compile_model(
            "@(initial_step) q=0; @(cross(pow(V(u,r),2)-2,1,1e-9,1e-8)) q=V(u,r); "
            "V(y,r)<+idt(q*q,0);", "real q;")
        result = run(program, {"u": [[0,0],[2,2]]}, [0,1,1.75,2], stop=2,
                     vabstol=1e-7, reltol=1e-7)
        for t, actual in zip([0,1,1.75,2], values(result)):
            assert_close(self, actual, 0 if t<math.sqrt(2) else 2*(t-math.sqrt(2)), delta=3e-7)

    def test_condition_uses_certified_execution_point_beyond_the_root_window(self):
        program = compile_model(
            "@(initial_step) q=1; @(cross(pow(V(u,r),2)-2,1,1e-6,1e-5)) "
            "if (V(u,r)>1.5) q=2; else q=3; V(y,r)<+idt(q,0);", "integer q;")
        result = run(program, {"u": [[0,0],[2,2]]}, [0,2], stop=2, vabstol=1e-4, reltol=0)
        assert_close(self, values(result)[-1], 6-2*math.sqrt(2), delta=1e-4)
        ambiguous = compile_model(
            "@(initial_step) q=1; @(cross(pow(V(u,r),2)-2,1,1e-5,1e-4)) "
            "if (V(u,r)>1.414214) q=2; else q=3; V(y,r)<+idt(q,0);", "integer q;")
        # The old root box straddled 1.414214. A certified execution point
        # has its own predicate; use that same point for sampling and flow.
        result=run(ambiguous, {"u": [[0,0],[2,2]]}, [0,2], stop=2, vabstol=1e-4, reltol=0)
        from fractions import Fraction as Q
        event,=result['transient']['events']
        te=event['time']
        guard=Q(te)**2-Q(2)
        self.assertGreater(guard,0)
        self.assertLessEqual(guard,Q(1e-4))
        self.assertLessEqual(te-math.sqrt(2),1e-5)
        expected=2 if Q(te)>Q(1.414214) else 3
        self.assertEqual(event['after'],[expected])
        self.assertAlmostEqual(event['guard_value'],float(guard),delta=1e-14)
        answer=Q(te)+expected*(Q(2)-Q(te))
        assert_close(self,values(result)[-1],float(answer),delta=1e-4)

    def test_amplified_sample_uses_the_certified_execution_time(self):
        program = compile_model(
            "@(initial_step) q=0; @(cross(pow(V(u,r),2)-2,1,1e-5,1e-4)) q=1e6*V(u,r); "
            "V(y,r)<+idt(q*q,0);", "real q;")
        # For u(t)=t, callback q=1e6*te and y(10)=q^2*(10-te).
        # Validate te against the mathematical root before using this IVP.
        result = run(program, {"u": [[0,0],[10,10]]}, [0,10], stop=10,
                     vabstol=2e7, reltol=1e-10)
        from fractions import Fraction as Q
        event,=result['transient']['events']
        te=event['time']
        self.assertGreater(Q(te)**2,Q(2))
        self.assertLessEqual(te-math.sqrt(2),1e-5)
        self.assertLessEqual(Q(te)**2-Q(2),Q(1e-4))
        self.assertAlmostEqual(event['after'][0],1e6*te,delta=1e-9)
        exact_q=Q(1000000)*Q(te)
        expected=float(exact_q**2*(Q(10)-Q(te)))
        assert_close(self, values(result)[-1], expected, delta=2e7)
        # The original root-reference consumer has its own unchanged budget.
        # Agreement with the actual-execution IVP cannot replace this check.
        assert_close(self, values(result)[-1], 2e12*(10-math.sqrt(2)), delta=2e7)
        # Input rounding fits this budget; the amplified integral does not.
        with self.assertRaises(KernelError) as caught:
            run(program, {"u": [[0,0],[10,10]]}, [0,10], stop=10, vabstol=1e-6, reltol=0)
        self.assertEqual(caught.exception.detail['kind'],'waveform_accuracy')
        self.assertRegex(str(caught.exception),
                         r'waveform_accuracy.*at y:|waveform_accuracy: nonlinear accumulated history accuracy '
                         r'could not be certified within 8 suffix refinements')

    def test_integral_history_sample_uses_event_instant_not_post_event_flow(self):
        # z(t)=t; q=z(sqrt(2)); y'=q^2 after that event. Resampling
        # candidate history at b after new-mode flow would change q's box.
        program=compile_model(
            "@(initial_step) q=0; @(cross(pow(V(u,r),2)-2,1,1e-9,1e-8)) q=V(z,r); "
            "V(z,r)<+idt(1,0); V(y,r)<+idt(q*q,0);", "real q; electrical z;")
        times=[0,1,1.75,2]
        result=run(program,{"u":[[0,0],[2,2]]},times,stop=2,vabstol=1e-7,reltol=1e-7)
        for t,row in zip(times,rows(result)):
            assert_close(self,row["dut:z"],t,delta=3e-7)
            assert_close(self,row["y"],0 if t<math.sqrt(2) else 2*(t-math.sqrt(2)),delta=3e-7)
