"""One output-point limit (1,000,000) shared by the SCS adapter, strobe expansion and response check.

Every boundary is stated with an independent point-count formula, never by calling
the function under test:
  * output grid {k*maxstep < stop} U {stop}: the adapter admits a request while
    floor(stop/maxstep) + 2 <= limit (a conservative bound: an exactly divisible
    stop/maxstep needs only floor(stop/maxstep) + 1 rows);
  * periodic strobe: floor((end - start - delay)/period) + 1 forced points;
  * union of sets: the size of the set union.
Large exact-limit acceptances build 10^6 points and run once; fine boundaries for
the checkpoints whose accepted side is expensive at 10^6 use a small patched limit
so cap-1, cap and cap+1 are all exercised on the same code path.
"""
GUARDS = ["DEV:scs-input", "DYNAMICS"]

from decimal import Decimal, getcontext
from fractions import Fraction as F
import json
import math
from pathlib import Path
import re
import resource
import tempfile
import time
import unittest
from unittest.mock import patch

from evas import CompileError, KernelError, compile_sources
from evas import limits, protocol, scs, scs_sources, strobe
from evas.runtime import _invoke
from evas.scs import load_scs, simulate_scs
from test_affine import EVAS, KERNEL, instance, model

CAP = 1_000_000
STEP = 2.0 ** -20


def decimal(x):
    """Exact decimal text of a binary64 (scientific notation avoided)."""
    return format(Decimal(x), 'f')


class OutputPointLimitConstants(unittest.TestCase):
    def test_python_symbols_are_the_one_named_limit(self):
        self.assertEqual(limits.MAX_OUTPUT_POINTS, 1_000_000)  # literal, not self-referential
        self.assertIs(scs_sources.POINT_BUDGET, limits.MAX_OUTPUT_POINTS)
        self.assertIs(scs.POINT_BUDGET, limits.MAX_OUTPUT_POINTS)
        self.assertIs(strobe.MAX_POINTS, limits.MAX_OUTPUT_POINTS)

    def test_no_stray_hundred_thousand_remains_at_the_eight_checkpoints(self):
        src = EVAS / 'src/evas'
        for name in ('scs_sources.py', 'strobe.py', 'protocol.py'):
            text = (src / name).read_text()
            self.assertNotRegex(text, r'100_?000\b', name)
        # scs.py keeps only the unrelated netlist token budget (its test and message).
        stray = [line.strip() for line in (src / 'scs.py').read_text().splitlines()
                 if re.search(r'100_?000\b', line)]
        self.assertEqual(stray, ['if count>100_000:', "_fail('netlist token budget (100000) exceeded',token)"])

    def test_rust_constant_has_the_same_value_and_guards_the_kernel_check(self):
        ir = (EVAS / 'rust_core/ir/src/lib.rs').read_text()
        rust = re.search(r'pub const MAX_OUTPUT_POINTS: usize = ([0-9_]+);', ir)
        self.assertIsNotNone(rust)
        self.assertEqual(int(rust.group(1).replace('_', '')), limits.MAX_OUTPUT_POINTS)
        kernel = (EVAS / 'rust_core/src/pwl.rs').read_text()
        self.assertIn('config.strobetimes.len() > crate::ir::MAX_OUTPUT_POINTS', kernel)
        self.assertNotIn('strobetimes.len() > 100_000', kernel)


