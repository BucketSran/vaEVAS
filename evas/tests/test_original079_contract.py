"""Unchanged 079 source: jointly verify guard history and wrapped phase.

These are independent consumer contracts, not the frozen benchmark checker.
Nanosecond parameter controls and binary-scaled parameter controls use the
same source bytes. No continuous numerical Transition target is introduced.
"""
GUARDS = ['LANG', 'TIMER', 'EVENT-ORDER', 'TRANSITION', 'COMPOSE', 'DYNAMICS']

from contextlib import nullcontext
from fractions import Fraction as F
import json
import os
from pathlib import Path
import tempfile
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient
from evas.runtime import _invoke

REPOSITORY = Path(__file__).resolve().parents[2]
FROZEN = REPOSITORY / 'benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/079-ramp-step-source'
SOURCE_PATH = FROZEN / 'evaluator/solution/bound_step_period_guard_ref.va'
KERNEL = Path(os.environ.get('EVAS_KERNEL', str(
    REPOSITORY / 'evas/rust_core/target/debug/evas-kernel')))


def program(*, canonical=False, pulse=None):
    parameters = (dict(period=8e-9, pulse_w=1.5e-9, points_per_period=16, tedge=40e-12)
                  if canonical else dict(period=8, pulse_w=1.5, points_per_period=16, tedge=.25))
    if pulse is not None:
        parameters['pulse_w'] = pulse
    return compile_sources({str(SOURCE_PATH): SOURCE_PATH.read_text()}, [Instance(
        'IDUT', 'bound_step_period_guard_ref',
        dict(VDD='VDD', VSS='VSS', guard_out='guard_out', phase_out='phase_out'), parameters)])


def sources(stop, *, high=1, low=0, future_pulse=False):
    rail = [[0, high], [stop, high]]
    if future_pulse:
        rail = [[0, high], [stop*.6, high], [stop*.7, high+.25],
                [stop*.8, high], [stop, high]]
    return dict(VDD=rail, VSS=[[0, low], [stop, low]])


def run(p, times, *, canonical=False, future_pulse=False, errors=None):
    stop = 34e-9 if canonical else 34
    return transient(p, sources(stop, high=.9 if canonical else 1,
                                future_pulse=future_pulse), times,
                     stop=stop, max_step=20e-9 if canonical else 20,
                     source_errors=errors, vabstol=1e-12, reltol=0, kernel=KERNEL)


def oracle(time, *, period=F(8), width=F(3, 2), edge=F(1, 4), high=F(1)):
    """Independent linear Transition edges following a periodic 0/1 target.

    At t=0 the original target is already one and seeds the high rail. At later
    wraps the output retains zero and rises over edge. The <= pulse endpoint
    retains the old value; the following open interval starts the falling edge.
    """
    time = F(time)
    epoch = time // period
    phase = time - epoch * period
    phase_voltage = high * phase / period
    if width >= period:
        guard = F(1)
    elif phase <= width:
        guard = F(1) if epoch == 0 else min(F(1), phase / edge)
    else:
        guard = max(F(0), 1 - (phase - width) / edge)
    return high * guard, phase_voltage


