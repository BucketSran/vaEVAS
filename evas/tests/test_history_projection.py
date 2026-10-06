"""Internal voltage histories use the same physical PWL as direct encodings."""
GUARDS = ["ABSDELAY", "SLEW", "TIMED-OPERATOR", "COMPOSE", "case:projected_history"]

from pathlib import Path
import unittest
from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


DUT = (Path(__file__).resolve().parents[1] / 'validation/cases/projected_history/dut.va').read_text()


def execute(body=None, *, times=None, step=8):
    source = model(body, 'electrical z;' + ('electrical d;' if 'V(d,' in body else '')) if body is not None else DUT
    program = compile_sources({'projection.va': source},
                              [instance(module='m' if body is not None else 'projected_history')])
    return transient(program, {'u': [[0,0],[2,2],[8,2]]},
                     times or [0,1,2,3,4,5,8], stop=8, max_step=step, kernel=KERNEL)


def values(result, node):
    index = result['nodes'].index(node)
    return [s['voltages'][index] for s in result['solutions']]


class HistoryProjection(unittest.TestCase):
    def test_solved_internal_feedback_drives_delay_and_slew(self):
        result = execute()
        self.assertEqual(values(result, 'dut:d'), [0,0,2,4,4,4,4])
        self.assertEqual(values(result, 'y'), [0,1,2,3,4,4,4])

    def test_equivalent_encodings_and_extra_samples(self):
        internal = '''V(z,r)<+2*V(u,r);
          V(d,r)<+absdelay(V(z,r),1); V(y,r)<+slew(V(z,r),1,-2);'''
        direct = internal.replace('absdelay(V(z,r)', 'absdelay(2*V(u,r)').replace(
            'slew(V(z,r)', 'slew(2*V(u,r)')
        a, b = execute(internal), execute(direct)
        for node in ('dut:d', 'y'):
            self.assertEqual(values(a,node), values(b,node))
        c = execute(internal, times=[i/8 for i in range(65)], step=.125)
        for t, y, d in zip(c['transient']['times'], values(c,'y'), values(c,'dut:d')):
            self.assertAlmostEqual(y, min(t,4), delta=1e-12)
            self.assertAlmostEqual(d, 2*min(max(t-1,0),2), delta=1e-12)

    def test_history_feedback_and_state_dependence_remain_explicit(self):
        for call in ('absdelay', 'slew'):
            args = '1' if call == 'absdelay' else '1,-2'
            for body in (f'V(y,r)<+{call}(V(y,r),{args});',
                         (f'V(z,r)<+{call}(V(u,r),{args}); V(y,r)<+absdelay(absdelay(V(z,r),1),1);' if call == 'absdelay' else f'V(z,r)<+{call}(V(u,r),{args}); V(y,r)<+{call}(V(z,r),{args});')):
                with self.subTest(body=body), self.assertRaises(KernelError):
                    execute(body)

    def test_cancelled_and_zero_internal_references_have_a_valid_projection(self):
        for call in ('absdelay', 'slew'):
            args = '0' if call == 'absdelay' else '10,-10'
            for expression in ('V(z,r)', '0*V(z,r)+V(u,r)',
                               'V(z,r)-V(z,r)+V(u,r)', 'V(z,z)+V(u,r)'):
                body = f'V(z,r)<+V(u,r); V(y,r)<+{call}({expression},{args});'
                with self.subTest(call=call, expression=expression):
                    result = execute(body)
                    self.assertEqual(values(result,'y'), [0,1,2,2,2,2,2])

    def test_projection_uncertainty_is_not_replaced_by_small_equation_residual(self):
        source = model('''V(z,r)<+((V(u,r)+1e-16*V(u,r))-V(u,r))*1e16;
          V(y,r)<+absdelay(V(z,r),0);''', 'electrical z;')
        program = compile_sources({'projection-error.va':source}, [instance()])
        # Original IR coefficient is about one. Rounded assembly may give zero;
        # a zero residual cannot establish a 1e-12 V output error budget.
        with self.assertRaises(KernelError):
            transient(program, {'u':[[0,1],[1,1]]}, [0,1], stop=1, max_step=1,
                      vabstol=1e-12, reltol=0, kernel=KERNEL)


if __name__ == '__main__':
    unittest.main()
