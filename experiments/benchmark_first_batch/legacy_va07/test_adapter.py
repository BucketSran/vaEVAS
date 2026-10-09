"""VA07 execution seam tests; constructed rows are not Spectre evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'benchmark/checkers'))
import first_batch_triangle as adapter
import triangle_oscillator as oracle
spec=importlib.util.spec_from_file_location('legacy_va07_candidates',Path(__file__).with_name('prepare_candidates.py'))
preparation=importlib.util.module_from_spec(spec);spec.loader.exec_module(preparation)


def case():
    return dict(lo=-.5,hi=.5,initial=0.,direction=1,control=[[0,1],[3,1]],
        stop=3.,maxstep=.25,wave_atol=1e-6,time_atol=2e-7)


def rows():
    # Hand-derived quarter-second observations of three reversals.
    z=[0,.25,.5,.25,0,-.25,-.5,-.25,0,.25,.5,.25,0]
    return [dict(time=i/4,z=value,count=int(i>=2)+int(i>=6)+int(i>=10)) for i,value in enumerate(z)]


class ExecutionAdapter(unittest.TestCase):
    def test_correct_rows_keep_canonical_result(self):
        self.assertEqual(adapter.evaluate(rows(),case()),oracle.evaluate(rows(),case()))
        self.assertTrue(adapter.evaluate(rows(),case())['passed'])

    def test_semantic_count_rejection_is_gradable(self):
        wrong=rows();wrong[4]['count']=.5
        with self.assertRaises(oracle.BehavioralRejection):oracle.evaluate(wrong,case())
        result=adapter.evaluate(wrong,case())
        self.assertFalse(result['passed']);self.assertEqual(result['failures'],['noninteger count'])

    def test_voltage_error_keeps_original_tolerance(self):
        wrong=rows();wrong[4]['z']+=2e-6
        result=adapter.evaluate(wrong,case())
        self.assertFalse(result['passed']);self.assertAlmostEqual(result['max_voltage_error_v'],2e-6)

    def test_incomplete_or_nonfinite_rows_remain_checker_errors(self):
        incomplete=rows()[:-1]
        nonfinite=rows();nonfinite[4]['z']=float('nan')
        for data in (incomplete,nonfinite):
            with self.assertRaises(ValueError):adapter.evaluate(data,case())

    def test_original_cases_and_canonical_copy_frozen(self):
        task=ROOT/'benchmark/tasks/va07-triangle-repair'
        self.assertEqual(hashlib.sha256((task/'tests/cases.json').read_bytes()).hexdigest(),
            'df84f3123a91a8ef6e70818d5437db8e101c871aba8d5da85c7e8302653417e1')
        self.assertEqual((task/'tests/triangle_oscillator.py').read_bytes(),(ROOT/'benchmark/checkers/triangle_oscillator.py').read_bytes())
        self.assertEqual(json.loads((task/'tests/contract.json').read_text())['signals'],['ctl','z','count'])

    def test_historical_variants_match_actual_calibration_identity(self):
        report=json.loads((ROOT/'experiments/backends/dvs2-spectre-validation/results/oscillator-compatibility.json').read_text())
        old={r['family']:r['source_sha256'] for r in report['runs'][1]['results'] if r['kind']=='calibration'}
        with tempfile.TemporaryDirectory() as directory:
            plan=preparation.prepare(Path(directory)/'candidates')
            self.assertEqual(plan['planned_condition_count'],14)
            for candidate in plan['candidates']:
                if candidate['variant']!='reference':
                    self.assertEqual(candidate['candidate_sha256'],old[candidate['variant']])


if __name__=='__main__':unittest.main()
