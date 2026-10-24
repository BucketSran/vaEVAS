"""Public raw IR ownership must reject silent event loss before simulation.

The fixture is the unchanged original reset counterexample. The oracle is the
IR33 source-owner invariant, with a truly legacy and a fully owned execution
control. It does not reinterpret source primitive rounding.
"""
GUARDS = ['LANG', 'EVENT-ORDER']
import json
import os
from pathlib import Path
import subprocess
import unittest

REQUEST = Path(__file__).parents[1] / 'rust_core/src/raw_event_owner_request.json'

class RawEventOwners(unittest.TestCase):
    def request(self):
        return json.loads(REQUEST.read_text())

    def invoke(self, request):
        result = subprocess.run([os.environ['EVAS_KERNEL']], input=json.dumps(request),
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            return result, json.loads(result.stderr)
        return result, json.loads(result.stdout)

    def reject(self, request):
        process, response = self.invoke(request)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(response['kind'], 'invalid_ir', response)
        self.assertEqual(process.stdout, '')

    def owned(self):
        q = self.request()
        e = q['program']['events'][0]
        e.update(procedure_id=0, expanded_statement_ordinal=1)
        q['program']['procedures'][0]['body'].append(dict(
            expanded_statement_ordinal=1, action=dict(kind='event_gate', event=0)))
        return q

    def test_original_mixed_raw_event_cannot_succeed_without_owner(self):
        self.reject(self.request())

    def test_legacy_empty_procedures_executes_timer_and_preserves_idt(self):
        q = self.request()
        q['program']['procedures'] = []
        for event in q['program']['events']:
            event.pop('procedure_id', None)
            event.pop('expanded_statement_ordinal', None)
        process, response = self.invoke(q)
        self.assertEqual(process.returncode, 0, response)
        self.assertEqual(response['transient']['states'][-1], [0])
        # Reset stays asserted until t=2, then integrates u=1 to t=3.
        self.assertAlmostEqual(response['solutions'][-1]['voltages'][-1], 1.25)

    def test_matching_gate_executes_original_timer(self):
        process, response = self.invoke(self.owned())
        self.assertEqual(process.returncode, 0, response)
        self.assertEqual(response['transient']['states'][-1], [0])
        self.assertAlmostEqual(response['solutions'][-1]['voltages'][-1], 1.25)

    def test_equal_arms_cannot_hide_unowned_event_drop(self):
        q = json.loads(REQUEST.with_name('raw_event_marker_request.json').read_text())
        selected = q['program']['events'][-1]['body'][0]['rhs']
        selected['then_value']['constant'] = 1
        selected['else_value']['constant'] = 1
        self.reject(q)
        procedure = q['program']['procedures'][0]
        ordinal = max(step['expanded_statement_ordinal'] for step in procedure['body']) + 1
        event_index = len(q['program']['events']) - 1
        q['program']['events'][event_index].update(
            procedure_id=procedure['procedure_id'], expanded_statement_ordinal=ordinal)
        procedure['body'].append(dict(expanded_statement_ordinal=ordinal,
                                     action=dict(kind='event_gate', event=event_index)))
        process, response = self.invoke(q)
        self.assertEqual(process.returncode, 0, response)
        self.assertEqual(response['transient']['states'][-1][q['program']['events'][event_index]['body'][0]['state']], 1)

    def test_partial_and_orphan_metadata_reject(self):
        for field in ('procedure_id', 'expanded_statement_ordinal'):
            q = self.request()
            q['program']['procedures'] = []
            q['program']['events'][0][field] = 0
            with self.subTest(field=field):
                self.reject(q)

    def test_mismatched_gate_metadata_and_cross_instance_reject(self):
        for field, value in (('procedure_id', 9), ('expanded_statement_ordinal', 5)):
            q = self.owned()
            q['program']['events'][0][field] = value
            with self.subTest(field=field):
                self.reject(q)
        q = self.owned()
        q['program']['events'][0]['origin']['instance'] = 'other'
        self.reject(q)

    def test_missing_gate_rejects_even_with_declared_metadata(self):
        q = self.owned()
        q['program']['procedures'][0]['body'].pop()
        self.reject(q)

if __name__ == '__main__':
    unittest.main()
