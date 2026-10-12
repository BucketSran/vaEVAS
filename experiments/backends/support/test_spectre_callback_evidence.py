"""Calibration of the finite trace gate, including failures that must stay open."""
from copy import deepcopy
import unittest

from breadth_callback_trace import instrument, parse
from spectre_callback_evidence import qualify, reanalyze


class TraceCalibration(unittest.TestCase):
    def setUp(self):
        self.card = {'id': 'EC01-v1', 'source': 'n0=n0+1;', 'stop_s': 3.,
                     'inputs': {}, 'outputs': ['out', 'n'],
                     'counter_channels': {'n': {'initial': 0, 'final': 2}},
                     'events': [{'id': 'one', 'counter': 'n', 'index': 1,
                                 'kind': 'timer', 'nominal_s': 1., 'early_s': .1, 'late_s': .1},
                                {'id': 'two', 'counter': 'n', 'index': 2,
                                 'kind': 'timer', 'nominal_s': 2., 'early_s': .1, 'late_s': .1}]}
        self.log = 'EVAS_BREADTH_CALLBACK n0 dut 1 1\nEVAS_BREADTH_CALLBACK n0 dut 2 2\n'
        self.rows = [{'time': t, 'n': n, 'out': .5} for t, n in [(0., 0), (.5, 0), (1., 1), (1.5, 1), (2., 2), (3., 2)]]

    def check(self, *, card=None, source=None, log=None, rows=None, approved=True):
        card = self.card if card is None else card
        return qualify(card, instrument(card)[0] if source is None else source,
                       self.log if log is None else log, self.rows if rows is None else rows,
                       producer_qualified=approved)

    def test_complete_trace(self):
        self.assertEqual(self.check()['event_bounds_s'], {'one': [1., 1.], 'two': [2., 2.]})

    def test_missing_evidence_is_not_a_pass(self):
        bad_rows = deepcopy(self.rows)
        del bad_rows[2]['out']
        for kwargs in [{'approved': False}, {'source': 'n0=n0+2;'}, {'rows': bad_rows},
                       {'rows': self.rows[::-1]}, {'log': self.log.splitlines()[0]},
                       {'log': self.log + self.log.splitlines()[1]},
                       {'log': self.log.replace('dut', 'dut.child')},
                       {'log': self.log.replace('1 1', '1 0.5')},
                       {'log': self.log.replace('1 1', '1 nan')},
                       {'log': self.log.replace('1 1', '2 1')}]:
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self.check(**kwargs)['status'], 'unknown')

    def test_counter_contradiction(self):
        rows = deepcopy(self.rows)
        rows[1]['n'] = 1
        self.assertEqual(self.check(rows=rows)['status'], 'unknown')

    def test_every_event_needs_a_unique_identity_and_reviewed_counter(self):
        for mutation in ('unmapped_counter', 'duplicate_id'):
            with self.subTest(mutation=mutation):
                card = deepcopy(self.card)
                if mutation == 'unmapped_counter':
                    card['events'][1]['counter'] = 'unobserved'
                else:
                    card['events'][1]['id'] = card['events'][0]['id']
                self.assertEqual(self.check(card=card)['status'], 'unknown')

    def test_invalid_cross_metadata_stays_unknown(self):
        import math
        for slope, tolerance in ((0., .1), (math.nan, .1), (math.inf, .1),
                                 (1., math.nan), (1., -.1)):
            with self.subTest(slope=slope, tolerance=tolerance):
                card = deepcopy(self.card)
                card['events'][0].update(kind='cross', slope_V_s=slope,
                                         expression_tolerance_V=tolerance)
                self.assertEqual(self.check(card=card)['status'], 'unknown')

    def test_frozen_time_allowance_is_retained(self):
        lower = self.card['events'][0]['nominal_s'] - self.card['events'][0]['early_s']
        import math
        permitted = math.nextafter(lower, -math.inf)
        rows = deepcopy(self.rows)
        rows[2]['time'] = permitted
        log = self.log.replace('1 1', '1 ' + repr(permitted))
        proof = self.check(log=log, rows=rows)
        self.assertEqual(proof['status'], 'qualified')
        self.assertEqual(proof['event_bounds_s']['one'], [permitted, permitted])
        outside = lower - 64 * math.ulp(self.card['stop_s'])
        self.assertEqual(self.check(log=self.log.replace('1 1', '1 ' + repr(outside)))['status'], 'unknown')

    def test_same_time_record_is_not_discarded(self):
        self.assertEqual(len(parse(self.log.replace('2 2', '2 1'))), 2)
        self.assertEqual(self.check(log=self.log.replace('2 2', '2 1'))['status'], 'unknown')

    def test_malformed_original_assessment_is_preserved(self):
        class Science:
            @staticmethod
            def assess(*args):
                return {'behavior': {'status': 'unknown'}, 'sentinel': 'original'}
        result = reanalyze(Science, self.card, instrument(self.card)[0], self.log,
                           self.rows, {}, producer_qualified=True)
        self.assertEqual(result['original_assessment']['sentinel'], 'original')
        self.assertNotIn('new_assessment', result)

    def test_format_identity(self):
        old = instrument(self.card, format_version=1)[0]
        self.assertEqual(self.check(source=old)['status'], 'unknown')
        self.assertEqual(qualify(self.card, old, self.log, self.rows,
                                producer_qualified=True, format_version=1)['status'], 'qualified')


if __name__ == '__main__':
    unittest.main()
