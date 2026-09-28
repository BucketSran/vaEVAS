"""Archive adapter controls, independent hand anchors, and native format failures."""
import copy
from fractions import Fraction as Q
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from history import value_at
from recheck import ROOT, event_contract, prepare_observations, read_waveform


class RecheckCalibration(unittest.TestCase):
    def test_hand_anchors_and_reset_history(self):
        anchors = [('v3-main', 1, '1/10'), ('v3-main', 3, '9/10'),
                   ('v4-c0', '7/4', '17/40'), ('v4-c1', '7/4', '1/10'),
                   ('v4-c1', '11/4', '23/40'), ('v5-main', '23/40', '1/2'),
                   ('v5-main', '51/40', '1/2')]
        for name, t, expected in anchors:
            events = event_contract(name)
            self.assertEqual(value_at(Q(t), events, [Q(0)] * len(events), Q(1, 10)), Q(expected))

    def test_export_validation_and_failures(self):
        condition = {'inputs': {'vin': [[0, 0], [4, 1]]}}
        rows = [{'time': Q(i, 10**9), 'vout': Q(0), 'vin': Q(i, 4000)} for i in range(4001)]
        observations, quality = prepare_observations(rows, condition)
        self.assertEqual(len(observations), 4001)
        self.assertEqual(quality['input_max_error_v'], {'vin': 0.0})
        invalid = [rows[:-1], rows[::2]]
        for key, value in [('time', rows[4]['time']), ('vin', 'NaN'), ('vin', 10)]:
            bad = copy.deepcopy(rows); bad[5][key] = value; invalid.append(bad)
        bad = copy.deepcopy(rows); bad[5].pop('vout'); invalid.append(bad)
        invalid.append([{**r, 'time': r['time'] * 10**6} for r in rows])
        for bad in invalid:
            with self.assertRaises((ValueError, KeyError)):
                prepare_observations(bad, condition)

    def test_native_reader_retains_duplicate_time_for_explicit_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'data.csv'
            path.write_text('time,vout\n0,0.1\n0,0.9\n0.000004,0.9\n')
            rows = read_waveform(path, 'evas')
            self.assertEqual(len(rows), 3)
            with self.assertRaisesRegex(ValueError, 'duplicate-time'):
                prepare_observations(rows, {'inputs': {}})
            path.write_text('HEADER\nVALUE\n"time" 0\n"vout" .1\n')
            with self.assertRaises(ValueError):
                read_waveform(path, 'spectre')

    def test_cli_never_writes_inside_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / 'evidence'; evidence.mkdir()
            output = evidence / 'new.json'
            result = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('recheck.py')),
                                     str(evidence), '--output', str(output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            self.assertIn('outside the evidence', result.stderr)

    def test_wrong_receipt_rejects_without_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / 'evidence'; evidence.mkdir()
            (evidence / 'FILE_MANIFEST.json').write_text('{}\n')
            output = Path(tmp) / 'new.json'
            result = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('recheck.py')),
                                     str(evidence), '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('does not match archive receipt', result.stderr)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
