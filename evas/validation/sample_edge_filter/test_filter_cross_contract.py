import copy
import math
import unittest

import filter_cross as contract


def analytical_rows(case):
    sef = contract.sef
    rows = []
    expected_roots = {p['name']: contract.roots(p) for p in case['instances']}
    for t in contract.times(case, True, root_centers=False):
        x = t/sef.T
        row = dict(time=t, **{n: float(sef.pwl(points, min(8.5, x)))
                             for n, points in [('u', sef.INPUT), ('clk', sef.CLOCK), ('rst', sef.RESET)]})
        for p in case['instances']:
            name = p['name']
            events = [(e, q) for e, q in sef.callbacks(p) if float(e)*sef.T <= t]
            crossings = [(e, d) for e, d in expected_roots[name] if e*sef.T <= t]
            row.update({name+'n': len(events), name+'h': float(events[-1][1] if events else sef.initial(p)),
                        name+'e': sef.edge_value(p, x), name+'f': sef.filter_value(p, x),
                        name+'c': len(crossings),
                        name+'s': float(sef.pwl(sef.INPUT, crossings[-1][0])) if crossings else 0.})
        rows.append(row)
    return rows


class FilterCrossCalibration(unittest.TestCase):
    def test_refuses_unqualified_boundary_root_instead_of_undercounting(self):
        p = copy.deepcopy(contract.CASES[0]['instances'][0])
        p['threshold'] = contract.sef.filter_value(p, 1.625)
        self.assertLess(contract.sef.filter_value(p, 1.625-1e-5), p['threshold'])
        self.assertGreater(contract.sef.filter_value(p, 1.625+1e-5), p['threshold'])
        with self.assertRaisesRegex(ValueError, 'boundary-root contract'):
            contract.roots(p)

    def test_accepts_analytical_histories_and_both_root_directions(self):
        for case in contract.CASES:
            with self.subTest(case=case['id']):
                report = contract.assess(case, analytical_rows(case))
                self.assertEqual(report['status'], 'PASS', report)
                for p in case['instances']:
                    roots = contract.roots(p)
                    self.assertEqual({d for _, d in roots}, {-1, 1})
                    for t, direction in roots:
                        self.assertLess(abs(contract.sef.filter_value(p, t)-p['threshold']), 1e-14)
                        difference = (contract.sef.filter_value(p, t+1e-5)-
                                      contract.sef.filter_value(p, t-1e-5))
                        self.assertGreater(difference*direction, 0)

    def test_rejects_missing_duplicate_late_and_wrongly_sampled_callbacks(self):
        case = contract.CASES[0]
        correct = analytical_rows(case)
        for fault in ('missing', 'duplicate', 'late', 'sample', 'nan', 'missing_port',
                      'missing_time', 'input', 'filter', 'boundary_coverage'):
            rows = copy.deepcopy(correct)
            root = contract.roots(case['instances'][0])[0][0]*contract.sef.T
            if fault == 'missing':
                for row in rows: row['ac'] = 0
            elif fault == 'duplicate':
                for row in rows:
                    if row['ac'] > 0: row['ac'] += 1
            elif fault == 'late':
                for row in rows:
                    if root <= row['time'] < root+1e-8: row['ac'], row['as'] = 0, 0
            elif fault == 'sample': rows[-1]['as'] += 2e-4
            elif fault == 'nan': rows[10]['ac'] = math.nan
            elif fault == 'missing_port': del rows[10]['as']
            elif fault == 'missing_time': del rows[10]['time']
            elif fault == 'input': rows[10]['u'] += 2e-8
            elif fault == 'filter': rows[10]['af'] += 2e-4
            else: rows = [row for row in rows if abs(row['time']-root) > 1e-9]
            with self.subTest(fault=fault):
                self.assertEqual(contract.assess(case, rows)['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
