import unittest
from callback_policy import predict, covers_windows


class AcceptedGridPolicy(unittest.TestCase):
    def test_first_point_inside_window(self):
        counts,events=predict([0.,.8,.95,1.,1.1,1.95,2.],1.,1.,.1)
        self.assertEqual(counts,[0,0,1,1,1,2,2])
        self.assertEqual(events,[.95,1.95])

    def test_one_shot_does_not_repeat(self):
        self.assertEqual(predict([0.,.95,1.,2.],1.,0.,.1)[0],[0,1,1,1])

    def test_grid_missing_window_is_not_silent_success(self):
        with self.assertRaises(ValueError): predict([0.,1.2],1.,1.,.1)

    def test_zero_tolerance_is_outside_hypothesis(self):
        with self.assertRaises(ValueError): predict([0.,1.],1.,1.,0.)

    def test_empty_or_truncated_window_is_not_coverage(self):
        self.assertFalse(covers_windows([],1.,1.,.1,2.5))
        self.assertFalse(covers_windows([{'time':0.},{'time':1.5}],1.,1.,.1,2.5))
        self.assertTrue(covers_windows([{'time':.1},{'time':2.5}],1.,1.,.1,2.5))


if __name__=='__main__':
    unittest.main()
