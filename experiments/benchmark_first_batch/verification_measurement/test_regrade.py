"""Integrity and exact-case refusal tests; no Spectre or candidate execution."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

PATH=Path(__file__).with_name('regrade_measurement.py')
SPEC=importlib.util.spec_from_file_location('strict_measurement_regrade',PATH)
R=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


class RegradeIntegrity(unittest.TestCase):
    def archive(self,directory,payload=b'raw waveform'):
        path=directory/'job.tar.gz'
        with tarfile.open(path,'w:gz') as stream:
            member=tarfile.TarInfo('run/raw.psf');member.size=len(payload)
            stream.addfile(member,io.BytesIO(payload))
        receipt={'package':{'sha256':R.digest(path.read_bytes()),'bytes':path.stat().st_size},
                 'members':{'run/raw.psf':{'sha256':R.digest(payload),'bytes':len(payload)}}}
        return path,receipt

    def test_verified_bytes_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            path,receipt=self.archive(Path(temporary))
            archive=R.SealedArchive(path,receipt)
            try:self.assertEqual(archive.read('run/raw.psf'),b'raw waveform')
            finally:archive.close()

    def test_archive_digest_corruption_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            path,receipt=self.archive(Path(temporary))
            receipt['package']['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'archive receipt SHA256'):
                R.SealedArchive(path,receipt)

    def test_member_digest_corruption_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            path,receipt=self.archive(Path(temporary))
            receipt['members']['run/raw.psf']['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'member receipt mismatch'):
                R.SealedArchive(path,receipt)

    def test_any_frozen_case_change_refused(self):
        original={'name':'x','stop':1e-6,'signals':['clk'],
                  'support':{'device.va':'original bytes'},'parameter':{'gain':2.0}}
        R.require_same_case(original,json.loads(json.dumps(original)))
        variants=[dict(original,stop=2e-6),dict(original,signals=['ref']),
                  dict(original,support={'device.va':'changed bytes'}),
                  dict(original,parameter={'gain':2}),dict(original,extra='new')]
        for changed in variants:
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(ValueError,'case values differ'):
                    R.require_same_case(changed,original)


if __name__=='__main__':unittest.main()
