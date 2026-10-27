"""Synthetic audited-source contracts; these do not certify backend execution."""
from pathlib import Path
import tempfile
import unittest

from actual_observation import EVAS_WORKER_ADAPTER, production_dependencies, producer_identity

PAPER = 'experiments/backends/paper/'
SHARED = 'experiments/backends/evidence/legacy_waveforms.py'
LEGACY = ('experiments/archive/dvs2-starter-pilot/analyze.py',
          'experiments/archive/dvs2-starter-pilot/suite.py')
CONSTRUCTOR = 'evas/validation/paper/case_inputs.py'


def fixture(root, *, legacy=False, constructor=False):
    def put(name, content='# synthetic source\n'):
        target = root/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    for name in ('runner', 'inputs', 'process', 'settings_readback', 'observations'):
        put(PAPER+name+'.py')
    if legacy:
        put(PAPER+'observations.py',
            "READER_DIR = ROOT/'experiments/archive/dvs2-starter-pilot'\n"
            "READER_DEPENDENCIES = (READER_DIR/'analyze.py', READER_DIR/'suite.py')\n")
    else:
        put(PAPER+'observations.py',
            "READER_FILES = ('experiments/backends/evidence/legacy_waveforms.py',)\n"
            "READER_DEPENDENCIES = tuple(ROOT/name for name in READER_FILES)\n")
    if constructor:
        put(PAPER+'inputs.py', "_CASE_INPUTS_PATH = ROOT/'evas/validation/paper/case_inputs.py'\n")
        put(CONSTRUCTOR)
    for name in (*LEGACY, SHARED, 'evas/src/probe.py',
                 'evas/rust_core/src/probe.rs', 'evas/rust_core/ir/src/probe.rs',
                 'evas/pyproject.toml', 'evas/rust_core/Cargo.toml',
                 'evas/rust_core/Cargo.lock', 'evas/rust_core/ir/Cargo.toml'):
        put(name)


class ProducerDependencyContracts(unittest.TestCase):
    def test_audited_migrated_worker_requires_adapter_without_changing_legacy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture(root)
            self.assertNotIn(EVAS_WORKER_ADAPTER, production_dependencies(root))
            runner = root/'experiments/backends/paper/runner.py'
            loader = ("def evas_worker_adapter():\n"
                      "    path = Path(__file__).resolve().parents[3] / "
                      "'evas/validation/adapters/paper_evas_worker.py'\n")
            runner.write_text(loader)
            with self.assertRaisesRegex(ValueError, 'audited production dependency missing'):
                production_dependencies(root)
            adapter = root/EVAS_WORKER_ADAPTER
            adapter.parent.mkdir(parents=True)
            adapter.write_text('# synthetic migrated worker\n')
            sources = production_dependencies(root)
            self.assertIn(EVAS_WORKER_ADAPTER, sources)
            missing = dict(sources)
            missing.pop(EVAS_WORKER_ADAPTER)
            self.assertIn(EVAS_WORKER_ADAPTER, producer_identity(missing, root)['missing_dependencies'])
            changed = dict(sources)
            changed[EVAS_WORKER_ADAPTER] = '0'*64
            self.assertIn(EVAS_WORKER_ADAPTER, producer_identity(changed, root)['changed_dependencies'])
            runner.write_text(loader.replace('parents[3]', 'parents[2]'))
            with self.assertRaisesRegex(ValueError, 'unknown audited EVAS worker adapter contract'):
                production_dependencies(root)

    def test_legacy_and_current_producers_keep_distinct_reader_contracts(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture(root, legacy=legacy)
                sources = production_dependencies(root)
                required, excluded = (LEGACY, (SHARED,)) if legacy else ((SHARED,), LEGACY)
                self.assertTrue(set(required).issubset(sources))
                self.assertTrue(set(excluded).isdisjoint(sources))
                self.assertTrue(producer_identity(sources, root)['verified'])
                mixed = dict(sources)
                mixed[excluded[0]] = '0'*64
                result = producer_identity(mixed, root)
                self.assertFalse(result['verified'])
                self.assertIn(excluded[0], result['unexpected_dependencies'])

    def test_missing_current_reader_does_not_fall_back_to_existing_legacy_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture(root)
            (root/SHARED).unlink()
            self.assertTrue(all((root/name).is_file() for name in LEGACY))
            with self.assertRaisesRegex(ValueError, 'audited production dependency missing'):
                production_dependencies(root)

    def test_shared_constructor_is_required_when_the_audited_worker_imports_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture(root, constructor=True)
            sources = production_dependencies(root)
            self.assertIn(CONSTRUCTOR, sources)
            missing = dict(sources)
            missing.pop(CONSTRUCTOR)
            self.assertIn(CONSTRUCTOR, producer_identity(missing, root)['missing_dependencies'])
            (root/CONSTRUCTOR).unlink()
            with self.assertRaisesRegex(ValueError, 'audited production dependency missing'):
                production_dependencies(root)

    def test_unknown_or_ambiguous_reader_contract_cannot_claim_a_complete_producer(self):
        invalid = [
            "READER_FILES = ('unreviewed/reader.py',)\n",
            "READER_FILES = ()\nREADER_FILES = ()\n",
            "# absent dependency contract\n",
        ]
        for content in invalid:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture(root)
                (root/(PAPER+'observations.py')).write_text(content)
                with self.assertRaises(ValueError):
                    production_dependencies(root)


if __name__ == '__main__':
    unittest.main()
