"""Shared manifest input checks and CLI / migration failure contracts."""
GUARDS = ["LANG", "DEV:manifest-input"]

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from evas.migrate import recompile_manifests
from test_affine import KERNEL, model


class ManifestContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'m.va').write_text(model('V(y,r)<+V(u,r);'))
        self.good=dict(models=['m.va'],instances=[dict(name='dut',module='m',connections=dict(u='u',y='y',r='0'))],driven=['u','y'],samples=[[1,1],[1,2]])
        self.path=self.root/'sim.json'; self.path.write_text(json.dumps(self.good))

    def cli(self,action,path=None,*extra):
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
        return subprocess.run([sys.executable,'-B','-m','evas',action,str(path or self.path),'--kernel',str(KERNEL),*extra],
                              env=env,text=True,capture_output=True,timeout=10)

    def test_bad_connections_cli_is_a_diagnostic(self):
        self.good['instances'][0]['connections']=['u','y','r']
        self.path.write_text(json.dumps(self.good))
        r=self.cli('compile')
        self.assertEqual(r.returncode,2); self.assertNotIn('Traceback',r.stderr)
        self.assertIn('connections',r.stderr)

    def test_bad_or_deep_item_does_not_abort_batch(self):
        bad=self.root/'bad.json'
        for kind in ('connections','depth'):
            obj=json.loads(json.dumps(self.good))
            if kind=='connections': obj['instances'][0]['connections']=['u','y','r']
            else:
                (self.root/'deep.va').write_text(model('V(y,r)<+'+'('*1500+'1'+')'*1500+';'))
                obj['models']=['deep.va']
            bad.write_text(json.dumps(obj))
            batch=recompile_manifests([bad,self.path],self.root/kind,repo_root=self.root)
            self.assertEqual([x.status for x in batch.results],['failure','success'])
            self.assertTrue((self.root/kind/'summary.json').is_file())

    def test_duplicate_json_fields_rejected_in_cli_and_migration(self):
        self.good['instances'][0]['parameters']={}
        raw=json.dumps(self.good).replace('"parameters": {}','"parameters": {}, "parameters": {}')
        self.path.write_text(raw)
        r=self.cli('compile'); self.assertEqual(r.returncode,2); self.assertIn('duplicate',r.stderr)
        batch=recompile_manifests([self.path],self.root/'out',repo_root=self.root)
        self.assertEqual(batch.results[0].status,'failure'); self.assertIn('duplicate',batch.results[0].diagnostic)

    def test_json_float_overflow_is_rejected_before_compilation(self):
        raw = json.dumps(self.good).replace('"samples": [[1, 1], [1, 2]]', '"samples": [[1e999]]')
        self.path.write_text(raw)
        result = self.cli('compile')
        self.assertEqual(result.returncode, 2)
        self.assertIn('nonfinite', result.stderr)

    def test_cli_kernel_error_is_json_and_keeps_sample(self):
        r=self.cli('solve')
        self.assertEqual(r.returncode,2)
        error=json.loads(r.stderr)
        self.assertEqual(error['kind'],'residual_failure'); self.assertEqual(error['sample'],1)

    def test_cli_timeout_option_reaches_kernel(self):
        child=self.root/'slow'; child.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(5)\n'); child.chmod(0o700)
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
        r=subprocess.run([sys.executable,'-B','-m','evas','solve',str(self.path),'--kernel',str(child),'--timeout','0.1'],
                         env=env,text=True,capture_output=True,timeout=5)
        self.assertEqual(r.returncode,2); self.assertEqual(json.loads(r.stderr)['kind'],'kernel_timeout')
