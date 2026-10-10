"""Forced solve points are independent of saved output samples."""
GUARDS = ["DYNAMICS", "EVENT-ORDER", "TIMER", "TRANSITION", "COMPOSE"]

import copy
from fractions import Fraction
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

    def test_signed_zero_is_one_physical_time_at_both_entry_points(self):
        program = compile_sources({'strobe.va': model('V(y,r)<+V(u,r);')}, [instance()])
        for output_zero, forced_zero in [(-0.0, 0.0), (0.0, -0.0)]:
            with self.subTest(output_zero=output_zero, forced_zero=forced_zero):
                response = transient(program, {'u':[[0,0],[1,1]]}, [output_zero,1],
                                     stop=1,max_step=1,strobetimes=[forced_zero],kernel=KERNEL)
                self.assertEqual(response['transient']['times'],[output_zero,1])
                self.assertEqual(response['strobe_evidence']['times'],[forced_zero])
                raw=_invoke(dict(program=program.to_dict(),driven=['u'],samples=[],
                                 transient=dict(pwl=[[[0,0],[1,1]]],output_times=[output_zero,1],
                                                stop=1,max_step=1,strobetimes=[forced_zero])),KERNEL)
                validate_response(raw,program,2,[output_zero,1],strobetimes=[forced_zero])

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

    def test_periodic_timer_forced_points_have_committed_state(self):
        source=model('@(initial_step) q=0.125; @(timer(T,T,1e-10)) q=V(u,r); V(y,r)<+q;',
                     'parameter real T=1e-6; real q;')
        program=compile_sources({'strobe.va':source}, [instance()])
        times=[0., 1e-6, 2e-6, 3e-6, 4e-6, 6e-6, 7e-6, 8e-6, 8.5e-6]
        result=transient(program, {'u':[[0,0],[8.5e-6,.85]]}, [0,8.5e-6],
                         stop=8.5e-6,max_step=1e-6,strobetimes=times,
                         vabstol=1e-9,reltol=0,kernel=KERNEL)
        receipt=result['strobe_evidence'];column=result['nodes'].index('y')
        self.assertEqual(receipt['sample_origins'],['accepted_controller_frame']*len(times))
        self.assertEqual(len(result['transient']['events']),8)
        period=Fraction.from_float(1e-6)
        for time,row in zip(times,receipt['voltages_V']):
            due=[k for k in range(1,9) if k*period<=Fraction.from_float(time)]
            expected=float(due[-1]*period)*1e5 if due else .125
            self.assertAlmostEqual(row[column],expected,delta=1e-9)
        # The last forced point is also the state used to continue/finish, not
        # a relabeled historical query returned by the strobe wrapper.
        self.assertEqual(receipt['voltages_V'][-1],result['solutions'][-1]['voltages'])

    def test_periodic_timer_forced_points_preserve_operator_history(self):
        body='@(initial_step) q=0.125; @(timer(T,T,1e-10)) q=V(u,r); '
        declarations='parameter real T=1e-6; real q;'
        # Constant sampled input isolates continuity at repeated callbacks.
        cases=[('V(y,r)<+transition(q,0,0.2*T);',lambda t:.125),
               ('V(y,r)<+idt(q/T,0.05);',lambda t:.05+.125*t/1e-6),
               ("V(y,r)<+laplace_nd(q,'{1},'{1,T});",lambda t:.125)]
        times=[0.,1e-6,3e-6,4e-6,6e-6,8e-6,8.5e-6]
        for contribution,answer in cases:
            with self.subTest(contribution=contribution):
                program=compile_sources({'strobe.va':model(body+contribution,declarations)},[instance()])
                result=transient(program,{'u':[[0,.125],[8.5e-6,.125]]},[0,8.5e-6],
                                 stop=8.5e-6,max_step=1e-6,strobetimes=times,
                                 vabstol=1e-8,reltol=0,kernel=KERNEL)
                column=result['nodes'].index('y')
                self.assertEqual(result['strobe_evidence']['sample_origins'],['accepted_controller_frame']*len(times))
                for t,row in zip(times,result['strobe_evidence']['voltages_V']):
                    self.assertAlmostEqual(row[column],answer(t),delta=1e-8)

    def test_forced_points_bracket_the_exact_clock_without_firing_early(self):
        source=model('@(initial_step) n=0; @(timer(0.1,0.1,1e-6)) n=n+1; V(y,r)<+n;',
                     'integer n;')
        program=compile_sources({'strobe.va':source},[instance()])
        times=[.3,math.nextafter(.3,math.inf)]
        result=transient(program,{'u':[[0,0],[.35,0]]},[0,.35],stop=.35,max_step=.35,
                         strobetimes=times,kernel=KERNEL)
        receipt=result['strobe_evidence'];column=result['nodes'].index('y')
        self.assertEqual([r[column] for r in receipt['voltages_V']],[2,3])
        self.assertEqual(receipt['sample_origins'],['accepted_controller_frame']*2)

    def test_sampled_changes_reach_each_history_and_continue_after_last_strobe(self):
        prefix='@(initial_step) q=0.125; @(timer(T,T,1e-10)) q=V(u,r); '
        # Each timer raises q by .1. Independent superposition of steps, ramps
        # and exponential responses detects stale slopes and history resets.
        cases=[('V(y,r)<+transition(q,0,0.2*T);',
                lambda x:.125+sum(.1*min(1,max(0,(x-k)/.2)) for k in range(1,9))),
               ('V(y,r)<+idt(q/T,0.05);',
                lambda x:.05+.125*x+sum(.1*max(0,x-k) for k in range(1,9))),
               ("V(y,r)<+laplace_nd(q,'{1},'{1,T});",
                lambda x:.125+sum(.1*(-math.expm1(-max(0,x-k))) for k in range(1,9)))]
        sparse=[0.,1e-6,1.1e-6,1.2e-6,3e-6,3.1e-6,4e-6,6e-6,8e-6,8.2e-6]
        dense=sorted(set(sparse+[k*1e-6/4 for k in range(33)]))
        for body,answer in cases:
            with self.subTest(body=body):
                program=compile_sources({'strobe.va':model(prefix+body,'parameter real T=1e-6; real q;')},[instance()])
                results=[]
                for ts in (sparse,dense):
                    r=transient(program,{'u':[[0,.125],[8.5e-6,.975]]},[0,8.5e-6],
                                stop=8.5e-6,max_step=1e-6,strobetimes=ts,vabstol=1e-8,reltol=0,kernel=KERNEL)
                    column=r['nodes'].index('y');s=r['strobe_evidence']
                    self.assertEqual(s['sample_origins'],['accepted_controller_frame']*len(ts))
                    values={t:v[column] for t,v in zip(ts,s['voltages_V'])}
                    for t,v in values.items():self.assertAlmostEqual(v,answer(t/1e-6),delta=1e-8)
                    self.assertAlmostEqual(r['solutions'][-1]['voltages'][column],answer(8.5),delta=1e-8)
                    results.append(values)
                for t in sparse:self.assertAlmostEqual(results[0][t],results[1][t],delta=1e-12)

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
