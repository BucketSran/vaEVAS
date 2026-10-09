import unittest
from readback_adapter import normalize

class UnitCalibration(unittest.TestCase):
    def test_known_actual_units(self):
        text='maxstep = 1 ms\nabstol(V) = 10 pV\nabstol(I) = 1 fA\n'
        actual,changes=normalize(text,'log')
        self.assertEqual(actual,'maxstep = 1E-3\nabstol(V) = 1.0E-11\nabstol(I) = 1E-15')
        self.assertEqual(len(changes),3)
    def test_psf_quotes_and_original(self):
        text='"maxstep" 1 ms\n'
        actual,changes=normalize(text,'psf');self.assertEqual(actual,'"maxstep" 1E-3');self.assertEqual(changes[0]['original_raw'],'"maxstep" 1 ms')
    def test_invalid_dimension_and_nonpositive(self):
        for text in ['maxstep = 1 pV','abstol(V) = 1 fA','maxstep = 0 ms']:
            with self.assertRaises(ValueError):normalize(text,'log')
    def test_unrecognized_lines_unchanged(self):
        text='foo = 1 ms\nmaxstep = nan ms\n'
        actual,changes=normalize(text,'log');self.assertEqual(actual,text.rstrip('\n'));self.assertEqual(changes,[])

if __name__=='__main__':unittest.main()
