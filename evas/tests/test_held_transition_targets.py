"""Held-only nested selection: exact source and independent ramp areas."""
GUARDS = ["TRANSITION", "EVENT-CONDITIONS"]
from fractions import Fraction as Q
from pathlib import Path
import unittest
from evas import Instance, CompileError, KernelError, compile_sources, transient
from evas.scs import load_scs
from test_affine import KERNEL

INPUTS=Path(__file__).resolve().parents[2]/'evas/validation/held_transition_targets/inputs'
TIMES=[0,.5,1,1.000000001,1.125,1.25,1.5,2,2.000000001,2.125,2.25,2.5,3,3.000000001,3.125,3.25]
def answer(t):
    t=Q(t)
    clip=lambda x:max(Q(0),min(Q(1),4*x))
    return clip(t-1)-clip(t-2)+clip(t-3)
def program(case='held-nested-select'):
    return compile_sources({'dut.va':(INPUTS/case/'dut.va').read_text()},[Instance('D','held',connections={'y':'y'})])
def run(p,times):
    return transient(p,{},times,stop=3.25,max_step=.01,kernel=KERNEL,vabstol=1e-7,reltol=0)
class HeldTransitionTargets(unittest.TestCase):
    def test_original_arithmetic_target_preserves_waveform_and_query_history(self):
        p=program();a=run(p,TIMES);dense=sorted(set(TIMES+[i/32 for i in range(105)]));b=run(p,dense)
        self.assertEqual(a['transient']['events'],b['transient']['events'])
        self.assertEqual(a['solutions'],[b['solutions'][dense.index(t)]for t in TIMES])
        for result,times in [(a,TIMES),(b,dense)]:
            i=result['nodes'].index('y');bounds=result['observation_evidence']['voltage_bounds_V']
            for n,(t,row) in enumerate(zip(times,result['solutions'])):
                expected=answer(t);actual=Q(row['voltages'][i]);lo,hi=map(Q,bounds[n][i])
                self.assertLessEqual(abs(actual-expected),Q(1e-7))
                self.assertLessEqual(lo,expected);self.assertGreaterEqual(hi,expected)
    def test_hidden_zero_feedback_is_still_structurally_rejected(self):
        with self.assertRaisesRegex(CompileError,'transition target values must be held states or constants'):
            run(program('held-hidden-feedback'),TIMES)
    def test_original_scs_method_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(CompileError,"got 'traponly'"):
            load_scs(INPUTS/'held-nested-select/tb.scs')
