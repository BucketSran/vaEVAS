"""Independent smallest consumer after the native sine entry.

This is a synthetic contract, not a rewritten 074/093/364 benchmark. The
quarter-cycle sample and linear ramp have exact rational answers. Actual
original checker execution remains a separate root-owned acceptance step.
"""
GUARDS = ['ANALOG', 'TIMER', 'TRANSITION', 'COMPOSE']

import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from evas import Instance, KernelError, compile_sources, transient
from evas.scs import simulate_scs

KERNEL = Path(os.environ.get('EVAS_KERNEL',
    Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel'))


class AnalyticProviderMappingContracts(unittest.TestCase):
    def program(self):
        source = '''`include "disciplines.vams"
module mapping(x,u,y); input x,u; output y; electrical x,u,y;
analog begin V(y)<+V(x)+V(u)+$abstime; end endmodule
'''
        return compile_sources({'mapping.va': source}, [Instance('dut', 'mapping',
            {'x':'x', 'u':'u', 'y':'y'}, {})])

    @staticmethod
    def descriptor():
        return dict(kind='sine', sinedc=.5, ampl=.25, freq=1., sinephase=0.,
                    source_name='VX', terminals=['x','0'], polarity=1,
                    parameter_origin='explicit-v1')

    def test_mixed_analytic_and_pwl_with_internal_time_stay_index_aligned(self):
        # Native external order may be either [x,u] or [u,x]. Internal
        # $abstime must receive a separate nonanalytic provider slot.
        # y=.5+.25*sin(2*pi*t)+u(t)+t, with u(t)=t.
        program = self.program()
        for sources in ({'x':[], 'u':[[0.,0.],[1.,1.]]},
                        {'u':[[0.,0.],[1.,1.]], 'x':[]}):
            with self.subTest(order=list(sources)):
                result = transient(program, sources, [0.,.25,.5,.75,1.],
                    stop=1., max_step=.25, analytic_sources={'x': self.descriptor()},
                    kernel=KERNEL, timeout=30)
                output = [row['voltages'][result['nodes'].index('y')]
                          for row in result['solutions']]
                for actual, expected in zip(output, [.5,1.25,1.5,1.75,2.5]):
                    self.assertLessEqual(abs(actual-expected), 1e-11)

    def test_raw_provider_count_and_terminals_are_not_repaired_by_time_injection(self):
        program = self.program().to_dict()
        request = dict(program=program, driven=['x','u'], samples=[],
            transient=dict(pwl=[[],[[0.,0.],[1.,1.]]], output_times=[0.,1.],
                stop=1., max_step=.25, analytic_sources=[self.descriptor(),None]),
            tolerances=dict(absolute=1e-12,relative=1e-10))
        for fault in ('missing-slot', 'extra-slot', 'wrong-terminal'):
            malformed = copy.deepcopy(request)
            providers = malformed['transient']['analytic_sources']
            if fault == 'missing-slot':
                providers.pop()
            elif fault == 'extra-slot':
                providers.append(None)
            else:
                providers[0]['terminals'] = ['u','0']
            with self.subTest(fault=fault):
                child = subprocess.run([str(KERNEL)], input=json.dumps(malformed),
                    text=True, capture_output=True, timeout=30)
                self.assertNotEqual(child.returncode, 0)
                self.assertIn('invalid_inputs', child.stdout+child.stderr)
                self.assertIn('analytic', child.stdout+child.stderr)


class OriginalSourceConsumerContracts(unittest.TestCase):
    def simulate(self, body):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory/'sample.va').write_text('''`include "disciplines.vams"
module sampled(x,y); input x; output y; electrical x,y; real held;
analog begin @(initial_step) held=0;
''' + body + '\nend endmodule\n')
            deck = directory/'sample.scs'
            deck.write_text('''simulator lang=spectre
global 0
ahdl_include "sample.va"
VX (x 0) vsource type=sine sinedc=0.5 ampl=0.25 freq=1
XD (x y) sampled
tran tran stop=0.5 maxstep=0.0625
save x y
''')
            return simulate_scs(deck, kernel=KERNEL, timeout=30)

    def test_fixed_timer_analytic_sample_drives_physical_transition(self):
        # sin(2*pi*1/4)=1 gives held=.75. Transition starts at .25,
        # rises linearly for .125 and then holds. No output-derived oracle.
        result = self.simulate('''@(timer(0.25,0)) held=V(x);
V(y)<+transition(held,0,0.125,0.125);''')
        times = result['saved']['times']
        index = result['saved']['nodes'].index('y')
        actual = dict(zip(times, (row[index] for row in result['saved']['values'])))
        for time, expected in [(0.,0.), (.25,0.), (.3125,.375), (.375,.75), (.5,.75)]:
            self.assertLessEqual(abs(actual[time]-expected), 1e-10)
        self.assertEqual(len(result['transient']['events']), 1)

    def test_analytic_cross_guard_still_needs_complete_root_certificate(self):
        # No Transition here: the intended independent guard boundary must
        # reject even when an unrelated operator-admission gate is absent.
        with self.assertRaises(KernelError) as caught:
            self.simulate('''@(cross(V(x)-0.6,+1)) held=V(x);
V(y)<+held;''')
        self.assertIn('sine cross guards', caught.exception.detail['message'])


class SampledTransitionProfileContracts(unittest.TestCase):
    def program(self, body, *, declarations='real h;', target='h', output=None):
        contribution = output or f'V(y)<+transition({target},0,0.0625,0.0625);'
        source = '''`include "disciplines.vams"
module profile(x,u,y); input x,u; output y; electrical x,u,y;
''' + declarations + '\nanalog begin\n' + body + '\n' + contribution + '\nend endmodule\n'
        return compile_sources({'sampled-profile.va':source}, [Instance('dut','profile',
            {'x':'x','u':'u','y':'y'}, {})])

    def run_profile(self, program, times, *, rail=1., source_error=None, absolute=1e-8):
        sources = {'x':[], 'u':[[0.,rail],[1.,rail]]}
        if isinstance(rail, list):
            sources['u'] = rail
        return transient(program, sources, times, stop=1., max_step=.125,
            analytic_sources={'x':AnalyticProviderMappingContracts.descriptor()},
            source_errors=source_error, vabstol=absolute, reltol=0,
            kernel=KERNEL, timeout=30)

    @staticmethod
    def values(result):
        return [row['voltages'][result['nodes'].index('y')] for row in result['solutions']]

    def test_sequential_extrema_ratio_drives_held_transition(self):
        # At .25/.5/.75, x=.75/.5/.25. The first span is zero and must
        # skip division; then max/span is 3 and 1.5. Both follow the writes
        # to extrema and span in this same callback, not their old values.
        p = self.program('''@(initial_step) begin lo=1e9; hi=-1e9; span=0; h=0; sampled=0; end
@(timer(0.25,0.25)) begin sampled=V(x);
if(sampled<lo) lo=sampled; if(sampled>hi) hi=sampled;
span=hi-lo; if(span>0.125) h=hi/span; end''',
            declarations='real h,lo,hi,span,sampled;')
        result = self.run_profile(p, [0.,.375,.5625,.8125])
        for actual, expected in zip(self.values(result), [0.,0.,3.,1.5]):
            self.assertLessEqual(abs(actual-expected), 1e-10)

    def test_selected_ratio_denominator_box_containing_zero_remains_rejected(self):
        p = self.program('''@(initial_step) h=0;
@(timer(0.25,0)) h=1.0/V(u);''')
        # The nominal denominator is positive, but the full physical input
        # box [-.125,.375] contains zero. The point value cannot approve it.
        with self.assertRaises(KernelError):
            self.run_profile(p, [0.,.5], rail=.125, source_error={'u':.25})

    def test_physical_dc_output_factor_and_varying_rail_refusal(self):
        p = self.program('''@(initial_step) h=0;
@(timer(0.25,0)) h=V(x);''',
            output='V(y)<+V(u)*transition(h,0,0.0625,0.0625);')
        result = self.run_profile(p, [0.,.28125,.375], rail=2.)
        for actual, expected in zip(self.values(result), [0.,.75,1.5]):
            self.assertLessEqual(abs(actual-expected), 1e-10)
        # Same initial rail, different whole-request waveform: not DC.
        with self.assertRaises(KernelError):
            self.run_profile(p, [0.,.375], rail=[[0.,2.],[.5,2.],[1.,3.]])

    def test_nonpoint_sample_keeps_error_and_passive_query_invariance(self):
        # sin(pi/4) is irrational; its certified held box cannot become a
        # manufactured exact point merely because Transition holds its target.
        from fractions import Fraction
        from test_analytic_sources import source_box
        p = self.program('''@(initial_step) h=0;
@(timer(0.125,0)) h=V(x);''')
        sparse = self.run_profile(p, [0.,.25,.5])
        dense = self.run_profile(p, [0.,.0625,.125,.15625,.1875,.25,.375,.5])
        self.assertEqual(sparse['transient']['events'], dense['transient']['events'])
        self.assertEqual(sparse['solutions'][-1], dense['solutions'][-1])
        lo, hi = source_box(Fraction(1,8))
        node = sparse['nodes'].index('y')
        bounds = sparse['observation_evidence']['voltage_bounds_V'][-1][node]
        self.assertLessEqual(Fraction(bounds[0]), lo)
        self.assertGreaterEqual(Fraction(bounds[1]), hi)
        amplified = self.program('''@(initial_step) h=0;
@(timer(0.125,0)) h=V(x);''', target='1e12*h')
        with self.assertRaises(KernelError):
            self.run_profile(amplified, [0.,.25,.5], absolute=1e-12)

    def test_continuous_target_and_foreign_or_hidden_history_roles_remain_rejected(self):
        continuous = self.program('''@(initial_step) h=0;
@(timer(0.25,0)) h=V(x);''', target='V(x)')
        with self.assertRaises(KernelError):
            self.run_profile(continuous, [0.,.5])
        valid = json.loads(json.dumps(self.program('''@(initial_step) h=0;
@(timer(0.25,0)) h=V(x);''').to_dict()))
        for fault in ('foreign-state', 'hidden-history'):
            wire = copy.deepcopy(valid)
            if fault == 'foreign-state':
                wire['states'][0]['instance'] = 'foreign'
            else:
                wire['events'][0]['body'].append(dict(kind='if', relation='gt',
                    left=dict(op='affine',constant=0.,terms=[]),
                    right=dict(op='affine',constant=1.,terms=[]),
                    then_body=[dict(kind='assign',state=0,rhs=dict(op='operator',operator=0))],
                    else_body=[], origin=wire['events'][0]['origin']))
            request = dict(program=wire,driven=['x','u'],samples=[],
                transient=dict(pwl=[[],[[0.,1.],[1.,1.]]],output_times=[0.,.5],
                    stop=1.,max_step=.125,
                    analytic_sources=[AnalyticProviderMappingContracts.descriptor(),None]),
                tolerances=dict(absolute=1e-8,relative=0.))
            with self.subTest(fault=fault):
                child = subprocess.run([str(KERNEL)], input=json.dumps(request),
                    text=True,capture_output=True,timeout=30)
                self.assertNotEqual(child.returncode,0)


if __name__ == '__main__':
    unittest.main()
