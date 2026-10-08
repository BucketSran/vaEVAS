"""Independent development contracts: triangular ramps have hand-computed roots.

These are new, transition-free probes, not replacements for DVS E1 or additional
conditions in its fixed 31-condition denominator. Freeze before implementing.
"""
# Guarded conditions/capabilities: see docs/PROCESS.md and docs/TRACEABILITY.md
GUARDS = ["CROSS", "EVENT-CONDITIONS"]

import copy
import json
import math
import subprocess
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

COUNTER = model('''
  @(initial_step) begin up=0; down=0; end
  @(cross(V(u,r)-.5, +1, 100p, 100u)) up=up+1;
  @(cross(V(u,r)-.5, -1, 100p, 100u)) down=down+1;
  V(y,r)<+.1*up+.01*down;
''', 'integer up,down;')


def compile_event(source=COUNTER, instances=None):
    return compile_sources({'events.va': source}, instances or [instance()])


def execute_event(source=COUNTER, *, instances=None, sources=None, times=None,
                  max_step=10e-6, stop=3e-6):
    return transient(compile_event(source, instances),
                     sources or {'u': [[0,.4],[1e-6,.6],[2e-6,.4],[3e-6,.6]]},
                     times or [0,.25e-6,.75e-6,1.75e-6,2.75e-6,3e-6],
                     stop=stop, max_step=max_step, kernel=KERNEL)