class Original079Contract(unittest.TestCase):
    def assert_outputs(self, result, times, *, canonical=False, width=F(3, 2)):
        options = (dict(period=F(8, 10**9), width=F(3, 2*10**9),
                        edge=F(1, 25*10**9), high=F.from_float(.9))
                   if canonical else dict(width=width))
        guard = result['nodes'].index('guard_out')
        phase = result['nodes'].index('phase_out')
        for time, row in zip(times, result['solutions']):
            expected = oracle(time, **options)
            for index, answer in zip([guard, phase], expected):
                self.assertLessEqual(abs(F(row['voltages'][index])-answer), F(1e-12),
                                     (time, result['nodes'][index]))

    def test_original_source_nanosecond_parameters_check_both_outputs_through_34ns(self):
        # Decimal-law answers are sampled away from wrap ambiguity. Exact
        # post-event endpoint equality is covered by the binary control below.
        times = [float(F(n, 100)*F(1, 10**9)) for n in
                 [0, 75, 150, 152, 154, 400, 750, 802, 804,
                  952, 1200, 1602, 2402, 3202, 3400]]
        result = run(program(canonical=True), times, canonical=True)
        self.assert_outputs(result, times, canonical=True)

    def test_same_source_binary_parameters_preserve_guard_edges_and_phase_wraps(self):
        times = [0, .75, 1.5, 1.625, 1.75, 4, 7.75, 8,
                 8.125, 8.25, 9.625, 16, 16.125, 24, 24.125, 32, 34]
        result = run(program(), times)
        self.assert_outputs(result, times)
        guard = result['nodes'].index('guard_out')
        by_time = dict(zip(times, [r['voltages'][guard] for r in result['solutions']]))
        self.assertEqual([by_time[t] for t in [0, 1.5, 1.625, 1.75, 8, 8.125, 8.25]],
                         [1, 1, .5, 0, 0, .5, 1])

    def test_extra_queries_preserve_joint_history_and_future_periods(self):
        times = [0, 1.5, 1.625, 4, 8, 8.125, 9.625, 16, 24.125, 32, 34]
        p = program()
        sparse = run(p, times)
        dense_times = sorted(set(times + [k/8 for k in range(273)]))
        dense = run(p, dense_times)
        self.assert_outputs(dense, dense_times)
        dense_rows = dict(zip(dense_times, [s['voltages'] for s in dense['solutions']]))
        self.assertEqual([dense_rows[t] for t in times],
                         [s['voltages'] for s in sparse['solutions']])
        self.assertEqual(dense['transient']['events'], sparse['transient']['events'])

    def test_pulse_at_least_period_has_no_low_remainder(self):
        times = [0, 4, 7.75, 8, 8.125, 12, 16, 24, 32, 34]
        result = run(program(pulse=8), times)
        self.assert_outputs(result, times, width=F(8))

    def test_future_rail_pulse_is_not_admitted_as_a_whole_request_dc_factor(self):
        # The supplied waveform changes after every requested observation.
        with self.assertRaises((CompileError, KernelError)) as caught:
            run(program(), [0, 4, 8], future_pulse=True)
        self.assertRegex(str(caught.exception), 'DC|source|affine|unsupported')

    def test_real_source_error_tube_is_not_erased_in_the_joint_consumer(self):
        with self.assertRaises((CompileError, KernelError)) as caught:
            run(program(), [0, 4, 8, 12, 16, 34], errors={'VDD': 1e-6})
        self.assertRegex(str(caught.exception), 'uncertainty|accuracy|source|affine|unsupported')

    def test_bound_step_limits_actual_committed_segments_of_both_output_request(self):
        p = program()
        inputs = sources(34)
        request = dict(program=p.to_dict(), driven=list(inputs), samples=[],
                       transient=dict(pwl=list(inputs.values()), output_times=[0, 34],
                                      stop=34, max_step=20),
                       tolerances=dict(absolute=1e-12, relative=0))
        evidence = os.environ.get('EVAS_ORIGINAL079_EVIDENCE_DIR')
        directory = (nullcontext(tempfile.mkdtemp(prefix='original079-', dir=evidence))
                     if evidence else tempfile.TemporaryDirectory(prefix='original079-'))
        with directory as directory:
            path = Path(directory)/'diagnostics.json'
            if evidence:
                (path.parent/'request.json').write_text(json.dumps(request, indent=2))
            result = _invoke(request, KERNEL, diagnostics_path=path)
            diagnostics = json.loads(path.read_text())
            if evidence:
                (path.parent/'response.json').write_text(json.dumps(result, indent=2))
        segments = [r for r in diagnostics['records']
                    if r['kind']=='controller_step' and r['outcome']=='committed']
        self.assertFalse(diagnostics['truncated'])
        self.assertTrue(segments, 'sampling density is not physical bound_step evidence')
        self.assertEqual(segments[0]['start'], 0)
        self.assertEqual(segments[-1]['end'], 34)
        for segment in segments:
            self.assertGreater(F(segment['end'])-F(segment['start']), 0)
            self.assertLessEqual(F(segment['end'])-F(segment['start']), F(1, 2))
        self.assert_outputs(result, [0, 34])


if __name__ == '__main__':
    unittest.main()
