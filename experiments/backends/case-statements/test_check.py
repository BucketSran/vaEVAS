"""Independent positive/negative controls for finite DC comparison accounting."""
import copy
import importlib.util
import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import check


def good():
    expected = dict(y0=3, f0=3, y1=3, f1=4, y2=7, f2=5, y3=9, f3=5, y4=9, f4=5)
    return [dict(time_s=t, Spectre_V=dict(expected), EVAS_V=dict(expected)) for t in check.NATIVE_TIMES]


class Calibration(unittest.TestCase):
    def test_independent_accept_and_full_denominator(self):
        result = check.assess(good())
        self.assertEqual((result['finite_comparison'], result['formal_qualification']), ('P','I'))
        self.assertEqual((result['fixed_scalars'], result['native_scalars']), (90,160))
        self.assertEqual(result['failures'], [])

    def test_wrong_values_keep_full_denominator(self):
        for backend in ('Spectre_V','EVAS_V'):
            rows = good()
            rows[0][backend]['y0'] += .001
            result = check.assess(rows)
            self.assertEqual(result['finite_comparison'],'F')
            self.assertEqual((result['fixed_scalars'],result['native_scalars']),(90,160))
            self.assertTrue(result['failures'])

    def test_missing_duplicate_reordered_times_reject(self):
        rows = good()
        variants = [rows[:-1], rows+[rows[-1]], [rows[0]]+rows[:-1], rows[::-1]]
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                check.assess(variant)

    def test_missing_extra_nonfinite_channels_reject(self):
        for backend in ('Spectre_V','EVAS_V'):
            for action in ('missing','extra','nan','inf','bool'):
                rows = good()
                values = rows[0][backend]
                if action=='missing': del values['f4']
                elif action=='extra': values['surprise']=0
                else: values['f4']={'nan':float('nan'),'inf':float('inf'),'bool':True}[action]
                with self.subTest(backend=backend,action=action), self.assertRaises(ValueError):
                    check.assess(rows)

    def test_compact_false_maximum_or_denominator_reject(self):
        original = check.load(Path(__file__).with_name('comparison.json'))
        for key,value in [('native_scalars',159),('fixed_scalars',89),('finite_comparison','F')]:
            document=copy.deepcopy(original)
            document['result'][key]=value
            with self.assertRaises(ValueError): check.check_compact(document)
        document=copy.deepcopy(original)
        document['result']['maxima']['EVAS_Spectre_V']=1
        with self.assertRaises(ValueError): check.check_compact(document)

    def test_compact_rejects_wrong_fixture_and_checker_identity(self):
        document=check.load(Path(__file__).with_name('comparison.json'))
        for key in ('checker_sha256','shared_psf_parser_sha256'):
            bad=copy.deepcopy(document);bad[key]='0'*64
            with self.assertRaises(ValueError): check.check_compact(bad)
        document['fixture_sha256']['expected.json']='0'*64
        with self.assertRaises(ValueError): check.check_compact(document)

    def test_shared_raw_psf_accept_reject_calibration(self):
        spec=importlib.util.spec_from_file_location("shared_psf_calibration",check.SHARED)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        original=module.tempfile.TemporaryDirectory
        # Keep checker calibration scratch within this task-owned directory.
        with patch.object(module.tempfile,"TemporaryDirectory",side_effect=lambda: original(dir=Path(__file__).parent)):
            self.assertEqual(module.calibrate()["status"],"PASS")

    def test_hash_maps_must_have_complete_required_keys(self):
        original=check.load(Path(__file__).with_name('comparison.json'))
        for field in ('fixture_sha256','raw_artifact_sha256'):
            for change in ('delete_mapping','empty','delete_one','extra','malformed_digest'):
                bad=copy.deepcopy(original)
                if change=='delete_mapping': del bad[field]
                elif change=='empty': bad[field]={}
                elif change=='delete_one': del bad[field][next(iter(bad[field]))]
                elif change=='extra': bad[field]['unexpected']='0'*64
                else: bad[field][next(iter(bad[field]))]='not-a-digest'
                with self.subTest(field=field,change=change):
                    with self.assertRaises(ValueError): check.check_compact(bad)
                    # Raw must refuse before trying to open any missing bundle files.
                    with self.assertRaises(ValueError): check.check_raw(Path('unavailable-bundle'),bad)

    def test_forged_execution_identity_rejects_in_both_entries(self):
        original=check.load(Path(__file__).with_name('comparison.json'))
        for key,value in [('evas_commit','0'*40),('evas_commit','fbf896bbbb6f66a85f2d8be159eb2657ea17f972'),
                          ('kernel_sha256','0'*64),('frontend_syntax_sha256','0'*64),
                          ('engine','fake-engine'),('ir_schema_version',17),('spectre_version','fake'),
                          ('model_sha256','0'*64)]:
            bad=copy.deepcopy(original);bad['execution_identity'][key]=value
            with self.subTest(key=key,value=value):
                with self.assertRaises(ValueError): check.check_compact(bad)
                with self.assertRaises(ValueError): check.check_raw(Path('unavailable-bundle'),bad)
        bad=copy.deepcopy(original)
        bad['fixture_sha256']={};bad['raw_artifact_sha256']={};bad['execution_identity']['evas_commit']='0'*40
        with self.assertRaises(ValueError): check.check_compact(bad)
        with self.assertRaises(ValueError): check.check_raw(Path('unavailable-bundle'),bad)

    def test_tampering_with_receipt_projection_cannot_rebind_execution(self):
        original=check.load(Path(__file__).with_name('comparison.json'))
        bad=copy.deepcopy(original)
        bad['execution_binding']['evas_commit']='0'*40
        bad['execution_identity']['evas_commit']='0'*40
        with self.assertRaises(ValueError): check.check_compact(bad)
        with self.assertRaises(ValueError): check.check_raw(Path('unavailable-bundle'),bad)

    def test_compact_cli_shape_errors_and_scientific_failure_have_distinct_exits(self):
        original=check.load(Path(__file__).with_name('comparison.json'))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'compact.json'
            for bad_backend in ([], None, 'wrong-shape', 1):
                bad=copy.deepcopy(original);bad['observations'][0]['Spectre_V']=bad_backend
                path.write_text(json.dumps(bad))
                run=subprocess.run([sys.executable,'-B',str(check.Path(check.__file__)),'--compact',str(path)],capture_output=True,text=True)
                self.assertEqual(run.returncode,2)
                self.assertEqual(json.loads(run.stdout)['status'],'ERROR')
                self.assertNotIn('finite_comparison',json.loads(run.stdout))
            bad=copy.deepcopy(original);bad['observations'][0]['EVAS_V']['f4']+=.001
            bad['result']=check.assess(bad['observations']);path.write_text(json.dumps(bad))
            run=subprocess.run([sys.executable,'-B',str(check.Path(check.__file__)),'--compact',str(path)],capture_output=True,text=True)
            self.assertEqual(run.returncode,1)
            result=json.loads(run.stdout)['result']
            self.assertEqual(result['finite_comparison'],'F')
            self.assertEqual((result['fixed_scalars'],result['native_scalars']),(90,160))

    def test_raw_cli_adapter_rejects_short_voltage_arrays_as_error(self):
        # Exercise the real CLI handler after an explicitly mocked identity gate.
        # This calibration is not execution/provenance evidence for a synthetic bundle.
        original=check.load(Path(__file__).with_name('comparison.json'))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            bundle=Path(folder)
            response=dict(nodes=list(check.NODES),transient=dict(times=check.NATIVE_TIMES),
                          solutions=[dict(voltages=list(row['EVAS_V'].values())) for row in good()])
            response['solutions'][0]['voltages']=response['solutions'][0]['voltages'][:-1]
            (bundle/'evas-native.stdout.json').write_text(json.dumps(response))
            normalized=[dict(time=row['time_s'],voltages=row['Spectre_V']) for row in good()]
            (bundle/'normalized.json').write_text(json.dumps(dict(rows=normalized)))
            raw=bundle/'collected/spectre/spectre-output/runs/case-statements/psf/tran.tran.tran'
            raw.parent.mkdir(parents=True)
            lines=['VALUE']
            for row in good():
                lines.append('"time" '+str(row['time_s']))
                lines.extend('"'+name+'" '+str(value) for name,value in row['Spectre_V'].items())
            raw.write_text('\n'.join(lines+['END'])+'\n')
            stdout=io.StringIO()
            # Keep main's error mapping, raw_rows and strict shape checks real.
            with patch.object(sys,'argv',['check.py','--raw',str(bundle)]), \
                 patch.object(check,'check_compact',return_value=original['result']), \
                 patch.object(check,'check_raw',side_effect=lambda root,doc: check.assess(check.raw_rows(root))), \
                 contextlib.redirect_stdout(stdout):
                self.assertEqual(check.main(),2)
            result=json.loads(stdout.getvalue())
            self.assertEqual(result['status'],'ERROR')
            self.assertIn('width mismatch',result['reason'])
            self.assertNotIn('finite_comparison',result)

    def test_json_duplicate_keys_reject(self):
        with self.assertRaises(ValueError):
            # Same object-pairs policy as actual compact/raw loading.
            import tempfile
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
                p=Path(folder)/'duplicate.json';p.write_text('{"x":0,"x":1}')
                check.load(p)


if __name__ == '__main__':
    unittest.main()
