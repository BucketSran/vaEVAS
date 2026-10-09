"""Forced solve points are independent of saved output samples."""
GUARDS = ["DYNAMICS", "EVENT-ORDER"]

import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from evas import KernelError, compile_sources, transient
from evas.diagnostics import capture
from evas.protocol import validate_response
from evas.runtime import _invoke
from evas.results import run as save_run
from test_affine import KERNEL, instance, model


class StrobeControl(unittest.TestCase):
    def test_irregular_strobes_solve_without_changing_saved_grid(self):
        program = compile_sources({'strobe.va': model('V(y,r)<+2*V(u,r);')}, [instance()])
        result = transient(program, {'u': [[0,0],[1,1]]}, [0,1], stop=1,
                           max_step=1, strobetimes=[0.2,0.7], kernel=KERNEL)
        self.assertEqual(result['transient']['times'], [0,1])
        self.assertEqual([s['voltages'][result['nodes'].index('y')] for s in result['solutions']], [0,2])
        receipt = result['strobe_evidence']
        self.assertEqual(receipt['schema_version'], 1)
        self.assertEqual(receipt['times'], [0.2,0.7])
        self.assertEqual(receipt['sample_origins'], ['stateless_working_point']*2)

    def test_periodic_strobes_use_declared_window_and_phase(self):
        program = compile_sources({'strobe.va': model('V(y,r)<+idt(1,0);')}, [instance()])
        result = transient(program, {'u': [[0,0],[1,0]]}, [0,1], stop=1,
                           max_step=1, strobeperiod=0.25, strobedelay=0.125,
                           skipstart=0.25, skipstop=0.9, kernel=KERNEL)
        self.assertEqual(result['strobe_evidence']['times'], [0.375,0.625,0.875])
        self.assertEqual(result['strobe_evidence']['sample_origins'], ['accepted_controller_frame']*3)
        self.assertEqual(result['solutions'][-1]['voltages'][result['nodes'].index('y')], 1)

    def test_continuous_and_implicit_forced_values_match_independent_answers(self):
        for body, answer in [('V(y,r)<+idt(1-V(y,r),0);', lambda t:1-math.exp(-t)),
                             ('V(y,r)<+idt(1+2*V(y,r),0)-pow(V(y,r),2);', lambda t:t)]:
            with self.subTest(body=body):
                program = compile_sources({'strobe.va':model(body)}, [instance()])
                result = transient(program, {'u':[[0,0],[1,1]]}, [0,1], stop=1,
                                   max_step=0.5, strobetimes=[0.2,0.7],
                                   vabstol=1e-8, reltol=1e-7, kernel=KERNEL)
                self.assertEqual(result['transient']['times'], [0,1])
                for time,row in zip([0.2,0.7],result['strobe_evidence']['voltages_V']):
                    self.assertAlmostEqual(row[result['nodes'].index('y')], answer(time), delta=1e-7)

    def test_invalid_controls_and_malformed_raw_requests_reject(self):
        program = compile_sources({'strobe.va':model('V(y,r)<+V(u,r);')}, [instance()])
        for options in [dict(strobetimes=[0.7,0.2]), dict(strobetimes=[0.2,0.2]),
                        dict(strobetimes=[-1]), dict(strobetimes=[2]), dict(strobetimes=[True]),
                        dict(strobetimes=[math.nan]), dict(strobeperiod=0),
                        dict(strobeperiod=1e-20), dict(strobedelay=0.1),
                        dict(strobeperiod=0.25,strobedelay=0.25),
                        dict(strobeperiod=0.25,skipstart=0.9,skipstop=0.2)]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                transient(program, {'u':[[0,0],[1,1]]}, [0,1], stop=1,
                          max_step=1, kernel=KERNEL, **options)
        for points in [[0.7,0.2], [0.2,0.2], [-1], [2], [True]]:
            request = dict(program=program.to_dict(),driven=['u'],samples=[],
                           transient=dict(pwl=[[[0,0],[1,1]]],output_times=[0,1],
                                          stop=1,max_step=1,strobetimes=points))
            with self.subTest(raw=points), self.assertRaises(KernelError):
                _invoke(request,KERNEL)

    def test_receipt_cannot_be_missing_or_claim_a_dense_causal_query(self):
        program = compile_sources({'strobe.va':model('V(y,r)<+V(u,r);')}, [instance()])
        result = transient(program, {'u':[[0,0],[1,1]]}, [0,1], stop=1,
                           max_step=1, strobetimes=[0.2], kernel=KERNEL)
        for mutate in [lambda r:r.pop('strobe_evidence'),
                       lambda r:r['strobe_evidence'].update(times=[0.3]),
                       lambda r:r['strobe_evidence'].update(sample_origins=['certified_causal_frame']),
                       lambda r:r['strobe_evidence'].update(voltages_V=[[math.nan]*len(program.nodes)])]:
            bad=copy.deepcopy(result);mutate(bad)
            with self.assertRaisesRegex(KernelError,'invalid_response'):
                validate_response(bad,program,2,[0,1],strobetimes=[0.2])

    def test_atomic_causal_query_is_not_claimed_as_a_forced_solve(self):
        source=model('@(initial_step) begin a=0; b=0; end @(timer(0.3,0,1e-6)) a=1; '
                     '@(timer(0.1,0.2,1e-6)) b=b+1; V(y,r)<+a+10*b;', declarations='integer a,b;')
        program=compile_sources({'strobe.va':source}, [instance()])
        with self.assertRaises(KernelError) as caught:
            transient(program, {'u':[[0,0],[1,0]]}, [0,1], stop=1, max_step=1,
                      strobetimes=[0.3], kernel=KERNEL)
        self.assertEqual(caught.exception.detail['kind'], 'unsupported_strobe')

    def test_manifest_capture_and_saved_bundle_retain_forced_points(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'dut.va').write_text(model('V(y,r)<+2*V(u,r);'))
            config=dict(models=['dut.va'],instances=[dict(name='dut',module='m',connections=dict(u='u',y='y',r='0'))],
                        transient=dict(sources={'u':[[0,0],[1,1]]},output_times=[0,1],stop=1,max_step=1,
                                       strobetimes=[0.2,0.7]))
            path=root/'sim.json';path.write_text(json.dumps(config))
            artifact=capture(path,KERNEL)
            self.assertEqual(artifact['payload']['status'],'complete')
            self.assertEqual(artifact['payload']['response']['strobe_evidence']['times'],[0.2,0.7])
            save_run(path,kernel=KERNEL,out=root/'saved')
            saved=json.loads((root/'saved/result.json').read_text())
            self.assertEqual(saved['strobe_evidence'],artifact['payload']['response']['strobe_evidence'])


if __name__ == '__main__':
    unittest.main()
