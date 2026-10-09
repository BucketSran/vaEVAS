"""Checker calibration with hand answers; no simulator needed."""
import math
import unittest

from ngspice_compare import (
    Affine, CompileError, EVAS, Instance, Power, TIMER_SOURCE, Unsupported, compare, compile_sources,
    expression, generated, interpolate, parse_manifest, relations,
)


class DifferentialCalibration(unittest.TestCase):
    def test_voltage_budget_accepts_boundary_and_rejects_perturbation(self):
        self.assertEqual(compare([0.0], [1e-12], relative=0), 1.0)
        self.assertGreater(compare([0.0], [1.01e-12], relative=0), 1.0)
        self.assertEqual(compare([-2.0, 0.25], [-2.0, 0.25]), 0.0)

    def test_shape_and_nonfinite_cannot_pass(self):
        for a, b in [([], []), ([0], [0, 1]), ([math.nan], [0]), ([0], [math.inf])]:
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                compare(a, b)

    def test_piecewise_interpolation_has_no_extrapolation(self):
        rows = [[0.0, 1.0], [0.25, 2.0], [1.0, -1.0]]
        self.assertEqual(interpolate(rows, .125), [0, 1.5])
        self.assertEqual(interpolate(rows, .5), [0, 1.0])
        self.assertEqual(interpolate(rows, 1), [0, -1.0])
        for time in [-.1, 1.1]:
            with self.assertRaises(ValueError):
                interpolate(rows, time)
        with self.assertRaises(ValueError):
            interpolate([[0, 0], [0, 1]], 0)

    def test_negative_integer_power_uses_polynomial_multiplication(self):
        text = expression(Power(Affine(-2.0, ()), 3))
        self.assertNotIn('^', text)
        self.assertEqual(eval(text, {'__builtins__': {}}), -8.0)

    def test_contributions_sum_within_branch(self):
        source = '`include "disciplines.vams"\nmodule m(y,r); output y; inout r; electrical y,r; analog begin V(y,r)<+1; V(y,r)<+2; end endmodule'
        program = compile_sources({'m.va': source}, [Instance('d', 'm', {'y':'y', 'r':'0'})])
        lines = relations(program, [])
        self.assertEqual(len(lines), 1)
        voltage = eval(lines[0].split('{', 1)[1].split('}', 1)[0], {'__builtins__': {}})
        orientation = 1 if program.contributions[0].positive else -1
        self.assertEqual(orientation * voltage, 3.0)

    def test_exporter_rejects_two_independent_ideal_sources_on_same_node(self):
        source = '`include "disciplines.vams"\nmodule m(y,r); output y; inout r; electrical y,r; analog begin V(y,r)<+1; end endmodule'
        program = compile_sources({'m.va': source}, [Instance(n, 'm', {'y':'y', 'r':'0'}) for n in ['a', 'b']])
        with self.assertRaises(Unsupported):
            relations(program, [])

    def test_original_smoke_admission_outcomes_remain_explicit(self):
        rejected = {'absdelay':'not declared', 'timer_counter':'not declared', 'cross_counter':'real literal'}
        paths = sorted((EVAS/'validation/smoke').glob('*.json'))
        self.assertEqual(len(paths), 6)
        for path in paths:
            with self.subTest(case=path.stem):
                manifest = parse_manifest(path.read_text())
                sources = {str((path.parent/n).resolve()):(path.parent/n).read_text() for n in manifest['models']}
                instances = [Instance(**row) for row in manifest['instances']]
                if path.stem in rejected:
                    with self.assertRaisesRegex(CompileError, rejected[path.stem]):
                        compile_sources(sources, instances)
                else:
                    compile_sources(sources, instances)

    def test_actual_suite_sources_reach_their_intended_export_paths(self):
        for size in (1, 4, 16, 64):
            with self.subTest(size=size):
                program, roots, source = generated(size, 20261003+size)
                self.assertEqual(len(roots), size)
                self.assertEqual(len(relations(program, ['u'])), size)
        timer = compile_sources({'timer-reference.va': TIMER_SOURCE},
                                [Instance('dut','timer_count',{'y':'y','r':'0'})])
        with self.assertRaisesRegex(Unsupported, 'state, event and operator'):
            relations(timer, [])

    def test_generated_cases_are_deterministic(self):
        first = generated(4, 31)
        second = generated(4, 31)
        self.assertEqual(first, second)
        self.assertEqual(len(relations(first[0], ['u'])), 4)


if __name__ == '__main__':
    unittest.main()
