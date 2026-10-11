"""Independent CDS values and legal repeated-signal fixture coverage."""
import copy
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / 'benchmark/tasks/v2-spec-308-correlated-double-sampler-offset-cancel'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seconds(token):
    match = re.fullmatch(r'([\d.eE+-]+)([np]?)', token)
    return float(match[1]) * {'': 1., 'n': 1e-9, 'p': 1e-12}[match[2]]


def pwl(netlist, name):
    body = re.search(r'^V' + name + r' .*?wave=\[([^]]+)\]', netlist, re.M)[1].split()
    return [(seconds(body[i]), float(body[i + 1])) for i in range(0, len(body), 2)]


def value(points, t):
    for (a, x), (b, y) in zip(points, points[1:]):
        if a <= t <= b:
            return x + (y - x) * (t - a) / (b - a)
    return points[-1][1]


class RepeatedSignalTests(unittest.TestCase):
    def test_independent_literal_difference_updates_twice(self):
        # Reset=.4, then signal=.5 and .6: independently known .55 -> .65.
        rows = []
        ramp = lambda t, start, a, b: a + (b - a) * max(0., min(1., (t - start) / 20e-12))
        for i in range(2501):
            t = i * 2e-12
            clk = 0.
            for start in (1e-9, 2e-9, 3e-9):
                if start <= t < start + .2e-9:
                    clk = ramp(t, start, 0., .9)
                elif start + .2e-9 <= t < start + .22e-9:
                    clk = ramp(t, start + .2e-9, .9, 0.)
            vin = .4 if t < 1.5e-9 else .5 if t < 2.5e-9 else .6
            out = .45
            if t >= 2.01e-9:
                out = ramp(t, 2.01e-9, .45, .55)
            if t >= 3.01e-9:
                out = ramp(t, 3.01e-9, .55, .65)
            rows.append(dict(time=t, clk=clk, rst=0., vin=vin,
                             sample_reset=.9 if t < 1.5e-9 else 0.,
                             sample_signal=.9 if t > 1.5e-9 else 0.,
                             vout=out, offset_dbg=ramp(t, 2.01e-9, 0., .4),
                             valid=ramp(t, 2.01e-9, 0., .9)))
        case = dict(source_id='308', stop=5e-9, resolution=2e-12,
                    signals=list(rows[0].keys() - {'time'}), params={'tr': 20e-12})
        checker = load('cds_checker', ROOT / 'benchmark/checkers/v2_spec.py')
        self.assertTrue(checker.evaluate(rows, case, ROOT)['passed'])
        stale = copy.deepcopy(rows)
        for row in stale:
            if row['time'] >= 3.01e-9:
                row['vout'] = .55
        verdict = checker.evaluate(stale, case, ROOT)
        self.assertFalse(verdict['passed'])
        self.assertTrue(any(f['node'] == 'vout' and abs(f['expected'] - .65) < 1e-12
                            for f in verdict['failures']))

    def test_private_fixture_has_two_legal_signal_samples(self):
        case = next(c for c in json.loads((TASK / 'tests/cases.json').read_text())
                    if c['name'] == 'contract-stretched-input')
        netlist = case['netlist']
        clock = re.search(r'^Vclk .*$', netlist, re.M)[0]
        fields = dict(re.findall(r'(period|delay|rise)=([\d.]+[np])', clock))
        crossings = [seconds(fields['delay']) + k * seconds(fields['period'])
                     + seconds(fields['rise']) / 2 for k in range(4)]
        self.assertAlmostEqual(crossings[3], 21.432e-9, delta=1e-18)
        reset, signal, vin = (pwl(netlist, n) for n in ('sample_reset', 'sample_signal', 'vin'))
        rst = pwl(netlist, 'rst')
        reset_time = crossings[1]
        signal_times = [t for t in crossings if t > reset_time
                        and value(signal, t) > .45 and value(rst, t) < .45]
        self.assertEqual(len(signal_times), 2)
        self.assertGreater(value(reset, reset_time), .45)
        for t in signal_times:
            self.assertLess(value(reset, t), .45)
        # The extended window never overlaps reset acquisition or reset.
        breaks = sorted({t for points in (reset, signal, rst) for t, _ in points})
        for a, b in zip(breaks, breaks[1:]):
            t = (a + b) / 2
            if value(signal, t) > .45:
                self.assertLess(value(reset, t), .45)
                self.assertLess(value(rst, t), .45)
        self.assertGreater(value(vin, signal_times[1]) - value(vin, signal_times[0]), .03)
        for t in signal_times:
            target = .45 + value(vin, t) - value(vin, reset_time)
            self.assertGreater(target, 0.)
            self.assertLess(target, .9)
        # Ensure the fixture patch survives regeneration and a second pass.
        builder = load('cds_builder', Path(__file__).with_name('build_structure.py'))
        current = json.loads((TASK / 'tests/cases.json').read_text())
        self.assertEqual(builder.build_cases(TASK, '308'), current)
        self.assertEqual(builder.build_cases(TASK, '308'), current)


if __name__ == '__main__':
    unittest.main()
