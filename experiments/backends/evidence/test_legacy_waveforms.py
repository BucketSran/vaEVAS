"""Legacy float projections and token-preserving PSF remain distinct contracts."""
import hashlib
import math
from pathlib import Path
import tempfile
import unittest

from legacy_waveforms import number, read_waveform
from psf import normalize


class LegacyWaveformContracts(unittest.TestCase):
    def test_duplicate_psf_times_order_and_original_file_survive_float_projection(self):
        text = ('HEADER\nVALUE\n"time" 0\n"u" 0.10000000000000001\n'
                '"time" 0\n"u" 0.20000000000000001\n'
                '"time" 1e-6\n"u" -0\nEND\n')
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'waveform.psf'
            path.write_text(text)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            projected = read_waveform(path, 'spectre')
            self.assertEqual(projected, [{'time': 0.0, 'u': .1},
                                         {'time': 0.0, 'u': .2},
                                         {'time': 1e-6, 'u': -0.0}])
            self.assertEqual(math.copysign(1, projected[-1]['u']), -1)
            exact = normalize(path, {'voltage_nodes': ['u']})
            self.assertEqual(exact['decimal_tokens'][0]['voltages']['u'],
                             '0.10000000000000001')
            self.assertEqual(exact['psf_value_line_numbers'], [3, 5, 7])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_csv_and_text_keep_original_columns_units_and_row_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'waveform.txt'
            path.write_text('time,u\n0,-0\n0,.25\n1e-6,.5\n')
            self.assertEqual(read_waveform(path, 'evas'),
                             [{'time': 0.0, 'u': -0.0}, {'time': 0.0, 'u': .25},
                              {'time': 1e-6, 'u': .5}])
            path.write_text('#Time v(u)\n0 -0\n0 .25\n1u 500m\n')
            self.assertEqual(read_waveform(path, 'gnucap'),
                             [{'time': 0.0, 'u': -0.0}, {'time': 0.0, 'u': .25},
                              {'time': 1e-6, 'u': .5}])

    def test_spice_number_rounding_and_unsupported_suffixes_keep_their_contract(self):
        for token, expected in [('2Meg', 2e6), ('1u', 1e-6), ('500m', .5),
                                ('1e-3', .001), ('-0', -0.0)]:
            with self.subTest(token=token):
                self.assertEqual(number(token).hex(), float(expected).hex())
        for token in ('1GHz', '1unknown', '', 'value'):
            with self.subTest(token=token), self.assertRaises(ValueError):
                number(token)

    def test_damaged_formats_still_fail_instead_of_returning_a_partial_export(self):
        invalid = [
            ('evas', 'time,u,u\n0,.1,.2\n'),
            ('spectre', 'VALUE\n"time" 0\n"u" .1\n'),
            ('spectre', 'VALUE\n"u" .1\nEND\n'),
            ('spectre', 'VALUE\n"time" 0\n"u" .1\n"u" .2\nEND\n'),
            ('gnucap', '#Time v(u)\n0 .1 extra\n'),
            ('gnucap', '#Time v(u) v(u)\n0 .1 .2\n'),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'waveform.txt'
            for backend, text in invalid:
                with self.subTest(backend=backend, text=text):
                    path.write_text(text)
                    with self.assertRaises(ValueError):
                        read_waveform(path, backend)


if __name__ == '__main__':
    unittest.main()
