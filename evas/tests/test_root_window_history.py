"""Physical threshold roots at exact timer endpoints; oracle uses binary tokens."""
GUARDS = ["DYNAMICS", "TIMER", "EVENT-ORDER", "COMPOSE"]

from fractions import Fraction as F
import math
import unittest

from evas import compile_sources, Instance
from evas.runtime import _invoke
from evas.errors import KernelError
from test_affine import KERNEL


def request(reverse=False, nested=False, before=False, gain=1e8, dense=False):
    a, b, stop = 1e-7, 1.002e-7, 2e-7
    root = (F(a)+F(b))/2
    event = float(root)
    assert F(math.nextafter(event,-math.inf)) < root < F(event)
    if before:
        event = math.nextafter(event,-math.inf)
    u0,u1 = (1.8,0.) if reverse else (0.,1.8)
    guard = 'V(u)<0.9' if reverse else 'V(u)>0.9'
    if nested:
        guard = f'(({guard})?1:0)>0.5'
    source = f'''`include "disciplines.vams"
module m(u,y,z); input u; output y,z; electrical u,y,z; real q;
analog begin
 @(initial_step) q=0;
 @(timer({event!r},1,0)) q=1;
 V(z)<+q;
 V(y)<+idt((1-q)*{gain!r}*(1+V(u)*V(u))*(({guard})?1.0:0.0),0);
end endmodule'''
    program=compile_sources({'root-window.va':source},[Instance('dut','m',dict(u='u',y='y',z='z'))]).to_dict()
    times=[0.,event,stop]
    if dense:
        times=sorted(set(times+[math.nextafter(float(root),-math.inf),float(root),math.nextafter(float(root),math.inf),1.5e-7]))
    slope=(F(u1)-F(u0))/(F(b)-F(a))
    expected=[]
    for t in times:
        length=max(F(0),min(F(t),F(event))-root)
        expected.append(F(gain)*((1+F(.9)**2)*length+F(.9)*slope*length**2+slope**2*length**3/3))
    return dict(program=program,driven=['u'],samples=[],tolerances=dict(absolute=1e-9,relative=1e-6),
                transient=dict(pwl=[[[0.,u0],[a,u0],[b,u1],[stop,u1]]],output_times=times,stop=stop,max_step=1e-8)),expected


class RootWindowHistory(unittest.TestCase):
    def check(self, response, expected):
        y=response['nodes'].index('y')
        by=response['observation_evidence']['nodes'].index('y')
        bounds=response['observation_evidence']['voltage_bounds_V']
        for row,bound,answer in zip(response['solutions'],bounds,expected,strict=True):
            value=F(row['voltages'][y]);lo,hi=map(F,bound[by])
            budget=F(1e-9)+F(1e-6)*abs(answer)
            self.assertLessEqual(lo,answer);self.assertLessEqual(answer,hi)
            self.assertLessEqual(abs(value-answer),budget)

    def test_endpoint_window_has_a_dense_history_and_survives_held_off(self):
        for reverse in [False,True]:
            for nested in [False,True]:
                for before in [False,True]:
                    with self.subTest(reverse=reverse,nested=nested,before=before):
                        req,exact=request(reverse,nested,before,dense=True)
                        self.check(_invoke(req,KERNEL,timeout=30),exact)

    def test_insufficient_budget_never_returns_a_false_zero_certificate(self):
        # Rejection is only a safety outcome. The moderate-gain test above
        # separately requires successful execution under the same tolerance.
        for reverse in [False,True]:
            for nested in [False,True]:
                for before in [False,True]:
                    with self.subTest(reverse=reverse,nested=nested,before=before):
                        req,exact=request(reverse,nested,before,gain=1e16)
                        try:
                            result=_invoke(req,KERNEL,timeout=30)
                        except KernelError as error:
                            self.assertIn(error.detail['kind'],('condition_precision','waveform_accuracy'))
                        else:
                            self.check(result,exact)


if __name__=='__main__':
    unittest.main()
