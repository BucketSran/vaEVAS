"""Independent polynomial forcing controls for accepted transition filters."""
GUARDS = ['TIMED-OPERATOR', 'DYNAMICS', 'COMPOSE']
import math
import unittest
from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL

T = 2.0**-20
XS = [0,1,1.125,1.25,1.5,1.75,2,2.5,3,4]


def execute(expression='(2+V(ctrl))*e+0.125-0.25*V(ctrl)', *, interrupt=False,
            times=None, forced=False, direct=False, capture=False):
    source = '''`include "disciplines.vams"
module live_filter(ctrl,y,f);input ctrl;output y,f;electrical ctrl,y,f;
parameter real T=9.5367431640625e-7;integer q;real e;
analog begin @(initial_step)q=0;@(timer(T,0,1e-12))q=1;
INTERRUPT
e=transition(q,0,T,T);
V(y)<+EXPR;
V(f)<+laplace_nd(V(y),'{-2},'{1,T});
end endmodule'''.replace('INTERRUPT', '@(timer(1.5*T,0,1e-12))q=0;' if interrupt else '').replace('EXPR',expression)
    if direct: source=source.replace('laplace_nd(V(y),', 'laplace_nd('+expression+',')
    connections=dict(ctrl='ctrl',y='y',f='f')
    if capture:
        source=source.replace('module live_filter(ctrl,y,f);','module live_filter(ctrl,y,f,sampled);')
        source=source.replace('parameter real T=', 'output sampled;electrical sampled;real held;parameter real T=')
        source=source.replace('end endmodule', '@(timer(1.75*T,0,1e-12))held=V(f);V(sampled)<+held;end endmodule')
        connections['sampled']='sampled'
    program=compile_sources({'live.va':source},[Instance('M','live_filter',connections)])
    grid=times or [x*T for x in XS]
    return transient(program, {'ctrl':[[0,0],[1.25*T,1.25],[2.5*T,-1.25],[4*T,.25]]}, grid,
                     stop=4*T,max_step=T/16,vabstol=1e-10,reltol=0,
                     strobetimes=grid if forced else [],kernel=KERNEL)


def answer(x, interrupt):
    # Separate local polynomial ODE solution. Segments combine the prescribed
    # source knots and original edge starts/ends, independent of saved queries.
    cuts=[0,1,1.25,1.5,2,2.5,4] if interrupt else [0,1,1.25,2,2.5,4]
    f=-.25
    for lo,hi in zip(cuts,cuts[1:]):
        if x<=lo: break
        h=min(x,hi)-lo
        if lo<1.25: c,dc=lo,1
        elif lo<2.5: c,dc=1.25-2*(lo-1.25),-2
        else: c,dc=-1.25+(lo-2.5),1
        if lo<1: e,de=0,0
        elif interrupt and lo>=1.5:
            e,de=(2-lo,-1) if lo<2 else (0,0)
        else: e,de=(lo-1,1) if lo<2 else (1,0)
        p0=(2+c)*e+.125-.25*c
        p1=(2+c)*de+dc*e-.25*dc
        p2=dc*de
        # tau=1: particular = K*(p-p'+p'').
        q0=-2*(p0-p1+2*p2)
        qh=-2*(p0+p1*h+p2*h*h-p1-2*p2*h+2*p2)
        f=qh+(f-q0)*math.exp(-h)
        if x<=hi: break
    return f


class LiveTransitionFilter(unittest.TestCase):
    def test_external_knots_signed_gain_offset_and_interruption(self):
        for interrupt in [False,True]:
            with self.subTest(interrupt=interrupt):
                result=execute(interrupt=interrupt)
                f=result['nodes'].index('f')
                for x,row in zip(XS,result['solutions']):
                    self.assertAlmostEqual(row['voltages'][f],answer(x,interrupt),delta=1e-8)

    def test_callback_samples_actual_filter_after_source_knot_and_interrupt(self):
        result=execute(interrupt=True,capture=True)
        sampled=result['nodes'].index('sampled')
        f=result['nodes'].index('f')
        for x,row in zip(XS,result['solutions']):
            self.assertAlmostEqual(row['voltages'][f],answer(x,True),delta=1e-8)
            self.assertAlmostEqual(row['voltages'][sampled],answer(1.75,True) if x>=1.75 else 0,delta=1e-8)

    def test_direct_expression_uses_same_history_as_grounded_alias(self):
        self.assertEqual(execute()['solutions'],execute(direct=True)['solutions'])

    def test_saved_and_forced_grids_do_not_rebuild_forcing(self):
        sparse=execute(interrupt=True)
        dense=execute(interrupt=True,times=[i*T/32 for i in range(129)])
        forced=execute(interrupt=True,forced=True)
        self.assertEqual(sparse['transient']['events'],dense['transient']['events'])
        for i,(x,row) in enumerate(zip(XS,sparse['solutions'])):
            self.assertEqual(row,dense['solutions'][int(x*32)])
            self.assertEqual(row,forced['solutions'][i])

    def test_invalid_dependencies_cannot_hide_in_zero_or_unselected_arm(self):
        invalid=['(2+V(ctrl))*e+0*V(f)',
                 '(2+V(ctrl))*e+0*transition(q,0,T,T)',
                 '(2+V(ctrl))*e+0*idt(1)',
                 '(2+V(ctrl))*e+0*sin(V(ctrl))',
                 "(2+V(ctrl))*e+0*laplace_nd(V(ctrl),'{1},'{1,T})",
                 '(2+V(ctrl))*e+0*q',
                 '(V(ctrl)>0 ? (2+V(ctrl))*e : V(f))',
                 'e*e', '(2+V(ctrl)*V(ctrl))*e',
                 '(2+(0*V(ctrl))*V(ctrl))*e',
                 '(2+V(ctrl))*e/(1+V(ctrl))',
                 '(2+V(ctrl))*transition(V(ctrl)>0 ? q : 0,0,T,T)']
        for expression in invalid:
            with self.subTest(expression=expression), self.assertRaises((CompileError, KernelError)):
                execute(expression)
