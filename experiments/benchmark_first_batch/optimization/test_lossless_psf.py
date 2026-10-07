"""Real gzip artifact integrity/failure checks, not Spectre or speedup evidence."""
import gzip
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('lossless_performance',ROOT/'benchmark/checkers/first_batch_optimization.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
DATA=b'PSFASCII\nVALUE\n'+b'"time" 1.234e-9\n"out" 0.5\n'*10000+b'END\n'


class LosslessPSF(unittest.TestCase):
    def test_real_gzip_roundtrip_all_bytes_and_identities(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'tran.tran.tran';path.write_bytes(DATA)
            record=M.lossless_compress_waveform(path);compressed=path.with_name(path.name+'.gz')
            self.assertFalse(path.exists())
            self.assertEqual(gzip.decompress(compressed.read_bytes()),DATA)
            self.assertEqual(record['raw_bytes'],len(DATA))
            self.assertEqual(record['raw_sha256'],hashlib.sha256(DATA).hexdigest())
            self.assertEqual(record['gzip_sha256'],hashlib.sha256(compressed.read_bytes()).hexdigest())
            self.assertEqual(record['gzip_bytes'],compressed.stat().st_size)
            self.assertTrue(record['roundtrip_verified'])
            self.assertEqual(record['version'],'gzip-lossless-psf-v1')

    def test_corrupt_real_gzip_keeps_raw_and_removes_unverified_copy(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'wave';path.write_bytes(DATA)
            original_open=gzip.open
            def corrupt_then_open(compressed,*args,**kwargs):
                data=bytearray(Path(compressed).read_bytes());data[-8]^=1
                Path(compressed).write_bytes(data)
                return original_open(compressed,*args,**kwargs)
            with patch.object(gzip,'open',side_effect=corrupt_then_open):
                with self.assertRaises((OSError,M.OptimizationEvidenceError)):M.lossless_compress_waveform(path)
            self.assertEqual(path.read_bytes(),DATA)
            self.assertFalse(path.with_name(path.name+'.gz').exists())

    def test_existing_artifact_is_never_overwritten_or_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'wave';path.write_bytes(DATA)
            compressed=path.with_name(path.name+'.gz');compressed.write_bytes(b'preserved')
            with self.assertRaises(FileExistsError):M.lossless_compress_waveform(path)
            self.assertEqual(path.read_bytes(),DATA)
            self.assertEqual(compressed.read_bytes(),b'preserved')

    def test_compression_failure_keeps_raw_and_cleans_partial(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'wave';path.write_bytes(DATA)
            with patch.object(shutil,'copyfileobj',side_effect=OSError('fixture disk write failure')):
                with self.assertRaises(OSError):M.lossless_compress_waveform(path)
            self.assertEqual(path.read_bytes(),DATA)
            self.assertFalse(path.with_name(path.name+'.gz').exists())

    def test_raw_unlink_failure_is_not_reported_as_compact_success(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'wave';path.write_bytes(DATA);original=Path.unlink
            def unlink(target,*a,**kw):
                if target==path:raise OSError('fixture raw unlink failure')
                return original(target,*a,**kw)
            with patch.object(Path,'unlink',unlink):
                with self.assertRaises(OSError):M.lossless_compress_waveform(path)
            self.assertEqual(path.read_bytes(),DATA)
            self.assertFalse(path.with_name(path.name+'.gz').exists())


if __name__=='__main__':unittest.main()
