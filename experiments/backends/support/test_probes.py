"""A time-resolution rerun must preserve the experiment's physical question."""
import json
from pathlib import Path
import tempfile
import unittest

from probes import freeze, verify, ROOT


class TimeResolutionFreeze(unittest.TestCase):
    def test_only_gnucap_time_setting_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            old, new = base/'original', base/'refined'
            freeze(old)
            freeze(new, gnucap_time_bits=24)
            verify(old)
            verify(new)
            changed = []
            for path in old.rglob('*'):
                if not path.is_file() or path.name == 'INPUT_MANIFEST.json':
                    continue
                relative = path.relative_to(old)
                if path.read_bytes() != (new/relative).read_bytes():
                    changed.append(relative)
                    self.assertEqual(relative.parts[0], 'gnucap_modelgen')
                    self.assertIn(path.name, ('tb.gc', 'requested_settings.json'))
                    if path.name == 'tb.gc':
                        before, after = path.read_text().splitlines(), (new/relative).read_text().splitlines()
                        differences = [(a,b) for a,b in zip(before,after) if a != b]
                        self.assertEqual(len(before), len(after))
                        self.assertEqual(len(differences), 1)
                        a,b = differences[0]
                        self.assertEqual([s for s in a.split() if not s.startswith('dtmin=')],
                                         [s for s in b.split() if not s.startswith('dtmin=')])
            cards = json.loads((ROOT/'evas/validation/support/cases-v2.json').read_text())['cards']
            self.assertEqual(len(changed), 2*len(cards))
            for card in cards:
                settings = json.loads((new/'gnucap_modelgen'/card['id']/'requested_settings.json').read_text())
                quantum = settings.pop('gnucap_dtmin_s')
                original = json.loads((old/'gnucap_modelgen'/card['id']/'requested_settings.json').read_text())
                self.assertEqual(settings, original)
                self.assertEqual(settings['stop_s']/quantum, round(settings['stop_s']/quantum))
                self.assertLess(settings['stop_s']/quantum, 2**53)


if __name__ == '__main__':
    unittest.main()
