"""Checker seam: a full waveform must satisfy independent recorded truth."""
import copy, importlib.util, json, math, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('v2_data',ROOT/'benchmark/checkers/v2_data.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
CASES=json.loads((ROOT/'benchmark/tasks/v2-data-sampling-identification/tests/cases.json').read_text())
class CheckerTests(unittest.TestCase):
    def test_sample_error_cannot_be_diluted_by_long_hold(self):
        case=copy.deepcopy(CASES[2])
        rows=[{'time':t,'vhold':v-.2 if abs(t-case['samples'][0])<1e-15 else v} for t,v in case['truth']]
        with tempfile.TemporaryDirectory() as d:
            result=mod.evaluate(rows,case,Path(d))
            self.assertFalse(result['passed'])
            self.assertNotEqual(result.get('status'),'checker_error')
            self.assertGreater(result['metrics_V']['sample_max'],.05)
    def test_truth_replay_passes_but_missing_and_nan_do_not(self):
        case=copy.deepcopy(CASES[2])
        with tempfile.TemporaryDirectory() as d:
            rows=[{'time':t,'vhold':v} for t,v in case['truth']]
            self.assertTrue(mod.evaluate(rows,case,Path(d))['passed'])
            case['samples'][0]=math.nextafter(case['samples'][0],math.inf)
            self.assertTrue(mod.evaluate(rows,case,Path(d))['passed'])
            self.assertEqual(mod.evaluate(rows[:-1],case,Path(d))['status'],'checker_error')
            rows[1]['vhold']=float('nan');self.assertEqual(mod.evaluate(rows,case,Path(d))['status'],'checker_error')
            rows[1]={'time':1};self.assertEqual(mod.evaluate(rows,case,Path(d))['status'],'checker_error')
            case['truth']=[[0,0],[1,float('nan')],[2,1]];self.assertEqual(mod.evaluate(rows,case,Path(d))['status'],'checker_error')
    def test_missing_acquisition_observation_is_checker_error(self):
        cases=json.loads((ROOT/'benchmark/tasks/v2-data-sampling-identification/tests/cases.json').read_text())
        case=copy.deepcopy(next(c for c in cases if c['name']=='heldout-0'))
        rows=[{'time':t,'vhold':v} for t,v in case['truth']]
        index=next(i for i,r in enumerate(rows) if abs(r['time']-40.75e-9)<1e-15)
        rows[index]['vhold']+=.5
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(mod.evaluate(rows,case,Path(d))['passed'])
            del case['truth'][index]
            self.assertEqual(mod.evaluate(rows,case,Path(d)).get('status'),'checker_error')
    def test_truncated_truth_tail_is_checker_error(self):
        case=copy.deepcopy(CASES[2])
        rows=[{'time':t,'vhold':v} for t,v in case['truth']]
        del case['truth'][-100:]
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(mod.evaluate(rows,case,Path(d)).get('status'),'checker_error')

    def test_changed_source_value_is_checker_error(self):
        case=copy.deepcopy(CASES[2])
        rows=[{'time':t,'vhold':v} for t,v in case['truth']]
        case['truth'][100][1]+=.1
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(mod.evaluate(rows,case,Path(d)).get('status'),'checker_error')

    def test_all_frozen_experiments_accept_truth_replay(self):
        for case in CASES:
            with self.subTest(case=case['name']),tempfile.TemporaryDirectory() as d:
                rows=[{'time':t,'vhold':v} for t,v in case['truth']]
                self.assertTrue(mod.evaluate(rows,case,Path(d))['passed'])
if __name__=='__main__':unittest.main()
