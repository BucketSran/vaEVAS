"""IR33 occurrence frames, joint reset release and inactive-arm validity."""
GUARDS = ["LANG", "TIMER", "DYNAMICS"]

import copy
import math
import json
import unittest

from evas import KernelError, compile_sources, transient
from evas.runtime import _invoke
from test_affine import KERNEL, instance, model


class ProcedureRuntime(unittest.TestCase):
    def test_feedback_reset_releases_at_same_occurrence(self):
        source = model('''reset=0;
            @(timer(0.5,0.5)) reset=1;
            V(y,r)<+idt(1-V(y,r),0,reset);''', 'integer reset;')
        times = [0, .25, .5, .75, 1, 1.25, 1.5, 1.75]
        expected = [1-math.exp(-(t-max([0]+[q for q in [.5,1,1.5] if q<=t])))
                    for t in times]
        for step in [2, .03125]:
            with self.subTest(max_step=step):
                program = compile_sources({'feedback-reset.va':source}, [instance()])
                result = transient(program, {'u':[[0,1],[2,1]]}, times,
                    stop=2, max_step=step, vabstol=1e-7, reltol=0, kernel=KERNEL)
                actual = [s['voltages'][result['nodes'].index('y')]
                          for s in result['solutions']]
                for value, want in zip(actual, expected):
                    self.assertLessEqual(abs(value-want), 1e-7)

    def test_inactive_numeric_domain_and_invalid_references_are_distinct(self):
        source = model('''@(initial_step) q=1;
            a=q; @(timer(0.5))q=a+2; V(y,r)<+q;''', 'real q,a;')
        program = compile_sources({'inactive-arm.va':source}, [instance()])
        payload = {'program':json.loads(json.dumps(program.to_dict())), 'driven':['u'], 'samples':[],
                   'transient':{'pwl':[[[0,0],[1,0]]], 'output_times':[0,.5,1],
                                'stop':1, 'max_step':.5}}
        procedure = payload['program']['procedures'][0]
        ordinal = max(s['expanded_statement_ordinal'] for s in procedure['body'])+1
        origin = dict(source='inactive-arm.va', line=1, column=1, instance='dut', expansion=[])
        constant = lambda value: dict(op='affine', constant=value, terms=[])
        action = dict(kind='assign', state=0, rhs=dict(op='real_binary', operation='divide',
                      left=constant(1), right=constant(0), origin=origin))
        procedure['body'].append(dict(expanded_statement_ordinal=ordinal,
            action=dict(kind='procedure_if', relation='gt', left=constant(0),
                right=constant(1), origin=origin,
                then_body=[dict(expanded_statement_ordinal=ordinal+1, action=action)],
                else_body=[])))
        response = _invoke(payload, KERNEL, 30)
        self.assertEqual([s['voltages'][response['nodes'].index('y')]
                          for s in response['solutions']], [1,3,3])
        for rhs in [dict(op='state', state=999), dict(op='real_local', binding=999),
                    dict(op='operator', operator=999)]:
            with self.subTest(rhs=rhs):
                invalid = copy.deepcopy(payload)
                invalid['program']['procedures'][0]['body'][-1]['action']['then_body'][0]['action']['rhs'] = rhs
                with self.assertRaises(KernelError) as caught:
                    _invoke(invalid, KERNEL, 30)
                self.assertEqual(caught.exception.diagnostic['kind'], 'invalid_ir')
