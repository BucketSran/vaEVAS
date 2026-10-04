"""Voltage-testbench adapter checked against manually authored input and answers."""
GUARDS = ["LANG", "DEV:scs-input"]

import json
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest
from evas import CompileError, Instance, compile_sources, transient
from evas.scs import load_scs, simulate_scs
from test_affine import KERNEL, model


class ScsContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.va=model('V(y,r)<+gain*V(u,r);','parameter real gain=2 from (0:inf);')
        (self.root/'m.va').write_text(self.va)
        self.path=self.root/'tb.scs'

    def deck(self, source='Vin (u 0) vsource type=pwl wave=[0 0 .5 1 1 0]', extra='', tran='tran tran stop=1 maxstep=.25'):
        self.path.write_text('simulator lang=spectre\nglobal 0\nahdl_include "m.va"\n'+source+'\nDUT (u y 0) m gain=3\n'+extra+'\n'+tran+'\nsave y u\n')
        return self.path

    def test_pwl_matches_manual_manifest_and_triangle_answer(self):
        self.deck(extra='simulatorOptions options reltol=0 vabstol=1n')
        actual=simulate_scs(self.path,kernel=KERNEL)
        program=compile_sources({str(self.root/'m.va'):self.va},[Instance('DUT','m',dict(u='u',y='y',r='0'),dict(gain=3))])
        expected=transient(program,{'u':[[0,0],[.5,1],[1,0]]},[0,.25,.5,.75,1],stop=1,max_step=.25,kernel=KERNEL,reltol=0,vabstol=1e-9)
        self.assertEqual(actual['solutions'],expected['solutions'])
        self.assertEqual(actual['saved']['values'],[[0,0],[1.5,.5],[3,1],[1.5,.5],[0,0]])
        self.assertEqual(actual['testbench']['effective_tolerances'],dict(vabstol=1e-9,reltol=0))

    def test_dc_units_parameters_reverse_ground_and_cli(self):
        self.deck('parameters level=250m\nVin (0 u) vsource type=dc dc=level',tran='tran tran stop=1u maxstep=250n')
        result=simulate_scs(self.path,kernel=KERNEL)
        self.assertEqual(result['saved']['values'],[[-.75,-.25]]*5)
        child=subprocess.run([sys.executable,'-m','evas','simulate',str(self.path),'--kernel',str(KERNEL)],text=True,capture_output=True)
        self.assertEqual(child.returncode,0,child.stderr)
        self.assertEqual(json.loads(child.stdout)['saved'],result['saved'])

    def test_pulse_corners_preserved_and_independent_of_observation_step(self):
        source='Vin (u 0) vsource type=pulse val0=0 val1=1 delay=.25 rise=.25 width=.25 fall=.25 period=1'
        self.deck(source,tran='tran tran stop=1.5 maxstep=.125')
        result=simulate_scs(self.path,kernel=KERNEL)
        expected=[0,0,0,.5,1,1,1,.5,0,0,0,.5,1]
        self.assertEqual([row[1] for row in result['saved']['values']],expected)
        first=load_scs(self.path).manifest['transient']['sources']
        self.deck(source,tran='tran tran stop=1.5 maxstep=.5')
        self.assertEqual(load_scs(self.path).manifest['transient']['sources'],first)

    def test_pulse_time_rounding_cannot_hide_behind_voltage_residual(self):
        self.deck('Vin (u 0) vsource type=pulse val0=0 val1=1 delay=1e9 rise=.2 width=.2 fall=.2 period=1',
                  tran='tran tran stop=1000000001 maxstep=1000000001')
        with self.assertRaisesRegex(CompileError,'corner.*exactly representable'):
            load_scs(self.path)

    def test_unknown_options_devices_discontinuities_and_sources_reject(self):
        cases=[('Vin (u 0) vsource type=sine ampl=1 freq=1',''),
               ('Vin (u 0) vsource type=dc dc=[0 1]',''),
               ('Vin (u y) vsource dc=1',''),
               ('Vin (u 0) vsource dc=1','R1 (y 0) resistor r=1k'),
               ('Vin (u 0) vsource dc=1','opts options iabstol=1p'),
               ('Vin (u 0) vsource dc=1','bad tran stop=1 maxstep=.1 errpreset=conservative'),
               ('Vin (u 0) vsource type=pwl wave=[0 0 .5 0 .5 1 1 1]',''),
               ('Vin (u 0) vsource type=pulse val0=0 val1=1 delay=0 rise=0 fall=.1 width=.1 period=1','')]
        for source,extra in cases:
            with self.subTest(source=source,extra=extra),self.assertRaises(CompileError) as caught:
                load_scs(self.deck(source,extra))
            self.assertIn(caught.exception.diagnostic['code'],('scs_input','unsupported_scs'))
            self.assertEqual(caught.exception.diagnostic['stage'],'netlist')

    def test_duplicate_unknown_net_and_resource_limit_reject(self):
        for source,extra,tran in [
            ('Vin (u 0) vsource dc=1 dc=2','','tran tran stop=1 maxstep=.1'),
            ('Vin (u 0) vsource dc=1','save absent','tran tran stop=1 maxstep=.1'),
            ('Vin (u 0) vsource dc=1','','tran tran stop=1 maxstep=1e-20')]:
            with self.subTest(extra=extra,tran=tran),self.assertRaises(CompileError):
                load_scs(self.deck(source,extra,tran))

    def test_include_errors_and_multiline_pwl_keep_location(self):
        self.deck('Vin (u 0) vsource type=pwl wave=[0 0\n .5 1\n1 0]')
        self.assertEqual(load_scs(self.path).manifest['transient']['sources']['u'],[[0,0],[.5,1],[1,0]])
        self.path.write_text('ahdl_include "missing.va"\n')
        with self.assertRaises(CompileError) as caught:
            load_scs(self.path)
        self.assertEqual(caught.exception.diagnostic['location']['line'],1)

    def test_malformed_statements_never_leak_index_or_type_errors(self):
        for statement in ('Vin (u 0)', 'Vin (u 0) vsource dc=',
                          'Vin (u 0) vsource wave=[0 0', 'opts options reltol=[1 2]',
                          'ahdl_include', 'save V(u)', 'global 0 1',
                          'Vin (u 0) vsource dc=1e999'):
            self.path.write_text(statement)
            with self.subTest(statement=statement),self.assertRaises(CompileError):
                load_scs(self.path)
