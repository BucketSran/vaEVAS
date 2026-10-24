"""Scientific inputs retain the pre-migration contract and need no backend."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from run_suite import ROOT, T, PROFILES, conditions, netlist, build
from dvs2 import source_files


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class SharedScience(unittest.TestCase):
    def test_source_identity_includes_new_scientific_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            science = root/'evas/validation/dvs2'
            science.mkdir(parents=True)
            (science/'__init__.py').write_text('# synthetic package\n')
            self.assertEqual(set(source_files(root)), {science/'__init__.py'})
            (science/'next_reference.py').write_text('# independent reference\n')
            self.assertIn(science/'next_reference.py', source_files(root))

    def test_original_conditions_profiles_and_decks_remain_fixed(self):
        # Captured from main b2e407fe before extraction. These are input
        # identities, not simulator-derived expected numerical answers.
        cases = conditions()
        self.assertEqual(identity({'T': T, 'profiles': PROFILES, 'conditions': cases}),
                         'a8dbfdfce59aeca52563a8dfcb8b03a8b9d8303e928ea8f92f468638eac2caf8')
        decks = {c['id']+'/'+profile: hashlib.sha256(netlist(c, profile).encode()).hexdigest()
                 for c in cases for profile in PROFILES}
        self.assertEqual(identity(decks),
                         '55140c5843db90a3684f109fd937407caccfd80eb4330558105faa3e3cf43f03')

    def test_scientific_import_needs_no_backend_archive_or_solver(self):
        code = '''
import importlib.abc
import sys
class NoBackend(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {
            'evas', 'experiments', 'run_suite', 'check_results',
            'suite', 'analyze', 'history', 'recheck'
        }:
            raise AssertionError('scientific import reached ' + fullname)
sys.meta_path.insert(0, NoBackend())
sys.path.insert(0, sys.argv[1])
from dvs2 import conditions, check
assert len(conditions()) == 31
assert check.__module__ == 'dvs2.checker'
'''
        with tempfile.TemporaryDirectory() as temporary:
            subprocess.run([sys.executable, '-I', '-B', '-c', code,
                            str(ROOT/'evas/validation')], cwd=temporary, check=True,
                           capture_output=True, text=True)

    def test_new_input_freeze_binds_shared_scientific_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'freeze'
            with contextlib.redirect_stdout(io.StringIO()):
                build(output)
            provenance = json.loads((output/'source_identity.json').read_text())
            for source in (ROOT/'evas/validation/dvs2').glob('*.py'):
                relative = str(source.relative_to(ROOT))
                self.assertEqual(provenance[relative], hashlib.sha256(source.read_bytes()).hexdigest())
                self.assertEqual((output/'analysis-source'/relative).read_bytes(), source.read_bytes())


if __name__ == '__main__':
    unittest.main()
