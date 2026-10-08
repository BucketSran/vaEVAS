"""Calibration of direct compatibility, independent of each backend's oracle."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from compare import compare


class DirectComparison(unittest.TestCase):
    def setUp(self):
        self.contract = dict(stop=1.0, required_times=[0.0, 0.5, 1.0],
                             budgets_v={'y': 1e-6, 'n': 0.0},
                             phase_nodes=['n'], event_windows_s=[[0.49, 0.51]])
        self.trace = dict(rows=[dict(time=t, voltages={'y': t, 'n': int(t >= .5)})
                               for t in [0.0, .5, 1.0]])

    def test_identical_complete_observations_pass_only_finite_comparison(self):
        r = compare(self.contract, self.trace, self.trace)
        self.assertEqual(r['finite_pair_status'], 'P')
        self.assertEqual(r['paired_rows'], 3)
        self.assertEqual(r['paired_values'], 6)
        self.assertEqual(r['formal_qualification'], 'I')

    def test_two_independent_passes_do_not_hide_c1_phase_difference(self):
        ev = copy.deepcopy(self.trace)
        ev['independent_status'] = 'P'
        sp = copy.deepcopy(self.trace)
        sp['independent_status'] = 'P'
        ev['rows'][1]['voltages']['n'] = 0
        r = compare(self.contract, ev, sp)
        self.assertEqual(r['finite_pair_status'], 'F')
        self.assertEqual(r['phase_status'], 'F')
        self.assertEqual(r['failed_values'], 1)
        self.assertEqual(r['failed_inside_windows'], 1)
        self.assertEqual(r['failed_outside_windows'], 0)

    def test_missing_native_row_remains_in_denominator(self):
        ev = copy.deepcopy(self.trace)
        ev['rows'].pop(1)
        r = compare(self.contract, ev, self.trace)
        self.assertEqual(r['finite_pair_status'], 'I')
        self.assertEqual(r['native_rows'], 3)
        self.assertEqual(r['unpaired_native_rows'], 1)

    def test_duplicate_native_and_out_of_domain_rows_cannot_qualify(self):
        for extra in [self.trace['rows'][1], dict(time=2., voltages={'y': 2., 'n': 1})]:
            sp = copy.deepcopy(self.trace)
            sp['rows'].append(extra)
            r = compare(self.contract, self.trace, sp)
            self.assertEqual(r['finite_pair_status'], 'I')
            self.assertEqual(r['native_rows'], 4)
            self.assertTrue(r['coverage_gaps'])

    def test_missing_required_strobe_is_not_replaced_by_nearest_time(self):
        ev = copy.deepcopy(self.trace)
        ev['rows'][1]['time'] += 1e-15
        r = compare(self.contract, ev, ev)
        self.assertEqual(r['finite_pair_status'], 'I')
        self.assertIn(.5, r['missing_required_times']['spectre'])

    def test_known_difference_remains_failure_with_incomplete_coverage(self):
        ev = copy.deepcopy(self.trace)
        ev['rows'][0]['voltages']['y'] = .1
        ev['rows'].pop(1)
        r = compare(self.contract, ev, self.trace)
        self.assertEqual(r['finite_pair_status'], 'F')
        self.assertEqual(r['unpaired_native_rows'], 1)

    def test_missing_signal_does_not_hide_another_signal_failure_in_same_row(self):
        for bad_backend in ['evas', 'spectre']:
            ev, sp = copy.deepcopy(self.trace), copy.deepcopy(self.trace)
            bad = ev if bad_backend == 'evas' else sp
            bad['rows'][0]['voltages']['y'] = .1
            bad['rows'][0]['voltages'].pop('n')
            result = compare(self.contract, ev, sp)
            self.assertEqual(result['finite_pair_status'], 'F')
            self.assertEqual(result['failed_values'], 1)
            self.assertEqual(result['paired_values'], 5)
            self.assertEqual(result['unpaired_native_rows'], 1)

    def test_nonfinite_missing_signal_and_empty_trace_are_incomplete(self):
        for mutate in [lambda r: r['rows'][0]['voltages'].update(y=float('nan')),
                       lambda r: r['rows'][0]['voltages'].pop('n'),
                       lambda r: r.update(rows=[])]:
            ev = copy.deepcopy(self.trace)
            mutate(ev)
            r = compare(self.contract, ev, self.trace)
            self.assertEqual(r['finite_pair_status'], 'I')
            self.assertTrue(r['coverage_gaps'])

    def test_invalid_budget_or_phase_signal_is_rejected(self):
        for update in [dict(budgets_v={'y': -1.}), dict(phase_nodes=['missing']),
                       dict(event_windows_s=[[.8, .2]])]:
            with self.assertRaises(ValueError):
                compare(dict(self.contract, **update), self.trace, self.trace)

    def test_no_phase_obligation_is_unassessed_even_when_voltage_passes(self):
        result = compare(dict(self.contract, phase_nodes=[]), self.trace, self.trace)
        self.assertEqual(result['finite_pair_status'], 'P')
        self.assertEqual(result['phase_status'], 'I')

    def test_cli_invalid_input_is_not_a_comparison_failure_or_old_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = Path(__file__).with_name('compare.py')
            (root/'trace.json').write_text(json.dumps(self.trace))
            (root/'contract.json').write_text(json.dumps(dict(self.contract, stop=-1)))
            argv = [sys.executable, str(script), str(root/'contract.json'),
                    str(root/'trace.json'), str(root/'trace.json'), str(root/'result.json')]
            proc = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(json.loads(proc.stderr)['status'], 'ERROR')
            self.assertFalse((root/'result.json').exists())
            (root/'contract.json').write_text(json.dumps(self.contract))
            (root/'result.json').write_text('preserved old result')
            proc = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 3)
            self.assertEqual((root/'result.json').read_text(), 'preserved old result')

    def test_cli_completed_verdicts_have_distinct_codes_and_valid_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'contract.json').write_text(json.dumps(self.contract))
            (root/'spectre.json').write_text(json.dumps(self.trace))
            for status, code in [('P', 0), ('F', 1), ('I', 2)]:
                ev = copy.deepcopy(self.trace)
                if status == 'F':
                    ev['rows'][0]['voltages']['y'] = 1
                elif status == 'I':
                    ev['rows'].pop(1)
                (root/'evas.json').write_text(json.dumps(ev))
                output = root/(status+'.json')
                proc = subprocess.run([sys.executable, str(Path(__file__).with_name('compare.py')),
                                       str(root/'contract.json'), str(root/'evas.json'),
                                       str(root/'spectre.json'), str(output)], capture_output=True, text=True)
                self.assertEqual((proc.returncode, proc.stdout.strip()), (code, status))
                self.assertEqual(json.loads(output.read_text())['finite_pair_status'], status)

    @unittest.skipUnless(os.name == 'posix', 'uses a real POSIX file-size limit')
    def test_cli_write_failure_does_not_publish_partial_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'contract.json').write_text(json.dumps(self.contract))
            (root/'trace.json').write_text(json.dumps(self.trace))
            # The OS rejects a real write; no comparator or file-write mock.
            driver = ('import resource,signal,runpy,sys; '
                      'resource.setrlimit(resource.RLIMIT_FSIZE,(200,200)); '
                      'signal.signal(signal.SIGXFSZ,signal.SIG_IGN); '
                      'sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name="__main__")')
            proc = subprocess.run([sys.executable, '-B', '-c', driver,
                                   str(Path(__file__).with_name('compare.py')),
                                   str(root/'contract.json'), str(root/'trace.json'),
                                   str(root/'trace.json'), str(root/'result.json')],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 3)
            self.assertFalse((root/'result.json').exists())
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['contract.json', 'trace.json'])

    def test_actual_c1_engineering_passes_still_fail_direct_comparison(self):
        root = Path(__file__).resolve().parent
        fixture = json.loads((root/'calibration/c1-phase.json').read_text())
        path = root.parents[2]/'evas/validation/event_alignment/checker.py'
        spec = importlib.util.spec_from_file_location('frozen_event_checker', path)
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        ev, sp = fixture['evas'], fixture['spectre']
        self.assertEqual(checker.inspect(fixture['case'], ev['rows'])['status'], 'P')
        self.assertEqual(checker.inspect(fixture['case'], sp['rows'],
                                        sp['decimal_tokens'])['status'], 'P')
        result = compare(fixture['contract'], ev, sp)
        self.assertEqual(result['finite_pair_status'], 'F')
        self.assertEqual(result['paired_rows'], 171)
        self.assertEqual(result['phase_failed_values'], 4)
        self.assertEqual(result['worst']['h1']['error_v'], 2.4)


if __name__ == '__main__':
    unittest.main()
