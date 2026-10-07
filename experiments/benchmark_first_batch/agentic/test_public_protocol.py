"""Compare the published native envelope against the actual configured harness."""
import os
from pathlib import Path
import re
import sys
import unittest
import jsonschema
from public_protocol import ENVELOPE_SCHEMA, NOTE, append_note

sys.path.insert(0, os.environ['CIRCUIT_HARNESS'])
from alphaapollo.common.execution.chips import current_evas_session as session


class ProtocolTests(unittest.TestCase):
    def test_tool_parameters_equal_actual_native_session(self):
        published = {item['if']['properties']['tool']['const']:
                     item['then']['properties']['arguments'] for item in ENVELOPE_SCHEMA['allOf']}
        actual = {item['function']['name']:item['function']['parameters']
                  for item in session.tool_schemas(experiments=False)}
        self.assertEqual(published, actual)
        self.assertEqual(set(ENVELOPE_SCHEMA['properties']['tool']['enum']), set(actual))
        self.assertEqual(set(ENVELOPE_SCHEMA['required']), {'action_id','tool','arguments'})
        self.assertFalse(ENVELOPE_SCHEMA['additionalProperties'])

    def test_envelope_acceptance_matches_actual_request(self):
        ids = ['', 'a', 'a_-0', 'a'*80, 'a'*81, 'a b', 'a\n', '汉', 3, None]
        for tool, fields in session.TOOLS.items():
            if tool == 'evas_experiment':
                continue  # Not enabled in this native session.
            valid = {key:'' for key in fields}
            variants = [valid, {}, {**valid,'unexpected':'x'}]
            if fields:
                variants += [{key:3 for key in fields}, {key:None for key in fields}]
            for identifier in ids:
                for args in variants:
                    request = {'action_id':identifier,'tool':tool,'arguments':args}
                    try: session._request(request); expected = True
                    except ValueError: expected = False
                    try: jsonschema.validate(request, ENVELOPE_SCHEMA); actual = True
                    except jsonschema.ValidationError: actual = False
                    self.assertEqual(actual, expected, repr(request))
        # Unknown tools, missing outer keys and extra outer keys must also agree.
        for request in [{'tool':'evas_read','arguments':{'path':''}},
                        {'action_id':'x','tool':'unknown','arguments':{}},
                        {'action_id':'x','tool':'evas_simulate','arguments':{},'extra':0}]:
            with self.assertRaises(ValueError): session._request(request)
            with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(request, ENVELOPE_SCHEMA)

    def test_note_is_idempotent_and_documents_end_freeze(self):
        self.assertEqual(append_note(append_note('task')), append_note('task'))
        self.assertIn('冻结最近完整候选', NOTE)
        self.assertIn('path为空字符串', NOTE)
        wrapper = Path(os.environ['CIRCUIT_HARNESS'])/'alphaapollo/workflows/harbor_chips/installed_agent.py'
        self.assertRegex(wrapper.read_text(), r'finally:\s+await environment.freeze\(reason\)')


if __name__ == '__main__':
    unittest.main()
