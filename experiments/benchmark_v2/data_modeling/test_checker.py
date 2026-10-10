"""Checker seam: a full waveform must satisfy independent recorded truth."""
import importlib.util, math, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('v2_data',ROOT/'benchmark/checkers/v2_data.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class CheckerTests(unittest.TestCase):
    def test_sample_error_cannot_be_diluted_by_long_hold(self):
        case={'truth':[[i*1e-9,1.0] for i in range(100)],'tracks':[[10e-9,12e-9]],'holds':[[13e-9,98e-9]],'samples':[12e-9],'stop':99e-9,'limits':{'track_rms':.025,'sample_max':.05,'hold_max':.05}}
        rows=[{'time':i*1e-9,'vhold':1.0 if i!=12 else .8} for i in range(100)]
        with tempfile.TemporaryDirectory() as d:self.assertFalse(mod.evaluate(rows,case,Path(d))['passed'])
    def test_truth_replay_passes_but_missing_and_nan_do_not(self):
        case={'truth':[[0,0],[1,1],[2,1]],'tracks':[[0,1]],'holds':[[1,2]],'samples':[1],'stop':2,'limits':{'track_rms':.025,'sample_max':.05,'hold_max':.05}}
        with tempfile.TemporaryDirectory() as d:
            rows=[{'time':t,'vhold':v} for t,v in case['truth']]
            self.assertTrue(mod.evaluate(rows,case,Path(d))['passed'])
            case['samples']=[math.nextafter(1.0,2.0)]
            self.assertTrue(mod.evaluate(rows,case,Path(d))['passed'])
            self.assertEqual(mod.evaluate(rows[:-1],case,Path(d))['status'],'checker_error')
            rows[1]['vhold']=float('nan');self.assertEqual(mod.evaluate(rows,case,Path(d))['status'],'checker_error')
            rows[1]={'time':1};self.assertEqual(mod.evaluate(rows,case,Path(d))['status'],'checker_error')
            case['truth']=[[0,0],[1,float('nan')],[2,1]];self.assertEqual(mod.evaluate(rows,case,Path(d))['status'],'checker_error')
if __name__=='__main__':unittest.main()
