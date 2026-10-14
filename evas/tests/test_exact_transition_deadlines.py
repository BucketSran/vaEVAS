"""A shared exact physical callback can certify fresh transition endpoints."""
GUARDS = ['CROSS','TRANSITION','COMPOSE','EVENT-ORDER']
import os
from pathlib import Path
import unittest
from evas import KernelError, compile_sources, transient
from test_affine import model, instance, KERNEL as DEFAULT_KERNEL
KERNEL=Path(os.environ.get('EVAS_DEADLINE_KERNEL',DEFAULT_KERNEL))
TIMES=[0.,0.3,0.34,0.35,0.5]

def execute(delay=0., instances=None, forced=False, consumers=False):
    body=f'@(initial_step)q=0; @(cross(V(u,r)-1,1,1e-9,1e-9))q=1; V(y,r)<+transition(q,{delay},0.01);V(a,r)<+transition(2*q,{delay},0.01);'
    if consumers:
        body += "V(i,r)<+idt(V(y,r),0);V(f,r)<+laplace_nd(V(a,r),'{1},'{1,0.01});"
    p=compile_sources({'deadline.va':model(body,'real q;electrical a,i,f;')},instances or [instance()])
    return transient(p,{'u':[[0.,0.],[1.,3.]]},TIMES,stop=0.5,max_step=0.05,
                     strobetimes=TIMES if forced else [],kernel=KERNEL)

class ExactTransitionDeadlines(unittest.TestCase):
    def test_same_source_callback_two_fresh_edges(self):
        result=execute()
        y=result['nodes'].index('y');a=result['nodes'].index('dut:a')
        for solution in result['solutions']:
            self.assertEqual(solution['voltages'][a],2*solution['voltages'][y])
        self.assertEqual(result['solutions'][-1]['voltages'][y],1.)
        self.assertEqual(result['solutions'],execute(forced=True)['solutions'])

    def test_fixed_delay_and_two_instances_keep_distinct_outputs(self):
        ins=[instance('d0',connections={'u':'u','y':'y0','r':'0'}),instance('d1',connections={'u':'u','y':'y1','r':'0'})]
        r=execute(delay=0.002,instances=ins)
        y0=r['nodes'].index('y0');y1=r['nodes'].index('y1')
        for solution in r['solutions']:
            self.assertEqual(solution['voltages'][y0],solution['voltages'][y1])
        self.assertEqual(r['solutions'][-1]['voltages'][y0],1.)

    def test_filtered_and_integral_consumers_share_the_same_preview(self):
        r=execute(consumers=True)
        i=r['nodes'].index('dut:i'); f=r['nodes'].index('dut:f')
        self.assertAlmostEqual(r['solutions'][-1]['voltages'][i],0.5-1/3-0.005,places=7)
        self.assertGreater(r['solutions'][-1]['voltages'][f],1.9)

    def test_interrupted_shared_callback_keeps_ordering_refusal(self):
        body='@(initial_step)q=0;@(cross(V(u,r)-1,1,1e-9,1e-9))q=1;@(timer(0.4,0,1e-9))q=2;V(y,r)<+transition(q,0,1);V(a,r)<+transition(2*q,0,1);'
        p=compile_sources({'interrupted.va':model(body,'real q;electrical a;')},[instance()])
        with self.assertRaises(KernelError) as caught:
            transient(p,{'u':[[0.,0.],[1.,3.],[1.5,3.]]},[0.,0.5,1.5],stop=1.5,max_step=0.05,kernel=KERNEL)
        self.assertEqual(caught.exception.detail['kind'],'event_resolution')
        self.assertIn('ordering of operator deadlines',caught.exception.detail['message'])
