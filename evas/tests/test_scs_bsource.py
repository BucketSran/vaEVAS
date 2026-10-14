"""Grounded behavioral voltage sources use the same coupled Rust solve as VA."""
GUARDS = ["LANG", "LIN", "COMPOSE", "DEV:scs-input"]

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evas import CompileError
from evas.scs import load_scs, simulate_scs
from test_affine import KERNEL, model


class ScsBehavioralVoltage(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.va=self.root/'m.va'
        self.va.write_text(model('V(y,r)<+gain*V(u,r);','parameter real gain=3;'))
        self.path=self.root/'tb.scs'

    def deck(self, devices, step='.25'):
        self.path.write_text('simulator lang=spectre\nahdl_include "m.va"\n'+devices+
                             '\nDUT (u y 0) m\ntran tran stop=1 maxstep='+step+'\nsave u y\n')
        return self.path

    def test_r01_copy_and_signed_offsets_match_triangle_at_all_samples(self):
        for expression,offset in [('V(x)',0),('V(x)+(0.04)',.04),('V(x)+(0.08)',.08),
                                  ('V(x)+(-0.04)',-.04),('V(x)-delta',-.04)]:
            with self.subTest(expression=expression):
                self.deck('parameters delta=40m\nVX (x 0) vsource type=pwl wave=[0 0 .5 1 1 0]\nB (u 0) bsource v='+expression)
                result=simulate_scs(self.path,kernel=KERNEL)
                for row,voltage in zip(result['saved']['values'],[0,.5,1,.5,0]):
                    self.assertAlmostEqual(row[0],voltage+offset,delta=1e-12)
                    self.assertAlmostEqual(row[1],3*(voltage+offset),delta=1e-12)
                self.assertEqual(result['testbench']['model_sha256'][str(self.va.resolve())],hashlib.sha256(self.va.read_bytes()).hexdigest())

    def test_internal_voltage_feedback_is_solved_not_precomputed(self):
        # y=3u and u=y+.25 imply u=-.125, y=-.375.
        result=simulate_scs(self.deck('B (u 0) bsource v=V(y)+.25'),kernel=KERNEL)
        for u,y in result['saved']['values']:
            self.assertAlmostEqual(u,-.125,delta=1e-12)
            self.assertAlmostEqual(y,-.375,delta=1e-12)

    def test_chains_reverse_terminals_and_statement_order(self):
        devices=['VX (x 0) vsource dc=.5','B1 (a 0) bsource v=V(x)+.25',
                 'B2 (0 u) bsource v=V(a)-.125']
        for order in (devices,devices[::-1]):
            result=simulate_scs(self.deck('\n'.join(order)),kernel=KERNEL)
            self.assertEqual(result['saved']['values'],[[-.625,-1.875]]*5)

    def test_cli_bsource_and_errpreset_produce_result_and_warning(self):
        self.deck('VX (x 0) vsource dc=.5\nB (u 0) bsource v=V(x)+.25')
        self.path.write_text(self.path.read_text().replace('maxstep=.25','maxstep=.25 errpreset=conservative'))
        child=subprocess.run([sys.executable,'-m','evas','simulate',str(self.path),'--kernel',str(KERNEL)],
                             text=True,capture_output=True)
        self.assertEqual(child.returncode,0,child.stderr)
        self.assertEqual(json.loads(child.stdout)['saved']['values'],[[.75,2.25]]*5)
        self.assertEqual(json.loads(child.stderr)['warnings'][0]['option'],'errpreset')

    def test_unsupported_expressions_connections_and_conflicting_sources_reject(self):
        for device in ('B (u 0) bsource i=V(x)', 'B (u 0) bsource v=I(x)',
                       'B (u 0) bsource v=V(x)*2', 'B (u 0) bsource v=V(x)+V(y)',
                       'B (u 0) bsource v=V(x)+1e999', 'B (u 0) bsource v=V(absent)',
                       'B (u y) bsource v=V(x)', 'B (u) bsource v=V(x)',
                       'B (u 0) bsource v=V(x) v=V(y)', 'B (u 0) bsource v=',
                       'B (u 0) bsource v=V(x)\nC (u 0) bsource v=V(y)',
                       'B (u 0) bsource v=V(x)\nVU (u 0) vsource dc=1'):
            with self.subTest(device=device),self.assertRaises(CompileError) as caught:
                load_scs(self.deck('VX (x 0) vsource dc=.5\n'+device))
            self.assertEqual(caught.exception.diagnostic['stage'],'netlist')
            self.assertIn('location',caught.exception.diagnostic)
