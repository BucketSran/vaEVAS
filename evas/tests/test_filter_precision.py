"""Tight filter certification, checked against an independent Decimal ODE."""
# Guarded conditions/capabilities: see docs/development/TRACEABILITY.md
GUARDS = ["DEV:filter-precision", "DYNAMICS"]

from decimal import Decimal, localcontext
import subprocess
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import EVAS, KERNEL, instance, model


def reference(points, time, initial):
    with localcontext() as ctx:
        ctx.prec = 90
        tau = Decimal.from_float(1e-6)
        y = Decimal.from_float(initial)
        t = Decimal.from_float(time)
        for (a, u), (b, v) in zip(points, points[1:]):
            a, u, b, v = map(Decimal.from_float, (a, u, b, v))
            if t <= a:
                break
            h = min(t, b) - a
            slope = (v-u)/(b-a)
            y = u + slope*(h-tau) + (y-u+slope*tau)*(-h/tau).exp()
            if t <= b:
                break
        return y


class TightFilterPrecision(unittest.TestCase):
    def run_filter(self, initial, integral, times, absolute=1e-14):
        points = [[0., initial], [1e-6, initial], [2e-6, 1.],
                  [4e-6, -.5], [4.9999999999999996e-6, .25], [8e-6, .25]]
        body = (f"V(y,r)<+idt((V(u,r)-V(y,r))/1e-6,{initial});" if integral else
                "V(y,r)<+laplace_nd(V(u,r),'{1},'{1,1e-6});")
        program = compile_sources({"precision.va": model(body)}, [instance()])
        result = transient(program, {"u": points}, times, stop=8e-6, max_step=8e-6,
                           kernel=KERNEL, vabstol=absolute, reltol=1e-10)
        node = result['nodes'].index('y')
        for t, solution, bounds in zip(times, result['solutions'],
                                       result['observation_evidence']['voltage_bounds_V']):
            y = solution['voltages'][node]
            expected = reference(points, t, initial)
            self.assertLessEqual(Decimal.from_float(bounds[node][0]), expected)
            self.assertLessEqual(expected, Decimal.from_float(bounds[node][1]))
            self.assertLessEqual(abs(Decimal.from_float(y)-expected),
                                 Decimal.from_float(absolute+1e-10*abs(y)))
        return [s['voltages'][node] for s in result['solutions']]

    def test_small_output_after_bipolar_history_certifies_without_relaxing_budget(self):
        for initial, integral, t in [(0., False, 4.130859374999995e-6),
                                     (.25, False, 4.178710937499984e-6),
                                     (0., True, 4.129882812499996e-6)]:
            with self.subTest(initial=initial, integral=integral):
                self.run_filter(initial, integral, [0.,t,8e-6])

    def test_extra_queries_preserve_history_and_certified_output(self):
        for integral in (False, True):
            with self.subTest(integral=integral):
                times = [0., 4.129882812499996e-6, 8e-6]
                sparse = self.run_filter(0., integral, times)
                dense_times = sorted(set(times + [i*1e-7 for i in range(80)]))
                dense = self.run_filter(0., integral, dense_times)
                self.assertEqual(sparse, [dense[dense_times.index(t)] for t in times])

    def test_polynomial_direct_filter_corner_keeps_q3_accuracy(self):
        # H(s)=(1+s*T)/(2+s*T), u=.5+x up to x=2 and 2.5
        # afterwards. Solving z'+2*z=u*u from DC z(0)=.125 gives
        # h=.5*x*x+x+.125 before the corner and 3.125+exp(-2*r)
        # afterwards. This oracle does not integrate the DUT recurrence.
        unit = 2.0 ** -20
        program = compile_sources({"precision.va": model(
            "V(y,r)<+laplace_nd(V(u,r)*V(u,r),'{1,9.5367431640625e-7},"
            "'{2,9.5367431640625e-7});")}, [instance()])
        times = [0., unit, 2*unit, 3*unit, 4*unit]
        # This 8192-step Q3 regression uses an explicitly built release
        # fixture: the debug kernel exceeds even a 600-second timeout.
        # Keep the original release-card 90-second execution budget.
        subprocess.run(["cargo", "build", "--locked", "--release", "--manifest-path",
                        str(EVAS / "rust_core/Cargo.toml")], check=True, timeout=300.)
        release_kernel = EVAS / "rust_core/target/release/evas-kernel"
        result = transient(program, {"u": [[0., .5], [2*unit, 2.5], [4*unit, 2.5]]},
                           times, strobetimes=times, stop=4*unit,
                           max_step=unit/2048, kernel=release_kernel,
                           vabstol=1e-14, reltol=1e-10, timeout=90.)
        node = result['nodes'].index('y')
        with localcontext() as ctx:
            ctx.prec = 90
            for t, solution, bounds in zip(times, result['solutions'],
                                           result['observation_evidence']['voltage_bounds_V']):
                x = Decimal.from_float(t)/Decimal.from_float(unit)
                expected = (x*x/2+x+Decimal('.125') if x <= 2 else
                            Decimal('3.125')+(-2*(x-2)).exp())
                value = solution['voltages'][node]
                self.assertLessEqual(Decimal.from_float(bounds[node][0]), expected)
                self.assertLessEqual(expected, Decimal.from_float(bounds[node][1]))
                self.assertLessEqual(abs(Decimal.from_float(value)-expected),
                                     Decimal.from_float(1e-14+1e-10*abs(value)))

    def test_unrepresentable_accuracy_still_refuses(self):
        with self.assertRaises(KernelError) as caught:
            # The valid positive budget is far below binary64 resolution.
            program=compile_sources({'precision.va':model("V(y,r)<+laplace_nd(V(u,r),'{1},'{1,1});")},[instance()])
            transient(program, {'u':[[0.,0.],[1.,1.]]}, [.5],stop=1.,max_step=1.,
                      kernel=KERNEL,vabstol=1e-30,reltol=0.)
        self.assertEqual(caught.exception.detail['kind'], 'waveform_accuracy')


if __name__ == '__main__':
    unittest.main()
