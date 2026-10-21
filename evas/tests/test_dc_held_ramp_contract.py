"""DC rails multiply held elapsed time without freezing it at an observation.

The oracle is a rational sawtooth, not an EVAS helper. This is only the
phase_out slice of 079; it supplies no continuous Transition-target contract.
"""
GUARDS = ['LANG', 'TIMER', 'EVENT-ORDER', 'COMPOSE', 'DYNAMICS']

from fractions import Fraction as F
from contextlib import nullcontext
import json
import os
from pathlib import Path
import tempfile
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from evas.runtime import _invoke
from test_affine import instance, model

KERNEL = Path(os.environ.get('EVAS_KERNEL', str(
    Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel')))


def program(*, shifted=False, bound=False):
    initial = 'cycle_start=-4;next_cycle=4;' if shifted else 'cycle_start=0;next_cycle=8;'
    body = ('vh=V(vdd);vl=V(vss);'
            '@(initial_step)begin ' + initial + 'end '
            '@(timer(next_cycle))begin cycle_start=next_cycle;next_cycle=next_cycle+8;end '
            + ('$bound_step(0.5);' if bound else '')
            + 'phase=$abstime-cycle_start;'
            'if(phase<0)phase=0;if(phase>8)phase=8;'
            'phase_norm=phase/8;V(y)<+vl+(vh-vl)*phase_norm;')
    text = model(body, 'real vh,vl,cycle_start,next_cycle,phase,phase_norm;',
                 ports='vdd,vss,y', directions='input vdd,vss;output y;')
    return compile_sources({'dc-held-ramp.va': text}, [instance(
        connections=dict(vdd='vdd', vss='vss', y='y'))])


def sources(vdd=None):
    return dict(vdd=vdd or [[0, 1], [16, 1]], vss=[[0, 0], [16, 0]])


def run(p, times, *, vdd=None, errors=None):
    return transient(p, sources(vdd), times, stop=16, max_step=16,
                     source_errors=errors, vabstol=1e-12, reltol=0, kernel=KERNEL)


def values(result):
    y = result['nodes'].index('y')
    return [row['voltages'][y] for row in result['solutions']]


def oracle(time, offset=0):
    # Exact binary fixtures; observations are post-event, so a cycle endpoint
    # belongs to the new epoch. No floor/solver implementation is imported.
    elapsed = F(time) + offset
    return (elapsed - 8 * (elapsed // 8)) / 8


class DcHeldRampContract(unittest.TestCase):
    def assert_ramp(self, result, times, offset=0):
        for actual, time in zip(values(result), times):
            self.assertLessEqual(abs(F(actual) - oracle(time, offset)), F(1e-12), time)

    def test_dc_rail_product_restarts_at_exact_held_timer_epochs(self):
        times = [0, 4, 8, 12, 16]
        result = run(program(), times)
        self.assertEqual(values(result), [0, .5, 0, .5, 0])
        self.assert_ramp(result, times)

    def test_extra_queries_preserve_wrap_and_future_phase(self):
        times = [0, 4, 8, 12, 16]
        p = program()
        sparse = run(p, times)
        dense_times = sorted(set(times + [F(k, 4) for k in range(65)]))
        dense_times = [float(t) for t in dense_times]
        dense = run(p, dense_times)
        selected = dict(zip(dense_times, values(dense)))
        self.assertEqual([selected[t] for t in times], values(sparse))
        self.assert_ramp(dense, dense_times)
        self.assertEqual(dense['transient']['events'], sparse['transient']['events'])

    def test_shifted_initial_epoch_does_not_reuse_the_zero_epoch(self):
        times = [0, 2, 4, 6, 8, 12, 16]
        result = run(program(shifted=True), times)
        self.assert_ramp(result, times, offset=4)
        self.assertEqual(values(result), [.5, .75, 0, .25, .5, 0, .5])

    def test_future_rail_change_is_not_a_whole_domain_dc_certificate(self):
        # Same initial/final values, but the pulse is outside all requested
        # samples. Whole-request admission must still see it.
        with self.assertRaises((CompileError, KernelError)) as caught:
            run(program(), [0, 4, 8], vdd=[[0, 1], [10, 1], [11, 2], [12, 1], [16, 1]])
        self.assertRegex(str(caught.exception), 'affine|DC|source|unsupported')

    def test_nonzero_source_tube_cannot_be_replaced_by_nominal_dc(self):
        # Even a nominally flat 1-V rail has a real uncertainty tube.
        # At phase 1/2 it would contribute 5e-7 V, far above 1e-12 V.
        with self.assertRaises((CompileError, KernelError)) as caught:
            run(program(), [0, 4, 8, 12, 16], errors={'vdd': 1e-6})
        self.assertRegex(str(caught.exception), 'affine|uncertainty|accuracy|source|unsupported')

    def test_bound_step_caps_committed_controller_segments(self):
        p = program(bound=True)
        inputs = sources()
        request = dict(program=p.to_dict(), driven=list(inputs), samples=[],
                       transient=dict(pwl=list(inputs.values()), output_times=[0, 16],
                                      stop=16, max_step=16),
                       tolerances=dict(absolute=1e-12, relative=0))
        # The main executor points this directory at its T7 evidence area.
        evidence = os.environ.get('EVAS_RAMP_EVIDENCE_DIR')
        directory = (nullcontext(tempfile.mkdtemp(prefix='dc-held-ramp-', dir=evidence))
                     if evidence else tempfile.TemporaryDirectory(prefix='dc-held-ramp-'))
        with directory as directory:
            path = Path(directory) / 'diagnostics.json'
            result = _invoke(request, KERNEL, diagnostics_path=path)
            diagnostics = json.loads(path.read_text())
            if evidence:
                (path.parent / 'request.json').write_text(json.dumps(request, indent=2))
                (path.parent / 'response.json').write_text(json.dumps(result, indent=2))
        self.assertFalse(diagnostics['truncated'])
        segments = [r for r in diagnostics['records']
                    if r['kind'] == 'controller_step' and r['outcome'] == 'committed']
        self.assertTrue(segments, 'output queries alone do not prove accepted step bounds')
        self.assertEqual(segments[0]['start'], 0)
        self.assertEqual(segments[-1]['end'], 16)
        for segment in segments:
            width = F(segment['end']) - F(segment['start'])
            self.assertGreater(width, 0)
            self.assertLessEqual(width, F(1, 2))
        self.assertEqual(values(result), [0, 0])


if __name__ == '__main__':
    unittest.main()
