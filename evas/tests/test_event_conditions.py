"""Independent event-body answers; no new formal matrix conditions.

Predicates refer to the exact-real interpolation of submitted binary64 points
at the chosen event time. Fraction supplies boundary controls, not EVAS output.
"""

# Guarded conditions/capabilities: see docs/PROCESS.md and docs/TRACEABILITY.md
GUARDS = ["EVENT-ORDER", "EVENT-CONDITIONS"]

import copy
from fractions import Fraction as Q
import json
import subprocess
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


def source(body, *, trigger='timer(0.5,0.5,0.001)', initial=0, kind='real', rhs='q', extra=''):
    return model(f'@(initial_step) q={initial}; @({trigger}) begin {body} end '
                 f'V(y,r)<+{rhs}; {extra}', f'{kind} q;' + ('electrical z;' if 'V(z' in body+extra else ''))


def execute(text, *, points=None, times=None, step=2, instances=None, **tolerances):
    program = compile_sources({'conditions.va': text}, instances or [instance()])
    return transient(program, {'u': points or [[0,0],[1,1]]}, times or [0,.5,1],
                     stop=1, max_step=step, kernel=KERNEL, **tolerances)


def states(result):
    return [row[0] for row in result['transient']['states']]


class ConditionalEvents(unittest.TestCase):
    def test_four_relations_at_exact_zero_and_neighbor(self):
        for relation, expected in [('>=',[0,2,2]), ('>',[0,3,2]),
                                   ('<=',[0,2,3]), ('<',[0,3,3])]:
            with self.subTest(relation=relation):
                r = execute(source(f'if (V(u,r) {relation} 0.5) q=2; else q=3;'))
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
        self.assertEqual(states(execute(text)), [0,2,2])
        # The exact root is 1/3, where u=1. The representative may be later;
        # an exact matching-guard certificate still proves u>1 is false at tau.
        text = source('if (V(u,r)>1) q=2; else q=3;',
                      trigger='cross(V(u,r)-1,1,0.001,0.001)')
        result = execute(text, points=[[0,0],[1,3]])
        self.assertEqual(result['transient']['events'][0]['after'], [3])

    def test_rounded_equality_is_not_a_truth_certificate(self):
        controls = [(.1,.9,'>',True), (.2,.7999999999999999,'>=',False)]
        for a,b,relation,truth in controls:
            exact = (Q(a)+Q(b))/2-Q(.5)
            self.assertEqual(exact>0 if relation=='>' else exact>=0, truth)
            self.assertEqual(.5*a+.5*b, .5)
            text = source(f'if (V(u,r){relation}0.5) q=2; else q=3;')
            with self.subTest(a=a), self.assertRaisesRegex(KernelError,'event_condition.*conditions.va'):
                execute(text, points=[[0,a],[1,b]])

    def test_input_enclosure_reaches_sampled_state_certificate(self):
        text = source('if (V(u,r)>0) q=V(u,r)-0.5; else q=0;', rhs='1e16*q')
        # Exact output is 1e16*((Q(.1)+Q(.9))/2-Q(.5)), about .139 V.
        # Numeric q and its equation residual are zero; exact q is nonzero.
        with self.assertRaisesRegex(KernelError, 'event_accuracy'):
            execute(text, points=[[0,.1],[1,.9]])

    def test_input_enclosure_reaches_amplified_voltage_certificate(self):
        text = source('if (V(u,r)>0) q=V(u,r); else q=0;',
                      initial=.5, rhs='1e8*(q-0.5)')
        with self.assertRaisesRegex(KernelError,'event_accuracy.*y'):
            execute(text, points=[[0,.1],[1,.9]])

    def test_internal_state_independent_predicate(self):
        text = source('if (V(z,r)>=0.75) q=2; else q=3;', extra='V(z,r)<+2*V(u,r)-0.25;')
        self.assertEqual(states(execute(text)), [0,2,2])

    def test_selected_assignments_keep_joint_voltage_state_solution(self):
        text = source('if (V(u,r)>=0.5) q=0.5*V(y,r)+1; else q=0;')
        self.assertEqual(states(execute(text)), [0,2,2])  # q=.5q+1
        self.assertEqual([s['voltages'][-1] for s in execute(text)['solutions']], [0,2,2])

    def test_unselected_bad_stateful_branches_still_reject(self):
        for expression in ['q', '0*q', 'q-q', '1e-200*(1e-200*q)']:
            text = source(f'if (1>0) q=2; else if ({expression}>0) q=3;')
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                execute(text)
        for expression in ['V(y,r)', '0*V(y,r)', 'V(y,y)', 'V(y,r)-V(y,r)', '1e-200*(1e-200*V(y,r))']:
            text = source(f'if (1>0) q=2; else if ({expression}>0) q=3;')
            with self.subTest(expression=expression), self.assertRaisesRegex(KernelError,'unsupported_condition'):
                execute(text)

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
        for body in ['if (V(u,r)==0.5) q=1;', 'if (V(u,r)!=0.5) q=1;',
                     'if (V(u,r)>0.5 && V(u,r)<1) q=1;',
                     'if (1>0) q=2; else missing=1;', 'if (1>0) q=2; else V(y,r)<+2;',
                     'if (1>0) q=2; else q=idt(V(u,r),0);']:
            with self.subTest(body=body), self.assertRaises(CompileError):
                execute(source(body))
        for trigger in ['initial_step']:
            with self.subTest(trigger=trigger), self.assertRaises(CompileError):
                execute(source('if (V(u,r)>0.5) q=1;', trigger=trigger))
        with self.assertRaisesRegex(KernelError,'unsupported_transient'):
            execute(source('if (V(u,r)*V(u,r)>0.5) q=1;'))

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
                               ('assignments','invalid_request'), ('state','unsupported_condition'),
                               ('index','invalid_ir'), ('owner','invalid_ir'), ('extra','invalid_request')]:
            program = copy.deepcopy(p)
            cond = program['events'][0]['body'][0]
            if mutation=='relation': cond['relation']='eq'
            elif mutation=='missing': del cond['else_body']
            elif mutation=='assignments': program['events'][0]['assignments']=program['events'][0].pop('body')
            elif mutation=='state': cond['left']={'op':'state','state':0}
            elif mutation=='index': cond['else_body'][0]['state']=100
            elif mutation=='owner': cond['origin']['instance']='elsewhere'
            else: cond['then_body'][0]['unknown']=1
            with self.subTest(mutation=mutation):
                self.assertEqual(request(program), kind)


if __name__ == '__main__':
    unittest.main()
