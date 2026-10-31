"""Source-driven quotient output contracts with independent answers."""
GUARDS = ['LANG', 'LIN', 'ANALOG']

import json
import subprocess
import unittest
from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL


def program(rhs='V(a)/V(b)', events=False):
    source = '''`include "disciplines.vams"
module m(a,b,y); input a,b; output y; electrical a,b,y;
real q; analog begin ''' + ('@(initial_step)q=0; @(timer(0.5))q=1; ' if events else '') + '''V(y)<+''' + rhs + ('+q' if events else '') + '''; end endmodule'''
    return compile_sources({'input-rational.va': source}, [Instance('dut','m',{'a':'a','b':'b','y':'y'})])


class InputRationalClosure(unittest.TestCase):
    def test_direct_input_quotient_preserves_original_error_bound(self):
        response = transient(program(), {'a':[[0,1],[1,3]], 'b':[[0,4],[1,4]]},
                             [0,0.5,1], stop=1,max_step=0.25,kernel=KERNEL)
        y=response['nodes'].index('y')
        self.assertEqual([r['voltages'][y] for r in response['solutions']], [0.25,0.5,0.75])

    def test_selected_input_quotient_is_evaluated_from_original_sources(self):
        response = transient(program('(V(a)>0) ? V(a)/V(b) : 0'),
                             {'a':[[0,-1],[1,3]], 'b':[[0,4],[1,4]]},
                             [0,0.5,1],stop=1,max_step=0.25,kernel=KERNEL)
        y=response['nodes'].index('y')
        self.assertEqual([r['voltages'][y] for r in response['solutions']], [0,0.25,0.75])

    def test_input_quotient_with_independent_timer_adds_the_timer_state(self):
        # a/b + q: 1/4 + 0, 2.5/4 + 1 after the 0.5 s timer, 3/4 + 1; every value is exact in binary64.
        response = transient(program(events=True), {'a':[[0,1],[1,3]],'b':[[0,4],[1,4]]},
                             [0,0.75,1],stop=1,max_step=0.25,kernel=KERNEL)
        y=response['nodes'].index('y')
        self.assertEqual([r['voltages'][y] for r in response['solutions']], [0.25,1.625,1.75])

    def test_zero_and_crossing_denominator_refuse(self):
        for points in ([[0,0],[1,0]], [[0,1],[1,-1]]):
            with self.subTest(points=points), self.assertRaises(KernelError):
                transient(program('(V(a)>0) ? V(a)/V(b) : 0'), {'a':[[0,1],[1,1]],'b':points}, [0,0.5,1],
                          stop=1,max_step=0.25,kernel=KERNEL)

    def test_inherited_source_error_cannot_be_dropped_after_division(self):
        with self.assertRaises(KernelError) as caught:
            transient(program('(V(a)>0) ? V(a)/V(b) : 0'), {'a':[[0,1],[1,1]],'b':[[0,0.01],[1,0.01]]}, [0,1],
                      stop=1,max_step=0.25,kernel=KERNEL,source_errors={'b':1e-5},
                      vabstol=1e-8,reltol=0)
        self.assertEqual(caught.exception.detail["kind"], "waveform_accuracy")

    def test_output_feedback_denominator_stays_unsupported(self):
        with self.assertRaises(KernelError):
            transient(program('V(a)/V(y)'), {'a':[[0,1],[1,1]],'b':[[0,4],[1,4]]},
                      [0,1],stop=1,max_step=0.25,kernel=KERNEL)

    def test_unselected_output_reference_cannot_qualify_as_input_only(self):
        with self.assertRaises(KernelError):
            transient(program('(V(a)>0) ? V(a)/V(b) : V(y)*V(y)'),
                      {'a':[[0,1],[1,1]],'b':[[0,4],[1,4]]},
                      [0,1],stop=1,max_step=0.25,kernel=KERNEL)

    def test_query_grid_does_not_change_selected_quotient(self):
        p=program('(V(a)>0) ? V(a)/V(b) : 0')
        sources={'a':[[0,-1],[1,3]],'b':[[0,4],[1,8]]}
        sparse=transient(p,sources,[0,0.5,1],stop=1,max_step=1,kernel=KERNEL)
        dense=transient(p,sources,[i/16 for i in range(17)],stop=1,max_step=1,kernel=KERNEL)
        y=sparse['nodes'].index('y')
        for i,j in [(0,0),(1,8),(2,16)]:
            self.assertAlmostEqual(sparse['solutions'][i]['voltages'][y],
                                   dense['solutions'][j]['voltages'][y],places=12)

    def test_uncertain_branch_boundary_stays_rejected(self):
        with self.assertRaises(KernelError):
            transient(program('(V(a)>0) ? V(a)/V(b) : 0'),
                      {'a':[[0,0],[1,0]],'b':[[0,4],[1,4]]}, [0,1],
                      stop=1,max_step=0.25,kernel=KERNEL,source_errors={'a':1e-8})

    def test_raw_dead_arm_invalid_denominator_and_hidden_output_are_rejected(self):
        for dead in [
            dict(op='affine',constant=0,terms=[dict(node=3,coefficient=0)]),
            dict(op='divide',left=dict(op='affine',constant=1,terms=[]),
                 right=dict(op='affine',constant=0,terms=[])),
        ]:
            with self.subTest(dead=dead):
                payload=program('(V(a)>0) ? V(a)/V(b) : 0').to_dict()
                # Resolve the actual output index rather than rely on node order.
                if dead['op']=='affine':
                    dead['terms'][0]['node']=payload['nodes'].index('y')
                pending=[payload['contributions'][0]['rhs']]
                while pending:
                    expression=pending.pop()
                    if expression['op']=='select':
                        expression['else_value']=dead
                        break
                    pending.extend(expression[key] for key in ('left','right') if key in expression)
                else:
                    self.fail('public compiler did not retain conditional expression')
                request=dict(program=payload,driven=['a','b'],samples=[],
                    transient=dict(pwl=[[[0,1],[1,1]],[[0,4],[1,4]]],
                                   output_times=[0,1],stop=1,max_step=0.25))
                response=subprocess.run([str(KERNEL)],input=json.dumps(request),
                                        text=True,capture_output=True)
                self.assertNotEqual(response.returncode,0)
                self.assertEqual(json.loads(response.stderr)['kind'],'unsupported_transient')
