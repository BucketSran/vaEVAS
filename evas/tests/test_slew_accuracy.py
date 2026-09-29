"""Independent binary64-input rational contracts for operator error transfer."""
from fractions import Fraction as F
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


def execute(body, *, sources=None, times=None, stop=3, atol=1e-12, rtol=0,
            declarations='', step=None):
    source = model(body, declarations, ports='u,v,y,r',
                   directions='input u,v; output y; inout r;')
    program = compile_sources({'accuracy.va': source}, [instance(connections={
        'u': 'u', 'v': 'v', 'y': 'y', 'r': '0'})])
    sources = dict(sources or {'u': [[0, 0], [3, 1]]})
    sources.setdefault('v', [[0, 0], [stop, 0]])
    return transient(program, sources,
                     times or [0, 1, 3], stop=stop,
                     max_step=stop if step is None else step, kernel=KERNEL,
                     vabstol=atol, reltol=rtol)


def value(result, row, node='y'):
    return result['solutions'][row]['voltages'][result['nodes'].index(node)]


class HistoryAccuracy(unittest.TestCase):
    def test_reversal_catchup_error_reaches_voltage_budget(self):
        body = 'V(y,r)<+1073741824*slew(V(u,r),1,-2);'
        sources = {'u': [[0,0],[2,4],[4,-4],[8,-4]]}
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body, sources=sources, times=[0,3,8], stop=8, atol=1e-9)
        result = execute(body, sources=sources, times=[0,3,8], stop=8, atol=1e-5)
        self.assertLessEqual(abs(F(value(result, 1))-F(6*1073741824,5)), F(1e-5))

    def test_network_gain_must_not_hide_interpolation_error(self):
        body = 'V(y,r)<+1073741824*slew(V(u,r),2,-2);'
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body, atol=1e-10)
        result = execute(body, atol=1e-6)
        self.assertLessEqual(abs(F(value(result, 1))-F(1073741824, 3)), F(1e-6))

    def test_source_interpolation_at_another_sources_knot_is_enclosed(self):
        # v adds a semantic knot at t=1. Materializing u there must retain
        # its exact 1/3 value's enclosure, rather than reset it to binary64.
        sources = {'u': [[0, 0], [3, 1]], 'v': [[0, 0], [1, 0], [3, 0]]}
        body = 'V(y,r)<+1073741824*slew(V(u,r),2,-2);'
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body, sources=sources, atol=1e-10)
        result = execute(body, sources=sources, atol=1e-6)
        self.assertLessEqual(abs(F(value(result, 1))-F(1073741824, 3)), F(1e-6))

    def test_initial_affine_input_arithmetic_is_enclosed(self):
        body = 'V(y,r)<+slew(.1*V(u,r)+.2*V(u,r),2,-2);'
        sources = {'u': [[0, 1], [3, 1]]}
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body, sources=sources, atol=1e-18)
        result = execute(body, sources=sources)
        self.assertLessEqual(abs(F(value(result, 0))-(F(.1)+F(.2))), F(1e-12))

    def test_same_time_sampling_uses_joint_voltage_solution(self):
        updates = ['@(timer(1,0,1e-12)) n=1;',
                   '@(timer(1,0,1e-12)) s=V(z,r);']
        for order in [updates, updates[::-1]]:
            body = ('@(initial_step) begin n=0; s=0; end ' + ' '.join(order)
                    + 'V(z,r)<+n+slew(V(u,r),2,-2); V(y,r)<+s;')
            for step in [3, .25]:
                result = execute(body, declarations='integer n; real s; electrical z;',
                                 sources={'u': [[0, 0], [3, 3]]},
                                 rtol=1e-10, step=step)
                self.assertEqual([value(result, k) for k in range(3)], [0, 2, 2])
                self.assertEqual(result['transient']['states'][1], [1, 2])

    def test_sampled_history_error_survives_later_event(self):
        body = ('@(initial_step) begin b=0;c=0;end '
                '@(timer(1,0,.001)) b=V(y,r); '
                '@(timer(2,0,.001)) c=1073741824*V(z,r)-357913941.3333333+1; '
                'V(y,r)<+slew(V(u,r),2,-2); V(z,r)<+b; V(w,r)<+c;')
        declarations = 'real b,c; electrical z,w;'
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body, times=[0,1,2,3], declarations=declarations,
                    atol=1e-9, rtol=1e-9)
        result = execute(body, times=[0,1,2,3], declarations=declarations,
                         atol=1e-6, rtol=1e-6)
        exact = F(1073741824,3)-F(357913941.3333333)+1
        self.assertLessEqual(abs(F(value(result, 2, 'dut:w'))-exact), F(1e-6))