class EventContracts(unittest.TestCase):
    def test_voltage_tolerance_aliases_preserve_event_trace(self):
        program = compile_event()
        sources = {'u': [[0,.4],[1e-6,.6],[2e-6,.4],[3e-6,.6]]}
        options = dict(stop=3e-6, max_step=10e-6, kernel=KERNEL)
        canonical = transient(program, sources, [0,3e-6], **options,
                              vabstol=1e-9, reltol=1e-6)
        legacy = transient(program, sources, [0,3e-6], **options,
                           absolute=1e-9, relative=1e-6)
        self.assertEqual(canonical, legacy)
        self.assertEqual(canonical['transient']['states'][-1], [2,1])
        for aliases in (dict(vabstol=1e-9, absolute=1e-9),
                        dict(reltol=1e-6, relative=1e-6)):
            with self.assertRaisesRegex(ValueError, 'both'):
                transient(program, sources, [0,3e-6], **options, **aliases)

    def test_direction_count_time_and_post_event_voltage(self):
        result = execute_event()
        events = result['transient']['events']
        self.assertEqual([e['event'] for e in events], [0,1,0])
        for event, expected in zip(events, [.5e-6,1.5e-6,2.5e-6]):
            self.assertAlmostEqual(event['time'], expected, delta=1e-18)
            self.assertLessEqual(abs(event['guard_value']), 1e-4)
        y = result['nodes'].index('y')
        for row, expected in zip(result['solutions'], [0,0,.1,.11,.21,.21]):
            self.assertAlmostEqual(row['voltages'][y], expected, places=12)
            self.assertLessEqual(row['max_residual_ratio'], 1)
        self.assertEqual(result['transient']['states'][-1], [2,1])

    def test_roots_independent_of_output_grid_step_shift_and_slope(self):
        # Each source segment has its zero at its midpoint. The shift is 37 ps;
        # amplitudes .1 and .025 give fourfold different slopes.
        for shift in [0,37e-12]:
            for amplitude in [.1,.025]:
                points = [[0,.5-amplitude], [shift+1e-6,.5+amplitude],
                          [shift+2e-6,.5-amplitude], [shift+3e-6,.5+amplitude]]
                if shift:
                    points.insert(1,[shift,.5-amplitude])
                expected = [shift+t for t in [.5e-6,1.5e-6,2.5e-6]]
                for step in [7e-6,97e-9,11e-9]:
                    with self.subTest(shift=shift, amplitude=amplitude, step=step):
                        r = execute_event(sources={'u':points}, times=[0,3e-6], max_step=step)
                        self.assertEqual(r['transient']['states'][-1], [2,1])
                        self.assertEqual(len(r['transient']['events']),3)
                        for event, root in zip(r['transient']['events'],expected):
                            self.assertAlmostEqual(event['time'],root,delta=1e-18)

    def test_initial_high_and_initial_zero_do_not_fire(self):
        for start in [.6,.5]:
            r = execute_event(sources={'u':[[0,start],[1e-6,.6],[2e-6,.4],[3e-6,.6]]})
            self.assertEqual([e['event'] for e in r['transient']['events']], [1,0])
            self.assertEqual(r['transient']['states'][-1],[1,1])

    def test_exact_knot_crossing_and_touch_each_fire_once(self):
        r = execute_event(sources={'u':[[0,.4],[.5e-6,.5],[1e-6,.6],
                                       [1.5e-6,.5],[2e-6,.6],[3e-6,.4]]})
        self.assertEqual([e['event'] for e in r['transient']['events']],[0,1,1])
        self.assertEqual(r['transient']['events'][0]['time'],.5e-6)
        self.assertEqual(r['transient']['events'][1]['time'],1.5e-6)
        self.assertAlmostEqual(r['transient']['events'][2]['time'],2.5e-6,delta=1e-18)

    def test_isolated_zero_arrival_direction_and_post_event_state(self):
        # Contract from the Spectre PWL experiment: arrival owns the zero;
        # returning to the same side or continuing across it cannot fire again.
        times = [0, 1e-6, 1.5e-6, 2e-6, 3e-6]
        for before in [.4, .6]:
            for after in [.4, .6]:
                arrival = 1 if before < .5 else -1
                for direction in [0, 1, -1]:
                    source = model(f'''@(initial_step) n=0;
                      @(cross(V(u,r)-.5,{direction},100p,100u)) n=n+1;
                      V(y,r)<+n;''', 'integer n;')
                    expected = int(direction in [0, arrival])
                    for step in [10e-6, 7e-9]:
                        with self.subTest(before=before, after=after, direction=direction, step=step):
                            r = execute_event(source, sources={'u':[[0,before],[1.5e-6,.5],[3e-6,after]]},
                                              times=times, max_step=step)
                            events = r['transient']['events']
                            self.assertEqual([e['time'] for e in events], [1.5e-6]*expected)
                            self.assertEqual([e['guard_value'] for e in events], [0.]*expected)
                            self.assertEqual(r['transient']['states'], [[0],[0]]+[[expected]]*3)
                            y = r['nodes'].index('y')
                            self.assertEqual([s['voltages'][y] for s in r['solutions']], [0,0]+[expected]*3)

    def test_separate_touches_rearm_without_departure_events(self):
        times = [0, .75e-6, 1.5e-6, 2.25e-6, 3e-6]
        for side, event in [(.4,0), (.6,1)]:
            points = [[t, .5 if i%2 else side] for i,t in enumerate(times)]
            r = execute_event(sources={'u':points}, times=times)
            self.assertEqual([e['event'] for e in r['transient']['events']], [event,event])
            self.assertEqual([e['time'] for e in r['transient']['events']], [.75e-6,2.25e-6])
            self.assertEqual([s[event] for s in r['transient']['states']], [0,1,1,2,2])
            self.assertEqual([s[1-event] for s in r['transient']['states']], [0]*5)

    def test_near_zero_is_not_a_touch_or_a_dead_band(self):
        for side in [.4, .6]:
            # One representable value away from threshold is still nonzero,
            # even though its distance is far smaller than expression tolerance.
            near = math.nextafter(.5, side)
            r = execute_event(sources={'u':[[0,side],[1.5e-6,near],[3e-6,side]]})
            self.assertEqual(r['transient']['events'], [])
            beyond = .5 + (1e-6 if side < .5 else -1e-6)
            r = execute_event(sources={'u':[[0,side],[1.5e-6,beyond],[3e-6,side]]})
            order = [0,1] if side < .5 else [1,0]
            self.assertEqual([e['event'] for e in r['transient']['events']], order)
            self.assertEqual(r['transient']['states'][-1], [1,1])

    def test_both_directions_sequential_assignments_and_initial_parameter(self):
        source = model('''@(initial_step) begin n=start; v=1; end
          @(cross(V(u,r)-.5,0)) begin n=n+1; v=n+v; end
          V(y,r)<+v;''', 'parameter real start=2; integer n; real v;')
        r = execute_event(source)
        self.assertEqual(r['transient']['states'][-1],[5,13])
        self.assertEqual(len(r['transient']['events']),3)

    def test_internal_affine_feedback_guard_uses_solved_voltage(self):
        source = model('''@(initial_step) n=0;
          V(z,r)<+V(u,r)+.5*V(z,r);
          @(cross(V(z,r)-1,0)) n=n+1;
          V(y,r)<+.1*n;''', 'integer n; electrical z;')
        r = execute_event(source)
        self.assertEqual(r['transient']['states'][-1],[3])
        for e,t in zip(r['transient']['events'],[.5e-6,1.5e-6,2.5e-6]):
            self.assertAlmostEqual(e['time'],t,delta=1e-18)

    def test_instance_isolation_and_order_invariance(self):
        a = instance('a',connections=dict(u='u',y='a',r='0'))
        b = instance('b',connections=dict(u='v',y='b',r='0'))
        sources = {'u':[[0,.4],[1e-6,.6],[2e-6,.4],[3e-6,.6]],
                   'v':[[0,.6],[1e-6,.4],[2e-6,.6],[3e-6,.4]]}
        results = [execute_event(instances=order,sources=sources) for order in [[a,b],[b,a]]]
        self.assertEqual(results[0]['solutions'],results[1]['solutions'])
        for r in results:
            states = dict(zip(r['transient']['state_names'],r['transient']['states'][-1]))
            self.assertEqual(states,{'a:up':2,'a:down':1,'b:up':1,'b:down':2})
            self.assertEqual(len(r['transient']['events']),6)

    def test_simultaneous_events_sample_common_settled_voltages(self):
        source = model('''@(initial_step) begin n=0; held=0; end
          @(cross(V(u,r)-.5,1)) n=n+1;
          @(cross(V(u,r)-.5,1)) held=V(y,r);
          V(y,r)<+n;''','integer n; real held;')
        r = execute_event(source)
        self.assertEqual(r['transient']['states'][-1],[2,2])

    def test_tolerances_do_not_suppress_small_or_merge_close_crossings(self):
        points = [[0,.4],[1e-6,.6],[1e-6+2e-12,.4],[1e-6+4e-12,.6],[3e-6,.6]]
        for stimulus in [points, [[0,.5-1e-8],[1e-6,.5+1e-8],[2e-6,.5-1e-8],[3e-6,.5+1e-8]]]:
            r = execute_event(sources={'u':stimulus},times=[0,3e-6])
            self.assertEqual(r['transient']['states'][-1],[2,1])
            self.assertEqual(len(r['transient']['events']),3)
        for e,t in zip(execute_event(sources={'u':points})['transient']['events'],
                       [.5e-6,1e-6+1e-12,1e-6+3e-12]):
            self.assertAlmostEqual(e['time'],t,delta=1e-18)

    def test_empty_event_body_forces_evaluation_without_state(self):
        source = model('@(cross(V(u,r)-.5)) ; V(y,r)<+V(u,r);')
        r = execute_event(source,times=[0,3e-6])
        self.assertEqual(r['transient']['state_names'],[])
        self.assertEqual(len(r['transient']['events']),3)
        self.assertEqual(len(r['solutions']),2)

    def test_state_contributions_keep_orientation_addition_and_feedback(self):
        source = model('''@(initial_step) n=0; @(cross(V(u,r)-.5,0)) n=n+1;
          V(y,r)<+.1*n+.5*V(y,r); V(r,y)<+-.2*n;''','integer n;')
        r = execute_event(source)
        y = r['nodes'].index('y')
        self.assertAlmostEqual(r['solutions'][-1]['voltages'][y],1.8,places=12)

    def test_sparse_output_preserves_events_and_rejected_trials(self):
        r = execute_event(times=[0,3e-6])
        self.assertEqual(len(r['solutions']),2)
        self.assertEqual(r['transient']['states'][-1],[2,1])
        self.assertGreater(r['transient']['discarded_trials'],0)


