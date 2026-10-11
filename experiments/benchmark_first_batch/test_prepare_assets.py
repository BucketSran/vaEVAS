"""Private source packaging is bounded and binds all nested source bytes."""
from pathlib import Path
import hashlib,json,os,tempfile,unittest
from experiments.benchmark_first_batch import runtime

class PreparedAssets(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'dut').mkdir()
        self.asset=self.root/'dut/model.spice';self.asset.write_bytes(b'original model\n')
        case={'support_files':{'model.spice':{'path':'dut/model.spice','sha256':hashlib.sha256(self.asset.read_bytes()).hexdigest()}}}
        (self.root/'cases.json').write_text(json.dumps([case]))
    def test_reference_is_packaged_with_exact_nested_key_and_bytes(self):
        assets=runtime.collect_test_assets(self.root)
        self.assertEqual(assets['dut/model.spice'],b'original model\n')
        self.assertEqual(set(assets),{'cases.json','dut/model.spice'})
    def test_changed_model_is_rejected(self):
        self.asset.write_bytes(b'changed')
        with self.assertRaises(ValueError):runtime.collect_test_assets(self.root)
    def test_linked_model_is_rejected(self):
        self.asset.unlink();self.asset.symlink_to(self.root/'cases.json')
        with self.assertRaises(ValueError):runtime.collect_test_assets(self.root)
    def test_linked_directory_is_rejected(self):
        self.asset.unlink();(self.root/'dut').rmdir();(self.root/'dut').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):runtime.collect_test_assets(self.root)
    def test_nonregular_model_is_rejected_without_blocking(self):
        self.asset.unlink();os.mkfifo(self.asset)
        with self.assertRaises(ValueError):runtime.collect_test_assets(self.root)
    def test_path_escape_is_rejected(self):
        p=self.root/'cases.json';cases=json.loads(p.read_text());cases[0]['support_files']['model.spice']['path']='../model.spice';p.write_text(json.dumps(cases))
        with self.assertRaises(ValueError):runtime.collect_test_assets(self.root)
if __name__=='__main__':unittest.main()
