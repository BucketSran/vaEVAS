"""Measurement records must follow accepted procedural execution."""
GUARDS = ['LANG', 'EVENT-ORDER', 'EVENT-CONDITIONS']

import unittest
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from evas import CompileError, KernelError, compile_sources, transient
from evas.runtime import _invoke
from test_affine import KERNEL, instance, model


def execute(body, declarations='integer n;'):
    program = compile_sources({'display.va': model(body, declarations)}, [instance()])
    return transient(program, {'u': [[0,1],[1,1]]}, [0,.5,1],
                     stop=1, max_step=1, kernel=KERNEL)


class DisplayMeasurements(unittest.TestCase):
    def test_same_batch_display_cannot_read_another_selected_writer(self):
        for expression in ['q', 'q>0?1:0', '0*q']:
            with self.subTest(expression=expression), self.assertRaisesRegex(KernelError, 'unsupported_cross'):
                execute('@(timer(0.5)) q=1; @(timer(0.5)) $display("q=%g",'
                        + expression + '); V(y,r)<+q;', 'real q;')
        # Variable denominators are not a VA event-language admission here;
        # raw IR still must apply the same dependency guard to Divide nodes.
        program = compile_sources({'display.va': model(
            '@(timer(0.5)) q=1; @(timer(0.5)) $display("q=%g",q); V(y,r)<+q;',
            'real q;')}, [instance()]).to_dict()
        program['events'][1]['body'][0]['args'] = [dict(op='divide',
            left=dict(op='affine', constant=1, terms=[]),
            right=dict(op='add', left=dict(op='state', state=0),
                       right=dict(op='affine', constant=1, terms=[])))]
        with self.assertRaisesRegex(KernelError, 'unsupported_cross'):
            _invoke(dict(program=program, driven=['u'], samples=[], transient=dict(
                pwl=[[[0,1],[1,1]]], output_times=[0,1], stop=1, max_step=1)), KERNEL)

    def test_display_read_controls_preserve_order_and_selected_branches(self):
        result = execute('''@(timer(0.25)) q=2;
            @(timer(0.5)) begin q=q+1; $display("q=%g",q); end
            @(timer(0.75)) $display("later=%g",q);
            V(y,r)<+q;''', 'real q;')
        self.assertEqual([r['text'] for r in result['transient']['display_records']],
                         ['q=3', 'later=3'])
        result = execute('''@(timer(0.5)) q=1;
            @(timer(0.5)) if(V(u,r)<0) $display("q=%g",q);
            V(y,r)<+q;''', 'real q;')
        self.assertEqual(result['transient']['display_records'], [])

    def test_response_display_records_must_belong_to_requested_display(self):
        for body in ['@(timer(0.5)) n=n+1;', '@(timer(0.5)) $display("n=%d",n);']:
            program = compile_sources({'display.va': model(body+' V(y,r)<+n;', 'integer n;')}, [instance()])
            response = transient(program, {'u':[[0,1],[1,1]]}, [0,1],
                                 stop=1, max_step=1, kernel=KERNEL)
            response['transient']['display_records'] = [dict(time=0.5, event=0,
                origin='unrelated.va:99:1 (not_dut)', text='forged')]
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                fixture = Path(directory) / 'kernel'
                fixture.write_text('#!'+sys.executable+'\nimport sys\nsys.stdin.read()\nprint('
                                   +repr(json.dumps(response))+')\n')
                fixture.chmod(0o700)
                with self.assertRaisesRegex(KernelError, 'invalid_response'):
                    transient(program, {'u':[[0,1],[1,1]]}, [0,1],
                              stop=1, max_step=1, kernel=fixture)

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
                     '@(initial_step) $display("bad=%g",V(y,r));']:
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_sources({'display.va':model(body+' V(y,r)<+n;','integer n;')},[instance()])
