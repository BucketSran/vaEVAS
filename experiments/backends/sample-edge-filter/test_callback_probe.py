import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import callback_probe as probe


class ProbeFailureReceipt(unittest.TestCase):
    def test_execution_failure_preserves_receipt_and_returns_failure(self):
        # No simulator is mocked as a success. This checks the runner's exit
        # contract with an explicit failed process result.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root/'inputs'
            case = inputs/'case'
            case.mkdir(parents=True)
            (case/'dut.va').write_text('fixture')
            (case/'tb.scs').write_text('fixture')
            probe.save(inputs/'MANIFEST.json', {str(p.relative_to(inputs)):probe.sha(p)
                        for p in case.iterdir()})
            profile = root/'profile.json'
            profile.write_text('{}')
            output = root/'results'
            with patch.object(probe,'preflight',return_value=({'binary':'unused','setup':''},{})), \
                 patch.object(probe,'verify_tool'), \
                 patch.object(probe,'stage',return_value={'cleanup':{'complete':True}}), \
                 patch.object(probe,'stage_failure',return_value='controlled failure'):
                with self.assertRaises(SystemExit) as caught:
                    probe.run(inputs,output,profile)
                self.assertNotEqual(caught.exception.code,0)
            self.assertTrue((output/'MANIFEST.json').exists())
            self.assertEqual(len(json.loads((output/'RESULTS.json').read_text())),1)


if __name__ == '__main__':
    unittest.main()
