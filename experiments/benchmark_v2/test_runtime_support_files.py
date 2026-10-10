"""Immutable source references exercise the verifier before backend execution."""
import hashlib,json,os
from pathlib import Path
import unittest
from unittest.mock import patch
from experiments.benchmark_v2 import test_runtime as protocol

class SupportReferences(unittest.TestCase):
    setUp=protocol.RuntimeProtocolTest.setUp
    run_verifier=protocol.RuntimeProtocolTest.run_verifier
    def configure(self,path='assets/model.spice',sha=None,name='model.spice'):
        asset=self.tests/'assets/model.spice';asset.parent.mkdir(exist_ok=True)
        asset.write_text('original source\n')
        cases=json.loads((self.tests/'cases.json').read_text())
        cases[0]['support_files']={name:{'path':path,'sha256':sha or hashlib.sha256(asset.read_bytes()).hexdigest()}}
        (self.tests/'cases.json').write_text(json.dumps(cases))
        return asset
    def test_referenced_source_runs_exact_bytes_and_receipt_identity(self):
        asset=self.configure()
        report=self.run_verifier()
        self.assertEqual(report['reward'],1)
        self.assertEqual((self.root/'result/probe/model.spice').read_bytes(),asset.read_bytes())
        self.assertEqual(report['cases'][0]['support_sha256']['model.spice'],hashlib.sha256(asset.read_bytes()).hexdigest())
    def test_bad_hash_is_rejected_before_execution(self):
        self.configure(sha='0'*64)
        self.assertEqual(self.run_verifier()['status'],'checker_error')
        self.assertFalse((self.root/'result/probe').exists())
    def test_traversal_is_rejected(self):
        self.configure(path='../outside.spice')
        self.assertEqual(self.run_verifier()['status'],'checker_error')
    def test_symlink_is_rejected_even_inside_root(self):
        asset=self.configure(path='assets/link.spice');asset.with_name('link.spice').symlink_to(asset)
        self.assertEqual(self.run_verifier()['status'],'checker_error')
    def test_nonregular_fifo_is_rejected_without_reading(self):
        asset=self.configure();asset.unlink();os.mkfifo(asset)
        self.assertEqual(self.run_verifier()['status'],'checker_error')
    def test_reference_cannot_override_candidate(self):
        self.configure(name='dut.va')
        self.assertEqual(self.run_verifier()['status'],'checker_error')
    def test_inline_duplicate_is_rejected(self):
        self.configure();p=self.tests/'cases.json';cases=json.loads(p.read_text());cases[0]['support']={'model.spice':'replacement'};p.write_text(json.dumps(cases))
        self.assertEqual(self.run_verifier()['status'],'checker_error')

if __name__=='__main__':unittest.main()
