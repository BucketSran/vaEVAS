"""Sample/edge/filter contracts use the closed form of tau*y'+y=u."""
GUARDS = ["TIMER", "CROSS", "EVENT-ORDER", "TRANSITION", "DYNAMICS", "COMPOSE"]

import math
import importlib.util
from pathlib import Path
import unittest
from evas import KernelError, Instance, compile_sources, transient
from test_continuous_dynamics import compile_model, run, rows
from test_affine import KERNEL

_spec=importlib.util.spec_from_file_location("sample_edge_contract",Path(__file__).resolve().parents[1]/"validation/sample_edge_filter/contract.py")
contract=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(contract)


def ramp_filter(t, start=1.25, duration=.5, tau=.25):
    """Response to a unit linear ramp followed by a unit plateau."""
    h = max(0., t-start)
    a = min(h, duration)
    rising = (a-tau*(-math.expm1(-a/tau)))/duration
    return rising if h <= duration else 1+(rising-1)*math.exp(-(h-duration)/tau)


class SampleEdgeFilter(unittest.TestCase):
    def test_timer_chain_forced_points_preserve_interruption_and_instance_history(self):
        for c in contract.CASES:
            if c['id']=='SEF-RESET':continue
            with self.subTest(case=c['id']):
                ports=['u','clk','rst',*[p['name']+x for p in c['instances'] for x in 'hefn']]
                p=compile_sources({'chain.va':contract.source(c)},[Instance('dut','dut',{n:n for n in ports})])
                inputs={n:[[t*contract.T,v] for t,v in pts] for n,pts in [('u',contract.INPUT),('clk',contract.CLOCK),('rst',contract.RESET)]}
                ts=contract.times(c,True)
                answer=transient(p,inputs,[0,contract.STOP],stop=contract.STOP,max_step=contract.T/64,
                                 strobetimes=ts,vabstol=1e-7,reltol=0,kernel=KERNEL)
                receipt=answer['strobe_evidence']
                self.assertEqual(receipt['sample_origins'],['accepted_controller_frame']*len(ts))
                output=[dict(time=t,**dict(zip(answer['nodes'],v))) for t,v in zip(receipt['times'],receipt['voltages_V'])]
                verdict=contract.assess(c,output)
                self.assertEqual(verdict['status'],'PASS',verdict)

    def test_tight_root_window_meets_voltage_budget_through_both_histories(self):
        for delay in (0, .125):
            with self.subTest(delay=delay):
                p = compile_model(
                    '@(initial_step) q=0; '
                    '@(cross(pow(V(u,r),2)-2,1,1e-12,1e-12)) q=1; '
                    f'V(e,r)<+transition(q,{delay},0.5,0.5); '
                    "V(y,r)<+laplace_nd(V(e,r),'{1},'{1,0.25});",
                    'integer q; electrical e;')
                ts = [0,1,1.75,2.5,3]
                response = run(p, {'u': [[0,0],[3,3]]}, ts,
                               stop=3, max_step=1, vabstol=1e-10, reltol=0)
                for t, row in zip(ts, rows(response)):
                    self.assertAlmostEqual(row['y'], ramp_filter(
                        t, start=math.sqrt(2)+delay), delta=1e-10)

    def test_nearby_exact_timers_keep_distinct_phases_with_filter_consumers(self):
        # float(.3) < exact(float(.1)+float(.2)) < nextafter(float(.3)).
        # Their enclosing windows touch, but the filter must retain both writes.
        p = compile_model(
            '@(initial_step) q=0; @(timer(0.1,0.2,1e-6)) q=q+1; '
            '@(timer(0.3,0,1e-6)) q=q+1; V(n,r)<+q; '
            'V(e,r)<+transition(q,0,0.5,0.5); '
            "V(y,r)<+laplace_nd(V(e,r),'{1},'{1,0.25});",
            'integer q; electrical e,n;')
        ts = [0,.3,math.nextafter(.3,math.inf),.31,.49]
        dense = sorted(set(ts+[.1,.2,.4]))
        a = run(p,times=ts,stop=.49,vabstol=1e-7,reltol=0)
        b = run(p,times=dense,stop=.49,vabstol=1e-7,reltol=0)
        self.assertEqual([r['dut:n'] for r in rows(a)], [0,2,3,3,3])
        self.assertEqual(a['solutions'], [b['solutions'][dense.index(t)] for t in ts])
        self.assertEqual(a['transient']['events'], b['transient']['events'])

    def test_loose_cross_tolerance_refines_for_downstream_voltage_budget(self):
        # The mathematical crossing is sqrt(2), independent of the root finder.
        # A loose root bracket previously became an exact transition start and
        # certified a 1e-4 V filter error against a 1e-10 V request. Retaining
        # uncertainty fixed that false acceptance. Now refine the certified root
        # to meet the downstream request without editing the VA tolerances.
        for delay in (0, .125):
            with self.subTest(delay=delay):
                p = compile_model(
                    '@(initial_step) q=0; '
                    '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3)) q=1; '
                    f'V(e,r)<+transition(q,{delay},0.5,0.5); '
                    "V(y,r)<+laplace_nd(V(e,r),'{1},'{1,0.25});",
                    'integer q; electrical e;')
                ts = [0,1,1.75,2.5,3]
                response = run(p, {'u': [[0,0],[3,3]]}, ts,
                               stop=3, max_step=1, vabstol=1e-10, reltol=0)
                for t, row in zip(ts, rows(response)):
                    self.assertAlmostEqual(row['y'], ramp_filter(
                        t, start=math.sqrt(2)+delay), delta=1e-10)

    def test_engineering_chain_variants_preserve_query_grid_and_physical_outputs(self):
        for c in contract.CASES:
            with self.subTest(case=c['id']):
                ports=['u','clk','rst',*[p['name']+x for p in c['instances'] for x in 'hefn']]
                p=compile_sources({'chain.va':contract.source(c)},[Instance('dut','dut',{n:n for n in ports})])
                inputs={n:[[t*contract.T,v] for t,v in points] for n,points in [('u',contract.INPUT),('clk',contract.CLOCK),('rst',contract.RESET)]}
                grids=[contract.times(c),contract.times(c,True)];answers=[]
                for grid in grids:
                    answer=transient(p,inputs,grid,stop=contract.STOP,max_step=contract.T/64,
                                     vabstol=1e-7,reltol=0,kernel=KERNEL)
                    output=[dict(time=t,**r) for t,r in zip(answer['transient']['times'],rows(answer))]
                    verdict=contract.assess(c,output)
                    self.assertEqual(verdict['status'],'PASS',verdict)
                    self.assertLess(max(verdict['maximum_errors_V'].values()),1e-8)
                    answers.append(answer)
                self.assertEqual(answers[0]['solutions'],[answers[1]['solutions'][grids[1].index(t)] for t in grids[0]])
                self.assertEqual(answers[0]['transient']['events'],answers[1]['transient']['events'])

    def test_refinement_retains_sample_error_and_is_independent_of_query_grid(self):
        # The dense grid enters the OLD broad root window on both sides of
        # sqrt(2). Preflight must run before a query can select physical phase.
        sparse = [0, 1, 1.75, 2.5, 3]
        dense = sorted(set(sparse + [1.4142, 1.41423, 1.55, 1.6, 2.0]))
        for delay in (0, .125):
            for gain in (1, -2):
                with self.subTest(delay=delay, gain=gain):
                    p = compile_model(
                        '@(initial_step) q=0; '
                        '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3)) q=V(u,r); '
                        f'V(e,r)<+transition(q,{delay},0.5,0.5); '
                        f"V(y,r)<+laplace_nd({gain}*V(e,r),'{{1}},'{{1,0.25}});",
                        'real q; electrical e;')
                    answers = [run(p, {'u': [[0,0],[3,3]]}, grid, stop=3,
                                   max_step=1, vabstol=1e-10, reltol=0)
                               for grid in (sparse, dense)]
                    self.assertEqual(answers[0]['solutions'],
                                     [answers[1]['solutions'][dense.index(t)] for t in sparse])
                    self.assertEqual(answers[0]['transient']['events'], answers[1]['transient']['events'])
                    for t, row in zip(dense, rows(answers[1])):
                        self.assertAlmostEqual(row['y'], gain*math.sqrt(2)*ramp_filter(
                            t, start=math.sqrt(2)+delay), delta=1e-10)

    def test_direct_sample_gain_drives_refinement_but_arithmetic_floor_still_rejects(self):
        for gain in (1, -1000, 1e6):
            with self.subTest(gain=gain):
                p = compile_model(
                    '@(initial_step) q=0; '
                    '@(cross(pow(V(u,r),2)-2,1,1e-3,1e-3)) q=V(u,r); '
                    f'V(y,r)<+{gain}*q;', 'real q;')
                response = run(p, {'u': [[0,0],[3,3]]}, [0, 2, 3],
                               stop=3, max_step=1, vabstol=1e-7, reltol=0)
                for row in rows(response)[1:]:
                    self.assertAlmostEqual(row['y'], gain*math.sqrt(2), delta=1e-7)
                with self.assertRaisesRegex(KernelError, 'event_accuracy|waveform_accuracy'):
                    run(p, {'u': [[0,0],[3,3]]}, [0,2,3], stop=3,
                        max_step=1, vabstol=1e-20, reltol=0)

    def test_negative_affine_projection_and_contribution_order(self):
        pieces=['V(e,r)<+transition(q,0.25,0.5,0.5);',
                "V(y,r)<+laplace_nd(-2*V(e,r)+0.125,'{1},'{1,0.25});"]
        ts=[0,.5,1,1.25,1.375,1.5,1.75,2,3]
        answers=[]
        for order in (pieces,pieces[::-1]):
            p=compile_model('@(initial_step) q=0.25; @(timer(1,0,1e-12)) q=1.25; '+''.join(order),
                            'real q; electrical e;')
            response=run(p,times=ts,stop=3,max_step=3,vabstol=1e-9,reltol=0)
            answers.append([r['y'] for r in rows(response)])
            for t,r in zip(ts,rows(response)):
                self.assertAlmostEqual(r['y'],.125-2*(.25+ramp_filter(t)),delta=1e-9)
        self.assertEqual(answers[0],answers[1])

    def test_unachievable_certificate_still_rejects(self):
        p=compile_model('@(initial_step) q=0.25; @(timer(1,0,1e-12)) q=1.25; '
                        "V(e,r)<+transition(q,0.25,0.5,0.5); V(y,r)<+laplace_nd(V(e,r),'{1},'{1,0.25});",
                        'real q; electrical e;')
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            run(p,times=[0,1,1.5,3],stop=3,vabstol=1e-20,reltol=0)

    def test_continuous_and_guard_consumers_remain_explicitly_unsupported(self):
        common=('@(initial_step) q=0.25; @(timer(1,0,1e-12)) q=1.25; '
                "V(e,r)<+transition(q,0.25,0.5,0.5); V(y,r)<+laplace_nd(V(e,r),'{1},'{1,0.25});")
        for extra in ["V(z,r)<+idt(V(y,r),0);",'@(cross(V(y,r)-0.5,1,1e-8,1e-8)) q=2;']:
            with self.subTest(extra=extra):
                p=compile_model(common+extra,'real q; electrical e,z;')
                with self.assertRaises(KernelError):run(p,times=[0,1,1.5,3],stop=3)

    def test_sample_edge_filter_preserves_dc_and_history_at_internal_deadlines(self):
        p = compile_model(
            '@(initial_step) q=0.25; @(timer(1,0,1e-12)) q=V(u,r); '
            "V(e,r)<+transition(q,0.25,0.5,0.5); "
            "V(y,r)<+laplace_nd(V(e,r),'{1},'{1,0.25});",
            'real q; electrical e;')
        sparse = [0,.5,1,1.125,1.25,1.375,1.5,1.75,2,3]
        dense = sorted(set(sparse+[i/32 for i in range(97)]))
        first = run(p, {'u': [[0,1.25],[3,1.25]]}, sparse, max_step=3,
                    vabstol=1e-9, reltol=0)
        second = run(p, {'u': [[0,1.25],[3,1.25]]}, dense, max_step=3,
                     vabstol=1e-9, reltol=0)
        self.assertEqual(first['solutions'], [second['solutions'][dense.index(t)] for t in sparse])
        for t, row in zip(sparse, rows(first)):
            self.assertAlmostEqual(row['y'], .25+ramp_filter(t), delta=1e-9)

    def test_feedback_through_filter_and_transition_is_not_silently_projected(self):
        p = compile_model(
            '@(initial_step) q=0; @(timer(1,0,1e-12)) q=1; '
            'V(e,r)<+transition(q,0.25,0.5,0.5)+0*V(y,r); '
            "V(y,r)<+laplace_nd(V(e,r),'{1},'{1,0.25});",
            'real q; electrical e;')
        with self.assertRaises(KernelError):
            run(p, times=[0,.5,1.5,3])
