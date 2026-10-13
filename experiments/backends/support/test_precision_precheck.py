"""Offline preflight and pilot scope; synthetic adapters are not simulator evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SUPPORT = Path(__file__).resolve().parent
sys.path.insert(0, str(SUPPORT))
import precision_breadth_run as runner
from precision_precheck import inspect_plan, pilot_plan


def contract():
    cards = []
    for name in ('a', 'b'):
        cards.append({'id': 'F01_' + name, 'group_id': 'F01', 'family': 'foundation',
            'title': name, 'source': 'module dut(u,y); inout u,y; electrical u,y; analog V(y)<+V(u); endmodule',
            'top': 'dut', 'ports': ['u', 'y'], 'parameters': {},
            'inputs': {'u': [[0, 1], [1e-6, 1]]}, 'outputs': ['y'],
            'scale_V': 1, 'unit_s': 1e-6, 'stop_s': 1e-6})
    return {'cards': cards,
        'profiles': [{'id': n, 'reltol': r, 'vabstol_V': 1e-9,
                      'iabstol_A': 1e-12, 'step_units': 1/32}
                     for n, r in [('base', 1e-3), ('both', 1e-6), ('deep', 1e-8)]],
        'tiers': [{'id': q, 'factor': f} for q, f in [('Q1', 10), ('Q2', 1), ('Q3', .1)]],
        'budgets': {'absolute_V': 1e-8, 'relative': 1e-6}}


class PrecheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.inputs = self.base / 'inputs'
        self.profile = self.base / 'host.json'
        self.profile.write_text('{}')
        for p in (patch.object(runner, 'load_contract', return_value=contract()),
                  patch.object(runner, 'observation_plan', return_value={'times_s': [0, 5e-7, 1e-6]}),
                  patch.object(runner, 'source_files', return_value=[Path(runner.__file__)])):
            p.start()
            self.addCleanup(p.stop)
        runner.freeze(self.inputs)
        self.plan = runner.select_plan(runner.load(self.inputs / 'PLAN.json'), 'evas', 'foundation')

    def reseal(self, path, value):
        """A valid frozen hash alone must not admit a contradictory recipe."""
        path.write_text(json.dumps(value))
        manifest = runner.load(self.inputs / 'MANIFEST.json')
        manifest[str(path.relative_to(self.inputs))] = runner.sha(path)
        runner.checkpoint(self.inputs / 'MANIFEST.json', manifest)

    def test_precheck_reads_frozen_recipe_without_backend_or_writes(self):
        before = {str(p): p.read_bytes() for p in self.inputs.rglob('*') if p.is_file()}
        with patch.object(runner, 'preflight') as backend:
            report = inspect_plan(self.inputs, self.plan)
        backend.assert_not_called()
        self.assertEqual(report['status'], 'ready')
        self.assertEqual(report['slots'], 6)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.inputs.rglob('*') if p.is_file()})

    def test_frozen_wrong_port_binding_stops_before_tool_preflight(self):
        path = self.inputs / self.plan[0]['work'] / 'request.json'
        request = runner.load(path)
        request['instances'][0]['ports']['u'] = 'wrong_input'
        self.reseal(path, request)
        with patch.object(runner, 'preflight') as backend:
            with self.assertRaisesRegex(ValueError, 'EVAS instance binding'):
                runner.run(self.inputs, self.base / 'out', 'evas', self.profile, 'foundation')
        backend.assert_not_called()
        records = runner.load(self.base / 'out' / 'EXECUTION.json')
        self.assertEqual(len(records), 6)
        self.assertTrue(all(r['status'] == 'not_run' for r in records))

    def test_frozen_nonfinite_and_duplicate_observations_rejected(self):
        path = self.inputs / self.plan[0]['work'] / 'requested_times.json'
        for times in ([0, 5e-7, 5e-7, 1e-6], [0, float('nan'), 1e-6], [0, 5e-7]):
            self.reseal(path, times)
            with self.assertRaisesRegex(ValueError, 'observation times'):
                inspect_plan(self.inputs, self.plan)

    def test_profile_binding_cannot_be_changed_by_editing_plan_only(self):
        plan = copy.deepcopy(self.plan)
        plan[0]['profile'] = 'deep'
        with self.assertRaisesRegex(ValueError, 'profile binding'):
            inspect_plan(self.inputs, plan)

    def test_other_backends_wrong_port_order_cannot_pass_recipe_precheck(self):
        complete = runner.load(self.inputs / 'PLAN.json')
        for backend, old, new in [('spectre', 'dut (u y)', 'dut (y u)'),
                                  ('openvaf_r_ngspice', 'N0 u y model0', 'N0 y u model0'),
                                  ('gnucap_modelgen', 'dut(u,y);', 'dut(y,u);')]:
            plan = runner.select_plan(complete, backend, 'foundation')
            path = self.inputs / plan[0]['work'] / plan[0]['deck']
            text = path.read_text()
            self.assertIn(old, text)
            path.write_text(text.replace(old, new))
            manifest = runner.load(self.inputs / 'MANIFEST.json')
            manifest[str(path.relative_to(self.inputs))] = runner.sha(path)
            runner.checkpoint(self.inputs / 'MANIFEST.json', manifest)
            with self.assertRaisesRegex(ValueError, 'instance binding'):
                inspect_plan(self.inputs, plan)

    def test_pilot_covers_each_group_and_actual_profile_and_keeps_order(self):
        selected = pilot_plan(self.plan)
        self.assertEqual([r['label'] for r in selected], ['F01_a--Q1', 'F01_a--Q2', 'F01_a--Q3'])
        reversed_order = pilot_plan(list(reversed(self.plan)))
        self.assertEqual([r['label'] for r in reversed_order], ['F01_b--Q3', 'F01_b--Q2', 'F01_b--Q1'])
        other = {**self.plan[0], 'group_id': 'F02', 'condition': 'F02_a', 'label': 'F02_a--Q1'}
        self.assertEqual(len(pilot_plan([*self.plan, other])), 4)

    def test_typo_in_subset_cannot_silently_remove_required_group(self):
        with self.assertRaisesRegex(ValueError, 'unknown selection group_id'):
            runner.select_plan(self.plan, 'evas', 'foundation', groups=['F01', 'F99_typo'])

    def test_real_root_window_caller_keeps_its_own_family_and_schema(self):
        import root_window_run
        root = self.base / 'root-window'
        root_window_run.freeze(root)
        total = 0
        for style in ('original', 'trace'):
            inputs = root / style
            plan = runner.load(inputs / 'PLAN.json')
            identities = runner.load(inputs / 'SOURCE_IDENTITY.json')
            self.assertEqual(identities['experiments/backends/support/precision_precheck.py'],
                             runner.sha(SUPPORT / 'precision_precheck.py'))
            self.assertEqual(inspect_plan(inputs, plan)['status'], 'ready')
            total += len(plan)
        self.assertEqual(total, 18)

    def test_pilot_receipts_keep_unselected_slots_and_analysis_is_deferred(self):
        def export(backend, tool, env, work):
            (work / 'waveform.csv').write_text('time,y\n0,1\n0.000001,1\n')
            return {'status': 'waveform_available', 'waveform': 'waveform.csv',
                    'stages': [], 'abort_batch': False}
        with patch.object(runner, 'preflight', return_value=({}, {})), patch.object(runner, 'verify_tool'), \
             patch.object(runner, 'execute_one', side_effect=export) as simulate, \
             patch.object(runner, 'read_native') as analyze:
            rows = runner.run(self.inputs, self.base / 'out', 'evas', self.profile, 'foundation',
                              pilot=True, defer_analysis=True)
        self.assertEqual(simulate.call_count, 3)
        analyze.assert_not_called()
        self.assertEqual(len(rows), 6)
        skipped = [r for r in rows if r['status'] == 'not_run']
        self.assertEqual(len(skipped), 3)
        self.assertTrue(all(r['reason'] == 'pilot did not select this frozen slot' for r in skipped))
        start = runner.load(self.base / 'out' / 'STARTED.json')
        self.assertEqual(start['scope'], 'pilot')
        self.assertEqual(len(start['full_selection']), 6)
        self.assertEqual(len(start['selected']), 3)
        timing = runner.load(self.base / 'out' / 'TIMINGS.json')
        self.assertGreaterEqual(timing['precheck_s'], 0)
        self.assertGreaterEqual(timing['artifact_sealing_s'], 0)
        self.assertGreaterEqual(timing['total_s'], timing['artifact_sealing_s'])
        from precision_breadth_reanalysis import verify_lane
        self.assertEqual(verify_lane(self.base / 'out')['status'], 'verified')
        for r in rows[:3]:
            self.assertEqual(r['phase_timings_s']['inline_analysis'], 0)
            self.assertGreaterEqual(r['phase_timings_s']['backend_execution'], 0)
            self.assertEqual(r['analysis_status'], 'pending')

    def test_adapter_failure_retains_elapsed_time_and_attempted_case(self):
        with patch.object(runner, 'preflight', return_value=({}, {})), patch.object(runner, 'verify_tool'), \
             patch.object(runner, 'execute_one', side_effect=RuntimeError('adapter broke')):
            with self.assertRaises(RuntimeError):
                runner.run(self.inputs, self.base / 'out', 'evas', self.profile, 'foundation',
                           defer_analysis=True)
        records = runner.load(self.base / 'out' / 'EXECUTION.json')
        self.assertEqual(records[0]['status'], 'execution_failed')
        self.assertGreaterEqual(records[0]['phase_timings_s']['backend_execution'], 0)
        self.assertEqual(len(records), 6)
        self.assertEqual(runner.load(self.base / 'out' / 'TIMINGS.json')['status'], 'interrupted')


if __name__ == '__main__':
    unittest.main()
