"""User budgets control certified trajectories independently of observation grids."""
GUARDS = ["DYNAMICS", "DEV:precision-chain"]

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evas import KernelError
from test_continuous_dynamics import compile_model, run, rows


class TransientAccuracyControl(unittest.TestCase):
    def measured(self, program, times, tolerance, max_step=1):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'diagnostics.json'
            with patch.dict(os.environ, EVAS_DIAGNOSTICS_PATH=str(path)):
                result = run(program, times=times, stop=1, max_step=max_step,
                             vabstol=tolerance, reltol=0)
            return result, json.loads(path.read_text())

    def test_tighter_voltage_budget_refines_amplified_rational_decay(self):
        # z'=−z², z(0)=1 gives z=1/(1+t). Gain and cancellation at t=1
        # require an absolute state budget; the final answer is independent.
        program = compile_model('V(z,r)<+idt(-pow(V(z,r),2),1); '
                                'V(y,r)<+1e4*(V(z,r)-0.5);', 'electrical z;')
        counts = []
        for tolerance in [1e-3, 1e-8]:
            result, report = self.measured(program, [0,.125,.5,1], tolerance)
            for t, row in zip([0,.125,.5,1], rows(result)):
                self.assertAlmostEqual(row['y'], 1e4*(1/(1+t)-.5), delta=tolerance)
                self.assertAlmostEqual(row['dut:z'], 1/(1+t), delta=tolerance)
            counts.append(report['counters']['nonlinear_certified_candidate_steps'])
        self.assertGreater(counts[1], counts[0])

    def test_query_grid_is_immutable_and_internal_steps_obey_ceiling(self):
        program = compile_model('V(z,r)<+idt(-pow(V(z,r),2),1); '
                                'V(y,r)<+1e4*(V(z,r)-0.5);', 'electrical z;')
        sparse = [0,.125,.5,1]
        dense = [i/32 for i in range(33)]
        first, a = self.measured(program, sparse, 1e-8, max_step=1/32)
        second, b = self.measured(program, dense, 1e-8, max_step=1/32)
        self.assertEqual(first['solutions'], [second['solutions'][dense.index(t)] for t in sparse])
        self.assertEqual(a['counters']['nonlinear_certified_candidate_steps'],
                         b['counters']['nonlinear_certified_candidate_steps'])
        for record in a['records']:
            if record['kind'] == 'nonlinear_candidate' and record['outcome'] == 'certified':
                self.assertLessEqual(record['end']-record['start'], 1/32)

    def test_amplified_initial_enclosure_has_explicit_precision_refusal(self):
        program = compile_model('V(z,r)<+idt(-pow(V(z,r),2),1); '
                                'V(y,r)<+1e4*(V(z,r)-0.5);', 'electrical z;')
        # The analytic nominal value is finite, but accumulated binary64
        # enclosure width cannot certify a 1e-20 V budget after amplification.
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy.*cannot certify'):
            self.measured(program, [0,1], 1e-20)

    def test_supported_event_continuation_preserves_history_and_grid(self):
        program = compile_model('@(initial_step) a=1; @(timer(.5,0,1e-12)) a=2; '
                                'V(z,r)<+idt(-a*pow(V(z,r),2),1); '
                                'V(y,r)<+1e4*(V(z,r)-0.5);',
                                'integer a; electrical z;')
        sparse = [0,.125,.5,.75,1]
        dense = [i/32 for i in range(33)]
        first, _ = self.measured(program, sparse, 1e-8)
        second, _ = self.measured(program, dense, 1e-8)
        self.assertEqual(first['solutions'], [second['solutions'][dense.index(t)] for t in sparse])
        for t, row in zip(sparse, rows(first)):
            expected = 1/(1+t) if t <= .5 else 1/(.5+2*t)
            self.assertAlmostEqual(row['y'], 1e4*(expected-.5), delta=1e-8)

    def test_relative_event_budget_preserves_precision_before_later_cancellation(self):
        program = compile_model('@(initial_step) a=1; @(timer(.5,0,1e-12)) a=2; '
                                'V(z,r)<+idt(-a*pow(V(z,r),2),1); '
                                'V(y,r)<+1e4*(V(z,r)-0.5);',
                                'integer a; electrical z;')
        sparse = [0,.125,.5,.75,1]
        dense = [i/32 for i in range(33)]
        results = [run(program, times=times, stop=1, max_step=1,
                       vabstol=1e-8, reltol=1e-5) for times in [sparse, dense]]
        self.assertEqual(results[0]['solutions'],
                         [results[1]['solutions'][dense.index(t)] for t in sparse])
        for t, row in zip(sparse, rows(results[0])):
            expected = 1/(1+t) if t <= .5 else 1/(.5+2*t)
            voltage = 1e4*(expected-.5)
            self.assertAlmostEqual(row['y'], voltage, delta=1e-8+1e-5*abs(voltage))

    def test_public_accumulated_roundoff_reaches_bounded_suffix_refusal(self):
        program = compile_model('V(z,r)<+idt(-pow(V(z,r),2),1); '
                                'V(y,r)<+1e4*(V(z,r)-0.5);', 'electrical z;')
        # Unlike the 1e-20 initial-observation refusal, the initial voltage
        # certifies and this fails while constructing a disposable suffix.
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy.*8 suffix refinements'):
            run(program, times=[0,1], stop=1, max_step=1, vabstol=1e-11, reltol=1e-8)

    def test_invalid_dae_tolerances_are_rejected_before_refinement(self):
        program = compile_model('V(y,r)<+idt(1+2*V(y,r),0)-pow(V(y,r),2);')
        for absolute, relative in [(-1,0), (0,0), (1e-9,-1)]:
            with self.subTest(absolute=absolute, relative=relative):
                with self.assertRaises(KernelError) as caught:
                    run(program, times=[0,.125], stop=.125,
                        vabstol=absolute, reltol=relative)
                self.assertEqual(caught.exception.detail['kind'], 'invalid_config')
