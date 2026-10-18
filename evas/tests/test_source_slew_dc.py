"""Whole-domain physical DC leaves retain limiter history and voltage errors."""
# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["SLEW", "TIMED-OPERATOR"]

from fractions import Fraction as F
import os
from pathlib import Path
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL as DEFAULT_KERNEL, instance, model

KERNEL = Path(os.environ.get('EVAS_SOURCE_SLEW_DC_KERNEL', DEFAULT_KERNEL))


def run(body='V(y,r)<+slew(V(u,r)>0.5?V(v,r)-V(w,r):0,1,-2);', *,
        sources=None, times=None, stop=2, atol=1e-12, errors=None, shapes=None):
    source = model(body, ports='u,v,w,y,r',
                   directions='input u,v,w; output y; inout r;')
    program = compile_sources({'dc_slew.va': source}, [instance(connections={
        'u':'u', 'v':'v', 'w':'w', 'y':'y', 'r':'r'})])
    inputs = {'u':[[0,0],[1,1],[2,1]], 'v':[[0,.9],[2,.9]],
              'w':[[0,.2],[2,.2]], 'r':[[0,.1],[2,.1]]}
    inputs.update(sources or {})
    return transient(program, inputs, times or [0,.5,.75,1,1.5,2], stop=stop,
                     max_step=stop, source_errors=errors, source_shapes=shapes,
                     vabstol=atol, reltol=0, kernel=KERNEL)


def voltage(result, name='y'):
    index = result['nodes'].index(name)
    return [row['voltages'][index] for row in result['solutions']]


class SourceSlewDc(unittest.TestCase):
    def test_nonzero_reference_dc_leaf_preserves_difference(self):
        result = run()
        # u-r crosses .5 at .6, y-r starts at zero and reaches .7 at 1.3.
        expected = [F(.1),F(.1),F(.1)+F(.75)-F(.6),F(.1)+1-F(.6),
                    F(.1)+F(.9)-F(.2),F(.1)+F(.9)-F(.2)]
        for actual, exact in zip(voltage(result), expected):
            self.assertLessEqual(abs(F(actual)-exact), F(1e-12))

    def test_isolated_third_point_keeps_continuous_history(self):
        result = run('V(y,r)<+slew(V(u,r)>0.5?V(v,r):(V(u,r)<0.5?0:V(w,r)),1,-2);',
                     sources={'r':[[0,0],[2,0]], 'v':[[0,1],[2,1]],'w':[[0,7],[2,7]]})
        self.assertEqual(voltage(result), [0,0,.25,.5,1,1])

    def test_two_call_sites_keep_independent_history(self):
        body = ('V(y,r)<+slew(V(u,r)>0.5?V(v,r):0,1,-2)'
                '+slew(V(u,r)>0.75?V(w,r):0,2,-1);')
        result = run(body,sources={'r':[[0,0],[2,0]],'v':[[0,1],[2,1]],'w':[[0,1],[2,1]]})
        self.assertEqual(voltage(result), [0,0,.25,1,2,2])

    def test_same_endpoints_with_middle_or_future_pulse_are_rejected(self):
        for points,times in [([[0,.9],[1,1],[2,.9]],None),
                             ([[0,.9],[1,.9],[1.5,1],[2,.9]],[0,.25,.5])]:
            with self.subTest(points=points), self.assertRaises(KernelError):
                run(sources={'v':points},times=times)

    def test_undefined_source_box_even_under_zero_weight_is_rejected(self):
        for term in ['V(v,r)', '0*V(v,r)']:
            with self.subTest(term=term), self.assertRaises(KernelError):
                run(f'V(y,r)<+slew(V(u,r)>0.5?{term}:0,1,-2);',errors={'v':1e-9})

    def test_varying_sources_do_not_gain_cancellation_certificate(self):
        with self.assertRaises(KernelError):
            run(sources={'v':[[0,.9],[2,1.9]],'w':[[0,.2],[2,1.2]]})

    def test_true_zero_seed_is_not_the_open_right_dc_target(self):
        result = run('V(y,r)<+slew(V(u,r)>0?V(v,r):V(w,r),1,-2);',
                     sources={'r':[[0,0],[2,0]],'v':[[0,1],[2,1]],'w':[[0,.25],[2,.25]]},
                     times=[0,.25,.5,1,2])
        self.assertEqual(voltage(result), [.25,.5,.75,1,1])

    def test_nonzero_shaped_source_error_domain_gate_is_preserved(self):
        shape=[dict(time_numerator=str(t),time_denominator='1',value_V=.75) for t in [0,2]]
        with self.assertRaisesRegex(KernelError,'unsupported_source_uncertainty'):
            run('V(y,r)<+slew(V(u,r)>0.5?V(v,r):0,1,-2);',
                sources={'r':[[0,0],[2,0]]},errors={'v':.2},shapes={'v':shape})

    def test_zero_error_physical_dc_shape_preserves_limiter(self):
        shape=[dict(time_numerator=str(t),time_denominator='1',value_V=.75) for t in [0,2]]
        result=run('V(y,r)<+slew(V(u,r)>0.5?V(v,r):0,1,-2);',
                   sources={'r':[[0,0],[2,0]],'v':[[0,.75],[2,.75]]},
                   errors={'v':0},shapes={'v':shape})
        self.assertEqual(voltage(result),[0,0,.25,.5,.75,.75])

    def test_transition_source_leaf_uses_whole_domain_dc_certificate(self):
        result = run('V(y,r)<+transition(V(u,r)>0.5?V(v,r):0,0,1,1);',
                     sources={'r':[[0,0],[2,0]],'v':[[0,1],[2,1]]})
        self.assertEqual(voltage(result),[0,0,0.25,0.5,1,1])

    def test_product_rounding_error_survives_future_gain(self):
        exact=F(.9)*F(.06666666666666667)
        rounded=float(exact)
        body=f'V(y,r)<+1073741824*(slew(V(u,r)>0.5?V(v,r)*0.06666666666666667:0,1,-2)-{rounded!r});'
        options=dict(sources={'r':[[0,0],[2,0]]},times=[1,2])
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            run(body,atol=1e-10,**options)
        result=run(body,atol=1e-5,**options)
        for actual in voltage(result):
            self.assertLessEqual(abs(F(actual)-2**30*(exact-F(rounded))),F(1e-5))


if __name__=='__main__':
    unittest.main()
