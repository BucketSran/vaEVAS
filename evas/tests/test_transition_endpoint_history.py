"""Issue #227: endpoint removal preserves the complete old ramp history.

These analytic references were retained from 59d82ee0's independent deadline
cases. Sign, retarget, step-size and query controls detect distinct losses of
an old edge; the production kernel does not supply the expected answers.
"""
GUARDS = ["TRANSITION", "DYNAMICS", "COMPOSE", "TIMER", "EVENT-ORDER"]
from decimal import Decimal, localcontext
from fractions import Fraction as F
import math
import unittest
from evas import Instance, compile_sources, transient
from test_affine import KERNEL
from test_timer_at_transition_ramp_end import SOURCE, answers


def continued_answers(t,tick,sign):
    a,b,p,q,r,tau=map(F,(2e-6,2.5e-7,sign*.5,-sign*.5,-sign*1.5,2e-7))
    t,c=F(t),F(tick)
    if t<=c:
        return answers(float(t),q0=float(p),q1=float(q))
    h=min(c-a,b)
    v=p+(q-p)*h/b
    origin=p if c<a+b else q
    slope=(r-origin)/b
    duration=(r-v)/slope
    u=min(t-c,duration)
    value=v+slope*u
    area_c=p*c+(q-p)*(h*h/(2*b)+max(F(0),c-a-b))
    area=area_c+v*u+slope*u*u/2+r*max(F(0),t-c-duration)
    with localcontext() as ctx:
        ctx.prec=80
        d=lambda x:Decimal(x.numerator)/Decimal(x.denominator)
        pd,qd,bd,td,hd,vd,sd,ud,rd=map(d,(p,q,b,tau,h,v,slope,u,r))
        f=pd+(qd-pd)/bd*(hd-td*(1-(-hd/td).exp()))
        if c>a+b:
            f=qd+(f-qd)*(-d(c-a-b)/td).exp()
        f=vd+sd*(ud-td)+(f-vd+sd*td)*(-ud/td).exp()
        if t-c>duration:
            f=rd+(f-rd)*(-d(t-c-duration)/td).exp()
    return tuple(map(float,(value,f,area)))


def run_case(parameters, times, *, strobe=False, order=("dut",)):
    instances = [Instance(name, "edge", {node: f"{name}_{node}" for node in "yfzn"},
                          parameters) for name in order]
    program = compile_sources({"edge.va": SOURCE}, instances)
    return transient(program, {}, times, stop=max(times), max_step=3.125e-8,
                     kernel=KERNEL, vabstol=1e-9, reltol=0,
                     **({"strobetimes": times} if strobe else {}))


class TransitionEndpointHistory(unittest.TestCase):
    def assert_values(self, result, parameters, times, names=("dut",)):
        self.assertEqual(result["transient"]["times"], times)
        self.assertEqual(len(result["solutions"]), len(times))
        events = result["transient"]["events"]
        self.assertEqual(len(events), 2*len(names))
        self.assertTrue(all(a["time"] <= b["time"] for a, b in zip(events, events[1:])))
        for t, row in zip(times, result["solutions"]):
            values = dict(zip(result["nodes"], row["voltages"]))
            wanted = answers(t, **{k:v for k,v in parameters.items() if k != "tick"})
            for name in names:
                for node, exact in zip("yfz", wanted):
                    self.assertAlmostEqual(values[f"{name}_{node}"], exact, delta=(2e-14 if node == "z" else 1e-9),
                                           msg=(name, node, t))
                count = int(t >= parameters.get("start",2e-6))+int(t >= parameters.get("tick",2.25e-6))
                self.assertEqual(values[f"{name}_n"], count)

    def test_both_exact_orders_and_signs_preserve_ramp_filter_and_area(self):
        # Both points touch the naive interval, but the exact sum lies between.
        for tick in (math.nextafter(2.25e-6, -math.inf), 2.25e-6):
            for q0, q1 in ((.5,-.5),(-.5,.5)):
                with self.subTest(tick=tick, q0=q0):
                    parameters = dict(tick=tick, q0=q0, q1=q1)
                    times = sorted(set([0., 2e-6, tick, 2.25e-6, 2.4e-6, 2.6e-6]))
                    self.assert_values(run_case(parameters, times), parameters, times)

    def test_exact_equality_and_separated_control_preserve_same_answers(self):
        for parameters in ({"start":2**-19,"width":2**-22,"tick":2**-19+2**-22},
                           {"tick":2.5e-6}):
            with self.subTest(parameters=parameters):
                times=sorted(set([0.,parameters.get("start",2e-6),parameters["tick"],2.8e-6]))
                self.assert_values(run_case(parameters,times),parameters,times)

    def test_queries_strobes_and_instance_order_do_not_change_history(self):
        sparse=[0.,2e-6,2.25e-6,2.4e-6,2.6e-6]
        dense=sorted(set(sparse+[i*2.6e-6/32 for i in range(33)]))
        parameters={}
        baseline=run_case(parameters,sparse,order=("a","b"))
        self.assert_values(baseline,parameters,sparse,("a","b"))
        for strobe, order in ((False,("b","a")),(True,("a","b"))):
            result=run_case(parameters,dense,strobe=strobe,order=order)
            self.assert_values(result,parameters,dense,("a","b"))
            for i,t in enumerate(sparse):
                before = dict(zip(baseline['nodes'], baseline['solutions'][i]['voltages']))
                after = dict(zip(result['nodes'], result['solutions'][dense.index(t)]['voltages']))
                self.assertEqual(before, after)

    def test_nearby_retarget_keeps_the_correct_ramp_origin(self):
        source=SOURCE.replace('q1=-0.5, tau=2e-7;', 'q1=-0.5, q2=-1.5, tau=2e-7;').replace(
            '@(timer(tick,0,1e-13)) count=count+1;',
            '@(timer(tick,0,1e-13)) begin q=q2; count=count+1; end')
        for tick in (math.nextafter(2.25e-6,-math.inf),2.25e-6):
            for sign in (-1,1):
                parameters=dict(tick=tick,q0=.5*sign,q1=-.5*sign,q2=-1.5*sign)
                program=compile_sources({'retarget.va':source},
                    [Instance('dut','edge',{n:n for n in 'yfzn'},parameters)])
                times=sorted(set([0.,2e-6,tick,2.25e-6,tick+6.25e-8,tick+1.25e-7,2.8e-6]))
                for step in (2.8e-6,3.125e-8):
                    with self.subTest(tick=tick,sign=sign,step=step):
                        result=transient(program,{},times,stop=times[-1],max_step=step,
                                         kernel=KERNEL,vabstol=1e-9,reltol=0)
                        self.assertEqual(len(result['solutions']),len(times))
                        for t,row in zip(times,result['solutions'],strict=True):
                            for node,wanted,budget in zip('yfz',continued_answers(t,tick,sign),
                                                          (2e-10,2e-10,2e-14),strict=True):
                                self.assertAlmostEqual(row['voltages'][result['nodes'].index(node)],
                                                       wanted,delta=budget,msg=(node,t))
