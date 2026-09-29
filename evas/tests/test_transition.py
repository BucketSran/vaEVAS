"""Independent transition development anchors, not 31-condition qualification.

Expected voltages come from frozen TR-* equations, not another simulator or
an EVAS-generated golden waveform. Binary64 rounding allowance is 2e-12 V.
"""
import copy
import json
import subprocess
import unittest

from evas import CompileError, KernelError, compile_sources, solve, transient
from test_affine import KERNEL, instance, model


def compile_transition(body, declarations='real a,b;'):
    return compile_sources({'transition.va': model(body, declarations)}, [instance()])


def run_transition(body, times, stop, step=None, declarations='real a,b;'):
    return transient(compile_transition(body, declarations),
                     {'u': [[0, 0], [stop, 0]]}, times,
                     stop=stop, max_step=stop if step is None else step, kernel=KERNEL)


class TransitionContracts(unittest.TestCase):
    def assert_waveform(self, result, expected):
        index = result['nodes'].index('y')
        for row, value in zip(result['solutions'], expected, strict=True):
            self.assertAlmostEqual(row['voltages'][index], value, delta=2e-12)
            self.assertLessEqual(row['max_residual_ratio'], 1)

    def test_edge_nonzero_initial_delay_and_asymmetric_times(self):
        body = '''@(initial_step) begin a=0; b=0; end
          @(timer(1n,0,1p)) a=.6;
          @(timer(12n,0,1p)) b=-.8;
          V(y,r)<+transition(.2+a+b,2n,4n,8n);'''
        times = [0, 1e-9, 3e-9, 5e-9, 7e-9, 14e-9, 18e-9, 22e-9, 24e-9]
        for step in [24e-9, .37e-9]:
            self.assert_waveform(run_transition(body, times, 24e-9, step),
                                 [.2, .2, .2, .5, .8, .8, .4, 0, 0])

    def test_interrupted_reverse_extend_reflection_and_equality(self):
        for sign in [1, -1]:
            for second, at10, final in [(0, .2, 0), (2, 1.2, 2), (.4, .4, .4)]:
                rise, fall = (10, 20) if sign == 1 else (20, 10)
                body = f'''@(initial_step) begin a=0; b=0; end
                  @(timer(2n,0,1p)) a={sign};
                  @(timer(6n,0,1p)) b={sign*(second-1)};
                  V(y,r)<+transition(a+b,0,{rise}n,{fall}n);'''
                with self.subTest(sign=sign, target=second):
                    self.assert_waveform(run_transition(body, [0,6e-9,10e-9,14e-9,20e-9], 20e-9),
                                         [0, sign*.4, sign*at10, sign*final, sign*final])

    def test_same_target_does_not_restart(self):
        body = '''@(initial_step) a=0;
          @(timer(2n,4n,1p)) a=1;
          V(y,r)<+transition(a,0,10n,20n);'''
        result = run_transition(body, [0,6e-9,10e-9,12e-9,14e-9], 14e-9, declarations='real a;')
        self.assert_waveform(result, [0,.4,.8,1,1])
        self.assertEqual(len(result['transient']['events']), 4)

    def test_delayed_queue_retains_short_pulse_without_observation(self):
        body = '''@(initial_step) begin a=0; b=0; end
          @(timer(2n,0,1p)) a=1;
          @(timer(3n,0,1p)) b=-1;
          V(y,r)<+transition(a+b,10n,2n,2n);'''
        points = [0,12e-9,12.5e-9,13e-9,13.5e-9,14e-9,16e-9]
        coarse = run_transition(body, points, 16e-9)
        fine = run_transition(body, points, 16e-9, .13e-9)
        self.assert_waveform(coarse, [0,0,.25,.5,.25,0,0])
        self.assertEqual(coarse['solutions'], fine['solutions'])
        sparse = run_transition(body, [0,13.5e-9,16e-9], 16e-9)
        self.assertEqual(sparse['solutions'][1], coarse['solutions'][4])

    def test_timer_zero_and_target_at_previous_edge_endpoint(self):
        body = '''@(initial_step) begin a=.2; b=0; end
          @(timer(0,0,1p)) a=.8;
          @(timer(4n,0,1p)) b=-.8;
          V(y,r)<+transition(a+b,0,4n,8n);'''
        result = run_transition(body, [0,2e-9,4e-9,8e-9,12e-9], 12e-9)
        self.assert_waveform(result,[.2,.5,.8,.4,0])
        self.assertEqual(result['transient']['states'][0], [.8,0])

    def test_same_instant_state_changes_have_one_common_input(self):
        body = '''@(initial_step) begin a=0; b=0; end
          @(timer(2n,0,1p)) a=1;
          @(timer(2n,0,1p)) b=-.5;
          V(y,r)<+transition(a+b,0,2n,2n);'''
        self.assert_waveform(run_transition(body,[0,2e-9,3e-9,4e-9],4e-9),[0,0,.25,.5])

    def test_distinct_call_sites_and_instances_keep_private_histories(self):
        body = '''@(initial_step) a=0;
          @(timer(2n,0,1p)) a=1;
          V(y,r)<+transition(a,0,2n,2n)+transition(a,2n,2n,2n);'''
        self.assert_waveform(run_transition(body,[0,3e-9,5e-9,6e-9],6e-9,declarations='real a;'),[0,.5,1.5,2])
        source = model('''@(initial_step) a=0; @(timer(2n,0,1p)) a=1;
          V(y,r)<+transition(a,d,2n,2n);''', 'parameter real d=0; real a;')
        from evas import Instance
        instances = [Instance('fast','m',{'u':'u','y':'y','r':'0'},{'d':0}),
                     Instance('slow','m',{'u':'u','y':'z','r':'0'},{'d':2e-9})]
        for inst in [instances, list(reversed(instances))]:
            program=compile_sources({'transition.va':source},inst)
            result=transient(program,{'u':[[0,0],[6e-9,0]]},[3e-9,5e-9],stop=6e-9,max_step=6e-9,kernel=KERNEL)
            y,z=(result['nodes'].index(n) for n in ['y','z'])
            self.assertAlmostEqual(result['solutions'][0]['voltages'][y],.5,delta=2e-12)
            self.assertEqual(result['solutions'][0]['voltages'][z],0)
            self.assertAlmostEqual(result['solutions'][1]['voltages'][z],.5,delta=2e-12)


