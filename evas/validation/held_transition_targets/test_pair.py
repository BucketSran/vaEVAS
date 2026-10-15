import unittest
from pair import B,print_cell_error,TIMES
class PrintCellCalibration(unittest.TestCase):
    def test_correct_boundary_and_interior(self):
        for t,v in [('3.250000000000000e+00','1.000000000000000e+00'),('1.125000000000000e+00','5.000000000000000e-01')]:
            self.assertLessEqual(print_cell_error(t,v),B)
    def test_error_above_original_budget_rejects(self):
        self.assertGreater(print_cell_error('1.125000000000000e+00','5.000002000000000e-01'),B)
    def test_nonfinite_rejects(self):
        with self.assertRaises(ValueError):print_cell_error('NaN','0')
    def test_adjacent_serialized_time_does_not_count_as_exact_forced(self):
        self.assertNotIn(3.249999999999989,TIMES)
if __name__=='__main__':unittest.main()
