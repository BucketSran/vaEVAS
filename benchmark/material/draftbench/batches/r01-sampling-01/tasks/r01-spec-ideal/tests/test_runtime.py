"""Runtime plumbing tests with an injected process double. Never launch Spectre."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

TASK = Path(__file__).resolve().parents[1]
PUBLIC = TASK / 'environment/starter/testbench'
sys.path.insert(0, str(PUBLIC))
from cases import public_cases
from contract import expected, pwl
from runtime import check_settings, digest, execute, freeze, measured_observations, preflight, read_json, read_psf, run_suite


def fixture_settings():
    # Numerical fixture only; it is not a user-approved or calibrated protocol.
    return dict(protocol='software-plumbing-fixture', status='specified_unvalidated',
                voltage_atol=.001, time_atol=1e-13, event_guard=1e-11, probe_step=1e-9,
                parameter_domain={'vth': [.3, 1.5], 'vinit': [0, 1.8]},
                stimulus_domain={'duration_s': [1e-9, 20e-6], 'vin_V': [0, 1.8],
                                 'vin_max_slope_V_per_s': .2e9, 'control_levels_V': [0, 1.8],
                                 'control_ramp_s': [.1e-9, 1e-9], 'min_event_gap_s': .2e-9},
                control_boundaries={'fixture': True}, backend_version='fixture-spectre',
                numerical_settings=dict(reltol=1e-6, vabstol=1e-8, iabstol=1e-12, maxstep=1e-10),
                timeout_seconds=120)


class ProcessDouble:
    def __init__(self, mode='pass'):
        self.mode = mode
        self.calls = []

    def __call__(self, argv, cwd, log, timeout):
        self.calls.append(argv)
        cwd, log = Path(cwd), Path(log)
        version = '-W' in argv
        text = ('wrong-version' if self.mode == 'version' else 'fixture-spectre') if version else 'software process double only'
        log.write_text(text + '\n')
        result = dict(returncode=0, timeout=False, argv=argv, log_sha256=digest(log), elapsed_s=0.)
        if version:
            return result
        if self.mode == 'timeout':
            return dict(result, timeout=True, returncode=-15)
        if self.mode == 'compile':
            return dict(result, returncode=1)
        if self.mode == 'missing_waveform':
            return result
        root = cwd.parent
        cases = read_json(root / 'cases.json')
        case = next(c for c in cases if c['name'] == cwd.name)
        mapping = read_json(cwd / 'nodes.json')
        plan = [r for r in read_json(root / 'plan.json') if r['case'] == cwd.name]
        times = sorted({r['time'] for r in plan})
        if self.mode == 'truncated':
            times = times[:-1]
        text = ['HEADER', 'VALUE']
        for t in times:
            text.append(f'"time" {t:.17g}')
            for instance in case['instances']:
                values = {s: pwl(instance[s], t) for s in ('vin', 'track', 'rst')}
                values['vout'] = expected(instance, t)[0]
                if self.mode == 'wrong_output':
                    values['vout'] += .1
                if self.mode == 'wrong_stimulus':
                    values['vin'] += .1
                for signal, node in mapping[instance['name']].items():
                    value = values[signal]
                    if self.mode == 'nan' and signal == 'vout':
                        value = float('nan')
                    text.append(f'"{node}" {value:.17g}')
        text.append('END')
        psf = cwd / 'psf/tran.tran.tran'
        psf.parent.mkdir()
        psf.write_text('\n'.join(text) + '\n')
        if self.mode == 'tamper':
            (cwd / 'circuit.va').write_text('tampered\n')
        return result


class RuntimeTests(unittest.TestCase):
    def suite(self, temp, *, mode='pass', launch=True, grading=True, candidate=None):
        candidate = candidate or TASK / 'solution/circuit.va'
        tool = ProcessDouble(mode)
        result = run_suite(candidate, Path(temp) / 'result', public_cases(), fixture_settings(),
                           launch=launch, binary='not-a-real-binary', executor=tool, grading=grading)
        return result, tool

    def test_prepare_never_calls_any_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, tool = self.suite(tmp, launch=False)
            self.assertFalse(tool.calls)
            self.assertIsNone(result['score'])
            self.assertEqual(result['status'], 'not_run')
            self.assertFalse((Path(tmp) / 'result/reward.txt').exists())
            self.assertEqual(len(result['prepared_cases']), 4)

    def test_frozen_file_and_native_measurement_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, tool = self.suite(tmp)
            self.assertEqual(result['score'], 1, result)
            self.assertEqual(result['execution_kind'], 'software-test-double')
            self.assertEqual(len(tool.calls), 5)
            self.assertTrue(all(r['native_rows'] > 0 for r in result['cases']))
            self.assertEqual(result['source'], digest(TASK / 'solution/circuit.va'))
            self.assertEqual((Path(tmp) / 'result/reward.txt').read_text(), '1\n')

    def test_public_execution_never_writes_task_reward(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = self.suite(tmp, grading=False)
            self.assertTrue(result['diagnostic_only'])
            self.assertTrue(result['passed'])
            self.assertIsNone(result['score'])
            self.assertFalse((Path(tmp) / 'result/reward.txt').exists())

    def test_executed_failures_are_zero_with_reasons(self):
        for mode in ('compile', 'timeout', 'missing_waveform', 'truncated', 'nan',
                     'wrong_output', 'wrong_stimulus', 'tamper'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                result, _ = self.suite(tmp, mode=mode)
                self.assertEqual(result['score'], 0, result)
                self.assertTrue(result['reasons'])
                self.assertEqual((Path(tmp) / 'result/reward.txt').read_text(), '0\n')

    def test_backend_version_mismatch_is_environment_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, tool = self.suite(tmp, mode='version')
            self.assertEqual(result['score'], 0)
            self.assertEqual(len(tool.calls), 1)
            self.assertIn('environment', result['reason'])

    def test_pending_protocol_never_launches_or_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = fixture_settings(); cfg['voltage_atol'] = None
            tool = ProcessDouble()
            result = run_suite(TASK / 'solution/circuit.va', Path(tmp) / 'result', public_cases(), cfg,
                               launch=True, executor=tool)
            self.assertEqual(result['status'], 'not_run')
            self.assertIsNone(result['score'])
            self.assertFalse(tool.calls)

    def test_missing_empty_and_external_io_submission(self):
        for kind in ('missing', 'empty', 'file_io'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                candidate = Path(tmp) / 'candidate.va'
                if kind != 'missing':
                    candidate.write_text('' if kind == 'empty' else 'module x; analog $fopen("bad"); endmodule')
                result, tool = self.suite(tmp, candidate=candidate)
                self.assertEqual(result['score'], 0)
                self.assertIn('submission_contract', result['reason'])
                self.assertFalse(tool.calls)

    def test_comments_and_console_strings_are_not_external_io(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / 'candidate.va'
            candidate.write_text('// $fopen("ignored")\nmodule x; analog $strobe("literal $fopen"); endmodule')
            preflight(candidate)

    def test_fifo_submission_is_rejected_without_waiting_for_a_writer(self):
        import os
        if not hasattr(os, 'mkfifo'):
            self.skipTest('POSIX fifo test')
        with tempfile.TemporaryDirectory() as tmp:
            fifo=Path(tmp)/'candidate.va'
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                freeze(fifo,Path(tmp)/'frozen.va')

    def test_timeout_always_kills_the_group_after_leader_exits(self):
        from unittest.mock import patch, Mock
        import signal
        import subprocess
        leader=Mock(pid=1234)
        leader.wait.side_effect=[subprocess.TimeoutExpired(['python'],.01),-15]
        with tempfile.TemporaryDirectory() as tmp:
            with patch('runtime.subprocess.Popen',return_value=leader), patch('runtime.os.killpg') as kill:
                result=execute(['python'],tmp,Path(tmp)/'process.log',.01)
        self.assertTrue(result['timeout'])
        self.assertEqual([c.args for c in kill.call_args_list],[(1234,signal.SIGTERM),(1234,signal.SIGKILL)])

    def test_external_io_object_macro_is_checked_without_banning_safe_macros(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate=Path(tmp)/'candidate.va'
            candidate.write_text('`define FD fopen\nmodule x; integer f; analog f=$`FD("x","w"); endmodule')
            with self.assertRaises(ValueError):
                preflight(candidate)
            candidate.write_text('`define NOW abstime\nmodule x; real t; analog t=$`NOW; endmodule')
            preflight(candidate)
            candidate.write_text('module x; integer f; analog begin $strobe("/*"); f=$fopen("bad"); $strobe("*/"); end endmodule')
            with self.assertRaises(ValueError):
                preflight(candidate)

    def test_existing_results_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.suite(tmp, launch=False)
            with self.assertRaises(FileExistsError):
                self.suite(tmp, launch=False)

    def test_psf_rejects_nonfinite_duplicate_and_missing_data(self):
        bad = ['VALUE\n"time" 0\n"y" 0\n',
               'VALUE\n"time" 0\n"y" nan\n"time" 1\n"y" 0\nEND\n',
               'VALUE\n"time" 0\n"y" 0\n"y" 1\n"time" 1\n"y" 0\nEND\n',
               'VALUE\n"time" 0\n"y" 0\n"time" 0\n"y" 0\nEND\n',
               'VALUE\n"time" 0\n"z" 0\n"time" 1\n"z" 0\nEND\n']
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.psf'
            for text in bad:
                path.write_text(text)
                with self.assertRaises(ValueError):
                    read_psf(path, ['y'])

    def test_protocol_json_rejects_duplicate_and_nonfinite_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'
            for text in ('{"x":1,"x":2}', '{"x":NaN}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    read_json(path)

    def test_frozen_inputs_use_native_strobes_not_candidate_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = self.suite(tmp, launch=False)
            for case in result['prepared_cases']:
                text = (Path(tmp) / 'result/attempt' / case / 'tb.scs').read_text()
                self.assertIn('strobetimes=[', text)
                self.assertIn('save vin_0 track_0 rst_0 vout_0', text)
                self.assertNotIn('observe.va', text)

if __name__ == '__main__':
    unittest.main()