class TransitionRejections(unittest.TestCase):
    def test_unsupported_inputs_settings_and_contexts(self):
        for expression in ['transition(V(u,r),0,1n,1n)', 'transition(a,0,0,1n)',
                           'transition(a,-1n,1n,1n)', 'transition(a,0,1n)',
                           'transition(transition(a,0,1n,1n),0,1n,1n)',
                           'transition(a,a,1n,1n)']:
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                compile_transition(f'@(initial_step) a=0; V(y,r)<+{expression};','real a;')
        for expression in ['transition(a,0,1n,1n)*V(u,r)',
                           'transition(a,0,1n,1n)*(V(u,r)-V(u,r))',
                           'transition(a,0,1n,1n)*a', 'transition(a*a,0,1n,1n)']:
            with self.subTest(expression=expression), self.assertRaises(KernelError):
                run_transition(f'@(initial_step) a=0; V(y,r)<+{expression};',[0,1e-9],1e-9,declarations='real a;')

    def test_cross_through_operator_output_rejected(self):
        body='''@(initial_step) begin a=0; b=0; end
          @(timer(0,0,1p)) a=1;
          @(cross(V(y,r)-.5,1,1p,1u)) b=b+1;
          V(y,r)<+transition(a,0,2n,2n);'''
        with self.assertRaisesRegex(KernelError,'unsupported_cross'):
            run_transition(body,[0,3e-9],3e-9)

    def test_static_and_raw_ir_validation(self):
        program=compile_transition('@(initial_step) a=0; V(y,r)<+transition(a,0,1n,1n);','real a;')
        with self.assertRaisesRegex(KernelError,'unsupported_analysis'):
            solve(program,['u'],[[0]],kernel=KERNEL)
        valid=program.to_dict()
        mutations=[]
        bad=copy.deepcopy(valid); bad['operators'][0]['rise']=0; mutations.append(bad)
        bad=copy.deepcopy(valid); bad['operators'][0]['origin']['instance']='other'; mutations.append(bad)
        bad=copy.deepcopy(valid); bad['operators'].append(copy.deepcopy(bad['operators'][0])); mutations.append(bad)
        bad=copy.deepcopy(valid); bad['operators'][0]['input']={'op':'operator','operator':0}; mutations.append(bad)
        bad=copy.deepcopy(valid); bad['operators'][0]['input']={'op':'state','state':99}; mutations.append(bad)
        bad=copy.deepcopy(valid); bad['operators'][0]['extra']=1; mutations.append(bad)
        bad=copy.deepcopy(valid); bad['contributions'][0]['rhs']={'op':'operator','operator':99}; mutations.append(bad)
        for bad in mutations:
            payload=dict(program=bad,driven=['u'],samples=[],transient=dict(pwl=[[[0,0],[1e-9,0]]],output_times=[0,1e-9],stop=1e-9,max_step=1e-9))
            result=subprocess.run([str(KERNEL)],input=json.dumps(payload),text=True,capture_output=True)
            self.assertEqual(result.returncode,2,result.stdout)
            self.assertIn(json.loads(result.stderr)['kind'],['invalid_ir','invalid_request','unsupported_operator'])
