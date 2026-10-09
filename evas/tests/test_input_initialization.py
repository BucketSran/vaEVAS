"""Public initialization controls with independent answers.

EV-HC-02 is verbatim from frozen Spec A core-v1 (SHA e1ae5311), source
SHA256 02734a00e6a7502fb22f01a8f39f5628ae806af838d06c85f533d3bce762525b.
Extra stimuli and encodings are development controls, outside the paper count.
"""
GUARDS = ['LANG', 'CROSS', 'TIMER']
import json
import math
import subprocess
import unittest
from evas import CompileError, Instance, KernelError, compile_sources, transient
from evas.ir import SCHEMA_VERSION
from test_affine import KERNEL, instance, model

SOURCE = """`include "disciplines.vams"
`include "constants.vams"
module paper_hc_start(in, out, count);
 inout in, out, count;
 electrical in, out, count;
 real q,n;
 analog begin
  @(initial_step) begin q=(V(in)>0.65); n=0; end
  @(cross(V(in)-0.65,+1,1e-9,2e-4)) begin q=1; n=n+1; end
  @(cross(V(in)-0.35,-1,1e-9,2e-4)) begin q=0; n=n+1; end
  V(out)<+0.1+0.8*q;
  V(count)<+n;
 end
endmodule
"""


def original_program(source=SOURCE):
    return compile_sources({'initialization.va': source},
        [Instance('dut','paper_hc_start', {'in':'in','out':'out','count':'count'})])


def run_original(value, source=SOURCE):
    return transient(original_program(source), {'in': [[0,value],[1,value]]},
                     [0,1], stop=1, max_step=1, kernel=KERNEL)


