"""Certificates keep live operator samples and same-time feedback after map reuse."""
GUARDS = ["LANG", "EVENT-ORDER", "COMPOSE"]
import os
from pathlib import Path
import unittest
from evas import KernelError, compile_sources, transient
from test_affine import KERNEL as DEFAULT_KERNEL, model, instance

KERNEL = Path(os.environ.get('EVAS_CERTIFICATE_KERNEL', DEFAULT_KERNEL))


def execute(body, declarations='real q;', *, times=None, forced=False):
    p = compile_sources({'certificate.va': model(body, declarations)}, [instance()])
    times = times or [0.,0.25,0.5,0.75,1.]
    return transient(p, {'u': [[0.,1.],[1.,1.]]}, times, stop=1., max_step=0.125,
                     strobetimes=times if forced else [], kernel=KERNEL)


def output(r):
    return [row['voltages'][r['nodes'].index('y')] for row in r['solutions']]


class CertificateCache(unittest.TestCase):
    def test_operator_samples_remain_live_and_queries_do_not_change_values(self):
        body = 'V(y,r)<+idt(V(u,r),0);'
        sparse = execute(body, times=[0.,0.5,1.])
        dense = execute(body)
        forced = execute(body, forced=True)
        self.assertEqual(output(dense),[0.,0.25,0.5,0.75,1.])
        self.assertEqual(output(sparse),[0.,0.5,1.])
        self.assertEqual(dense['solutions'],forced['solutions'])

    def test_ordered_sample_assignment_keeps_joint_feedback(self):
        body = '@(initial_step)q=0; @(timer(0.5,0,0.001)) begin q=V(y,r);q=q+1;end V(y,r)<+0.5*q+idt(V(u,r),0);'
        result = execute(body)
        # At tau=.5: q=.5*q+.5+1, so q=3 and y=2.
        self.assertEqual(result['transient']['states'][-1],[3.])
        self.assertEqual(output(result),[0.,0.25,2.,2.25,2.5])

    def test_unsupported_continuous_state_product_remains_rejected(self):
        with self.assertRaises(KernelError) as caught:
            execute('@(initial_step)q=2; V(y,r)<+q*idt(V(u,r),0);')
        self.assertEqual(caught.exception.detail['kind'],'unsupported_transient')

    def test_singular_same_time_feedback_remains_rejected(self):
        with self.assertRaises(KernelError) as caught:
            execute('@(initial_step)q=0; @(timer(0.5,0,0.001))q=V(y,r); V(y,r)<+q+idt(V(u,r),0);')
        self.assertIn(caught.exception.detail['kind'],['event_accuracy','unsupported_event','singular_system'])
