"""Independent event-body answers; no new formal matrix conditions.

Predicates read RN of each submitted-source sample. Fraction proves the full
rounding cell independently of EVAS; continuous physical interpolation remains exact.
"""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["EVENT-ORDER", "EVENT-CONDITIONS"]

import copy
from fractions import Fraction as Q
import json
import subprocess
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model
from initial_record_contract import check_initial_record_batch


def source(body, *, trigger='timer(0.5,0.5,0.001)', initial=0, kind='real', rhs='q', extra=''):
    return model(f'@(initial_step) q={initial}; @({trigger}) begin {body} end '
                 f'V(y,r)<+{rhs}; {extra}', f'{kind} q;' + ('electrical z;' if 'V(z' in body+extra else ''))


def execute(text, *, points=None, times=None, step=2, instances=None, initial_records=None, **tolerances):
    program = compile_sources({'conditions.va': text}, instances or [instance()])
    result = transient(program, {'u': points or [[0,0],[1,1]]}, times or [0,.5,1],
                     stop=1, max_step=step, kernel=KERNEL, **tolerances)
    return (check_initial_record_batch(result, program, *initial_records)
            if initial_records is not None else result)


def states(result):
    return [row[0] for row in result['transient']['states']]


class ConditionalEvents(unittest.TestCase):
    def test_four_relations_at_exact_zero_and_neighbor(self):
        for relation, expected in [('>=',[0,2,2]), ('>',[0,3,2]),
                                   ('<=',[0,2,3]), ('<',[0,3,3])]:
            with self.subTest(relation=relation):
                r = execute(source(f'if (V(u,r) {relation} 0.5) q=2; else q=3;'), initial_records=([0], [0], 1))
                self.assertEqual(states(r), expected)
                self.assertEqual([e['time'] for e in r['transient']['events']], [.5,1])

    def test_order_nested_blocks_and_nearest_else(self):
        text = source('''q=q+1;
            if (V(u,r)>=0.25) if (V(u,r)>0.5) begin ; q=q+2; end else q=q+4;
            q=2*q;''', kind='integer')
        self.assertEqual(states(execute(text)), [0,10,26])

    def test_unselected_ambiguous_predicate_is_not_executed(self):
        text = source('if (V(u,r)>0) q=7; else if (V(u,r)>0.5) q=9;')
        self.assertEqual(states(execute(text, points=[[0,.1],[1,.9]])), [0,7,7])

    def test_missing_else_and_null_statement_leave_state_unchanged(self):
        for body in ['if (V(u,r)>0.5) q=9;', 'if (V(u,r)<=0.5) ; else q=9;']:
            self.assertEqual(states(execute(source(body, initial=4))), [4,4,9])

    def test_branch_cache_tracks_reset_sample_reset_and_grid(self):
        text = source('if (V(u,r)>=0.5) q=0; else q=2*V(u,r)+1;',
                      trigger='timer(0.25,0.25,0.001)', initial=3)
        points = [[0,0],[.25,.75],[.5,.25],[.75,.75],[1,.25]]
        times = [0,.25,.5,.75,1]
        reference = execute(text, points=points, times=times)
        self.assertEqual(states(reference), [3,0,1.5,0,1.5])
        for step in [.0625,2]:
            result = execute(text, points=points, times=[0,.125,.25,.5,.625,.75,1], step=step)
            self.assertEqual(result['transient']['events'], reference['transient']['events'])
            self.assertEqual(states(result), [3,3,0,1.5,1.5,0,1.5])

    def test_cross_selects_at_actual_event_time(self):
        text = source('if (V(u,r)>=0.5) q=2; else q=3;',
                      trigger='cross(V(u,r)-0.5,1,0.001,0.001)')
        self.assertEqual(states(execute(text, initial_records=([0], [0], 1))), [0,2,2])
        # The exact root is 1/3, where u=1. LRM 2.4 5.10.3.1 places the event
        # after the crossing; the matching-guard certificate proves u>1 just
        # after tau. A rounded representative cannot flip the falling side.
        text = source('if (V(u,r)>1) q=2; else q=3;',
                      trigger='cross(V(u,r)-1,1,0.001,0.001)')
        result = execute(text, points=[[0,0],[1,3]], initial_records=([0], [0], 1))
        self.assertEqual([e['after'] for e in result['transient']['events'] if e['kind']=='cross'], [[2]])
        text = source('if (V(u,r)>1) q=2; else q=3;',
                      trigger='cross(V(u,r)-1,-1,0.001,0.001)')
        result = execute(text, points=[[0,3],[1,0]], initial_records=([0], [0], 1))
        self.assertEqual([e['after'] for e in result['transient']['events'] if e['kind']=='cross'], [[3]])

    def test_rounded_equality_is_not_a_truth_certificate(self):
        # Historical method identity retained; oracle migrates to ADR-006.
        controls = [(.1,.9,'>',False), (.2,.7999999999999999,'>=',True)]
        for a,b,relation,truth in controls:
            exact = (Q(a)+Q(b))/2
            # All values in this exact singleton round to .5. The lower
            # neighbor gap is half the upper gap at this binade boundary.
            self.assertTrue(Q(.5)-Q(1,2**55) <= exact <= Q(.5)+Q(1,2**54))
            self.assertEqual(float(exact),.5)
            text = source(f'if (V(u,r){relation}0.5) q=2; else q=3;')
            with self.subTest(a=a):
                result=execute(text, points=[[0,a],[1,b]], initial_records=([0], [0], 1))
                timers=[e for e in result['transient']['events'] if e['kind']=='timer']
                self.assertEqual(timers[0]['after'],[2 if truth else 3])
                self.assertEqual(states(result),[0,2 if truth else 3,2])
                self.assertEqual([e['after'] for e in result['_checked_initial_records']],[[0]])
                # The unchanged true source band crosses rounding cells.
                with self.assertRaisesRegex(KernelError,'event_condition.*conditions.va'):
                    execute(text, points=[[0,a],[1,b]],source_errors={'u':1e-12}, initial_records=([0], [0], 1))

    def test_input_enclosure_reaches_sampled_state_certificate(self):
        text = source('if (V(u,r)>0) q=V(u,r)-0.5; else q=0;', rhs='1e16*q')
        # Original periodic timer also fires at t=1, where the source is .9.
        # At .5, sample RN((Q(.1)+Q(.9))/2)=.5, then subtraction is 0.
        # At 1, q=RN(.9-.5); preserve this nonzero final observation.
        expected=[0.,0.,1e16*(.9-.5)]
        result=execute(text, points=[[0,.1],[1,.9]], initial_records=([0], [0], 1))
        self.assertEqual(states(result),[0.,0.,.9-.5])
        for row,want in zip(result['solutions'],expected):
            self.assertAlmostEqual(row['voltages'][result['nodes'].index('y')],want,delta=max(1e-12,abs(want)*1e-10))

    def test_input_enclosure_reaches_amplified_voltage_certificate(self):
        text = source('if (V(u,r)>0) q=V(u,r); else q=0;',
                      initial=.5, rhs='1e8*(q-0.5)')
        result=execute(text, points=[[0,.1],[1,.9]], initial_records=([0], [.5], 1))
        self.assertEqual(states(result),[.5,.5,.9])
        for row,want in zip(result['solutions'],[0.,0.,1e8*(.9-.5)]):
            self.assertAlmostEqual(row['voltages'][result['nodes'].index('y')],want,delta=max(1e-12,abs(want)*1e-10))

    def test_internal_state_independent_predicate(self):
        text = source('if (V(z,r)>=0.75) q=2; else q=3;', extra='V(z,r)<+2*V(u,r)-0.25;')
        self.assertEqual(states(execute(text)), [0,2,2])

    def test_selected_assignments_keep_joint_voltage_state_solution(self):
        text = source('if (V(u,r)>=0.5) q=0.5*V(y,r)+1; else q=0;')
        self.assertEqual(states(execute(text)), [0,2,2])  # q=.5q+1
        self.assertEqual([s['voltages'][-1] for s in execute(text)['solutions']], [0,2,2])

    def test_unselected_state_predicates_leave_selected_value_unchanged(self):
        for expression in ['q', '0*q', 'q-q', '1e-200*(1e-200*q)']:
            text = source(f'if (1>0) q=2; else if ({expression}>0) q=3;')
            with self.subTest(expression=expression):
                self.assertEqual(states(execute(text)), [0, 2, 2])

    def assert_source_state_event_box(self, text, expected):
        # Native source execution keeps every t0/timer record. No legacy-event
        # filtering or old unsupported diagnostic is used as a numeric oracle.
        program = compile_sources({'conditions.va': text}, [instance()])
        result = transient(program, {'u': [[0,0],[1,1]]}, [0,.5,1],
                           stop=1, max_step=2, kernel=KERNEL)
        # Validate the complete initial record without filtering the raw events.
        check_initial_record_batch(result, program, [0], [0], 1)
        self.assertEqual(result['transient']['times'], [0,.5,1])
        self.assertEqual(result['transient']['state_names'], ['dut:q'])
        self.assertEqual(states(result), expected)
        events = result['transient']['events']
        self.assertEqual(len(events), 3)
        before = 0
        declarations = program.to_dict()['events']
        for event,time,after,kind in zip(events,[0,.5,1],expected,
                ['initial_step','timer','timer']):
            declaration = declarations[event['event']]
            origin = declaration['origin']
            self.assertEqual(declaration['trigger']['kind'], kind)
            self.assertEqual((event['time'], event['kind']), (time, kind))
            self.assertEqual(event['origin'],
                f"{origin['source']}:{origin['line']}:{origin['column']} ({origin['instance']})")
            self.assertEqual((event['before'], event['after']), ([before], [after]))
            before = after
        evidence = result['observation_evidence']
        self.assertTrue(evidence['initial_settled'])
        self.assertEqual(evidence['nodes'], result['nodes'])
        self.assertEqual(len(result['solutions']), len(expected))
        self.assertEqual(len(evidence['voltage_bounds_V']), len(expected))
        for time,value,solution,box in zip([0,.5,1],expected,result['solutions'],
                evidence['voltage_bounds_V']):
            for name,want in [('0',0),('u',time),('y',value)]:
                node = result['nodes'].index(name)
                self.assertEqual(solution['voltages'][node], want)
                self.assertLessEqual(Q.from_float(box[node][0]), want)
                self.assertGreaterEqual(Q.from_float(box[node][1]), want)
                controls = evidence['effective_controls']
                tolerance = controls['absolute_V'] + controls['relative']*max(abs(x) for x in box[node])
                self.assertLessEqual((box[node][1]-box[node][0])/2, tolerance)

    def test_unselected_legal_voltage_branches_skip_numeric_execution(self):
        for expression in ['V(y,r)', '0*V(y,r)', 'V(y,y)', 'V(y,r)-V(y,r)', '1e-200*(1e-200*V(y,r))']:
            text = source(f'if (1>0) q=2; else if ({expression}>0) q=3;')
            with self.subTest(expression=expression):
                self.assert_source_state_event_box(text, [0,2,2])

    def test_selected_feedback_predicates_need_a_physical_enclosure(self):
        for expression in ['V(y,r)', '0*V(y,r)', 'V(y,r)-V(y,r)', '1e-200*(1e-200*V(y,r))']:
            text = source(f'if (1<0) q=2; else if ({expression}>0) q=3;')
            with self.subTest(expression=expression), self.assertRaisesRegex(KernelError,'event_condition'):
                execute(text)
        # A same-node voltage difference is identically zero after its two
        # node names have passed the original source checks.
        self.assert_source_state_event_box(source('if (1<0) q=2; else if (V(y,y)>0) q=3;'), [0,0,0])

    def test_structural_internal_feedback_does_not_disappear(self):
        for rhs in ['q-q', '0*q', '1e-200*(1e-200*q)', 'V(y,r)-V(y,r)']:
            text = source('if (V(z,r)>0) q=2; else q=3;', extra=f'V(z,r)<+{rhs};')
            with self.subTest(rhs=rhs), self.assertRaisesRegex(KernelError, 'unsupported_condition'):
                execute(text)

    def test_history_dependent_predicate_rejected(self):
        text = source('if (V(z,r)>0) q=2; else q=3;', extra='V(z,r)<+absdelay(V(u,r),0.125);')
        with self.assertRaisesRegex(KernelError, 'unsupported_condition'):
            execute(text)

    def test_integer_intermediate_overflow_is_checked_only_on_selected_path(self):
        body = 'if (V(u,r)>0.5) begin q=q+1; q=q-1; end else q=4;'
        text = source(body, trigger='timer(0.5,0,0.001)', kind='integer', initial=2147483647)
        self.assertEqual(states(execute(text)), [2147483647,4,4])
        with self.assertRaisesRegex(KernelError,'state_range'):
            execute(text, points=[[0,1],[1,1]])

    def test_instances_bind_parameters_and_preserve_order(self):
        text = source('if (V(u,r)>=threshold) q=V(u,r); else q=-1;').replace('real q;', 'real q; parameter real threshold=0.5;')
        instances = [instance('a',connections=dict(u='u',y='ya',r='0'), parameters={'threshold':.25}),
                     instance('b',connections=dict(u='u',y='yb',r='0'), parameters={'threshold':.75})]
        for order in [instances,list(reversed(instances))]:
            r = execute(text, instances=order)
            row = dict(zip(r['nodes'], r['solutions'][1]['voltages']))
            self.assertEqual((row['ya'],row['yb']), (.5,-1))

    def test_unsupported_syntax_and_static_invalid_arm(self):
        for body in ['if (1>0) q=2; else missing=1;', 'if (1>0) q=2; else V(y,r)<+2;',
                     'if (1>0) q=2; else q=idt(V(u,r),0);',
                     'if (1>0) q=2; else if (V(missing,missing)>0) q=3;',
                     'if (1>0) q=2; else if (0*V(missing,r)>0) q=3;',
                     'if (1>0) q=2; else q=missingfn(1.0);',
                     'if (1>0) q=2; else q=1.0&1;']:
            with self.subTest(body=body), self.assertRaises(CompileError):
                execute(source(body))

    def test_selected_nonlinear_input_condition_uses_source_value(self):
        # At the two source timers u is exactly .5 and 1. Its binary64
        # products are exactly .25 and 1; Fraction independently fixes truth.
        truths = [Q.from_float(t)**2 > Q(1,2) for t in [.5,1]]
        self.assert_source_state_event_box(source('if (V(u,r)*V(u,r)>0.5) q=1;'),
                                          [0, *[int(truth) for truth in truths]])
        self.assert_source_state_event_box(source('if (V(u,r)*V(u,r)>0.5) q=1;else q=2;'),
                                          [0, *[1 if truth else 2 for truth in truths]])
        with self.assertRaisesRegex(KernelError,'event_condition'):
            execute(source('if (V(u,r)*V(u,r)>0.5) q=1;else q=2;'),
                    points=[[0,2**-.5],[1,2**-.5]], source_errors={'u':1e-16})

    def test_initial_condition_uses_initial_input_and_preserves_missing_else(self):
        text = source('if (V(u,r)>0.5) q=1;', trigger='initial_step')
        for points, expected in [([[0,0],[1,1]], [0,0,0]),
                                 ([[0,1],[1,0]], [1,1,1])]:
            with self.subTest(points=points):
                result = execute(text, points=points, initial_records=([0], [expected[0]], 2))
                self.assertEqual(states(result), expected)
                self.assertEqual(result['transient']['events'], [])

    def test_equality_and_logic_without_else_preserve_unselected_state(self):
        for predicate, expected in [('V(u,r)==0.5',[0,1,1]),
                                    ('V(u,r)!=0.5',[0,0,1]),
                                    ('V(u,r)>0.5 && V(u,r)<1',[0,0,0])]:
            with self.subTest(predicate=predicate):
                self.assertEqual(states(execute(source(f'if({predicate}) q=1;'))),expected)

    def test_conditional_target_transition_has_independent_edge_values(self):
        text = source('if (V(u,r)>0.25) q=2; else q=0;',
                      trigger='timer(0.25,0.25,0.001)', rhs='transition(q,0,0.25,0.25)')
        for step in [.0625,2]:
            result = execute(text, times=[0,.25,.5,.625,.75,1], step=step)
            y = result['nodes'].index('y')
            self.assertEqual([row['voltages'][y] for row in result['solutions']], [0,0,0,1,2,2])
            self.assertEqual(states(result), [0,0,2,2,2,2])

    def test_independent_contribution_order_and_local_name_invariance(self):
        pieces = ['V(y,r)<+0.25*q;', 'V(y,r)<+0.75*q;']
        text = source('if (V(u,r)>=0.5) q=0.5*V(y,r)+1; else q=0;')
        reference = execute(text)
        for additions in [pieces, list(reversed(pieces))]:
            variant = text.replace('V(y,r)<+q;', ''.join(additions)).replace('q', 'held')
            result = execute(variant)
            self.assertEqual(result['solutions'], reference['solutions'])
            self.assertEqual(result['transient']['states'], reference['transient']['states'])

    def test_raw_ir_conditions_are_checked_without_frontend(self):
        p = compile_sources({'raw.va': source('if (V(u,r)>0.5) q=2; else q=3;')}, [instance()]).to_dict()
        def request(program):
            payload = dict(program=program, driven=['u'], samples=[], transient=dict(
                pwl=[[[0,0],[1,1]]], output_times=[0,1], stop=1, max_step=2))
            run = subprocess.run([str(KERNEL)], input=json.dumps(payload), capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            return json.loads(run.stderr)['kind']
        for mutation, kind in [('relation','invalid_request'), ('missing','invalid_request'),
                               ('assignments','invalid_request'), ('state_index','invalid_ir'),
                               ('index','invalid_ir'), ('owner','invalid_ir'), ('extra','invalid_request')]:
            program = copy.deepcopy(p)
            cond = program['events'][0]['body'][0]
            if mutation=='relation': cond['relation']='eq'
            elif mutation=='missing': del cond['else_body']
            elif mutation=='assignments': program['events'][0]['assignments']=program['events'][0].pop('body')
            elif mutation=='state_index': cond['left']={'op':'state','state':100}
            elif mutation=='index': cond['else_body'][0]['state']=100
            elif mutation=='owner': cond['origin']['instance']='elsewhere'
            else: cond['then_body'][0]['unknown']=1
            with self.subTest(mutation=mutation):
                self.assertEqual(request(program), kind)

    def test_raw_ir_state_predicate_reads_accepted_state_at_each_event(self):
        program = compile_sources({'raw.va': source('if (V(u,r)>0.5) q=2; else q=3;')}, [instance()]).to_dict()
        program['events'][0]['body'][0]['left'] = {'op':'state','state':0}
        payload = dict(program=program, driven=['u'], samples=[], transient=dict(
            pwl=[[[0,0],[1,1]]], output_times=[0,1], stop=1, max_step=2))
        run = subprocess.run([str(KERNEL)], input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        result = check_initial_record_batch(result, program, *([0], [0], 1))
        self.assertEqual(result['transient']['states'], [[0],[2]])
        self.assertEqual([event['after'] for event in result['transient']['events']], [[3],[2]])


if __name__ == '__main__':
    unittest.main()
