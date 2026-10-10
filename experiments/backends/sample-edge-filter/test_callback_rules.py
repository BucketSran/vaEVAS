"""Calibrate diagnostic receipt checks; these do not simulate circuit behavior."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import callback_rules as rules


class CallbackReceipt(unittest.TestCase):
    def fixture(self, root, count=1):
        inputs, results = root/'inputs', root/'results'
        for i in range(count):
            for parent in (inputs, results):
                work = parent/str(i)
                work.mkdir(parents=True)
                (work/'dut.va').write_text('@(timer(1,0,0.1))')
                (work/'tb.scs').write_text('fixture')
                (work/'probe.json').write_text(json.dumps(dict(start_s=1.,period_s=0.)))
                (work/'requested_settings.json').write_text(json.dumps(dict(stop_s=2.)))
            work=results/str(i)
            (work/'RESULT.json').write_text(json.dumps(dict(execution=dict(stage='simulate',
                status='completed',returncode=0,timeout=False,cleanup=dict(complete=True)))))
            rows=[dict(time=0.,an=0.,cb=0.),dict(time=1.,an=1.,cb=1.),dict(time=2.,an=1.,cb=1.)]
            (work/'rows.json').write_text(json.dumps(rows))
            (work/'spectre.log').write_text('...9.CALLBACK 1 1 0.25\n')
            (work/'psf').mkdir()
            raw=work/'psf/tran.tran.tran'
            raw.write_text('VALUE\n'+''.join(''.join(f'"{k}" {v}\n' for k,v in row.items()) for row in rows)+'END\n')
            p=work/'RESULT.json'; record=json.loads(p.read_text());record['raw_sha256']=rules.sha(raw)
            p.write_text(json.dumps(record))
        rules.save(inputs/'MANIFEST.json', {str(p.relative_to(inputs)):rules.sha(p)
            for p in inputs.rglob('*') if p.is_file()})
        return inputs, results

    def run_analysis(self, root, inputs, results):
        # Seal each intentional calibration fixture after constructing its fault.
        rules.save(results/'MANIFEST.json',{str(p.relative_to(results)):rules.sha(p)
                   for p in results.rglob('*') if p.is_file()})
        with contextlib.redirect_stdout(io.StringIO()):
            rules.analyze(results, root/'analysis.json', inputs)

    def test_progress_prefixed_callback_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); inputs,results=self.fixture(root)
            self.run_analysis(root,inputs,results)

    def test_missing_condition_keeps_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); inputs,results=self.fixture(root,2)
            (results/'1/RESULT.json').unlink()
            with self.assertRaises(SystemExit): self.run_analysis(root,inputs,results)
            report=json.loads((root/'analysis.json').read_text())
            self.assertEqual(report['expected_probe_count'],2)
            self.assertEqual(len(report['records']),2)

    def test_failed_process_with_complete_rows_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); inputs,results=self.fixture(root)
            p=results/'0/RESULT.json'; r=json.loads(p.read_text())
            r['execution']['returncode']=9; p.write_text(json.dumps(r))
            with self.assertRaises(SystemExit): self.run_analysis(root,inputs,results)

    def test_changed_executed_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); inputs,results=self.fixture(root)
            (results/'0/dut.va').write_text('changed')
            with self.assertRaises(ValueError): self.run_analysis(root,inputs,results)

    def test_duplicate_callback_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); inputs,results=self.fixture(root)
            p=results/'0/spectre.log'; p.write_text(p.read_text()*2)
            with self.assertRaises(SystemExit): self.run_analysis(root,inputs,results)

    def test_rows_cannot_be_substituted_for_native_waveform(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); inputs,results=self.fixture(root)
            (results/'0/rows.json').write_text(json.dumps([dict(time=1.,an=1.,cb=1.)]))
            with self.assertRaises(ValueError): self.run_analysis(root,inputs,results)

    def test_raw_hash_must_match_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); inputs,results=self.fixture(root)
            p=results/'0/RESULT.json';record=json.loads(p.read_text());record['raw_sha256']='wrong';p.write_text(json.dumps(record))
            with self.assertRaises(ValueError): self.run_analysis(root,inputs,results)


if __name__=='__main__':
    unittest.main()
