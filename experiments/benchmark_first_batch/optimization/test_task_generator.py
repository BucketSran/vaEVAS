"""Generator admission/leakage checks; temporary files are not benchmark tasks."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('optimization_generator',ROOT/'generate_admitted_tasks.py')
G=importlib.util.module_from_spec(spec);spec.loader.exec_module(G)


class Generator(unittest.TestCase):
    def test_pending_or_nonactual_evidence_cannot_admit_a_task(self):
        family=ROOT/'vco_boundstep';cases=json.loads((family/'cases.json').read_text())
        for config,paired in ((dict(admitted=False),{}),(dict(admitted=True),dict(kind='synthetic_fixture'))):
            with self.assertRaises(ValueError):G.admission_policy('optimize-vco-step',config,paired,'a'*64,cases,family)

    def test_functional_replay_requires_current_oracle_and_cases(self):
        family=ROOT/'flash_thresholds'
        record=dict(task_id='optimize-flash-thresholds',role='reference',case='bank-throughput',
                    candidate_sha256=G.sha((family/'reference.va').read_bytes()),replay={'passed':True},
                    replay_checker_sha256=G.sha((family/'evaluate.py').read_bytes()),
                    replay_cases_sha256=G.sha((family/'cases.json').read_bytes()))
        document=dict(kind='actual_waveform_replay_not_new_va_execution',records=[record])
        self.assertEqual(len(list(G.functional_records(document))),1)
        record['replay_checker_sha256']='0'*64
        self.assertEqual(list(G.functional_records(document)),[])
        record['replay_checker_sha256']=G.sha((family/'evaluate.py').read_bytes())
        record['replay_cases_sha256']='0'*64
        self.assertEqual(list(G.functional_records(document)),[])
        document['kind']='synthetic_fixture'
        self.assertEqual(list(G.functional_records(document)),[])

    def test_public_materials_contain_baseline_and_no_reference_source(self):
        # Explicitly synthetic policy exercises packaging only. No actual
        # admission is simulated and no repository task directory is created.
        family=ROOT/'vco_boundstep';cases=json.loads((family/'cases.json').read_text())
        policy=dict(metric='accepted_steps',max_median_ratio=.1,min_winning_pairs=5,admission_evidence_sha256='a'*64)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);runtime=root/'circuit_task.py';runtime.write_text('# fixture runtime only\n')
            task=root/'packaging-fixture'
            G.write_task('optimize-vco-step',policy,family,task,runtime)
            self.assertEqual((task/'environment/public/starter.va').read_bytes(),(family/'baseline.va').read_bytes())
            self.assertEqual((task/'solution/dut.va').read_bytes(),(family/'reference.va').read_bytes())
            self.assertEqual((task/'tests/baseline.va').read_bytes(),(family/'baseline.va').read_bytes())
            for path in (task/'environment/public').rglob('*'):
                if path.is_file():self.assertNotEqual(path.read_bytes(),(family/'reference.va').read_bytes())
            self.assertIn('tuning_vco(control,out)',(task/'instruction.md').read_text())
            self.assertIn('performance_main',(task/'tests/verify.py').read_text())
            with self.assertRaises(FileExistsError):G.write_task('optimize-vco-step',policy,family,task,runtime)

if __name__=='__main__':unittest.main()
