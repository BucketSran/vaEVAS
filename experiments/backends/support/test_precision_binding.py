import copy
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from precision_binding_evidence import callback_trace, axes, complete_boundary_search
from precision_binding_run import recipe, TRACE
from precision_v2 import load_contract


class Calibration(unittest.TestCase):
    def setUp(self):
        self.card = copy.deepcopy(load_contract()['cards'][0])
        self.card['expected_events'] = 1
        self.source = self.card['source'].replace('n=n+1; end', 'n=n+1; ' + TRACE + ' end')
        self.rows = [{'time': 0., 'count': 0., 'y': 0., 'u': 0.},
                     {'time': 1e-6, 'count': 1., 'y': .2, 'u': .2},
                     {'time': 2e-6, 'count': 1., 'y': .2, 'u': .3}]
        self.log = 'EVAS_CALLBACK 1 9.9999999999999995e-07\n'

    def test_same_run_callback_bound(self):
        value = callback_trace(self.card, self.source, self.log, self.rows)
        lo, hi = value['events'][0]['time_bounds_s']
        self.assertEqual([lo, hi], [1e-6, 1e-6])

    def test_missing_extra_duplicate_malformed_trace_rejected(self):
        for log in ('', self.log * 2, self.log + 'EVAS_CALLBACK 2 2e-6\n',
                    self.log.replace('CALLBACK 1', 'CALLBACK dut 1'),
                    self.log.replace('9.9999999999999995e-07', 'nan'),
                    self.log.replace('9.9999999999999995e-07', '1e-6'),
                    self.log.replace('9.9999999999999995e-07', '0.0000010000000000000000')):
            with self.subTest(log=log), self.assertRaises(ValueError):
                callback_trace(self.card, self.source, log, self.rows)

    def test_other_run_time_counter_value_or_model_rejected(self):
        for key, value in [('time', 1.1e-6), ('time', math.nextafter(1e-6, math.inf)), ('count', 2.), ('y', .3)]:
            rows = copy.deepcopy(self.rows); rows[1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                callback_trace(self.card, self.source, self.log, rows)
        with self.assertRaises(ValueError):
            callback_trace(self.card, self.source + '\n', self.log, self.rows)

    def test_numerical_pass_does_not_hide_missing_evidence(self):
        a = {'error_upper_V': 1e-9, 'error_lower_V': 0., 'hold_drift_upper_V': 0.,
             'hold_drift_lower_V': 0., 'behavior': {'status': 'pass'}, 'observation_issues': [],
             'tiers': {'Q3': {'status': 'pass', 'voltage_budget_V': 1e-7, 'reasons': []}}}
        result = axes(a, {'issues': ['missing runtime maxstep']})['Q3']
        self.assertEqual((result['numerical'], result['evidence'], result['status']),
                         ('pass', 'incomplete', 'evidence_insufficient'))
        a['error_lower_V'] = a['error_upper_V'] = 1e-6
        a['tiers']['Q3']['status'] = 'numerical_error'
        result = axes(a, {'issues': []})['Q3']
        self.assertEqual((result['numerical'], result['evidence']), ('numerical_error', 'complete'))

    def test_broken_event_count_is_not_a_zero_error_pass(self):
        from precision_v2 import assess
        card = load_contract()['cards'][0]
        rows = [{'time': 0., 'u': -.4, 'count': 0., 'y': 1e9},
                {'time': card['stop_s']/2, 'u': .2, 'count': 2., 'y': 1e9},
                {'time': card['stop_s'], 'u': .4, 'count': 2., 'y': 1e9}]
        a = assess(card, rows, load_contract())
        self.assertEqual(a['behavior']['status'], 'behavior_error')
        self.assertEqual(axes(a, {'issues': []})['Q3']['numerical'], 'unavailable')

    def test_dense_boundary_points_do_not_hide_an_observed_side(self):
        card = next(c for c in load_contract()['cards'] if c['id'] == 'LP-RAMP')
        t = 1e-6; reason = 'missing boundary sides: input:u:1'
        a = {'time_serialization_bound_s': 1e-19, 'observation_issues': [reason],
             'error_upper_V': 1e-10, 'hold_drift_upper_V': 0.,
             'tiers': {'Q3': {'status': 'evidence_insufficient', 'reasons': [reason], 'voltage_budget_V': 1e-7}}}
        times = [t-1e-12, t, t+1e-21, t+2e-21, t+4e-21, t+1e-12]
        fixed, witnesses = complete_boundary_search(card, [{'time': x} for x in times], a, load_contract())
        self.assertEqual(fixed['tiers']['Q3']['status'], 'pass')
        self.assertEqual(len(witnesses), 1)
        self.assertEqual(a['observation_issues'], [reason])
        other = copy.deepcopy(a)
        other['tiers']['Q3']['reasons'].append('reference uncertainty exceeds tier limit')
        fixed, _ = complete_boundary_search(card, [{'time': x} for x in times], other, load_contract())
        self.assertEqual(fixed['tiers']['Q3']['status'], 'evidence_insufficient')
        for missing in ([x for x in times if x >= t], times[:-1],
                        [t-1e-19, t, t+1e-19], [t-3e-12, t, t+3e-12]):
            fixed, witnesses = complete_boundary_search(card, [{'time': x} for x in missing], a, load_contract())
            self.assertEqual(fixed['tiers']['Q3']['status'], 'evidence_insufficient')
            self.assertEqual(witnesses, [])

    def test_machine_endpoint_allowed_but_one_ulp_early_is_not(self):
        import tempfile, json
        from inputs import sha
        from precision_v2 import assess
        from test_precision_v2 import sample_rows
        card = load_contract()['cards'][0]
        source = card['source'].replace('n=n+1; end', 'n=n+1; ' + TRACE + ' end')
        for early in (False, True):
            rows = sample_rows(card, -card['event_early_s'])
            if early:
                row = next(r for r in rows if r['count'] == 1)
                row['time'] = math.nextafter(row['time'], -math.inf)
                row['u'] = row['y'] = -.4 + .2 * row['time'] / 1e-6
            changes = [b for a, b in zip(rows, rows[1:]) if a['count'] != b['count']]
            log = ''.join('EVAS_CALLBACK %d %s\n' % (r['count'], format(r['time'], '.17g')) for r in changes)
            proof = callback_trace(card, source, log, rows)
            with tempfile.TemporaryDirectory() as temp:
                base = Path(temp); (base/'trace.txt').write_text(log)
                proof.update(artifact='trace.txt', artifact_sha256=sha(base/'trace.txt'))
                (base/'proof.json').write_text(json.dumps(proof))
                result = assess(card, rows, load_contract(), event_evidence_path=base/'proof.json')
            self.assertEqual(result['tiers']['Q3']['status'], 'behavior_error' if early else 'pass')

    def test_ng_audit_cannot_hide_other_failures_or_identity_drift(self):
        import json, tempfile
        from inputs import sha
        from precision_binding_evidence import qualify_ngspice_step, ROOT
        (ROOT / 'runs').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as temp:
            base = Path(temp); (base/'code.txt').write_text('synthetic mapping calibration')
            (base/'review.txt').write_text('synthetic reviewer fixture')
            audit = {'method': 'installed_binary_parameter_path', 'mapping': 'ngspice-explicit-tmax-v1',
                     'image_id': 'fixture-image', 'controls': ['maxstep', 'stop'],
                     'binary_sha256': 'e9b0e776ac656de5e470f6b339c4a7254c961d77714b4b94f4b71be2422e7b46',
                     'attachments': {str((base/'code.txt').relative_to(ROOT)): sha(base/'code.txt')}}
            (base/'audit.json').write_text(json.dumps(audit))
            refs = {k: {'path': str((base/n).relative_to(ROOT)), 'sha256': sha(base/n)}
                    for k,n in [('artifact','audit.json'), ('review','review.txt')]}
            refs['review']['reviewer'] = 'synthetic test'
            tool = {'images': {'ngspice': {'config_id': 'fixture-image'}}}
            req = {'maxstep_s': 4e-10, 'stop_s': 8e-6}
            gap = 'maxstep/stop have no runtime echo or verified installed-version parameter path'
            q = {'issues': [gap]}
            self.assertEqual(qualify_ngspice_step(q, req, tool, refs)['status'], 'qualified')
            bad = {'issues': [gap, 'integration method missing or unexpected']}
            self.assertEqual(qualify_ngspice_step(bad, req, tool, refs)['issues'], [bad['issues'][1]])
            tool['images']['ngspice']['config_id'] = 'other-image'
            self.assertEqual(qualify_ngspice_step(q, req, tool, refs)['issues'], [gap])
            tool['images']['ngspice']['config_id'] = 'fixture-image'
            (base/'code.txt').write_text('changed')
            self.assertEqual(qualify_ngspice_step(q, req, tool, refs)['issues'], [gap])

    def test_recipe_preserves_all_original_v2_inputs(self):
        # Generated baseline recipes must equal independently retained original
        # frozen input files, if the local evidence archive is available.
        root = Path(__file__).resolve().parents[3] / 'runs/precision-tiers-20261011/inputs/runs'
        if not root.exists(): self.skipTest('original local archive unavailable')
        data = load_contract()
        import json
        for c in data['cards']:
            for b in ('spectre', 'evas', 'openvaf_r_ngspice', 'gnucap_modelgen'):
                for name, value in recipe(c, data['profiles'][0], b).items():
                    old = root / b / (c['id'] + '--base') / name
                    actual = old.read_text() if isinstance(value, str) else json.loads(old.read_text())
                    self.assertEqual(value, actual, (c['id'], b, name))


if __name__ == '__main__': unittest.main()
