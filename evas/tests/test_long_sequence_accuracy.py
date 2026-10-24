"""Bounded long-sequence accuracy through the public compiler/runtime API.

No interrupted-edge oracle, timing benchmark or same-Controller retry claim.
Build the usual test kernel first. Each request has a 30-second process limit;
a timeout is a failure, not an accepted semantic outcome.
"""
# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ['TRANSITION', 'TIMED-OPERATOR', 'DYNAMICS', 'COMPOSE']

import copy
from decimal import Decimal, localcontext
from fractions import Fraction as F
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL
from initial_record_contract import check_initial_record_batch
from long_sequence_oracle import BUDGET, check_result, decimal, held, pwl_area, regular_answers


def source(period, reset=None):
    reset_events = '' if reset is None else f'''
    @(timer({float(5*period)!r},0,1e-12)) rst=1;
    @(timer({float(6*period)!r},0,1e-12)) rst=0;'''
    integral = 'idt(V(s,r),0)' if reset is None else (
        'idt(2*V(u,r),-0.25,rst)' if reset == 'direct' else 'idt(V(s,r),0,rst)')
    return f'''`include "disciplines.vams"
module m(u,s,y,f,h,r); input u; output s,y,f,h; inout r;
 electrical u,s,y,f,h,r; integer n,rst; real held;
 analog begin
    @(initial_step) begin n=0; rst=0; held=0; end
    @(timer({float(period)!r},{float(period)!r},1e-12)) begin n=n+1; held=V(u,r); end
    {reset_events}
    V(h,r)<+held;
    V(s,r)<+transition(held,0,{float(period)!r},{float(period)!r});
    V(y,r)<+{integral};
    V(f,r)<+laplace_np(V(s,r),'{{1}},'{{{float(-2/period)!r},0}});
 end endmodule'''


def scenario(periods, period=F(1,8), amplitude=F(2), divisions=2, reset=None):
    period, amplitude = F(period), F(amplitude)
    program = compile_sources({'long.va': source(period, reset)},
                              [Instance('dut', 'm', dict(u='u', s='s', y='y', f='f', h='h', r='0'))])
    times = [float(k*period/divisions) for k in range(periods*divisions+1)]
    points = [[float(k*period), float(held(k, amplitude))] for k in range(periods+1)]
    result = transient(program, {'u': points}, times, stop=float(periods*period),
                       max_step=float(2*period), kernel=KERNEL, timeout=30)
    result=check_initial_record_batch(result,program,[0,0,0],[0,0,0],1)
    return result, times, points


def chain_events(periods, period, amplitude):
    return [(k*period, 0, (F(k), F(0), held(k, amplitude))) for k in range(1, periods+1)]


def check_chain(result, times, periods, period, amplitude):
    return check_result(result, times, regular_answers(times, period, amplitude),
                        dict(s=amplitude, y=amplitude*period, f=amplitude, h=amplitude),
                        chain_events(periods, period, amplitude))


