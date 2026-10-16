"""Omitted pulse delay follows the installed source contract through Rust."""
GUARDS = ["DEV:scs-input"]

from pathlib import Path
import tempfile
import unittest

from evas import CompileError, KernelError
from evas.scs import load_scs, simulate_scs
from test_affine import KERNEL, model


class PulseDelayDefault(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root/'m.va').write_text(model('V(y,r)<+3*V(u,r);'))
        self.path = self.root/'tb.scs'
        self.settings = dict(val0='-.25', val1='.75', rise='.125', fall='.125', width='.25', period='1')

    def deck(self, settings=None, stop='1.75', step='.25', options='reltol=0 vabstol=1n'):
        values = self.settings if settings is None else settings
        source = ' '.join(f'{key}={value}' for key,value in values.items())
        self.path.write_text('simulator lang=spectre\nahdl_include "m.va"\n'
                             'Vin (u 0) vsource type=pulse '+source+'\n'
                             'DUT (u y 0) m\nopts options '+options+'\n'
                             f'tran tran stop={stop} maxstep={step} '
                             'strobetimes=[0 .03125 .125 .25 .375 .5 .625] strobeoutput=all\n'
                             'save u y\n')
        return self.path

    def test_omitted_delay_matches_zero_and_analytic_cycle_under_changed_controls(self):
        # The independent source is -.25+8t on the rise, .75 on the
        # plateau, .75-8(t-.375) on the fall, then -.25 until the next cycle.
        for stop,step in [('1.75','.25'),('.75','.0625')]:
            with self.subTest(stop=stop,step=step):
                path=self.deck(stop=stop,step=step)
                omitted=simulate_scs(path,kernel=KERNEL)
                manifest=load_scs(path).manifest
                self.deck(dict(self.settings,delay='0'),stop,step)
                explicit=simulate_scs(self.path,kernel=KERNEL)
                self.assertEqual(load_scs(self.path).manifest,manifest)
                self.assertEqual(omitted['saved'],explicit['saved'])
                saved=omitted['saved']
                self.assertEqual(saved['times'][0],0)
                self.assertIn(.03125,saved['times'])
                for t,values in zip(saved['times'],saved['values']):
                    phase=t%1
                    expected=(-.25+8*phase if phase<.125 else .75 if phase<.375
                              else .75-8*(phase-.375) if phase<.5 else -.25)
                    self.assertEqual(dict(zip(saved['nodes'],values)),dict(u=expected,y=3*expected))

    def test_only_delay_can_be_omitted_and_explicit_invalid_delay_still_rejects(self):
        for name in self.settings:
            values={key:value for key,value in self.settings.items() if key!=name}
            with self.subTest(missing=name),self.assertRaisesRegex(CompileError,'requires explicit'):
                load_scs(self.deck(values))
        for delay in ('-.125','[0]','1e999','unknown','0 delay=0'):
            with self.subTest(delay=delay),self.assertRaises(CompileError) as caught:
                load_scs(self.deck(dict(self.settings,delay=delay)))
            self.assertEqual(caught.exception.diagnostic['stage'],'netlist')
            self.assertEqual(caught.exception.diagnostic['location']['line'],3)

    def test_default_does_not_bypass_edge_resolution_or_point_budget(self):
        cases=[(dict(self.settings,rise='0'),'1.75','rise/fall/period'),
               (dict(self.settings,fall='0'),'1.75','rise/fall/period'),
               (dict(self.settings,period='0'),'1.75','rise/fall/period'),
               (dict(self.settings,width='-.125'),'1.75','delay/width'),
               (dict(self.settings,width='1'),'1.75','rise\\+width\\+fall'),
               (dict(self.settings,edgetype='exp'),'1.75','linear edges'),
               (dict(self.settings,rise='.0000001',fall='.0000001',width='.0000001',period='.000001'),'1','pulse point budget'),
               (dict(self.settings,period='1e16'),'10000000000000002','collapse')]
        for values,stop,diagnostic in cases:
            with self.subTest(settings=values),self.assertRaisesRegex(CompileError,diagnostic):
                load_scs(self.deck(values,stop=stop,step=stop))

    def test_default_preserves_rounding_proof_and_downstream_voltage_rejection(self):
        # A second pulse at 1e9 s has inexact .2 s corners. The 3x output
        # must reject their propagated source error under a tight voltage budget.
        values=dict(val0='0',val1='1',rise='.2',fall='.2',width='.2',period='1e9')
        self.deck(values,stop='1000000001',step='1000000001')
        omitted=load_scs(self.path)
        self.assertGreater(omitted.manifest['transient']['source_errors']['u'],2e-7)
        with self.assertRaises(KernelError):
            simulate_scs(self.path,kernel=KERNEL)
        self.deck(dict(values,delay='0'),stop='1000000001',step='1000000001')
        explicit=load_scs(self.path)
        self.assertEqual(omitted.manifest,explicit.manifest)
        self.assertEqual(omitted.metadata['pulse_corner_proofs'],explicit.metadata['pulse_corner_proofs'])
        self.deck(values,stop='1000000001',step='1000000001',options='reltol=0 vabstol=1e-5')
        result=simulate_scs(self.path,kernel=KERNEL)
        self.assertGreater(result['testbench']['pulse_corner_proofs']['Vin']['voltage_error_bound_V'],2e-7)


if __name__=='__main__':
    unittest.main()
