"""Complete run bundles and failures at the public results entry."""
GUARDS = ['DEV:complete-run-output']

import csv
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / 'rust_core/target/debug/evas-kernel'


class ResultOutputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'm.va'
        self.source.write_text('`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y; analog begin V(y)<+2*V(u)+0.25; end endmodule')
        self.data = dict(models=['m.va'], instances=[dict(name='dut', module='m', connections=dict(u='u', y='y'))], driven=['u'], samples=[[-.5], [0.0], [.75]])
        self.path = self.root / 'sim.json'
        self.path.write_text(json.dumps(self.data))
        self.out = self.root / 'out'

    def cli(self, kernel=KERNEL, *extra):
        return subprocess.run([sys.executable, '-B', '-m', 'evas.results', 'run', str(self.path),
                               '--kernel', str(kernel), '--out', str(self.out), *extra],
                              capture_output=True, text=True, timeout=12,
                              env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')))

    def test_static_csv_matches_independent_answer_and_original_json(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual(manifest['bundle_version'], 1)
        self.assertEqual(manifest['mode'], 'static')
        response = json.loads((self.out / 'result.json').read_text())
        with (self.out / 'observations.csv').open(newline='') as file:
            rows = list(csv.reader(file))
        self.assertEqual(rows[0], ['sample_index', *[f'{node}_V' for node in response['nodes']]])
        index = response['nodes'].index('y')
        self.assertEqual([int(row[0]) for row in rows[1:]], [0, 1, 2])
        self.assertEqual(len(rows), 4)
        for row, solved, expected in zip(rows[1:], response['solutions'], [-.75, .25, 1.75]):
            values = list(map(float, row[1:]))
            self.assertEqual(values, solved['voltages'])
            self.assertAlmostEqual(values[index], expected, delta=1e-9)
        self.assertEqual(manifest['columns'][index+1], dict(name='y_V', node='y', unit='V'))
        self.assertEqual(manifest['identity']['kernel']['status'], 'queried')
        for file in manifest['files']:
            self.assertTrue((self.out / file['path']).is_file())

    def test_transient_csv_time_units_order_and_round_trip(self):
        self.source.write_text('`include "disciplines.vams"\nmodule m(y); output y; electrical y; analog begin V(y)<+idt(1,0.25); end endmodule')
        self.data['instances'][0]['connections'] = dict(y='y')
        self.data.pop('driven')
        self.data.pop('samples')
        self.data.update(transient=dict(sources={}, output_times=[0,.25,.5], stop=.5, max_step=.5), tolerances=dict(reltol=0,vabstol=1e-9))
        self.path.write_text(json.dumps(self.data))
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads((self.out / 'result.json').read_text())
        manifest = json.loads((self.out / 'manifest.json').read_text())
        request = json.loads((self.out / 'request.json').read_text())
        self.assertEqual(request['tolerances'], dict(absolute=1e-9,relative=0))
        with (self.out / 'observations.csv').open(newline='') as file:
            rows = list(csv.reader(file))
        self.assertEqual(rows[0], ['time_s', *[f'{node}_V' for node in response['nodes']]])
        self.assertEqual([float(row[0]) for row in rows[1:]], [0,.25,.5])
        self.assertEqual(manifest['columns'][0], dict(name='time_s',unit='s'))
        self.assertEqual(manifest['mode'], 'transient')
        index = response['nodes'].index('y')
        self.assertEqual(len(rows),4)
        for row, solved, expected in zip(rows[1:], response['solutions'], [.25,.5,.75]):
            values = list(map(float,row[1:]))
            self.assertEqual(values,solved['voltages'])
            self.assertAlmostEqual(values[index],expected,delta=1e-9)

    def test_failure_from_first_input_access_source_and_compile(self):
        for kind in ('missing_input','missing_source','compile','missing_mode','ambiguous_mode'):
            with self.subTest(kind=kind):
                self.out = self.root / kind
                if kind == 'missing_input':
                    self.path.unlink()
                else:
                    self.path.write_text(json.dumps(self.data))
                if kind == 'missing_source':
                    self.source.unlink()
                else:
                    self.source.write_text('`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y; analog begin V(y)<+2*V(u)+0.25; end endmodule' if kind != 'compile' else 'invalid Verilog-A')
                if kind == 'missing_mode':
                    manifest = dict(self.data)
                    manifest.pop('driven'); manifest.pop('samples')
                    self.path.write_text(json.dumps(manifest))
                if kind == 'ambiguous_mode':
                    self.path.write_text(json.dumps(dict(self.data,transient={})))
                result = self.cli()
                self.assertEqual(result.returncode,2,result.stderr)
                self.assertNotIn('Traceback',result.stderr)
                state=json.loads((self.out / 'manifest.json').read_text())
                self.assertEqual(state['status'],'failed')
                self.assertEqual(state['error'],json.loads(result.stderr))
                self.assertFalse((self.out / 'observations.csv').exists())

    def test_directory_conflict_preserves_unrelated_contents(self):
        self.out.mkdir()
        sentinel=self.out/'manifest.json'
        sentinel.write_text('previous bundle')
        result=self.cli()
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertEqual(sentinel.read_text(),'previous bundle')
        self.assertEqual(list(self.out.iterdir()),[sentinel])

    def test_retargeted_kernel_alias_cannot_change_the_inspected_executable(self):
        alias = self.root / 'selected-kernel'
        alias.symlink_to(KERNEL)
        other = self.root / 'other-kernel'
        other.write_text('#!/bin/sh\nexit 9\n')
        other.chmod(0o700)
        script = '''
import sys
from pathlib import Path
import evas.results as results
alias, other = map(Path, sys.argv[1:3])
inspect = results.inspect_identity
def retarget(selected):
    identity = inspect(selected)
    alias.unlink()
    alias.symlink_to(other)
    return identity
results.inspect_identity = retarget
raise SystemExit(results.main(sys.argv[3:]))
'''
        result = subprocess.run([sys.executable, '-B', '-c', script, str(alias), str(other),
                                 'run', str(self.path), '--kernel', str(alias), '--out', str(self.out)],
                                capture_output=True, text=True, timeout=12,
                                env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(alias.resolve(), other.resolve())
        state = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(state['identity']['kernel']['path'], str(KERNEL.resolve()))
        response = json.loads((self.out / 'result.json').read_text())
        column = response['nodes'].index('y')
        self.assertEqual([row['voltages'][column] for row in response['solutions']], [-.75, .25, 1.75])

    def test_missing_installed_metadata_saves_structured_failure(self):
        site = self.root / 'site'
        shutil.copytree(ROOT / 'src/evas', site / 'evas', ignore=shutil.ignore_patterns('__pycache__'))
        result = subprocess.run([sys.executable, '-S', '-B', '-m', 'evas.results', 'run', str(self.path),
                                 '--kernel', str(KERNEL), '--out', str(self.out)],
                                cwd=self.root, capture_output=True, text=True, timeout=12,
                                env=dict(os.environ, PYTHONPATH=str(site)))
        self.assertEqual(result.returncode, 2, result.stderr)
        detail = json.loads(result.stderr)
        self.assertEqual(detail['code'], 'input_error')
        state = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual(state['status'], 'failed')
        self.assertEqual(state['error'], detail)

    def fixture_kernel(self, body):
        path=self.root/'fixture'
        identity=dict(identity_version=1,name='evas-kernel',version='fixture',build_revision=None,
                      ir_schema_version=18,request_protocol_version=None,platform=dict(os='fixture',arch='fixture'))
        path.write_text('#!'+sys.executable+'\nimport json,sys,time\n'
                        +'if sys.argv[1:]==["--version","--json"]:\n print('+repr(json.dumps(identity))+')\n sys.exit(0)\n'
                        +body+'\n')
        path.chmod(0o700)
        return path

    def test_kernel_failure_timeout_truncation_rows_nodes_and_nonfinite(self):
        good=dict(schema_version=18,engine='fixture',nodes=['0','u','y'],solutions=[dict(voltages=[0,-.5,-.75],max_residual_v=0,max_residual_ratio=0),dict(voltages=[0,0,.25],max_residual_v=0,max_residual_ratio=0),dict(voltages=[0,.75,1.75],max_residual_v=0,max_residual_ratio=0)])
        bodies={
            'failure':'sys.stderr.write(\'{"kind":"invalid_request","message":"fixture failure"}\'); sys.exit(2)',
            'timeout':'time.sleep(3)',
            'truncated':'print("{\\\"schema_version\\\":")',
            'fewer_rows':'print('+repr(json.dumps(dict(good,solutions=good['solutions'][:2])))+')',
            'wrong_nodes':'print('+repr(json.dumps(dict(good,nodes=['0','y','u'])))+')',
            'nonfinite':'print('+repr(json.dumps(dict(good,solutions=[dict(voltages=[0,0,float('nan')],max_residual_v=0,max_residual_ratio=0)]*3)))+')'}
        for label,body in bodies.items():
            with self.subTest(label=label):
                self.out=self.root/label
                result=self.cli(self.fixture_kernel(body),'--timeout','0.1')
                self.assertEqual(result.returncode,2,result.stderr)
                state=json.loads((self.out/'manifest.json').read_text())
                self.assertEqual(state['status'],'failed')
                self.assertFalse((self.out/'observations.csv').exists())
                self.assertEqual(state['error'],json.loads(result.stderr))
                if label in ('fewer_rows','wrong_nodes'):
                    self.assertTrue((self.out/'result.json').exists())

    def test_csv_escapes_names_and_preserves_binary64_bits(self):
        import struct
        name='y,\n"quoted'
        self.data['instances'][0]['connections']['y']=name
        self.data['samples']=[[.1],[.10000000000000002],[-.0]]
        self.path.write_text(json.dumps(self.data))
        result=self.cli()
        self.assertEqual(result.returncode,0,result.stderr)
        response=json.loads((self.out/'result.json').read_text())
        with (self.out/'observations.csv').open(newline='') as file:
            rows=list(csv.reader(file))
        index=response['nodes'].index(name)
        self.assertEqual(rows[0][index+1],name+'_V')
        for row,solved in zip(rows[1:],response['solutions']):
            for text,value in zip(row[1:],solved['voltages']):
                self.assertEqual(struct.pack('>d',float(text)),struct.pack('>d',value))

    def test_filesystem_failures_cannot_mark_complete(self):
        script='''
import sys
from pathlib import Path
from evas.results import main
mode=sys.argv.pop(1)
open_original=Path.open
replace_original=Path.replace

def fixture_open(self,*args,**kwargs):
    if self.name=='observations.csv' and mode=='csv':
        raise OSError('fixture CSV write failure')
    return open_original(self,*args,**kwargs)

def fixture_replace(self,target):
    if self.name=='manifest.tmp' and mode=='complete' and '"status": "complete"' in self.read_text():
        raise OSError('fixture completion write failure')
    return replace_original(self,target)
Path.open=fixture_open
Path.replace=fixture_replace
raise SystemExit(main(sys.argv[1:]))
'''
        for mode in ('csv','complete'):
            with self.subTest(mode=mode):
                self.out=self.root/('write-'+mode)
                result=subprocess.run([sys.executable,'-B','-c',script,mode,'run',str(self.path),
                                       '--kernel',str(KERNEL),'--out',str(self.out)],
                                      capture_output=True,text=True,timeout=12,
                                      env=dict(os.environ,PYTHONPATH=str(ROOT/'src')))
                self.assertEqual(result.returncode,2,result.stderr)
                state=json.loads((self.out/'manifest.json').read_text())
                self.assertEqual(state['status'],'failed')
                self.assertEqual(state['error'],json.loads(result.stderr))
                if mode=='csv':
                    self.assertFalse((self.out/'observations.csv').exists())
                else:
                    self.assertTrue((self.out/'observations.csv').exists())

    def test_invalid_timeout_has_structured_failure_state(self):
        result=self.cli(KERNEL,'--timeout','nan')
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertEqual(json.loads((self.out/'manifest.json').read_text())['status'],'failed')
        self.assertNotIn('Traceback',result.stderr)

    def test_wrong_transient_time_coverage_is_failed(self):
        self.source.write_text('`include "disciplines.vams"\nmodule m(y); output y; electrical y; analog begin V(y)<+idt(1,0.25); end endmodule')
        self.data=dict(models=['m.va'],instances=[dict(name='dut',module='m',connections=dict(y='y'))],
                       transient=dict(sources={},output_times=[0,.25,.5],stop=.5,max_step=.5))
        self.path.write_text(json.dumps(self.data))
        response=dict(schema_version=18,engine='fixture',nodes=['0','y'],
                      solutions=[dict(voltages=[0,v],max_residual_v=0,max_residual_ratio=0) for v in [.25,.5,.75]],
                      transient=dict(times=[0,.2,.5],state_names=[],states=[[],[],[]],events=[],accepted_steps=2,discarded_trials=0))
        result=self.cli(self.fixture_kernel('print('+repr(json.dumps(response))+')'))
        self.assertEqual(result.returncode,2,result.stderr)
        state=json.loads((self.out/'manifest.json').read_text())
        self.assertEqual(state['status'],'failed')
        self.assertEqual(state['error']['kind'],'invalid_response')
        self.assertFalse((self.out/'observations.csv').exists())

    def test_unwritable_failure_state_reports_stderr_and_no_marker(self):
        script='''
import sys
from pathlib import Path
from evas.results import main
original=Path.open
def unavailable(self,*args,**kwargs):
    if self.name=='manifest.tmp':
        raise OSError('fixture unavailable output filesystem')
    return original(self,*args,**kwargs)
Path.open=unavailable
raise SystemExit(main(sys.argv[1:]))
'''
        result=subprocess.run([sys.executable,'-B','-c',script,'run',str(self.path),
                               '--kernel',str(KERNEL),'--out',str(self.out)],
                              capture_output=True,text=True,timeout=12,
                              env=dict(os.environ,PYTHONPATH=str(ROOT/'src')))
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertIn('output_write_error',json.loads(result.stderr))
        self.assertFalse((self.out/'manifest.json').exists())
