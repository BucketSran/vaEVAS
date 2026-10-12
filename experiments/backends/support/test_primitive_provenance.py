"""Fault calibration for sealed inputs and collected execution identities."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from precision_readback_audit import sha, verify_lane
from primitives_run import analyze, freeze, verify


class Provenance(unittest.TestCase):
    def seal(self, root):
        manifest={str(p.relative_to(root)):{'sha256':sha(p),'bytes':p.stat().st_size}
                  for p in root.rglob('*') if p.is_file() and p != root/'FILE_MANIFEST.json'}
        (root/'FILE_MANIFEST.json').write_text(json.dumps(manifest))

    def test_inventory_and_content_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p=root/'EXECUTION.json';p.write_text('[]');self.seal(root)
            verify_lane(root)
            p.write_text('[ ]')
            with self.assertRaises(ValueError): verify_lane(root)
            p.write_text('[]');(root/'extra').write_text('x')
            with self.assertRaises(ValueError): verify_lane(root)

    def test_nested_manifest_is_not_exempt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'nested').mkdir();p=root/'nested/FILE_MANIFEST.json';p.write_text('{}')
            self.seal(root);verify_lane(root);p.write_text('{ }')
            with self.assertRaises(ValueError):verify_lane(root)

    def test_symlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'real').write_text('x');(root/'alias').symlink_to(root/'real')
            self.seal(root)
            with self.assertRaises(ValueError):verify_lane(root)

    def test_not_run_can_be_analyzed_without_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);lane=root/'lane';lane.mkdir()
            (lane/'EXECUTION.json').write_text(json.dumps([{'backend':'evas','label':'P-sin--Q1','tier':'Q1','status':'not_run'}]))
            self.seal(lane);output=root/'result.json';analyze([lane],output)
            record=json.loads(output.read_text())['records'][0]
            self.assertIsNone(record['result_sha256']);self.assertNotIn('assessment',record)
            with self.assertRaises(ValueError):analyze([lane],output)

    def test_frozen_inputs_and_source_are_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'inputs';freeze(root);verify(root)
            (root/'PLAN.json').write_text('[]')
            with self.assertRaises(ValueError):verify(root)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'inputs';freeze(root);(root/'unlisted').write_text('x')
            with self.assertRaises(ValueError):verify(root)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'inputs';freeze(root)
            source=json.loads((root/'SOURCE_IDENTITY.json').read_text())
            name=next(iter(source['files']))
            original_sha=sha
            with patch('primitives_run.sha',side_effect=lambda p:'changed' if str(p).endswith(name) else original_sha(p)):
                with self.assertRaises(ValueError):verify(root)


if __name__=='__main__':unittest.main()
