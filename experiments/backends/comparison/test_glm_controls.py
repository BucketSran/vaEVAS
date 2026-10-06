"""Independent GLM follow-up controls; fake worker stages, never simulations."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import sys
import shutil
import unittest
from unittest.mock import patch

import ingest
import runner
import seed
from records import ROOT, load, sha
from freeze import freeze, save


class GlmControls(unittest.TestCase):
    def test_worker_exit_failure_stays_simulate_and_missing_success_result_is_worker(self):
        for code, expected_stage in [(1, 'simulate'), (0, 'worker')]:
            with self.subTest(exit_code=code), tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                inputs=root/'inputs'
                freeze(inputs)
                kernel=root/'fake-kernel'
                reported={'identity_version':1,'name':'evas-kernel','version':'0.13.0',
                          'ir_schema_version':17,'build_revision':None,'request_protocol_version':None,
                          'platform':{'os':'test','arch':'test'}}
                kernel.write_text('#!'+sys.executable+'\nprint('+repr(json.dumps(reported))+')\n')
                kernel.chmod(0o755)  # Identity query only; numerical worker remains mocked.
                args=SimpleNamespace(inputs=inputs,output=root/'output',backend='evas',kernel=kernel,
                                     allocation='synthetic-control',resume_finished_spectre=False)
                stage={'stage':'simulate','exit_code':code,'timed_out':False}
                with patch('runner.execute',return_value=stage) as execute:
                    runner.run(args)
                self.assertEqual(execute.call_count,8)
                rows=load(args.output/'EXECUTION.json')
                self.assertEqual({r['status'] for r in rows},{'execution_failed'})
                self.assertEqual({r['failure_stage'] for r in rows},{expected_stage})

    def test_seed_accepts_explicit_unsupported_and_missing_compile_artifact(self):
        original=seed.load
        def changed(path):
            data=copy.deepcopy(original(path))
            if path==ROOT/seed.HISTORICAL:
                for row,status in zip(data['records'],['confirmed_unsupported','missing_compile_artifact']):
                    row['analysis']={'status':status}
            return data
        with patch('seed.load',side_effect=changed):
            data=seed.create()
        rows=[r for r in data['records'] if r['accounting']=='reused']
        self.assertEqual([r['verdict'] for r in rows[:2]],['U','X'])
        self.assertTrue(all(r['availability']['raw']=='local-only' for r in rows))
        self.assertTrue(all(r['availability']['raw_note'] for r in rows))

    def test_ingest_new_receipts_preserve_status_and_canonical_raw_availability(self):
        # Exercise actual new receipt/record writes using a synthetic execution,
        # with final snapshot validation isolated from unrelated source archives.
        parent=ROOT/'runs/cmp-glm-fix'
        parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            root=Path(directory); inputs=root/'inputs';freeze(inputs)
            snapshot=root/'seed.json';save(snapshot,seed.create())
            data=load(snapshot)
            cases=next(d for d in data['datasets'] if d['id']=='cmp8-base')['cases']
            output=root/'synthetic-execution';output.mkdir()
            save(output/'STARTED.json',{'backend':'evas','input_manifest_sha256':sha(inputs/'INPUT_MANIFEST.json'),
                 'runner_sha256':'synthetic','allocation':'synthetic-only'})
            rows=[]
            for case in cases:
                status='confirmed_unsupported' if not rows else 'missing_compile_artifact'
                work=output/'runs'/case['id']/'base';work.mkdir(parents=True)
                save(work/'requested_settings.json',{})
                rows.append({'backend':'evas','condition':case['id'],'profile':'base','input_identity':case['input_identity'],
                     'analysis':{'status':status},'status':status,'failure_stage':'compile','source_sha256':'synthetic',
                     'tool':{'revision':'unknown','runtime_identity':'synthetic'},'commands':[]})
            save(output/'EXECUTION.json',rows);save(output/'FILE_MANIFEST.json',{})
            compact=root/'compact'
            with patch('ingest.runner_sources',return_value=[]),patch('derive.freeze_candidates'),patch('ingest.validate'):
                result=ingest.ingest(snapshot,inputs,[output],compact)
            actual=[r for r in result['records'] if r['dataset']=='cmp8-base' and r['backend']=='evas']
            self.assertEqual([r['verdict'] for r in actual],['U']+['X']*7)
            for r in actual:
                receipt=load(ROOT/r['execution_receipt']['path'])
                self.assertNotEqual(receipt['run_id'], output.name)
                self.assertEqual(receipt['run_directory'], output.name)
                self.assertEqual(receipt['started_sha256'], sha(output/'STARTED.json'))
                self.assertEqual(r['measurement']['run_id'], receipt['run_id'])
                self.assertEqual(receipt['raw_availability'],'local-only')
                self.assertTrue(receipt['raw_availability_note'])
                self.assertEqual(r['availability']['raw'],'local-only')
                self.assertEqual(r['availability']['raw_note'],receipt['raw_availability_note'])
            other = root/'another-task'/output.name
            shutil.copytree(output, other)
            started = load(other/'STARTED.json')
            started['allocation'] = 'distinct-synthetic-execution'
            (other/'STARTED.json').write_text(json.dumps(started))
            with patch('ingest.runner_sources',return_value=[]),patch('derive.freeze_candidates'),patch('ingest.validate'):
                second = ingest.ingest(snapshot, inputs, [other], root/'second-compact')
            ids = {r['measurement']['run_id'] for r in actual}
            second_ids = {r['measurement']['run_id'] for r in second['records'] if r['dataset']=='cmp8-base' and r['backend']=='evas'}
            self.assertTrue(ids.isdisjoint(second_ids), 'same directory basename must not collapse distinct STARTED identities')


if __name__=='__main__':
    unittest.main()
