"""Feed-forward transition areas; answers are hand-derived, not DUT replay."""
GUARDS = ["TRANSITION", "DYNAMICS", "COMPOSE", "TIMER"]

import unittest
from evas import KernelError
from test_continuous_dynamics import compile_model, run, rows


def model(extra="V(y,r)<+idt(V(e,r),0.1);"):
    internal='e,nc'+(',z,f' if 'V(z,r)' in extra else '')
    return compile_model(
        '@(initial_step) begin q=0; n=0; end '
        '@(timer(1,0,1e-10)) begin q=1; n=n+1; end '
        '@(timer(1.25,0,1e-10)) begin q=0; n=n+1; end '
        'V(e,r)<+transition(q,0,0.5,1); V(nc,r)<+n; '+extra,
        'integer q,n; electrical '+internal+';')


def area(t):
    # Rising triangle to t=1.25: 1/16. Reversal retains old target 1,
    # so falling slope is -1, ending at 1.75: another triangle 1/8.
    if t <= 1: return .1
    if t <= 1.25: return .1+(t-1)**2
    if t <= 1.75:
        h=t-1.25
        return .1625+.5*h-.5*h*h
    return .2875


class TransitionIntegral(unittest.TestCase):
    def test_interrupted_transition_area_has_original_duration_and_nonzero_ic(self):
        ts=[0,1,1.125,1.25,1.5,1.75,2.25,3]
        answer=run(model(),times=ts,stop=3,max_step=.5,vabstol=1e-10,reltol=0)
        for t,r in zip(ts,rows(answer)):
            self.assertAlmostEqual(r['y'],area(t),delta=1e-10)
        self.assertEqual(rows(answer)[-1]['dut:nc'],2)

    def test_extra_queries_and_forced_points_preserve_physical_history(self):
        p=model();sparse=[0,1.125,1.5,1.75,3]
        dense=sorted(set(sparse+[i/32 for i in range(97)]))
        a=run(p,times=sparse,stop=3,max_step=.5,vabstol=1e-10,reltol=0)
        b=run(p,times=dense,stop=3,max_step=.5,vabstol=1e-10,reltol=0)
        c=run(p,times=dense,stop=3,max_step=.5,strobetimes=dense,vabstol=1e-10,reltol=0)
        self.assertEqual(a['solutions'],[b['solutions'][dense.index(t)] for t in sparse])
        self.assertEqual(a['transient']['events'],b['transient']['events'])
        self.assertEqual(b['transient']['events'],c['transient']['events'])
        for t,r in zip(dense,rows(c)):
            self.assertAlmostEqual(r['y'],area(t),delta=1e-10)

    def test_affine_projection_preserves_sign_offset_and_other_consumers(self):
        p=model('V(y,r)<+idt(-2*V(e,r)+0.25,0.5); '
                'V(z,r)<+idt(V(e,r),-0.25); '
                "V(f,r)<+laplace_nd(V(e,r),'{1},'{1,0.5});")
        ts=[0,1,1.125,1.5,1.75,3]
        a=run(p,times=ts,stop=3,vabstol=1e-10,reltol=0)
        for t,r in zip(ts,rows(a)):
            self.assertAlmostEqual(r['y'],.5+.25*t-2*(area(t)-.1),delta=1e-10)
            self.assertAlmostEqual(r['dut:z'],-.25+area(t)-.1,delta=1e-10)

    def test_feedback_nonlinear_forcing_and_reset_remain_explicitly_rejected(self):
        for expression in ('idt(V(e,r)*V(e,r),0.1)',
                           'idt(V(e,r)+V(y,r),0.1)',
                           'idt(V(e,r),0.1,q)'):
            with self.subTest(expression=expression), self.assertRaisesRegex(KernelError,'unsupported_operator'):
                run(model('V(y,r)<+'+expression+';'),times=[0,3],stop=3)


if __name__=='__main__': unittest.main()
