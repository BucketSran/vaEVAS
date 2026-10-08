"""Scalar case selection through the production compile/kernel path."""
GUARDS = ['LANG']
import json
from pathlib import Path
import unittest
from evas import CompileError, Instance, compile_sources, solve, transient
from evas.scs import load_scs, simulate_scs
from test_affine import KERNEL, model, instance


def program(body, declarations='real value;'):
    return compile_sources({'case.va': model(body, declarations)}, [instance()])


def output(p, inputs):
    result = solve(p, ['u'], [[v] for v in inputs], kernel=KERNEL)
    return [row['voltages'][result['nodes'].index('y')] for row in result['solutions']]


class CaseStatements(unittest.TestCase):
    def test_priority_multiple_labels_and_default_position(self):
        p = program('value=-1; case(V(u)) default: value=9; '
                    '0,1: begin value=2; value=value+1; end '
                    '1: value=5; 2: value=7; endcase V(y,r)<+value;')
        self.assertEqual(output(p, [-1, 0, 1, 2, 3]), [9, 3, 3, 7, 9])

    def test_missing_default_retains_incoming_assignment(self):
        p = program('value=8; case(V(u)) 1: value=3; endcase V(y,r)<+value;')
        self.assertEqual(output(p, [0, 1, 2]), [8, 3, 8])

    def test_parameter_labels_and_nested_cases(self):
        p = program('value=8; case(V(u)) k: case(V(u)) '
                    '1: value=4; default: value=6; endcase '
                    'default: value=9; endcase V(y,r)<+value;',
                    'parameter real k=1; real value;')
        self.assertEqual(output(p, [0, 1, 2]), [9, 4, 9])

    def test_pure_function_case_keeps_sequential_locals(self):
        function = ('analog function real pick; input x; real x,t; begin '
                    't=0; case(x) 0: t=2; 1: t=3; default: t=4; endcase '
                    'pick=t+1; end endfunction')
        self.assertEqual(output(program('V(y,r)<+pick(V(u));', function), [0, 1, 2]), [3, 4, 5])

    def test_event_case_first_match_and_observation_invariance(self):
        p = program('@(initial_step) value=0; @(timer(1,1,1e-12)) '
                    'case(V(u)) 0: value=2; 1: value=value+1; default: value=7; '
                    'endcase V(y,r)<+value;')
        for times in ([0, 1, 2, 3], [0, .5, 1, 1.5, 2, 2.5, 3]):
            result = transient(p, {'u':[[0,0],[1,0],[1.5,1],[2,1],[2.5,2],[3,2]]}, times, stop=3,
                               max_step=.25, kernel=KERNEL)
            y = result['nodes'].index('y')
            values = dict(zip(times, [row['voltages'][y] for row in result['solutions']]))
            self.assertEqual([values[t] for t in (0,1,2,3)], [0,2,3,7])

    def test_equivalent_if_and_exact_boundary_neighbors(self):
        case = program('value=8; case(V(u)) 1:value=3; endcase V(y,r)<+value;')
        equivalent = program('value=8; if(V(u)<=1) begin '
                             'if(V(u)>=1) value=3; end V(y,r)<+value;')
        import math
        inputs = [math.nextafter(1,0), 1, math.nextafter(1,2)]
        self.assertEqual(output(case,inputs), [8,3,8])
        self.assertEqual(output(case,inputs), output(equivalent,inputs))

    def test_default_without_colon_and_null_matching_body(self):
        p = program('value=1; case(V(u)) 0: ; '
                    'default value=value+1; endcase V(y,r)<+value;')
        self.assertEqual(output(p,[0,1]),[1,2])

    def test_expansion_resources_reject_before_recursive_compilation(self):
        for body in (' '.join(f'{i}: value={i};' for i in range(17)),
                     ' '.join(f'{i}: value={i};' for i in range(16))):
            with self.subTest(body=body), self.assertRaises(CompileError) as caught:
                program('value=0; case(V(u)) '+body+' endcase V(y,r)<+value;')
            self.assertEqual(caught.exception.diagnostic['code'],'resource_budget')

    def test_frozen_scs_and_manual_manifest_match_independent_table(self):
        root = Path(__file__).resolve().parents[1]/'validation/cases/case_statements'
        manifest = json.loads((root/'table.json').read_text())
        bench = load_scs(root/'table.scs')
        self.assertEqual(bench.manifest['instances'], manifest['instances'])
        self.assertEqual(bench.manifest['transient'], manifest['transient'])
        p = compile_sources({str(root/'dut.va'):(root/'dut.va').read_text()},
                            [Instance(**i) for i in manifest['instances']])
        expected = transient(p,kernel=KERNEL,**manifest['transient'],**manifest['tolerances'])
        actual = simulate_scs(root/'table.scs',kernel=KERNEL)
        self.assertEqual(actual['solutions'],expected['solutions'])
        answer = json.loads((root/'expected.json').read_text())
        for row in actual['solutions']:
            for prefix in ('y','f'):
                self.assertEqual([row['voltages'][actual['nodes'].index(f'{prefix}{i}')]
                                  for i in range(5)],answer[prefix])

    def test_rejected_boundaries(self):
        bodies = [
            'value=0; case(missing) endcase V(y,r)<+value;',
            'value=0; case(missing) default:value=1; endcase V(y,r)<+value;',
            '@(initial_step) value=0; @(timer(1)) case(value) 0:value=1; endcase V(y,r)<+value;',
            'value=0; case(V(u)) default:value=1; default:value=2; endcase V(y,r)<+value;',
            'case(V(u)) 1:value=1; endcase V(y,r)<+value;',
            'case(V(u)) 1:V(y,r)<+1; default:V(y,r)<+2; endcase',
            'value=0; case(idt(V(u),0)) 1:value=1; endcase V(y,r)<+value;',
            'value=0; case(V(y)) 1:value=1; endcase V(y,r)<+value;',
        ]
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(CompileError):
                program(body)


if __name__ == '__main__':
    unittest.main()
