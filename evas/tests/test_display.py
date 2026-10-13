"""Measurement records must follow accepted procedural execution."""
GUARDS = ['LANG', 'EVENT-ORDER', 'EVENT-CONDITIONS']

import unittest
import copy
import json
import subprocess
from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


def execute(body, declarations='integer n;'):
    program = compile_sources({'display.va': model(body, declarations)}, [instance()])
    return transient(program, {'u': [[0,1],[1,1]]}, [0,.5,1],
                     stop=1, max_step=1, kernel=KERNEL)


class DisplayMeasurements(unittest.TestCase):
    def test_timer_records_prior_and_following_assignment_in_source_order(self):
        result = execute('''@(timer(0.5)) begin
            $display("before=%d t=%.12g", n, $abstime);
            n=n+1; $display("after=%d", n);
            end V(y,r)<+n;''')
        records = result['transient']['display_records']
        self.assertEqual([r['text'] for r in records], ['before=0 t=0.5', 'after=1'])
        self.assertEqual([r['time'] for r in records], [.5,.5])
        self.assertEqual(len(records), 2)

    def test_discarded_time_proposal_cannot_duplicate_measurement(self):
        program = compile_sources({'display.va': model(
            '@(timer(0.5)) begin n=n+1; $display("n=%d",n); end V(y,r)<+n;',
            'integer n;')}, [instance()])
        result = transient(program, {'u':[[0,1],[1,1]]}, [0,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertGreater(result['transient']['discarded_trials'], 0)
        self.assertEqual([r['text'] for r in result['transient']['display_records']], ['n=1'])

    def test_selected_branch_emits_only_selected_record(self):
        result = execute('''@(timer(0.5)) begin
            if (V(u,r)>0) $display("yes=%d", n);
            else $display("no=%d", n);
            end V(y,r)<+n;''')
        self.assertEqual([r['text'] for r in result['transient']['display_records']], ['yes=0'])

    def test_final_record_uses_stop_and_accepted_timer_state(self):
        result = execute('''@(timer(0.5)) n=n+2;
            @(final_step) $display("final=%d t=%.12g", n, $abstime);
            V(y,r)<+n;''')
        records = result['transient']['display_records']
        self.assertEqual([(r['time'],r['text']) for r in records], [(1,'final=2 t=1')])

    def test_passive_initial_records_source_order_before_timer_zero(self):
        text = model('''@(initial_step) begin $display("before=%d",n); n=3;
            $display("after=%d",n); end
            @(timer(0)) $display("timer=%d",n);''', 'integer n;')
        program = compile_sources({'display.va':text},[instance(connections=dict(u='u',y='u',r='0'))])
        result = transient(program, {'u':[[0,1],[1,1]]}, [0,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([r['text'] for r in result['transient']['display_records']],
                         ['before=0','after=3','timer=3'])

    def test_final_runs_after_same_stop_timer_even_when_declared_first(self):
        result = execute('''@(final_step) $display("final=%d",n);
            @(timer(1)) n=7; V(y,r)<+n;''')
        self.assertEqual([r['text'] for r in result['transient']['display_records']], ['final=7'])
        events = result['transient']['events']
        self.assertEqual([(e['event'],e['time'],e['kind']) for e in events],
                         [(1,1,'timer'),(0,1,'final_step')])
        record = result['transient']['display_records'][0]
        self.assertEqual((record['event'],record['time']), (0,1))

    def test_passive_floating_voltage_is_rejected(self):
        text = model('@(final_step) $display("n=%d",n);','integer n;')
        program = compile_sources({'display.va':text}, [instance()])
        with self.assertRaises(KernelError):
            transient(program, {'u':[[0,1],[1,1]]}, [0,1],stop=1,max_step=1,kernel=KERNEL)

    def test_raw_ir_rejects_bad_display_origin_and_reference(self):
        program = compile_sources({'display.va':model(
            '@(timer(0.5)) $display("n=%d",n); V(y,r)<+n;', 'integer n;')},[instance()])
        for field, value in [('source',''),('instance','other'),('line',0),('column',0)]:
            with self.subTest(field=field):
                payload = copy.deepcopy(program.to_dict())
                payload['events'][0]['body'][0]['origin'][field] = value
                request = dict(program=payload,driven=['u'],samples=[],transient=dict(
                    pwl=[[[0,1],[1,1]]],output_times=[0,1],stop=1,max_step=1))
                process = subprocess.run([str(KERNEL)],input=json.dumps(request),capture_output=True,text=True)
                self.assertNotEqual(process.returncode,0)
                self.assertEqual(process.stdout,'')
                self.assertEqual(json.loads(process.stderr)['kind'],'invalid_ir')
        for op,index in [('state',999),('operator',999)]:
            with self.subTest(op=op):
                payload = copy.deepcopy(program.to_dict())
                payload['events'][0]['body'][0]['args'] = [{'op':op,op:index}]
                request = dict(program=payload,driven=['u'],samples=[],transient=dict(
                    pwl=[[[0,1],[1,1]]],output_times=[0,1],stop=1,max_step=1))
                process = subprocess.run([str(KERNEL)],input=json.dumps(request),capture_output=True,text=True)
                self.assertNotEqual(process.returncode,0)
                self.assertEqual(process.stdout,'')
                self.assertIn(json.loads(process.stderr)['kind'],['invalid_ir','unsupported_display'])

    def test_invalid_format_and_initial_side_effect_are_explicit(self):
        for body in ['@(timer(0.5)) $display("bad=%s",n);',
                     '@(timer(0.5)) $display("bad=%d");',
                     '@(initial_step) $display("bad=%d",n);']:
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_sources({'display.va':model(body+' V(y,r)<+n;','integer n;')},[instance()])
