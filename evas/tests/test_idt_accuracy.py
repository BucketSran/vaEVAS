"""Binary64-source rational references; no sampled numerical-integration oracle."""
from fractions import Fraction as F
import json
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model
from test_idt import compiled, execute, integral, values


class IdtAccuracy(unittest.TestCase):
    def test_history_intervals_enclose_exact_rational_integrals(self):
        # Exercise the real Rust history module; only its Error transport is
        # stubbed. Expected integrals come from Fraction on original source bits.
        root = Path(__file__).resolve().parents[1]/'rust_core/src'
        harness = '''#[allow(dead_code)]
mod ir {
    #[derive(Debug)] pub struct Error;
    impl Error { pub fn new(_: &str, _: impl Into<String>) -> Self { Self } }
}
#[allow(dead_code)] #[path=INTERVAL] mod interval;
#[allow(dead_code)] #[path=IDT] mod idt;
use interval::Interval as I;
use std::io::{self, BufRead};
fn main() {
    for line in io::stdin().lock().lines() {
        let x: Vec<f64> = line.unwrap().split_whitespace()
            .map(|s| f64::from_bits(s.parse().unwrap())).collect();
        let points: Vec<_> = x[..6].chunks(2).map(|p| (p[0], p[1])).collect();
        let bounds = points.iter().map(|p| I::point(p.1)).collect();
        let history = idt::Idt::enclosed(points, bounds, x[6]).unwrap();
        let b = history.value_bounds(x[7]).unwrap();
        println!("{} {}", b.lo.to_bits(), b.hi.to_bits());
    }
}'''.replace('INTERVAL', json.dumps(str(root/'interval.rs'))).replace('IDT', json.dumps(str(root/'idt.rs')))
        rng = random.Random(29092026)
        cases = []
        for _ in range(128):
            ts, us = 2.0**rng.randrange(-200, 201), 2.0**rng.randrange(-200, 201)
            end = rng.randrange(2, 17)*ts
            points = [(0., rng.uniform(-2, 2)*us), (end/2, rng.uniform(-2, 2)*us),
                      (end, rng.uniform(-2, 2)*us)]
            ic = rng.uniform(-1, 1)*us*ts
            for t in [0., end/8, end/2, end*7/8, end]:
                cases.append((points, ic, t))
        for u in [2.0**-1074, 1e-308, -2.0**-1074]:
            for t in [.5, 1., 2.]:
                cases.append(([(0., u), (1., u), (2., -u)], 0., t))
        def encode(x): return struct.unpack('>Q', struct.pack('>d', x))[0]
        def decode(x): return struct.unpack('>d', struct.pack('>Q', x))[0]
        with tempfile.TemporaryDirectory() as directory:
            source, binary = Path(directory)/'integral.rs', Path(directory)/'integral'
            source.write_text(harness)
            subprocess.run(['rustc', '--edition=2021', str(source), '-o', str(binary)],
                           check=True, capture_output=True, text=True)
            rows = [list(v for point in points for v in point)+[ic, t] for points, ic, t in cases]
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True,
                                    input=''.join(' '.join(str(encode(v)) for v in row)+'\n' for row in rows))
        bounds = result.stdout.splitlines()
        self.assertEqual(len(bounds), len(cases))
        for (points, ic, t), line in zip(cases, bounds):
            lo, hi = (decode(int(v)) for v in line.split())
            expected = integral(points, t, ic)
            self.assertLessEqual(lo, expected, (points, ic, t, lo, hi))
            self.assertGreaterEqual(hi, expected, (points, ic, t, lo, hi))

    def test_reset_release_interval_encloses_uncertain_zero_knot_and_rounded_zero(self):
        root = Path(__file__).resolve().parents[1]/'rust_core/src'
        harness = '''#[allow(dead_code)]
mod ir {
    #[derive(Debug)] pub struct Error;
    impl Error { pub fn new(_: &str, _: impl Into<String>) -> Self { Self } }
}
#[allow(dead_code)] #[path=INTERVAL] mod interval;
#[allow(dead_code)] #[path=IDT] mod idt;
use interval::Interval as I;
fn main() {
    let uncertain = idt::Idt::enclosed(
        vec![(0.0,0.25),(1.0,-0.75),(2.0,0.5),(3.0,-0.5)],
        vec![I{lo:0.25,hi:1.0}, I{lo:-1.0,hi:-0.75}, I{lo:0.25,hi:0.75}, I{lo:-0.75,hi:-0.25}],
        0.0).unwrap();
    let mut reset = uncertain.with_reset(true);
    reset.advance_reset(1.0, I{lo:0.45,hi:1.25}, false).unwrap();
    let b = reset.value_bounds(1.5).unwrap();
    println!("{} {}", b.lo.to_bits(), b.hi.to_bits());

    let rounded = idt::Idt::enclosed(
        vec![(0.0,1.0),(1.0,-2.0),(2.0,-2.0)],
        vec![I::point(1.0), I::point(-2.0), I::point(-2.0)],
        0.0).unwrap();
    let root = 1.0f64 / 3.0;
    let mut reset = rounded.with_reset(true);
    reset.advance_reset(root, I{lo:root.next_down(), hi:root.next_up()}, false).unwrap();
    let b = reset.value_bounds(0.75).unwrap();
    println!("{} {}", b.lo.to_bits(), b.hi.to_bits());
}'''.replace('INTERVAL', json.dumps(str(root/'interval.rs'))).replace('IDT', json.dumps(str(root/'idt.rs')))
        def decode(bits): return struct.unpack('>d', struct.pack('>Q', int(bits)))[0]
        with tempfile.TemporaryDirectory() as directory:
            source, binary = Path(directory)/'reset_integral.rs', Path(directory)/'reset_integral'
            source.write_text(harness)
            subprocess.run(['rustc', '--edition=2021', str(source), '-o', str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        rows = [[decode(x) for x in line.split()] for line in result.stdout.splitlines()]
        self.assertEqual(len(rows), 2)

        def exact(points, query, release):
            return integral(points, query) - integral(points, release)

        # Nonzero input bounds: a legal history has an interior input zero at
        # x=1/2 inside the reset uncertainty; another legal release at x=5/4
        # is across the source knot.  Both answers are independent Fractions.
        uncertain_expectations = [
            exact([(0, 1), (1, -1), (2, F(1, 4)), (3, F(-1, 4))], F(3, 2), F(1, 2)),
            exact([(0, F(1, 4)), (1, -1), (2, F(1, 4)), (3, F(-1, 4))], F(3, 2), F(5, 4)),
        ]
        for expected in uncertain_expectations:
            self.assertLessEqual(rows[0][0], expected)
            self.assertGreaterEqual(rows[0][1], expected)

        # The exact zero of u(t)=1-3t is x=1/3, which is not binary64.  The
        # release interval is the two neighboring floats around the rounded
        # representative; the bound must include the exact-root answer.
        rounded_expected = exact([(0, 1), (1, -2), (2, -2)], F(3, 4), F(1, 3))
        self.assertLessEqual(rows[1][0], rounded_expected)
        self.assertGreaterEqual(rows[1][1], rounded_expected)

    def test_fractional_integral_and_network_gain_require_history_budget(self):
        points = [[0, 0], [3, 1]]
        for body, gain in [('V(y,r)<+1073741824*idt(V(u,r),0);', 2**30),
                           ('V(y,r)<+.99999904632568359375*V(y,r)+idt(V(u,r),0);', 2**20)]:
            program = compiled(body)
            with self.subTest(gain=gain), self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
                execute(program, points, [0, 1, 3], vabstol=1e-12, reltol=0)
            result = execute(program, points, [0, 1, 3], vabstol=1e-5, reltol=0)
            self.assertLessEqual(abs(F(values(result)[1])-F(gain, 6)), F(1e-5))

    def test_source_interpolation_at_other_knots_retains_uncertainty(self):
        source = model('V(y,r)<+1073741824*idt(V(u,r)+0*V(v,r),0);',
                       ports='u,v,y,r', directions='input u,v; output y; inout r;')
        program = compile_sources({'idt.va': source}, [instance(connections=dict(u='u', v='v', y='y', r='0'))])
        sources = {'u': [[0, 0], [3, 1]], 'v': [[0, 0], [1, 0], [2, 0], [3, 0]]}
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            transient(program, sources, [0, 1, 2, 3], stop=3, max_step=3,
                      vabstol=1e-10, reltol=0, kernel=KERNEL)
        result = transient(program, sources, [0, 1, 2, 3], stop=3, max_step=3,
                           vabstol=1e-5, reltol=0, kernel=KERNEL)
        for t, actual in zip([0, 1, 2, 3], values(result)):
            self.assertLessEqual(abs(F(actual)-F(2**30*t*t, 6)), F(1e-5))

    def test_affine_arithmetic_and_prior_segments_are_not_reset_to_points(self):
        program = compiled('V(y,r)<+idt(.1*V(u,r)+.2*V(u,r),.1);')
        points = [[0, 1], [1, 1], [2, 1], [3, 1]]
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(program, points, [0, 1, 2, 3], vabstol=1e-18, reltol=0)
        result = execute(program, points, [0, 1, 2, 3], vabstol=1e-12, reltol=0)
        for t, actual in zip([0, 1, 2, 3], values(result)):
            self.assertLessEqual(abs(F(actual)-(F(.1)+(F(.1)+F(.2))*t)), F(1e-12))

    def test_large_absolute_time_and_small_physical_time_use_local_offsets(self):
        for scale in [F(1), F(1, 2**40)]:
            for origin in [0, 2**54]:
                points = ([[0, 0]] if origin else []) + [
                    [float((origin+h)*scale), float(F(u)/scale)] for h, u in [(0, 0), (8, 4), (16, 4)]]
                times = [float((origin+h)*scale) for h in [0, 4, 8, 12, 16]]
                result = execute(compiled('V(y,r)<+idt(V(u,r),1);'), points, times,
                                 step=points[-1][0], vabstol=1e-12, reltol=0)
                self.assertEqual(values(result), [1, 5, 17, 33, 49])
                for t, actual in zip(times, values(result)):
                    self.assertEqual(F(actual), integral(points, t, 1))

    def test_rational_multisegment_accumulation_and_reflection(self):
        points = [[i/8, ((i*17) % 23-11)/10] for i in range(129)]
        times = [i/16 for i in range(257)]
        for sign in [1, -1]:
            source = [[t, sign*u] for t, u in points]
            result = execute(compiled(f'V(y,r)<+idt(V(u,r),{sign*.125});'), source, times,
                             vabstol=1e-10, reltol=0)
            for t, actual in zip(times, values(result)):
                self.assertLessEqual(abs(F(actual)-integral(source, t, sign*.125)), F(1e-10))

    def test_sampled_integral_error_survives_later_event(self):
        body = ('@(initial_step) begin b=0; c=0; end '
                '@(timer(1,0,.001)) b=V(z,r); '
                '@(timer(2,0,.001)) c=1073741824*V(w,r)-178956970.66666666+1; '
                'V(z,r)<+idt(V(u,r),0); V(w,r)<+b; V(y,r)<+c;')
        program = compiled(body, 'real b,c; electrical z,w;')
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(program, [[0, 0], [3, 1]], [0, 1, 2, 3], vabstol=1e-9, reltol=1e-9)
        result = execute(program, [[0, 0], [3, 1]], [0, 1, 2, 3], vabstol=1e-5, reltol=1e-5)
        exact = F(2**30, 6)-F(178956970.66666666)+1
        self.assertLessEqual(abs(F(values(result)[2])-exact), F(1e-5))

    def test_nonfinite_area_rejects_and_fresh_retry_is_clean(self):
        program = compiled('V(y,r)<+idt(V(u,r),0);')
        for _ in range(2):
            with self.assertRaises(KernelError) as error:
                execute(program, [[0, 1e308], [8, 1e308]], [0, 8])
            self.assertIn(error.exception.detail['kind'], ['numerical_failure', 'waveform_accuracy'])
        result = execute(program, [[0, 1], [8, 1]], [0, 8])
        self.assertEqual(values(result), [0, 8])


if __name__ == '__main__':
    unittest.main()
