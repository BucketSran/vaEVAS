"""Raw observation controls; no simulator or interpolation."""
from pathlib import Path
import tempfile
import unittest

from normalize_psf import normalize


class Observations(unittest.TestCase):
    def test_duplicate_times_and_original_tokens_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.psf"
            path.write_text('HEADER\nVALUE\n"time" 0\n"y" 0.10000000000000001\n'
                            '"time" 0\n"y" 0.20000000000000001\n'
                            '"time" 1e-6\n"y" 3\nEND\n')
            result = normalize(path, {"voltage_nodes": ["y"]})
            self.assertEqual([r["time"] for r in result["rows"]], [0, 0, 1e-6])
            self.assertEqual(result["decimal_tokens"][0]["voltages"]["y"],
                             "0.10000000000000001")
            self.assertEqual(result["psf_value_line_numbers"], [3, 5, 7])

    def test_missing_truncated_duplicate_or_nonfinite_values_fail(self):
        invalid = [
            'VALUE\n"time" 0\n"y" 1\n',
            'VALUE\n"time" 0\n"y" NaN\nEND\n',
            'VALUE\n"time" 0\n"y" 1\n"y" 2\nEND\n',
            'VALUE\n"time" 0\n"z" 1\nEND\n',
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.psf"
            for text in invalid:
                with self.subTest(text=text):
                    path.write_text(text)
                    with self.assertRaises(ValueError):
                        normalize(path, {"voltage_nodes": ["y"]})


if __name__ == "__main__":
    unittest.main()
