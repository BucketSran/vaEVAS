"""Voltage-testbench adapter checked against manually authored input and answers."""
GUARDS = ["LANG", "DEV:scs-input"]

import json
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import warnings
from evas import CompileError, Instance, KernelError, compile_sources, transient
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

    def test_saved_grid_preserves_off_grid_source_corners_for_interpolation(self):
        # A narrow triangle is invisible on [0, .5, 1]. Its independent
        # answer at .3125 is .5 V at u and 1.5 V at y.
        self.deck('Vin (u 0) vsource type=pwl wave=[0 0 .25 0 .375 1 .4375 0 2 0]',
                  tran='tran tran stop=1 maxstep=.5')
        actual=simulate_scs(self.path,kernel=KERNEL)
        self.assertEqual(actual['saved']['times'],[0,.25,.375,.4375,.5,1])
        self.assertEqual(actual['saved']['values'],[[0,0],[0,0],[3,1],[0,0],[0,0],[0,0]])
        a,b=actual['saved']['times'][1:3]
        left,right=actual['saved']['values'][1:3]
        interpolated=[x+(.3125-a)/(b-a)*(y-x) for x,y in zip(left,right)]
        self.assertEqual(interpolated,[1.5,.5])

    def test_saved_grid_unions_corners_of_multiple_sources_once(self):
        self.deck('Vin (u 0) vsource type=pwl wave=[0 0 .125 1 1 0]\n'
                  'Vaux (aux 0) vsource type=pwl wave=[0 0 .125 2 .375 0 1 0]',
                  tran='tran tran stop=1 maxstep=.5')
        self.assertEqual(load_scs(self.path).manifest['transient']['output_times'],[0,.125,.375,.5,1])

    def test_saved_grid_keeps_pulse_corners_without_resampling_source(self):
        source='Vin (u 0) vsource type=pulse val0=0 val1=1 delay=.125 rise=.125 width=.125 fall=.125 period=1'
        self.deck(source,tran='tran tran stop=1 maxstep=1')
        actual=simulate_scs(self.path,kernel=KERNEL)
        self.assertEqual(actual['saved']['times'],[0,.125,.25,.375,.5,1])
        self.assertEqual([row[1] for row in actual['saved']['values']],[0,0,1,1,0,0])

    def test_source_corners_count_towards_total_output_budget(self):
        self.deck('Vin (u 0) vsource type=pwl wave=[0 0 .125 0 .25 1 .375 0 1 0]',
                  tran='tran tran stop=1 maxstep=.5')
        with patch('evas.scs.POINT_BUDGET',5),self.assertRaisesRegex(CompileError,'output point budget.*source corners'):
            load_scs(self.path)

    def test_iabstol_warns_without_changing_voltage_request_or_solution(self):
        self.deck(extra='opts options reltol=0 vabstol=1n')
        baseline=load_scs(self.path)
        expected=simulate_scs(self.path,kernel=KERNEL)
        for value in ('0','1f','2m'):
            with self.subTest(value=value):
                self.deck(extra=f'parameters current_tol={value}\nopts options reltol=0 vabstol=1n iabstol=current_tol')
                with self.assertWarnsRegex(UserWarning,'iabstol.*ignored.*no effect'):
                    bench=load_scs(self.path)
                self.assertEqual(bench.manifest,baseline.manifest)
                with self.assertWarnsRegex(UserWarning,'iabstol.*ignored'):
                    actual=simulate_scs(self.path,kernel=KERNEL)
                self.assertEqual(actual['solutions'],expected['solutions'])
                self.assertEqual(actual['saved']['values'],[[0,0],[1.5,.5],[3,1],[1.5,.5],[0,0]])
                report=actual['testbench']['warnings'][0]
                self.assertEqual(report['code'],'ignored_scs_option')
                self.assertEqual(report['option'],'iabstol')
                self.assertEqual(report['severity'],'warning')
                self.assertEqual(report['location']['source'],str(self.path.resolve()))
                self.assertEqual(report['location']['line'],7)
                self.assertEqual(report['requested_value'],dict(zip(('0','1f','2m'),(0.,1e-15,.002)))[value])

    def test_iabstol_warning_cli_preserves_json_on_success_and_later_failure(self):
        for extra,exit_code in [('',0),('\nbad options mystery=1',2)]:
            with self.subTest(extra=extra):
                self.deck(extra='opts options iabstol=1f'+extra)
                child=subprocess.run([sys.executable,'-m','evas','simulate',str(self.path),'--kernel',str(KERNEL)],
                                     text=True,capture_output=True)
                self.assertEqual(child.returncode,exit_code,child.stderr)
                report=json.loads(child.stderr)
                self.assertEqual(report['warnings'][0]['option'],'iabstol')
                if exit_code==0:
                    self.assertEqual(json.loads(child.stdout)['testbench']['warnings'],report['warnings'])
                else:
                    self.assertEqual(child.stdout,'')
                    self.assertEqual(report['code'],'unsupported_scs')

    def test_invalid_or_duplicate_iabstol_still_rejects(self):
        for settings in ('iabstol=-1f','iabstol=1e999','iabstol=[1f]',
                         'iabstol=missing','iabstol=1f iabstol=2f',
                         'iabstol=1f\nmore options iabstol=2f'):
            with self.subTest(settings=settings),warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                with self.assertRaises(CompileError):
                    load_scs(self.deck(extra='opts options '+settings))

    def test_iabstol_warning_location_identifies_setting_not_constant_or_statement(self):
        self.deck(extra='parameters iabstol=1f\niabstol options reltol=iabstol \\\n  iabstol=1f')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always',UserWarning)
            bench=load_scs(self.path)
        self.assertEqual(len(caught),1)
        location=bench.metadata['warnings'][0]['location']
        self.assertEqual((location['line'],location['column']),(8,3))

    def test_strobe_controls_reach_kernel_without_changing_output_grid(self):
        self.deck(tran='tran tran stop=1 maxstep=.25 strobetimes=[.125 .625] strobeperiod=.25 strobedelay=.0625 skipstart=.25 skipstop=.75')
        actual=simulate_scs(self.path,kernel=KERNEL)
        program=compile_sources({str(self.root/'m.va'):self.va},[Instance('DUT','m',dict(u='u',y='y',r='0'),dict(gain=3))])
        expected=transient(program,{'u':[[0,0],[.5,1],[1,0]]},[0,.25,.5,.75,1],stop=1,max_step=.25,kernel=KERNEL,
            strobetimes=[.125,.625],strobeperiod=.25,strobedelay=.0625,skipstart=.25,skipstop=.75)
        self.assertEqual(actual['strobe_evidence'],expected['strobe_evidence'])
        self.assertEqual(actual['strobe_evidence']['times'],[.125,.3125,.5625,.625])
        self.assertEqual(actual['saved']['times'],[0,.25,.5,.75,1])
        self.assertEqual(actual['solutions'],expected['solutions'])

    def test_explicit_strobeoutput_retains_terminal_and_selects_forced_rows(self):
        for policy,times in [('all',[0,.125,.25,.5,.625,.75,1]),('strobeonly',[.125,.625,1])]:
            with self.subTest(policy=policy):
                self.deck(tran=f'tran tran stop=1 maxstep=.25 strobetimes=[.125 .625] strobeoutput={policy}')
                result=simulate_scs(self.path,kernel=KERNEL)
                self.assertEqual(result['saved']['times'],times)
                self.assertEqual([row[1] for row in result['saved']['values']],
                                 [2*t if t<=.5 else 2*(1-t) for t in times])

    def test_periodic_strobeonly_keeps_regular_rows_outside_window(self):
        self.deck(tran='tran tran stop=1 maxstep=.25 strobeperiod=.25 strobedelay=.125 skipstart=.2 skipstop=.8 strobeoutput=strobeonly')
        result=simulate_scs(self.path,kernel=KERNEL)
        self.assertEqual(result['strobe_evidence']['times'],[.325,.575])
        self.assertEqual(result['saved']['times'],[0,.325,.575,1])

    def test_strobeoutput_without_strobes_preserves_regular_rows(self):
        self.deck();expected=simulate_scs(self.path,kernel=KERNEL)
        for policy in ('all','strobeonly'):
            self.deck(tran=f'tran tran stop=1 maxstep=.25 strobeoutput={policy}')
            result=simulate_scs(self.path,kernel=KERNEL)
            self.assertEqual(result['saved'],expected['saved'])
            self.assertEqual(result['solutions'],expected['solutions'])

    def test_explicit_points_do_not_hide_an_empty_periodic_strobeonly_schedule(self):
        self.deck(tran='tran tran stop=1 maxstep=.25 strobeperiod=.25 '
                  'strobedelay=.125 skipstart=.2 skipstop=.25 '
                  'strobetimes=[.625] strobeoutput=strobeonly')
        with self.assertRaisesRegex(CompileError, 'empty periodic schedule'):
            load_scs(self.path)

    def test_strobeoutput_policies_preserve_complete_timer_history_and_observations(self):
        (self.root/'m.va').write_text(model('''@(initial_step) q=0;
            @(timer(0.125,0.25)) q=V(u,r); V(y,r)<+gain*q;''','parameter real gain=2; real q;'))
        results=[]
        for policy in ('all','strobeonly'):
            self.deck(tran=f'tran tran stop=1 maxstep=.25 strobetimes=[.125 .625] strobeoutput={policy}')
            results.append(simulate_scs(self.path,kernel=KERNEL))
        for key in ('solutions','transient','strobe_evidence','observation_evidence'):
            self.assertEqual(results[0][key],results[1][key],key)
        self.assertNotEqual(results[0]['saved']['times'],results[1]['saved']['times'])

    def test_errpreset_warns_and_preserves_explicit_and_default_controls(self):
        for options in ('','opts options vabstol=1n reltol=1u'):
            self.deck(extra=options)
            baseline=load_scs(self.path)
            expected=simulate_scs(self.path,kernel=KERNEL)
            for preset in ('liberal','moderate','conservative'):
                with self.subTest(options=options,preset=preset):
                    self.deck(extra=options,tran='tran tran stop=1 maxstep=.25 errpreset='+preset)
                    # Options after tran must still determine the effective controls.
                    if options:
                        self.path.write_text(self.path.read_text().replace(options+'\n','')+options+'\n')
                    with self.assertWarnsRegex(UserWarning,'errpreset.*ignored'):
                        bench=load_scs(self.path)
                    self.assertEqual(bench.manifest,baseline.manifest)
                    with self.assertWarnsRegex(UserWarning,'errpreset.*ignored'):
                        actual=simulate_scs(self.path,kernel=KERNEL)
                    self.assertEqual(actual['solutions'],expected['solutions'])
                    report=actual['testbench']['warnings'][0]
                    self.assertEqual(report['requested_value'],preset)
                    self.assertEqual(report['effective_controls'],dict(baseline.manifest['tolerances'],max_step=.25))

    def test_errpreset_cli_keeps_both_warnings_when_kernel_fails(self):
        self.deck(extra='opts options iabstol=1f',tran='tran tran stop=1 maxstep=.25 errpreset=conservative')
        child=subprocess.run([sys.executable,'-m','evas','simulate',str(self.path),'--kernel',str(self.root/'missing')],
                             text=True,capture_output=True)
        self.assertEqual(child.returncode,2)
        self.assertEqual(child.stdout,'')
        report=json.loads(child.stderr)
        self.assertEqual(report['code'],'kernel.kernel_process')
        self.assertEqual([w['option'] for w in report['warnings']],['iabstol','errpreset'])

    def test_unknown_malformed_or_duplicate_errpreset_rejects(self):
        for value in ('conservativ','1','[1]','conservative errpreset=moderate'):
            with self.subTest(value=value),self.assertRaises(CompileError):
                load_scs(self.deck(tran='tran tran stop=1 maxstep=.25 errpreset='+value))

    def test_invalid_strobe_settings_fail_in_netlist_with_location(self):
        for controls in ['strobetimes=.1','strobetimes=[.2 .1]','strobetimes=[1.1]',
                         'strobeperiod=0','strobeperiod=[.1]', 'skipstop=.5',
                         'strobeperiod=.1 strobedelay=.1','strobeperiod=1e-20',
                         'strobeoutput=unknown','strobeoutput=1',
                         'strobeperiod=.25 skipstart=.2 skipstop=.25 strobedelay=.125 strobeoutput=strobeonly']:
            with self.subTest(controls=controls),self.assertRaises(CompileError) as caught:
                load_scs(self.deck(tran='tran tran stop=1 maxstep=.25 '+controls))
            self.assertEqual(caught.exception.diagnostic['stage'],'netlist')
            self.assertIn('location',caught.exception.diagnostic)

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
        bench=load_scs(self.path)
        self.assertGreater(bench.manifest['transient']['source_errors']['u'],2e-7)
        with self.assertRaises(KernelError):
            simulate_scs(self.path,kernel=KERNEL)
        original=self.path.read_text()
        self.path.write_text(original+'opts options reltol=0 vabstol=5e-7\n')
        with self.assertRaisesRegex(KernelError,'at y'):
            simulate_scs(self.path,kernel=KERNEL)
        self.path.write_text(original+'opts options reltol=0 vabstol=1e-5\n')
        result=simulate_scs(self.path,kernel=KERNEL)
        proof=result['testbench']['pulse_corner_proofs']['Vin']
        self.assertGreater(proof['voltage_error_bound_V'],2e-7)
        self.assertEqual(proof['value_rounding_error_V'],0.)
        self.assertGreater(len(proof['corners']),0)

    def test_unknown_options_devices_discontinuities_and_sources_reject(self):
        cases=[('Vin (u 0) vsource type=sine ampl=1 freq=1',''),
               ('Vin (u 0) vsource type=dc dc=[0 1]',''),
               ('Vin (u y) vsource dc=1',''),
               ('Vin (u 0) vsource dc=1','R1 (y 0) resistor r=1k'),
               ('Vin (u 0) vsource dc=1','opts options mystery=1p'),
               ('Vin (u 0) vsource dc=1','bad tran stop=1 maxstep=.1 errpreset=unknown'),
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
