"""A shared initial/timer body initializes histories once, then runs in time."""
GUARDS = ['TIMER', 'EVENT-ORDER', 'TIMED-OPERATOR', 'LANG']
import copy,json,subprocess,unittest
from fractions import Fraction as F
from evas import CompileError,KernelError,compile_sources,transient,Instance
from test_affine import KERNEL,instance,model


def run(body,decl='integer n,m;',times=None,stop=0.625,forced=False,instances=None):
    times=[0.,0.125,0.25,0.375,0.5,0.625] if times is None else times
    p=compile_sources({'initial-timer.va':model(body,decl)},instances or [instance()])
    return transient(p,{'u':[[0,1],[stop,1]]},times,stop=stop,max_step=0.125,
                     strobetimes=times if forced else [],kernel=KERNEL)


class InitialTimer(unittest.TestCase):
    def test_nonidempotent_body_initializes_once_in_both_leaf_orders(self):
        for trigger in ['initial_step or timer(0,0.25,0)', 'timer(0,0.25,0) or initial_step']:
            for forced in [False,True]:
                r=run(f'@({trigger}) begin n=n+1;m=n;end V(y,r)<+1.0*n+10.0*m;',forced=forced)
                self.assertEqual(r['transient']['states'],[[v,v] for v in [1,1,2,2,3,3]])
                self.assertEqual([e['time'] for e in r['transient']['events']],[0.25,0.5])

    def test_positive_start_single_shot_disabled_and_signed_zero(self):
        for args,expected in [('0.25,0.25,0',[1,1,2,2,3,3]),('0,0,0',[1]*6),('-0.0,-1,0',[1]*6),('0,0.25,0,0',[1]*6)]:
            r=run(f'@(initial_step or timer({args})) n=n+1;V(y,r)<+n;')
            self.assertEqual([s[0] for s in r['transient']['states']],expected)

    def test_separate_blocks_still_each_execute_at_zero(self):
        r=run('@(initial_step)n=n+1;@(timer(0,0.25,0))n=n+1;V(y,r)<+n;')
        self.assertEqual([s[0] for s in r['transient']['states']],[2,2,3,3,4,4])
        self.assertEqual(r['transient']['events'][0]['before'],[1])

    def test_initial_history_is_not_a_fictional_zero_time_transition(self):
        times=[0.,0.0625,0.125,0.25,0.3125,0.375,0.5,0.5625,0.625]
        for op in ['transition(n,0,0.125)','idt(n,0)',"laplace_nd(n,'{1.0},'{1.0,0.125})"]:
            shared='@(initial_step or timer(0,0.25,0))n=n+1;V(y,r)<+'+op+';'
            expanded='@(initial_step)n=n+1;@(timer(0.25,0.25,0))n=n+1;V(y,r)<+'+op+';'
            for forced in [False,True]:
                a=run(shared,times=times,forced=forced);b=run(expanded,times=times,forced=forced)
                self.assertEqual(a['solutions'],b['solutions'])
                y=a['nodes'].index('y')
                if op.startswith('transition'):
                    expected=[1.,1.,1.,1.,1.5,2.,2.,2.5,3.]
                elif op.startswith('idt'):
                    expected=[float(F(t)+max(F(t)-F(1,4),0)+max(F(t)-F(1,2),0)) for t in times]
                else:continue
                for row,v in zip(a['solutions'],expected):self.assertAlmostEqual(row['voltages'][y],v,places=13)

    def test_binding_then_shift_preserves_fraction_clock_and_instance_state(self):
        body='@(initial_step or timer(S,P,T))n=n+1;V(y,r)<+n;'
        decl='integer n;parameter real S=0;parameter real P=0.125;parameter real T=0;'
        for order in [[0,1],[1,0]]:
            instances=[instance('a'+str(i),connections={'u':'u','y':'y'+str(i),'r':'0'},parameters={'P':[0.125,0.25][i]}) for i in order]
            for _ in range(2):
                r=run(body,decl,times=[0,0.5],stop=0.5,instances=instances)
                for name,expect in [('y0',5),('y1',3)]:self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index(name)],expect)
        # Shifting by assigning the same p preserves binary-rational timing.
        r=run(body,decl,times=[0.,0.2],stop=0.2,instances=[instance(parameters={'P':0.1})])
        self.assertEqual([e['time'] for e in r['transient']['events']],[0.1,0.2])
        with self.assertRaisesRegex(KernelError,'event_resolution'):
            run(body,decl,times=[0.,0.31],stop=0.31,instances=[instance(parameters={'P':0.1})])

    def test_initial_input_choice_and_static_array_source_order_are_preserved(self):
        r=run('@(initial_step or timer(0,0.25,0))begin n=(V(u)>0?2:1);m=n+1;end V(y,r)<+1.0*n+m;')
        self.assertEqual(r['transient']['states'],[[2,3]]*6)
        r=run('@(initial_step or timer(0,0.25,0))begin a[0]=a[0]+1;a[1]=a[0];end V(y,r)<+1.0*a[0]+a[1];','integer a[0:1];')
        self.assertEqual(r['transient']['states'],[[v,v] for v in [1,1,2,2,3,3]])

    def test_mixed_scope_remains_explicit(self):
        for trigger in ['initial_step or timer(n,0.25,0.001)','initial_step or timer(0,n,0.001)',
                        'initial_step or timer(0,0.25,0.001,n)','initial_step("tran") or timer(0,0.25)',
                        'initial_step or initial_step or timer(0,0.25)',
                        'initial_step or timer(0,0.25) or timer(0,0.5)',
                        'initial_step or cross(V(u)-1,1) or timer(0,0.25)',
                        'initial_step or timer(-1,0.25,0,0)','initial_step or timer(0,0.25,-1,0)']:
            with self.subTest(trigger=trigger),self.assertRaises(CompileError):
                run(f'@({trigger}) n=n+1;V(y,r)<+n;')
        for body in ['n=n+1;$display("n=%d",n);','n=n+1;$strobe("n=%d",n);','@(timer(0.5))n=n+1;']:
            with self.assertRaises(CompileError):run('@(initial_step or timer(0,0.25))begin '+body+'end V(y,r)<+n;')

    def test_raw_or_cannot_bypass_lifecycle_contract(self):
        p=compile_sources({'raw.va':model('@(timer(0,0.25,1e-9))begin n=n+1;$display("n=%d",n);end','integer n;')},[instance(connections={'u':'u','y':'u','r':'0'})]).to_dict()
        for kind in ['initial_step','final_step']:
            request=dict(program=copy.deepcopy(p),driven=['u'],samples=[],transient=dict(pwl=[[[0,1],[0.5,1]]],output_times=[0,0.5],stop=0.5,max_step=0.5))
            e=request['program']['events'][0];e['trigger']={'kind':'or','triggers':[{'kind':kind},e['trigger']]}
            r=subprocess.run([str(KERNEL)],input=json.dumps(request),text=True,capture_output=True)
            self.assertEqual(r.returncode,2);self.assertEqual(r.stdout,'');self.assertEqual(json.loads(r.stderr)['kind'],'invalid_ir')

if __name__=='__main__':unittest.main()
