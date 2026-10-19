"""Sample an event-only integer prefix at each physical callback root.

Floor answers use Fraction over the original binary64 operand, independently
of EVAS lowering. The prefix assignment must reject signed32 overflow before
its subsequent clamp can hide the value.
"""
import math
import os
from fractions import Fraction
from pathlib import Path
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient

GUARDS = ['LANG', 'EVENT-ORDER', 'EVENT-CONDITIONS', 'COMPOSE']
KERNEL = Path(os.environ.get('EVAS_TEST_KERNEL', str(Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel')))


def text(prefix='ratio=$floor(V(u)+0.5);if(ratio<1)ratio=1;', extra='', event='@(timer(0.25,1)) q=q+ratio;'):
    return ('`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;'
            'integer ratio,q;analog begin @(initial_step)q=0;'+prefix+event+
            'V(y)<+q;'+extra+'end endmodule')


def build(source=None):
    return compile_sources({'integer-prefix.va':source or text()},
                           [Instance('dut','m',dict(u='u',y='y'))])


def run(program, points, times=(0,.5,1.5), **options):
    return transient(program, {'u':points}, list(times), stop=times[-1], max_step=.125,
                     kernel=KERNEL, **options)


def values(result):
    i=result['nodes'].index('y')
    return [row['voltages'][i] for row in result['solutions']]


class OrdinaryIntegerEventPrefix(unittest.TestCase):
    def test_controller_fixture_is_produced_by_current_public_frontend(self):
        import json
        fixtures=Path(__file__).resolve().parents[1]/'rust_core/tests/fixtures'
        source=(fixtures/'ordinary_integer_prefix_joint.va').read_text()
        request=json.loads((fixtures/'ordinary_integer_prefix_joint.request.json').read_text())
        program=compile_sources({'ordinary_integer_prefix_joint.va':source},
                                [Instance('M','joint',dict(u='u',y='y',h='h'))])
        self.assertEqual(json.loads(json.dumps(program.to_dict())),request['program'])

    def test_floor_clamp_prefix_samples_each_current_callback(self):
        result=run(build(),[[0,2],[.75,2],[1,4],[1.5,4]])
        self.assertEqual(values(result),[0,2,6])
        trace=result['transient']
        slot=trace['state_names'].index('dut:ratio')
        # The internal seed is unobservable to q. Each callback first replaces
        # it with the Floor of that callback's current original input.
        self.assertEqual([row[slot] for row in trace['states']][1:],[2,4])

    def test_original_binary64_floor_and_signed_cuts_keep_assignment_type(self):
        for value in [-1.5,-.5,.5,math.nextafter(1.5,0),1.5,2.5]:
            want=max(1, math.floor(Fraction.from_float(value)+Fraction(1,2)))
            with self.subTest(value=value):
                result=run(build(),[[0,value],[.5,value]],times=(0,.5))
                self.assertEqual(values(result),[0,want])

    def test_signed32_first_assignment_cannot_be_hidden_by_later_clamp(self):
        prefix='ratio=$floor(V(u)+0.5);if(ratio<1)ratio=1;if(ratio>7)ratio=7;'
        for value in [2147483648.,-2147483649.]:
            with self.subTest(value=value),self.assertRaises(KernelError) as refused:
                run(build(text(prefix)),[[0,value],[.5,value]],times=(0,.5))
            self.assertEqual(refused.exception.detail['kind'],'state_range')

    def test_source_box_crossing_floor_bin_cannot_choose_nominal(self):
        with self.assertRaises(KernelError) as refused:
            run(build(),[[0,1.5],[.5,1.5]],times=(0,.5),
                source_errors={'u':1e-8},vabstol=.1,reltol=0)
        self.assertEqual(refused.exception.detail['kind'],'event_condition')

    def test_continuous_consumer_does_not_inherit_event_floor_permission(self):
        for extra in ['V(y)<+ratio;','V(y)<+0.0*ratio;']:
            with self.subTest(extra=extra),self.assertRaises(CompileError):
                build(text(extra=extra))

    def test_hidden_noninput_or_invalid_original_children_remain_rejected(self):
        for prefix in ['ratio=$floor(0*V(y)+V(u)+0.5);',
                       'ratio=$floor($abstime+V(u));',
                       'ratio=$floor(V(u)/0);']:
            with self.subTest(prefix=prefix),self.assertRaises(CompileError):
                build(text(prefix))

    def test_callback_before_definition_cannot_read_later_prefix(self):
        source=text(prefix='',event='@(timer(.25))q=ratio;ratio=$floor(V(u)+.5);')
        with self.assertRaises(CompileError):build(source)

    def test_default_owner_natural_exhaustion_keeps_two_failed_retries_charged(self):
        from unittest.mock import patch
        from evas import ordinary_integer_event_prefix
        captured=[]
        original=ordinary_integer_event_prefix.qualify
        def observe(compiler):
            captured.append(compiler)
            return original(compiler)
        with patch.object(ordinary_integer_event_prefix,'qualify',side_effect=observe):
            program=build()
        compiler=captured[-1]
        owner=program._native_audit
        self.assertIs(owner,compiler.compilation.native_audit)
        self.assertTrue(owner.active)
        # Actual repeated full wire materialization exhausts the production
        # default owner. Never set a counter, replace an owner or lower a cap.
        for _ in range(100001):
            try:program.to_dict()
            except CompileError as error:
                self.assertEqual(error.diagnostic['code'],'resource_budget')
                break
        else:self.fail('active production owner did not naturally exhaust')
        self.assertGreater(owner.used,100000)
        states=program.states
        for _ in range(2):
            spent=owner.used
            with self.assertRaises(CompileError) as refused:original(compiler)
            self.assertEqual(refused.exception.diagnostic['code'],'resource_budget')
            self.assertIs(owner,program._native_audit)
            self.assertTrue(owner.active)
            self.assertGreater(owner.used,spent)
            self.assertEqual(program.states,states)

    def test_two_integer_prefix_variables_keep_the_unexpanded_contract(self):
        source=text().replace('integer ratio,q;','integer ratio,second,q;')
        source=source.replace('@(timer(0.25,1))',
                              'second=$floor(V(u)+.5);@(timer(0.25,1))')
        source=source.replace('q=q+ratio;','q=q+ratio+second;')
        with self.assertRaises(CompileError):build(source)

    def test_original_typed_source_at_default_budget_boundary_keeps_full_wire(self):
        import hashlib
        from test_native_audit import source
        original=source(True)
        def consumer(k):
            return original.replace('n=n+1;','n=n+1;'*k).replace('m=m+1;','m=m+1;'*k)
        text225=consumer(225)
        self.assertEqual(hashlib.sha256(text225.encode()).hexdigest(),
                         '2071555869fc4bb90e83e54ccc859aa9d89d7beaf934218acade489f9ffc12da')
        instances=[Instance('dut','m',dict(y='y',z='z',r='0'))]
        program=compile_sources({'ledger.va':text225},instances)
        self.assertIsInstance(program.to_dict(),dict)
        self.assertLessEqual(program._native_audit.used,100000)
        # The next unchanged original consumer remains over the same cap.
        with self.assertRaises(CompileError):
            compile_sources({'ledger.va':consumer(226)},instances).to_dict()
