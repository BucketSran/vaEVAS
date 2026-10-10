import unittest
from analyze import compare, CASES, T


class NativePairing(unittest.TestCase):
    def test_boundary_jump_is_retained_beside_windowed_values(self):
        reference = [dict(time=0, ah=.25, ae=.25, af=.25, an=0),
                     dict(time=T, ah=.25, ae=.25, af=.25, an=0),
                     dict(time=2*T, ah=.75, ae=.75, af=.6, an=1)]
        candidate = [dict(row) for row in reference]
        candidate[1].update(ah=.75, an=1)
        r = compare(CASES[0], reference, candidate)['instances']['a']
        self.assertEqual(r['maximum_difference_V_all_rows']['h'], .5)
        self.assertEqual(r['held_difference_V_outside_event_windows'], 0)
        self.assertEqual(r['counter_disagreements_all_rows'], 1)
        self.assertEqual(r['counter_disagreements_outside_event_windows'], 0)

    def test_nearby_time_cannot_substitute_for_same_time(self):
        self.assertEqual(compare(CASES[0], [{'time': T}], [{'time': T+1e-16}])['status'], 'GRID_MISMATCH')


if __name__ == '__main__':
    unittest.main()