class LongSequenceAccuracy(unittest.TestCase):
    def test_small_model_oracle_exact_values_and_precision(self):
        t, a = F(1,8), F(2)
        times = [float(k*t/2) for k in range(17)]
        low, high = (regular_answers(times, t, a, precision=p) for p in (60, 90))
        self.assertEqual(high[5]['s'], F(1))
        self.assertEqual(high[5]['y'], F(1,32))
        self.assertEqual(high[6]['s'], F(2))
        self.assertEqual(high[6]['y'], F(1,8))
        self.assertEqual(high[-1]['y'], F(3,4))
        # First rising segment independently integrates exp convolution to
        # A*(1/2 - tau/T + (tau/T)*exp(-T/(2*tau))) = exp(-1).
        with localcontext() as context:
            context.prec = 90
            self.assertLess(abs(high[5]['f'] - Decimal(-1).exp()), Decimal('1e-85'))
            self.assertLess(max(abs(x['f']-y['f']) for x,y in zip(low, high)), Decimal('1e-55'))

    def test_256_period_accumulation(self):
        t, a = F(1,8), F(2)
        result, times, _ = scenario(256)
        check_chain(result, times, 256, t, a)
        # Exact area accumulates rather than cancelling: 254 triangular periods.
        self.assertEqual(F(result['solutions'][-1]['voltages'][result['nodes'].index('y')]), 254*a*t/2)

    def test_32_period_scales_and_shared_observations(self):
        t, a = F(1,8), F(2)
        sparse, times, _ = scenario(32)
        dense, dense_times, _ = scenario(32, divisions=16)
        check_chain(sparse, times, 32, t, a)
        check_chain(dense, dense_times, 32, t, a)
        self.assertEqual(sparse['transient']['events'], dense['transient']['events'])
        scales = dict(s=a, y=a*t, f=a, h=a)
        for name, scale in scales.items():
            j, k = sparse['nodes'].index(name), dense['nodes'].index(name)
            with localcontext() as context:
                context.prec = 80
                for i in range(len(times)):
                    self.assertEqual(times[i], dense_times[8*i])
                    error = abs(Decimal(sparse['solutions'][i]['voltages'][j])-Decimal(dense['solutions'][8*i]['voltages'][k]))
                    self.assertLessEqual(error/decimal(scale), BUDGET)
        for period, amplitude in ((t*F(1,2**20), a), (t, F(0.002))):
            with self.subTest(period=period, amplitude=amplitude):
                result, scaled_times, _ = scenario(32, period, amplitude)
                check_chain(result, scaled_times, 32, period, amplitude)

    def test_direct_input_reset_keeps_ic_and_release_area(self):
        t, a, ic = F(1,8), F(2), F(-1,4)
        result, times, points = scenario(16, reset='direct')
        answers = regular_answers(times, t, a)
        for time, answer in zip(map(F, times), answers):
            answer['y'] = (ic+2*pwl_area(points,time) if time < 5*t else ic if time < 6*t
                           else ic+2*(pwl_area(points,time)-pwl_area(points,6*t)))
        events = []
        for k in range(1,17):
            after = (F(k), F(k==5), held(k,a))
            events.append((k*t,0,after))
            if k in (5,6):
                events.append((k*t,k-4,after))
        check_result(result,times,answers,dict(s=a,y=a*t,f=a,h=a),events)
        index = result['nodes'].index('y')
        self.assertTrue(all(F(row['voltages'][index])==answer['y'] for row,answer in zip(result['solutions'],answers)))

    def test_explicit_admission_boundaries(self):
        with self.assertRaises(CompileError) as error:
            scenario(4, period=F(1.25e-7))
        # Compiled pole -16000000 has a non-dyadic exact reciprocal.
        self.assertIn('reciprocal coefficient', str(error.exception))
        with self.assertRaises(KernelError) as error:
            scenario(8, reset='transition')
        self.assertEqual(error.exception.detail['kind'], 'unsupported_operator')
        self.assertIn('continuous network cannot depend on an unsupported dynamic operator', error.exception.detail['message'])

    def test_checker_calibration_uses_the_same_normalized_budget(self):
        t,a=F(1,8),F(2);times=[float(k*t/2) for k in range(17)]
        answers=regular_answers(times,t,a);scales=dict(s=a,y=a*t,f=a,h=a)
        events=chain_events(8,t,a);nodes=list(scales)
        good=dict(nodes=nodes,solutions=[dict(voltages=[float(row[n]) for n in nodes],max_residual_ratio=0.0) for row in answers],
                  transient=dict(times=times,events=[dict(time=float(time),event=event,after=list(map(float,after))) for time,event,after in events]))
        def check(value):
            return check_result(value,times,answers,scales,events)
        check(good)
        for name,scale in scales.items():
            for factor,accepted in ((Decimal('.5'),True),(Decimal(2),False)):
                with self.subTest(node=name,factor=factor):
                    value=copy.deepcopy(good)
                    value['solutions'][-1]['voltages'][nodes.index(name)]+=float(factor*BUDGET*decimal(scale))
                    if accepted:check(value)
                    else:
                        with self.assertRaises(AssertionError):check(value)
        for bias,accepted in ((1e-15,True),(1e-13,True),(1e-9,False)):
            value=copy.deepcopy(good)
            for row in value['solutions']:row['voltages'][nodes.index('s')]+=bias
            if accepted:check(value)
            else:
                with self.assertRaises(AssertionError):check(value)
        faults = {
            'missing row':lambda r:r['solutions'].pop(),
            'wrong time':lambda r:r['transient']['times'].__setitem__(-1,.99),
            'missing event':lambda r:r['transient']['events'].pop(),
            'wrong state':lambda r:r['transient']['events'][-1]['after'].__setitem__(0,7.),
            'missed late fall':lambda r:r['solutions'][-1]['voltages'].__setitem__(nodes.index('s'),2.),
            'nan':lambda r:r['solutions'][-1]['voltages'].__setitem__(nodes.index('f'),float('nan')),
        }
        for name,edit in faults.items():
            with self.subTest(fault=name):
                value=copy.deepcopy(good);edit(value)
                with self.assertRaises(AssertionError):check(value)


if __name__ == '__main__':
    unittest.main()