class ScsGridCheckpoint(unittest.TestCase):
    """scs.py: grid count (checkpoint 1) at the real limit."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'm.va').write_text(model('V(y,r)<+2*V(u,r);'))
        self.path = self.root / 'tb.scs'

    def deck(self, c, extra=''):
        stop = c * STEP
        self.path.write_text('simulator lang=spectre\nglobal 0\nahdl_include "m.va"\n'
                             f'Vin (u 0) vsource dc=1\nDUT (u y 0) m\n'
                             f'tran tran stop={decimal(stop)} maxstep={decimal(STEP)}{extra}\nsave y\n')
        return stop

    def test_grid_is_admitted_exactly_while_floor_ratio_plus_two_fits(self):
        for c in (CAP - 2, CAP - 1, CAP, CAP + 1):
            with self.subTest(floor_ratio=c):
                stop = self.deck(c)
                self.assertEqual(F(stop) // F(STEP), c)  # independent: floor(stop/maxstep)
                if c + 2 <= CAP:
                    times = load_scs(self.path).manifest['transient']['output_times']
                    # stop/maxstep is an exact integer c: rows k*maxstep (k<c) plus stop.
                    self.assertEqual(len(times), c + 1)
                    self.assertEqual((times[0], times[-1]), (0, stop))
                else:
                    with self.assertRaisesRegex(CompileError,
                            r'output point budget \(1000000\) exceeded; increase maxstep'):
                        load_scs(self.path)

    def test_the_previous_hundred_thousand_rows_are_no_longer_rejected(self):
        for c in (99_998, 99_999, 100_000, 100_001):
            with self.subTest(floor_ratio=c):
                self.deck(c)
                self.assertEqual(len(load_scs(self.path).manifest['transient']['output_times']), c + 1)

    def test_message_names_the_enforced_limit(self):
        with patch('evas.scs.POINT_BUDGET', 7):
            self.deck(6)
            with self.assertRaisesRegex(CompileError, r'output point budget \(7\) exceeded; increase maxstep'):
                load_scs(self.path)


class ScsCornerAndSavedCheckpoints(unittest.TestCase):
    """scs.py checkpoints 2 and 3 with a small patched limit: cap-1, cap, cap+1."""
    LIMIT = 12

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'm.va').write_text(model('V(y,r)<+2*V(u,r);'))
        self.path = self.root / 'tb.scs'

    def deck(self, corners=0, strobes=0):
        # Grid {0,.25,.5,.75,1}: 5 rows. Odd sixteenths are never grid rows.
        odd = [f'{(2 * i + 1) / 16:g}' for i in range(corners)]
        wave = '0 0 ' + ' '.join(f'{t} 1' for t in odd) + ' 1 0'
        tran = 'tran tran stop=1 maxstep=.25'
        if strobes:
            points = ' '.join(f'{(2 * i + 1) / 32:g}' for i in range(strobes))
            tran += f' strobetimes=[{points}] strobeoutput=all'
        self.path.write_text('simulator lang=spectre\nglobal 0\nahdl_include "m.va"\n'
                             f'Vin (u 0) vsource type=pwl wave=[{wave}]\nDUT (u y 0) m\n{tran}\nsave y\n')

    def test_rows_after_including_source_corners(self):
        for corners in (6, 7, 8):
            rows = 5 + corners  # independent union size: 5 grid rows + distinct odd-sixteenth corners
            with self.subTest(rows=rows), patch('evas.scs.POINT_BUDGET', self.LIMIT):
                self.deck(corners=corners)
                if rows <= self.LIMIT:
                    self.assertEqual(len(load_scs(self.path).manifest['transient']['output_times']), rows)
                else:
                    with self.assertRaisesRegex(CompileError, r'output point budget \(12\) exceeded after including source corners'):
                        load_scs(self.path)

    def test_saved_rows_with_forced_points(self):
        for strobes in (6, 7, 8):
            rows = 5 + strobes  # grid rows + distinct odd-thirty-seconds forced points
            with self.subTest(rows=rows), patch('evas.scs.POINT_BUDGET', self.LIMIT):
                self.deck(strobes=strobes)
                if rows <= self.LIMIT:
                    self.assertEqual(len(load_scs(self.path).metadata['saved_output_times']), rows)
                else:
                    with self.assertRaisesRegex(CompileError, r'saved output point budget \(12\) exceeded'):
                        load_scs(self.path)


class PulseCornerCheckpoint(unittest.TestCase):
    """scs_sources.py: 4*periods+2 corners must fit the limit."""

    def points(self, periods, limit):
        settings = dict(type='pulse', val0=0., val1=1., delay=0., rise=.0625, width=.0625,
                        fall=.0625, period=.25)
        stop = (periods - 1) * .25  # floor((stop-delay)/period)+1 == periods
        messages = []

        def fail(message, **kwargs):
            messages.append(message)
            raise CompileError(message)
        with patch('evas.scs_sources.POINT_BUDGET', limit):
            try:
                points, _, _ = scs_sources.voltage_points(settings, stop, fail)
            except CompileError:
                return None, messages
        return points, messages

    def test_corner_count_cap_minus_one_cap_and_cap_plus_one(self):
        # corners = 4*periods + 2 (independent): 22, 26, 30 against limits 25, 26.
        for periods, limit, accepted in [(5, 25, True), (6, 25, False), (6, 26, True), (7, 26, False)]:
            with self.subTest(periods=periods, limit=limit):
                points, messages = self.points(periods, limit)
                self.assertEqual(points is not None, accepted)
                self.assertEqual(4 * periods + 2 <= limit, accepted)
                if not accepted:
                    self.assertEqual(messages, [f'pulse point budget ({limit}) exceeded'])

    def test_real_limit_rejects_before_building_a_million_corners(self):
        # 250000 periods -> 1,000,002 corners > 1,000,000; the check precedes the loop.
        points, messages = self.points(250_000, CAP)
        self.assertIsNone(points)
        self.assertEqual(messages, ['pulse point budget (1000000) exceeded'])


class StrobeCheckpoints(unittest.TestCase):
    """strobe.py: explicit, periodic and union counts at the real limit."""

    def test_explicit_count(self):
        ok = [k / (CAP + 1) for k in range(1, CAP + 1)]
        self.assertEqual(len(ok), CAP)
        self.assertEqual(len(strobe.expand(1.0, strobetimes=ok)), CAP)
        with self.assertRaisesRegex(ValueError, r'at most 1000000 points'):
            strobe.expand(1.0, strobetimes=ok + [1.0])

    def test_periodic_count(self):
        # first=0, points at k*2^-20 up to end: floor(end/period)+1 (independent).
        for last, accepted in [(CAP - 1, True), (CAP, False)]:
            end = last * STEP
            self.assertEqual(int(F(end) // F(STEP)) + 1, last + 1)
            with self.subTest(points=last + 1):
                if accepted:
                    self.assertEqual(len(strobe.expand(1.0, strobeperiod=STEP, skipstop=end)), CAP)
                else:
                    with self.assertRaisesRegex(ValueError, r'periodic strobe exceeds 1000000 points'):
                        strobe.expand(1.0, strobeperiod=STEP, skipstop=end)

    def test_union_count(self):
        periodic = 600_000
        end = (periodic - 1) * STEP
        # Explicit points on odd multiples of 2^-21 never coincide with periodic ones.
        for extra, accepted in [(400_000, True), (400_001, False)]:
            explicit = [(2 * k + 1) * STEP / 2 for k in range(extra)]
            union = periodic + extra  # disjoint sets
            self.assertEqual(union <= CAP, accepted)
            with self.subTest(union=union):
                if accepted:
                    self.assertEqual(len(strobe.expand(1.0, strobetimes=explicit, strobeperiod=STEP,
                                                       skipstop=end)), union)
                else:
                    with self.assertRaisesRegex(ValueError, r'combined strobe exceeds 1000000 points'):
                        strobe.expand(1.0, strobetimes=explicit, strobeperiod=STEP, skipstop=end)

    def test_patched_symbol_changes_the_enforced_limit_and_message(self):
        with patch('evas.strobe.MAX_POINTS', 3):
            self.assertEqual(len(strobe.expand(1.0, strobetimes=[.25, .5, .75])), 3)
            with self.assertRaisesRegex(ValueError, r'at most 3 points'):
                strobe.expand(1.0, strobetimes=[.25, .5, .75, 1.0])


class ResponseEvidenceCheckpoint(unittest.TestCase):
    """protocol.py: strobe_evidence.times length at the real limit."""

    @classmethod
    def setUpClass(cls):
        cls.program = compile_sources({'p.va': model('V(y,r)<+V(u,r);')}, [instance()])
        cls.base = _invoke(dict(program=cls.program.to_dict(), driven=['u'], samples=[],
                                transient=dict(pwl=[[[0, 0], [1, 1]]], output_times=[0, 1], stop=1,
                                               max_step=1, strobetimes=[.5])), KERNEL)

    def response(self, count):
        response = json.loads(json.dumps(self.base))
        nodes = len(response['nodes'])
        row = [0.0] * nodes
        response['strobe_evidence'] = dict(
            schema_version=1, times=[k / (count + 1) for k in range(1, count + 1)],
            sample_origins=['stateless_working_point'] * count, voltages_V=[row] * count)
        return response

    def test_times_length_cap_minus_one_cap_and_cap_plus_one(self):
        for count in (CAP - 1, CAP, CAP + 1):
            with self.subTest(count=count):
                response = self.response(count)
                if count <= CAP:
                    protocol.validate_response(response, self.program, 2, [0, 1], strobetimes=None)
                else:
                    with self.assertRaisesRegex(KernelError, 'invalid strobe execution evidence'):
                        protocol.validate_response(response, self.program, 2, [0, 1], strobetimes=None)


class KernelCheckpoint(unittest.TestCase):
    def test_kernel_rejects_one_more_than_the_limit_of_forced_points(self):
        program = compile_sources({'p.va': model('V(y,r)<+V(u,r);')}, [instance()])
        points = [k / (CAP + 2) for k in range(1, CAP + 2)]
        self.assertEqual(len(points), CAP + 1)
        request = dict(program=program.to_dict(), driven=['u'], samples=[],
                       transient=dict(pwl=[[[0, 0], [1, 1]]], output_times=[0, 1], stop=1,
                                      max_step=1, strobetimes=points))
        with self.assertRaises(KernelError) as caught:
            _invoke(request, KERNEL, 120)
        self.assertEqual(caught.exception.detail['kind'], 'invalid_inputs')


class LargeGridEndToEnd(unittest.TestCase):
    """More than the former 100000 rows through the actual adapter and kernel.

    The default test is a stateless gain y = 3*u driven by a triangle PWL, whose
    closed form is exact piecewise-linear arithmetic (Fractions). A first-order
    RC (y' = 1 - y from 0, y(t) = 1 - exp(-t), Decimal at 50 digits) is the
    dynamic variant; it needs the proof work limit raised and, with the debug
    kernel, minutes, so it is an explicit check that discovery does not collect
    (CI records no skip). Run it by name with EVAS_TEST_KERNEL naming a release
    kernel:
      python3 -B -m unittest test_output_point_limit.LargeGridEndToEnd.check_rc_step_response_over_a_hundred_thousand_rows
    """
    ROWS = 120_000
    TIMEOUT = 900

    def run_deck(self, body, source, rows=None, **options):
        rows = rows or self.ROWS
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'm.va').write_text(model(body))
            stop = rows * STEP
            (root / 'tb.scs').write_text(
                'simulator lang=spectre\nglobal 0\nahdl_include "m.va"\n'
                f'{source}\nDUT (u y 0) m\n'
                f'tran tran stop={decimal(stop)} maxstep={decimal(STEP)}\nsave y u\n')
            started = time.monotonic()
            result = simulate_scs(root / 'tb.scs', kernel=KERNEL, timeout=self.TIMEOUT, **options)
            elapsed = time.monotonic() - started
        rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        print(f'large_grid rows={len(result["saved"]["times"])} seconds={elapsed:.1f} '
              f'children_maxrss_bytes={rss}')
        return result, stop

    def test_stateless_gain_over_a_hundred_thousand_rows_matches_the_closed_form(self):
        stop = self.ROWS * STEP
        half = stop / 2
        result, _ = self.run_deck(
            'V(y,r)<+3*V(u,r);',
            f'Vin (u 0) vsource type=pwl wave=[0 0 {decimal(half)} 1 {decimal(stop)} 0]')
        times, values = result['saved']['times'], result['saved']['values']
        self.assertGreater(len(times), 100_000)
        self.assertEqual(len(times), self.ROWS + 1)  # k*step (k<ROWS) plus stop; half is a grid row
        self.assertEqual(result['transient']['times'], times)
        for t, (y, u) in zip(times, values):
            ramp = F(t) / F(half) if t <= half else (F(stop) - F(t)) / F(half)
            self.assertLessEqual(abs(F(u) - ramp), F(1, 10**12), t)
            self.assertLessEqual(abs(F(y) - 3 * ramp), F(3, 10**12), t)

    def test_exceeding_the_new_limit_is_still_rejected_with_the_actual_constant(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'm.va').write_text(model('V(y,r)<+3*V(u,r);'))
            (root / 'tb.scs').write_text(
                'simulator lang=spectre\nglobal 0\nahdl_include "m.va"\nVin (u 0) vsource dc=1\n'
                f'DUT (u y 0) m\ntran tran stop=1 maxstep=1e-7\nsave y\n')  # 10^7 rows
            with self.assertRaisesRegex(CompileError, r'output point budget \(1000000\) exceeded'):
                load_scs(root / 'tb.scs')

    def check_rc_step_response_over_a_hundred_thousand_rows(self):
        result, stop = self.run_deck('V(y,r)<+idt(V(u,r)-V(y,r),0);', 'Vin (u 0) vsource dc=1',
                                     proof_work_limit=2_000_000_000_000)
        times, values = result['saved']['times'], result['saved']['values']
        self.assertEqual(len(times), self.ROWS + 1)
        getcontext().prec = 50
        worst = 0.0
        for t, (y, _) in list(zip(times, values))[::997] + [(times[-1], values[-1])]:
            worst = max(worst, abs(float(Decimal(y) - (1 - (-Decimal(t)).exp()))))
        self.assertLess(worst, 1e-9)


if __name__ == '__main__':
    unittest.main()