class InputInitialization(unittest.TestCase):
    def test_original_high_low_and_exact_strict_tie(self):
        for value, q in [(.9,1),(.1,0),(.65,0)]:
            with self.subTest(value=value):
                result=run_original(value)
                self.assertEqual(result['transient']['states'], [[q,0],[q,0]])
                self.assertEqual(result['transient']['events'], [])
                for row in result['solutions']:
                    self.assertAlmostEqual(row['voltages'][result['nodes'].index('out')],.1+.8*q)

    def test_original_high_start_then_both_cross_events_keep_one_history(self):
        p=original_program()
        result=transient(p,{'in':[[0,.9],[2e-6,.5],[4e-6,.1],[6e-6,.9]]},
            [0,2e-6,3e-6,5e-6,6e-6],stop=6e-6,max_step=6e-6,kernel=KERNEL)
        self.assertEqual(result['transient']['states'],[[1,0],[1,0],[0,1],[0,1],[1,2]])
        self.assertEqual([e['event'] for e in result['transient']['events']],[1,0])
        for event, expected in zip(result['transient']['events'], [2.75e-6,5.375e-6]):
            self.assertAlmostEqual(event['time'],expected,delta=1e-15)

    def test_nonstrict_tie_and_adjacent_binary64_values(self):
        for relation in ['>', '>=', '<', '<=']:
            for value in [math.nextafter(.65,0),.65,math.nextafter(.65,1)]:
                q=int({'>':value>.65,'>=':value>=.65,'<':value<.65,'<=':value<=.65}[relation])
                result=run_original(value,SOURCE.replace('V(in)>0.65','V(in)'+relation+'0.65'))
                self.assertEqual(result['transient']['states'][0],[q,0])

    def test_affine_parameter_comparison_and_ground_are_allowed(self):
        source=model('@(initial_step) q=(2*V(u,r)-V(u,r)>=H); V(y,r)<+q;', 'parameter real H=0.65; real q;')
        p=compile_sources({'affine-initial.va':source},[instance()])
        result=transient(p,{'u':[[0,.65],[1,.65]]},[0],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(result['transient']['states'],[[1]])
        for relation, expected in [('>',0),('>=',1)]:
            source=model(f'@(initial_step) q=(V(r){relation}0); V(y,r)<+q;', 'real q;')
            p=compile_sources({'ground-initial.va':source},[instance()])
            result=transient(p,{'u':[[0,.9],[1,.9]]},[0],stop=1,max_step=1,kernel=KERNEL)
            self.assertEqual(result['transient']['states'],[[expected]])

    def test_real_distinct_instances_resolve_bound_inputs(self):
        wrapper='''`include "disciplines.vams"
module pair(a,b,oa,ob,na,nb); inout a,b,oa,ob,na,nb;
        electrical a,b,oa,ob,na,nb;
        paper_hc_start A(a,oa,na); paper_hc_start B(b,ob,nb); endmodule'''
        program=compile_sources({'initialization.va':SOURCE+wrapper},
            [Instance('dut','pair',{n:n for n in ('a','b','oa','ob','na','nb')})])
        result=transient(program,{'a':[[0,.9],[1,.9]],'b':[[0,.1],[1,.1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(result['transient']['state_names'],['dut/A:q','dut/A:n','dut/B:q','dut/B:n'])
        self.assertEqual(result['transient']['states'],[[1,0,0,0],[1,0,0,0]])

    def test_t0_timer_reads_resolved_initial_before_first_output(self):
        source=model('@(initial_step) q=(V(u,r)>0.65); @(timer(0)) q=q+2; V(y,r)<+q;', 'real q;')
        p=compile_sources({'timer-initial.va':source},[instance()])
        for value, expected in [(.9,3),(.1,2)]:
            result=transient(p,{'u':[[0,value],[1,value]]},[0,1],stop=1,max_step=1,kernel=KERNEL)
            self.assertEqual(result['transient']['states'],[[expected],[expected]])
            self.assertEqual([(e['time'],e['kind']) for e in result['transient']['events']],[(0,'timer')])

    def test_resolved_initial_is_used_by_operator_history_and_held_timer_guard(self):
        for op, expected in [('transition(q,0,0.1,0.1)', [1,1]), ('idt(q,0)', [0,1])]:
            source=model(f'@(initial_step) q=(V(u,r)>0.65); V(y,r)<+{op};', 'real q;')
            p=compile_sources({'history-initial.va':source},[instance()])
            result=transient(p,{'u':[[0,.9],[1,.9]]},[0,1],stop=1,max_step=.1,kernel=KERNEL)
            self.assertEqual(result['transient']['states'], [[1],[1]])
            for row, value in zip(result['solutions'], expected):
                self.assertAlmostEqual(row['voltages'][result['nodes'].index('y')],value,delta=1e-12)
        source=model('@(initial_step) q=(V(u,r)>0.65); @(timer(q,0)) q=q+2; V(y,r)<+q;', 'real q;')
        p=compile_sources({'guard-initial.va':source},[instance()])
        result=transient(p,{'u':[[0,.9],[1,.9]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(result['transient']['states'],[[1],[1],[3]])
        self.assertEqual([e['time'] for e in result['transient']['events']],[1])

    def test_kernel_rejects_malformed_and_structurally_hidden_initial_payloads(self):
        import copy
        p=compile_sources({'initial.va':model('@(initial_step) q=(V(u,r)>0.65); V(y,r)<+q;', 'real q;')},[instance()])
        payload=p.to_dict()
        mutations = [
            ('unknown', lambda initial: initial.update(extra=0)),
            ('wrong owner', lambda initial: initial['origin'].update(instance='other')),
            ('wrong source', lambda initial: initial['origin'].update(source='')),
            ('wrong arms', lambda initial: initial['then_value'].update(constant=2)),
            ('state', lambda initial: initial.update(left=dict(op='state',state=0))),
            ('operator', lambda initial: initial.update(left=dict(op='operator',operator=0))),
            ('cancelled undriven', lambda initial: initial.update(left=dict(op='affine',constant=1,terms=[dict(node=2,coefficient=0)]))),
            ('out of range', lambda initial: initial.update(left=dict(op='affine',constant=1,terms=[dict(node=999,coefficient=1)]))),
            ('not predicate', lambda initial: initial.update(op='affine',constant=0,terms=[])),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name):
                program=copy.deepcopy(payload); mutate(program['states'][0]['initial'])
                request=dict(program=program,driven=['u'],samples=[], transient=dict(pwl=[[[0,.9],[1,.9]]],output_times=[0],stop=1,max_step=1))
                proc=subprocess.run([str(KERNEL)],input=json.dumps(request),text=True,capture_output=True)
                self.assertNotEqual(proc.returncode,0)
                self.assertEqual(proc.stdout,'')
                self.assertIn(json.loads(proc.stderr)['kind'],['invalid_request','invalid_ir','unsupported_initialization'])

    def test_frontend_rejects_broader_initialization_structurally(self):
        for rhs in ['V(u,r)', '(V(y,r)>0.65)', '(0*V(y,r)>0.65)',
                    '(V(y,y)>0.65)', '(q>0.65)', '(idt(V(u,r),0)>0.65)',
                    '(V(u,r)>0.65)?1:(V(y,r)>0.65)', '(V(u,r)*V(u,r)>0.65)']:
            with self.subTest(rhs=rhs), self.assertRaises(CompileError):
                compile_sources({'bad.va':model(f'@(initial_step) q={rhs}; V(y,r)<+q;', 'real q;')},[instance()])
        with self.assertRaises(CompileError):
            compile_sources({'integer.va':model('@(initial_step) q=(V(u,r)>0.65); V(y,r)<+q;', 'integer q;')},[instance()])

    def test_undriven_inout_rejected_by_kernel(self):
        p=original_program(SOURCE.replace('V(in)>0.65','V(out)>0.65'))
        with self.assertRaises(KernelError) as caught:
            transient(p,{'in':[[0,.9],[1,.9]]},[0],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(caught.exception.detail['kind'],'unsupported_initialization')

    def test_cross_instance_output_input_is_not_an_external_driven_source(self):
        wrapper="""`include "disciplines.vams"
module cascade(a,oa,ob,na,nb); inout a,oa,ob,na,nb;
        electrical a,oa,ob,na,nb; paper_hc_start A(a,oa,na); paper_hc_start B(oa,ob,nb); endmodule"""
        p=compile_sources({'cascade.va':SOURCE+wrapper},
            [Instance('dut','cascade',{n:n for n in ('a','oa','ob','na','nb')})])
        with self.assertRaises(KernelError) as caught:
            transient(p,{'a':[[0,.9],[1,.9]]},[0],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(caught.exception.detail['kind'],'unsupported_initialization')
        self.assertIn('dut/B:q',caught.exception.detail['message'])

    def test_constant_and_version_compatibility(self):
        p=compile_sources({'constant.va':model('@(initial_step) q=3; V(y,r)<+q;', 'real q;')},[instance()])
        result=transient(p,{'u':[[0,0],[1,0]]},[0],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(result['transient']['states'],[[3]])
        for version in range(1,SCHEMA_VERSION):
            proc=subprocess.run([str(KERNEL)],input=json.dumps({'program':{'schema_version':version}}),text=True,capture_output=True)
            self.assertEqual(json.loads(proc.stderr)['kind'],'unsupported_ir_version')
