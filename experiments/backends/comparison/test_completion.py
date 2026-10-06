"""Synthetic receipt batches test static completion; no backend is launched."""
import copy
import json
from pathlib import Path
import unittest

import test_refresh
from records import ROOT, load, sha, validate, render
from freeze import save


class CompletionControls(unittest.TestCase):
    def setUp(self):
        test_refresh.RefreshControls.setUp(self)
        self.original = copy.deepcopy(self.fresh)
        evas = {r['case']: r for r in self.fresh['records'] if r['dataset']=='cmp8-base' and r['backend']=='evas'}
        for backend in ('evas', 'openvaf_ngspice', 'gnucap'):
            target = self.fresh['targets'][backend]
            started = {'backend': backend, 'tool': {**target, 'kernel_sha256': 'synthetic-new-kernel' if backend=='evas' else None},
                       'runner_sha256': 'synthetic-runner', 'input_manifest_sha256': sha(self.new/'INPUT_MANIFEST.json')}
            start_path = self.work/(backend+'-STARTED.json');save(start_path,started)
            for index, old in enumerate(self.fresh['records']):
                if old['dataset']!='cmp8-base' or old['backend']!=backend: continue
                row=copy.deepcopy(evas[old['case']]);row['backend']=backend
                receipt=load(ROOT/row['execution_receipt']['path'])
                receipt.update(backend=backend,source_revision=target['revision'],runtime_identity=target['runtime_identity'],
                               kernel_sha256=started['tool']['kernel_sha256'],tool=copy.deepcopy(started['tool']),
                               initial_runner_sha256='synthetic-runner',started_sha256=sha(start_path),
                               started={'path':str(start_path.relative_to(ROOT)),'sha256':sha(start_path)},
                               run_directory='synthetic-'+backend,run_id='synthetic-'+backend+'-'+sha(start_path))
                row['measurement'].update(revision=target['revision'],runtime_identity=target['runtime_identity'],
                                          kernel_sha256=started['tool']['kernel_sha256'],run_id=receipt['run_id'])
                path=self.work/(backend+'-'+row['case']+'-complete-receipt.json');save(path,receipt)
                ref={'path':str(path.relative_to(ROOT)),'sha256':sha(path)}
                row['execution_receipt']=ref
                row['evidence']=[e for e in row['evidence'] if e['kind']!='receipt']+[dict(ref,kind='receipt')]
                self.fresh['records'][index]=row
        # A compile failure belongs in the same complete eight-case denominator.
        row=next(r for r in self.fresh['records'] if r['dataset']=='cmp8-base' and r['backend']=='gnucap')
        receipt=load(ROOT/row['execution_receipt']['path'])
        observation=self.work/'synthetic-failed-observation.json';save(observation,{'status':'compile_failed','formal_dvs_qualification':'I'})
        receipt.update(execution_status='compile_failed',waveform_sha256=None,
                       commands=[{'stage':'compile','exit_code':1,'timed_out':False}],
                       observation={'path':str(observation.relative_to(ROOT)),'sha256':sha(observation)})
        row.update(verdict='X',stage='compile',reason='compile_failed',metrics={})
        row['measurement']['output_sha256']=None
        row['evidence']=[e for e in row['evidence'] if e['kind'] not in ('analysis','receipt')]+[dict(receipt['observation'],kind='analysis')]
        self.rebind(row,receipt)
        self.fresh_path.write_text(json.dumps(self.fresh))
        validate(self.fresh)

    def rebind(self,row,receipt):
        path=ROOT/row['execution_receipt']['path'];path.write_text(json.dumps(receipt))
        ref={'path':str(path.relative_to(ROOT)),'sha256':sha(path)}
        row['execution_receipt']=ref
        row['evidence']=[e for e in row['evidence'] if e['kind']!='receipt']+[dict(ref,kind='receipt')]

    def make(self):
        from completion import complete
        return complete(self.parent_path,self.fresh_path,self.old,self.new,self.work/'completion-proof')

    def test_three_full_batches_retain_failed_case_and_parent_evidence(self):
        before={p:sha(p) for p in (self.parent_path,self.fresh_path)}
        result=self.make();validate(result)
        rows=[r for r in result['records'] if r['dataset']=='cmp8-base']
        self.assertEqual(len(rows),32)
        self.assertEqual(sum(r['accounting']=='executed' for r in rows),24)
        self.assertEqual(sum(r['accounting']=='reused' for r in rows),8)
        self.assertEqual(sum(r['verdict']=='X' for r in rows),1)
        self.assertTrue(all(r['qualification']=='I' for r in rows))
        self.assertEqual(result['components'],self.parent['components'])
        text=render(result)
        self.assertIn('三后端共24项新执行结果（含失败）',text)
        self.assertIn('synthetic-new-kernel',text)
        self.assertIn('以下为冻结的parent组件清单',text)
        for line in result['limits']:
            self.assertIn(line,text[:text.index('## '+result['datasets'][0]['label'])])
        self.assertEqual([r for r in result['records'] if r['dataset']!='cmp8-base'],
                         [r for r in self.parent['records'] if r['dataset']!='cmp8-base'])
        self.assertEqual(before,{p:sha(p) for p in before})

    def test_incomplete_new_batch_is_rejected(self):
        self.fresh['records'].pop(next(i for i,r in enumerate(self.fresh['records']) if r['dataset']=='cmp8-base' and r['backend']=='gnucap'))
        self.fresh_path.write_text(json.dumps(self.fresh))
        with self.assertRaises(ValueError): self.make()

    def test_forged_tool_source_runtime_and_duplicate_run_are_rejected(self):
        original=copy.deepcopy(self.fresh)
        paths={ROOT/r['execution_receipt']['path'] for r in original['records'] if r['dataset']=='cmp8-base' and r['backend']=='gnucap'}
        before={p:p.read_bytes() for p in paths}
        for field,value in [('revision','e'*40),('runtime_identity','forged-runtime'),('run_id','duplicate')]:
            with self.subTest(field=field):
                self.fresh=copy.deepcopy(original)
                for path,content in before.items(): path.write_bytes(content)
                rows=[r for r in self.fresh['records'] if r['dataset']=='cmp8-base' and r['backend']=='gnucap']
                other=next(r for r in self.fresh['records'] if r['dataset']=='cmp8-base' and r['backend']=='evas')
                for row in rows:
                    receipt=load(ROOT/row['execution_receipt']['path'])
                    if field=='run_id':
                        row['measurement']['run_id']=other['measurement']['run_id']
                        receipt['run_id']=other['measurement']['run_id']
                    else:
                        row['measurement'][field]=value
                        receipt['source_revision' if field=='revision' else field]=value
                        receipt['tool'][field]=value
                        self.fresh['targets']['gnucap'][field]=value
                    self.rebind(row,receipt)
                self.fresh_path.write_text(json.dumps(self.fresh))
                with self.assertRaises(ValueError): self.make()

    def test_complete_failure_cannot_be_renamed_as_pass(self):
        result=self.make()
        failed=next(r for r in result['records'] if r['dataset']=='cmp8-base' and r['verdict']=='X')
        failed.update(verdict='P',stage='analysis',reason='observations_within_targets')
        with self.assertRaises(ValueError): validate(result)
