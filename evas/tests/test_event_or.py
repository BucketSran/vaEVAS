"""OR is a union of certified root occurrences belonging to one event body.

The roots and counter values below are hand-derived from u(t)=t, not from
EVAS output or a second implementation of its root finder.
"""
import copy
import json
import subprocess
import unittest
from evas import CompileError, compile_sources, transient
from test_event_conditions import execute, source, states
from test_affine import KERNEL, instance, model


class EventOrContracts(unittest.TestCase):
    def test_distinct_roots_execute_body_twice(self):
        trigger = 'cross(V(u,r)-.25,1,.001,.001) or cross(V(u,r)-.75,1,.001,.001)'
        result = execute(source('q=q+1;', kind='integer', trigger=trigger), times=[0,.25,.5,.75,1])
        self.assertEqual(states(result), [0,1,1,2,2])
        self.assertEqual([e['time'] for e in result['transient']['events']], [.25,.75])

    def test_same_root_executes_body_once_and_retains_both_sources(self):
        a = 'cross(V(u,r)-.5,1,.001,.001)'
        b = 'cross(2*V(u,r)-1,1,.001,.001)'
        for trigger in [a+' or '+b, b+' or '+a, a+' or '+a]:
            with self.subTest(trigger=trigger):
                result = execute(source('q=q+1;', kind='integer', trigger=trigger))
                self.assertEqual(states(result), [0,1,1])
                events = result['transient']['events']
                self.assertEqual(len(events), 1)
                self.assertEqual([t['trigger'] for t in events[0]['fired_triggers']], [0,1])

    def test_nearby_distinct_roots_are_not_tolerance_clustered(self):
        # Separation 2^-10 is smaller than ttol=.01, but the exact roots differ.
        a = 'cross(V(u,r)-.5,1,.01,.01)'
        b = 'cross(V(u,r)-.5009765625,1,.01,.01)'
        for trigger in [a+' or '+b, b+' or '+a]:
            result = execute(source('q=q+1;', kind='integer', trigger=trigger), times=[0,.5,.5009765625,1])
            self.assertEqual(states(result), [0,1,2,2])
            self.assertEqual([e['time'] for e in result['transient']['events']], [.5,.5009765625])

    def test_output_grid_does_not_create_triggers(self):
        trigger = 'cross(V(u,r)-.25,1,.001,.001) or cross(V(u,r)-.75,1,.001,.001)'
        text = source('q=q+1;', kind='integer', trigger=trigger)
        sparse = execute(text, times=[0,1])
        dense = execute(text, times=[i/16 for i in range(17)])
        self.assertEqual(sparse['transient']['events'], dense['transient']['events'])
        self.assertEqual(states(sparse), [0,2])

    def test_each_leaf_keeps_direction_and_its_own_tolerance(self):
        a = 'cross(V(u,r)-.25,-1,.001,.001)'
        b = 'cross(V(u,r)-.75,1,.001,.001)'
        r = execute(source('q=q+1;', kind='integer', trigger=a+' or '+b))
        self.assertEqual(states(r), [0,0,1])
        self.assertEqual(r['transient']['events'][0]['fired_triggers'][0]['trigger'], 1)
        for fired in r['transient']['events'][0]['fired_triggers']:
            self.assertEqual(fired['time_bounds'], [.75,.75])

    def test_leaf_ids_and_body_ids_remain_distinct_in_mixed_calendars(self):
        import itertools
        for simultaneous in [False, True]:
            times = [.5, .5, .5] if simultaneous else [.25, .5, .75]
            blocks = [
                f"@(cross(V(u,r)-{times[0]},1,.001,.001)) a=a+1;",
                f"@(cross(V(u,r)-{times[1]},1,.001,.001) or "
                f"cross(2*V(u,r)-{2*times[1]},1,.001,.001)) b=b+1;",
                f"@(timer({times[2]},0,.001)) c=c+1;",
            ]
            for order in itertools.permutations(blocks):
                with self.subTest(simultaneous=simultaneous, order=order):
                    text = model("@(initial_step) begin a=0; b=0; c=0; end "
                                 + "".join(order) + " V(y,r)<+a+10*b+100*c;",
                                 "integer a,b,c;")
                    result = execute(text, times=[0,.25,.5,.75,1])
                    y = result['nodes'].index('y')
                    self.assertEqual([row['voltages'][y] for row in result['solutions']],
                                     [0,0,111,111,111] if simultaneous else [0,1,11,111,111])
                    events = result['transient']['events']
                    self.assertEqual(len(events), 3)
                    self.assertEqual(sorted(e['kind'] for e in events), ['cross','or','timer'])
                    group = next(e for e in events if e['kind']=='or')
                    self.assertEqual([leaf['trigger'] for leaf in group['fired_triggers']], [0,1])

    def test_simultaneous_clock_reset_obeys_source_comparison_at_exact_root(self):
        clock = 'cross(V(u,r)-.5,1,.001,.001)'
        reset = 'cross(V(v,r)-.5,1,.001,.001)'
        for relation, expected in [('>=',1),('>',2)]:
            for trigger in [clock+' or '+reset,reset+' or '+clock]:
                text = model('@(initial_step) q=0; @('+trigger+') '
                             f'if(V(v,r){relation}.5) q=1; else q=2; V(y,r)<+q;',
                             'integer q;',ports='u,v,y,r',directions='input u,v; output y; inout r;')
                program = compile_sources({'reset.va':text},[instance(connections=dict(u='u',v='v',y='y',r='0'))])
                result = transient(program,{'u':[[0,0],[1,1]],'v':[[0,0],[1,1]]},
                                   [0,.5,1],stop=1,max_step=1,kernel=KERNEL)
                self.assertEqual(states(result),[0,expected,expected])
                self.assertEqual(len(result['transient']['events']),1)
                self.assertEqual(len(result['transient']['events'][0]['fired_triggers']),2)

    def test_timer_or_is_explicitly_outside_scope(self):
        for trigger in ['timer(.5,0,.001) or cross(V(u,r)-.5)',
                        'cross(V(u,r)-.5) or timer(.5,0,.001)']:
            with self.subTest(trigger=trigger), self.assertRaisesRegex(CompileError, 'OR supports only cross'):
                execute(source('q=q+1;', kind='integer', trigger=trigger))

    def test_raw_ir_rejects_empty_single_nested_or_and_timer_leaves(self):
        trigger = 'cross(V(u,r)-.25,1,.001,.001) or cross(V(u,r)-.75,1,.001,.001)'
        program = compile_sources({'or.va': source('q=q+1;', kind='integer', trigger=trigger)}, [instance()]).to_dict()
        original = program['events'][0]['trigger']
        variants = [[], original['triggers'][:1], [original, original['triggers'][0]],
                    [dict(kind='timer',start=.5,period=0,time_tolerance=.001,enabled=True),original['triggers'][0]]]
        for leaves in variants:
            with self.subTest(leaves=leaves):
                p = copy.deepcopy(program)
                p['events'][0]['trigger']['triggers'] = leaves
                payload = dict(program=p,driven=['u'],samples=[],transient=dict(
                    pwl=[[[0,0],[1,1]]],output_times=[0,1],stop=1,max_step=1))
                run = subprocess.run([str(KERNEL)],input=json.dumps(payload),capture_output=True,text=True)
                self.assertNotEqual(run.returncode,0)
                self.assertEqual(json.loads(run.stderr)['kind'],'invalid_ir')

    def test_unrelated_input_knot_at_exact_root_does_not_change_event(self):
        # Four exact-real midpoints of submitted binary64 endpoints. Unused
        # source knots at nearby nominal times must not alter their root sets.
        from fractions import Fraction as Q
        unit=1e-6
        points=[[0,0]]
        roots=[]
        for j in range(4):
            points += [[(j+.65)*unit,0],[(j+.85)*unit,1],[(j+.9)*unit,1],[(j+1)*unit,0]]
            roots.append((Q((j+.65)*unit)+Q((j+.85)*unit))/2)
        text = model('@(initial_step) q=0; @(cross(V(u,r)-.5,1,1e-9,2e-4)) q=q+1; V(y,r)<+q;',
                     'integer q;',ports='u,w,y,r',directions='input u,w; output y; inout r;')
        p = compile_sources({'unrelated.va':text},[instance(connections=dict(u='u',w='w',y='y',r='0'))])
        observed=[]
        extra=[[0,0]]+[[(j+.75)*unit,0] for j in range(4)]+[[4*unit,0]]
        for w in [[[0,0],[4*unit,0]],extra]:
            result=transient(p,{'u':points,'w':w},[0,4*unit],
                             stop=4*unit,max_step=4*unit,kernel=KERNEL)
            self.assertEqual(states(result),[0,4])
            events=result['transient']['events']
            self.assertEqual(len(events),4)
            for event,root in zip(events,roots):
                self.assertLessEqual(abs(Q(event['time'])-root),Q(1e-9))
            observed.append(events)
        self.assertEqual(observed[0],observed[1])


if __name__ == '__main__':
    unittest.main()