class EventRejections(unittest.TestCase):
    def test_frontend_rejects_uninitialized_nonconstant_init_and_unsupported_events(self):
        bodies = [
            ('integer n;','@(cross(V(u),1)) n=n+1; V(y)<+n;'),
            ('integer n;','@(initial_step) n=V(u); V(y)<+n;'),
            ('integer n;','@(initial_step) begin n=0; n=1; end V(y)<+n;'),
            ('integer n;','@(initial_step) n=0; @(cross(V(u),2)) n=n+1; V(y)<+n;'),
            ('integer n;','@(initial_step) n=0; @(cross(V(u),1,0)) n=n+1; V(y)<+n;'),
            ('integer n;','@(initial_step) n=0; @(timer(V(u))) n=n+1; V(y)<+n;'),
            ('integer n;','@(initial_step) n=0; @(cross(V(u),1)) n=n+.5; V(y)<+n;'),
            ('integer n;','@(initial_step) n=0; @(cross(V(u),1)) n=n+1; V(y)<+transition(n,0);'),
        ]
        for declarations, body in bodies:
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_event(model(body,declarations))

    def test_state_feedback_nonlinear_and_cross_block_state_dependency_rejected(self):
        for source in [
            model('@(initial_step) n=0; @(cross(V(y)-.5,1)) n=n+1; V(y)<+V(u)+n;','integer n;'),
            model('''@(initial_step) n=0; @(cross(V(u)-.5,1)) n=n+1;
              @(cross(V(y)-.25,1)) ; V(y)<+V(y)+n; V(y)<+-2*V(y);''','integer n;'),
            model('@(initial_step) n=0; @(cross(V(u),1)) n=n+1; V(y)<+V(u)*V(u)+n;','integer n;'),
            model('''@(initial_step) begin n=0; m=0; end
              @(cross(V(u)-.5,1)) n=m+1;
              @(cross(V(u)-.5,-1)) m=n+1; V(y)<+n+m;''','integer n,m;'),
        ]:
            with self.subTest(source=source), self.assertRaises((CompileError,KernelError)):
                execute_event(source)

    def test_terminal_zero_commits_arrival_before_final_output(self):
        for before in [.375,.625]:
            arrival = 1 if before < .5 else -1
            for direction in [0,1,-1]:
                source = model(f'''@(initial_step) n=0;
                  @(cross(V(u,r)-.5,{direction},100p,100u)) n=n+1;
                  V(y,r)<+n;''', 'integer n;')
                expected = int(direction in [0,arrival])
                for continued in [False,True]:
                    points = [[0,before],[3e-6,.5]]
                    if continued:
                        points.append([4e-6,1-before])
                    for step in [10e-6,7e-9]:
                        with self.subTest(before=before, direction=direction, continued=continued, step=step):
                            r = execute_event(source, sources={'u':points}, times=[0,1.5e-6,3e-6], max_step=step)
                            self.assertEqual([e['time'] for e in r['transient']['events']], [3e-6]*expected)
                            self.assertEqual(r['transient']['states'], [[0],[0],[expected]])
                            y = r['nodes'].index('y')
                            self.assertEqual([s['voltages'][y] for s in r['solutions']], [0,0,expected])

    def test_zero_plateau_arrival_only_across_width_sign_and_direction(self):
        for before in [.375,.625]:
            arrival = 1 if before < .5 else -1
            for after in [.375,.5,.625]:
                for end in [1e-6+20e-12,2e-6]:
                    for direction in [0,1,-1]:
                        source = model(f'''@(initial_step) n=0;
                          @(cross(V(u,r)-.5,{direction},100p,100u)) n=n+1;
                          V(y,r)<+n;''', 'integer n;')
                        expected = int(direction in [0,arrival])
                        for step in [10e-6,7e-9]:
                            with self.subTest(before=before, after=after, end=end, direction=direction, step=step):
                                r = execute_event(source, sources={'u':[[0,before],[1e-6,.5],[end,.5],[3e-6,after]]},
                                                  times=[0,1e-6,end,3e-6], max_step=step)
                                self.assertEqual([e['time'] for e in r['transient']['events']], [1e-6]*expected)
                                self.assertEqual(r['transient']['states'], [[0]]+[[expected]]*3)

    def test_initial_constant_and_near_zero_plateaus_do_not_fire(self):
        for after in [.375,.5,.625]:
            r = execute_event(sources={'u':[[0,.5],[1e-6,.5],[2e-6,.5],[3e-6,after]]})
            self.assertEqual(r['transient']['events'], [])
            self.assertEqual(r['transient']['states'][-1], [0,0])
        for side in [.375,.625]:
            near = math.nextafter(.5,side)
            r = execute_event(sources={'u':[[0,side],[1e-6,near],[2e-6,near],[3e-6,side]]})
            self.assertEqual(r['transient']['events'], [])

    def test_separate_zero_plateaus_rearm_once_each(self):
        times = [0,.5e-6,1e-6,1.5e-6,2e-6,2.5e-6,3e-6]
        for side,event in [(.375,0),(.625,1)]:
            points = [[t,v] for t,v in zip(times,[side,.5,.5,side,.5,.5,.5])]
            r = execute_event(sources={'u':points}, times=times)
            self.assertEqual([e['event'] for e in r['transient']['events']], [event,event])
            self.assertEqual([e['time'] for e in r['transient']['events']], [.5e-6,2e-6])
            self.assertEqual([s[event] for s in r['transient']['states']], [0,1,1,1,2,2,2])
            self.assertEqual([s[1-event] for s in r['transient']['states']], [0]*7)

    def test_terminal_batch_settles_without_stop_output(self):
        source = model('''@(initial_step) begin n=0; held=0; end
          @(cross(V(u,r)-.5,1)) n=n+1;
          @(cross(V(u,r)-.5,1)) held=V(y,r);
          V(y,r)<+n;''', 'integer n; real held;')
        for times in [[0,1e-6],[0,1e-6,3e-6]]:
            r = execute_event(source, sources={'u':[[0,.375],[3e-6,.5]]}, times=times)
            events = r['transient']['events']
            self.assertEqual([e['time'] for e in events], [3e-6,3e-6])
            self.assertEqual([e['before'] for e in events], [[0,0],[0,0]])
            self.assertEqual([e['after'] for e in events], [[1,1],[1,1]])
            self.assertEqual(r['transient']['states'], [[0,0],[0,0]]+([[1,1]] if len(times)==3 else []))

    def test_invalid_pwl_and_time_settings(self):
        program = compile_event()
        settings = [dict(sources={'u':[[0,.4],[0,.6],[3e-6,.4]]}),
                    dict(sources={'u':[[0,.4],[1e-6,.6]]}),
                    dict(output_times=[0,0,3e-6]), dict(max_step=0), dict(stop=0)]
        for patch in settings:
            arguments=dict(sources={'u':[[0,.4],[3e-6,.6]]}, output_times=[0,3e-6],
                           stop=3e-6,max_step=1e-6,kernel=KERNEL)
            arguments.update(patch)
            with self.subTest(patch=patch),self.assertRaises((ValueError,KernelError)):
                transient(program,**arguments)

    def test_static_entry_rejects_event_program(self):
        from evas import solve
        with self.assertRaises(KernelError) as error:
            solve(compile_event(),['u'],[[.4]],kernel=KERNEL)
        self.assertEqual(error.exception.detail['kind'],'unsupported_analysis')

    def test_kernel_revalidates_state_and_event_ir(self):
        request = dict(program=compile_event().to_dict(),driven=['u'],samples=[],
                       transient=dict(pwl=[[[0,.4],[3e-6,.6]]],output_times=[0,3e-6],
                                      stop=3e-6,max_step=1e-6))
        mutations = [lambda p:p['states'][0].update(initial=.5),
                     lambda p:p['events'][0]['trigger'].update(direction=2),
                     lambda p:p['events'][0]['body'][0].update(state=999),
                     lambda p:p['events'][0]['trigger'].update(time_tolerance=0),
                     lambda p:p['states'][0].update(instance='foreign'),
                     lambda p:p['events'][0].update(extra_semantics=True)]
        for mutate in mutations:
            bad=copy.deepcopy(request); mutate(bad['program'])
            with self.subTest(bad=bad):
                proc=subprocess.run([str(KERNEL)],input=json.dumps(bad),text=True,capture_output=True)
                self.assertEqual(proc.returncode,2)
                self.assertEqual(proc.stdout,'')
                self.assertIn('kind',json.loads(proc.stderr))
