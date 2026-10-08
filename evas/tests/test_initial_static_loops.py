"""Static initialization/event loops through public compilation and Rust transient."""
GUARDS = ['LANG', 'CROSS', 'EVENT-ORDER', 'EVENT-CONDITIONS', 'case:initial_static_loop']
import unittest
from evas import CompileError, Instance, compile_sources, transient
from test_affine import KERNEL, model


def compiled(body, declarations='real q[0:1]; genvar i;', instances=None):
    return compile_sources({'initial-static-loop.va': model(body,declarations)},instances or [
        Instance('dut','m',{'u':'u','y':'y','r':'0'})])


def run(program,times=(0,.125,.375,.625,1)):
    return transient(program,{'u':[[0,0],[1,1]]},list(times),stop=1,max_step=.25,kernel=KERNEL)


def values(result,node='y'):
    index=result['nodes'].index(node)
    return [row['voltages'][index] for row in result['solutions']]


class InitialStaticLoops(unittest.TestCase):
    def test_mixed_body_initializes_each_element_and_restores_it_on_cross(self):
        program=compiled('''@(initial_step or cross(V(u,r)-0.5,1,1e-12,1e-9))
          for(i=0;i<2;i=i+1) q[i]=i;
          @(timer(0.25)) begin q[0]=40; q[1]=57; end
          V(y,r)<+q[0]+q[1];''')
        result=run(program)
        self.assertEqual(values(result),[1,1,97,1,1])
        self.assertEqual(result['transient']['states'][0],[0,1])
        self.assertEqual(len(result['transient']['events']),2)
        self.assertEqual([e['kind'] for e in result['transient']['events']],['timer','cross'])
        self.assertEqual(result['transient']['events'][-1]['before'],[40,57])
        self.assertEqual(result['transient']['events'][-1]['after'],[0,1])

    def test_empty_initial_loop_does_not_erase_invalid_values_or_controls(self):
        for loop in (
            'for(i=0;i<0;i=i+1) q[i]=V(u,r);',
            'for(i=0;i<0;i=i+1) q[i]=q[0];',
            'for(i=0;i<0;i=i+1) q[i]=idt(1,0);',
            'for(i=0;i<0;i=V(u,r)) q[i]=1;',
            'for(i=0;i<0;i=i+0.5) q[i]=1;',
            'for(i=0;i<0;i=i+1) q[V(u,r)]=1;',
            'for(i=0;i<0;i=i+1) q[2]=1;',
            'for(i=0;i<0;i=i+1) q=1;',
        ):
            with self.subTest(loop=loop),self.assertRaises(CompileError):
                compiled('@(initial_step or cross(V(u,r)-0.5,1)) '+loop+' V(y,r)<+1;')


    def test_explicit_element_rewrite_has_the_same_public_platforms_and_state_changes(self):
        trigger='@(initial_step or cross(V(u,r)-0.5,1,1e-12,1e-9)) '
        results=[run(compiled(trigger+body+"""
          @(timer(0.25)) begin q[0]=40; q[1]=57; end
          V(y,r)<+q[0]+q[1];""")) for body in
          ('for(i=0;i<2;i=i+1) q[i]=i;', 'begin q[0]=0; q[1]=1; end')]
        for result in results:
            self.assertEqual(values(result),[1,1,97,1,1])
        self.assertEqual(results[0]['solutions'],results[1]['solutions'])
        self.assertEqual(results[0]['transient']['states'],results[1]['transient']['states'])
        for a,b in zip(results[0]['transient']['events'],results[1]['transient']['events']):
            self.assertEqual({k:a[k] for k in ('time','kind','before','after')},
                             {k:b[k] for k in ('time','kind','before','after')})

    def test_pure_initial_nested_descending_and_empty_loops_use_existing_order(self):
        for loop,declared,expected in (
            ('for(i=1;i>=0;i=i-1) q[i]=i;', 'real q[1:0]; genvar i;', 1),
            ('for(i=0;i<2;i=i+1) for(j=0;j<2;j=j+1) q[2*i+j]=10*i+j;',
             'real q[0:3]; genvar i,j;', 22),
        ):
            nodes='q[0]+q[1]' if expected==1 else 'q[0]+q[1]+q[2]+q[3]'
            with self.subTest(loop=loop):
                result=run(compiled('@(initial_step) '+loop+' V(y,r)<+'+nodes+';',declared))
                self.assertEqual(values(result),[expected]*5)
                self.assertEqual(result['transient']['events'],[])
        self.assertEqual(values(run(compiled('@(initial_step) for(i=0;i<0;i=i+1) q[i]=1; V(y,r)<+1;'))),[1]*5)

    def test_parameterized_instances_reversed_order_repeat_and_grid_remain_independent(self):
        body="""@(initial_step or cross(V(u,r)-0.5,1,1e-12,1e-9))
          for(i=0;i<N;i=i+1) q[i]=SEED+i;
          @(timer(0.25)) for(i=0;i<N;i=i+1) q[i]=40+i;
          for(i=0;i<N;i=i+1) V(y,r)<+q[i];"""
        a=Instance('a','m',{'u':'u','y':'a','r':'0'},{'N':2,'SEED':1})
        b=Instance('b','m',{'u':'u','y':'b','r':'0'},{'N':3,'SEED':10})
        for order in ([a,b],[b,a]):
            program=compiled(body,'parameter integer N=2; parameter real SEED=1; real q[0:N-1]; genvar i;',order)
            for _ in range(2):
                sparse=run(program)
                dense=run(program,[0,.0625,.125,.1875,.375,.4375,.625,.75,1])
                self.assertEqual(values(sparse,'a'),[3,3,81,3,3])
                self.assertEqual(values(sparse,'b'),[33,33,123,33,33])
                self.assertEqual(len(sparse['transient']['events']),4)
                self.assertEqual(sparse['transient']['events'],dense['transient']['events'])
                for time,row in zip(sparse['transient']['times'],sparse['solutions']):
                    self.assertEqual(row,dense['solutions'][dense['transient']['times'].index(time)])

    def test_pure_initial_loop_and_duplicate_event_leaves_execute_one_ordered_body(self):
        program=compiled("""@(initial_step) for(i=0;i<2;i=i+1) q[i]=i;
          @(cross(V(u,r)-0.5,1) or cross(V(u,r)-0.5,1))
            for(i=0;i<2;i=i+1) q[i]=10*q[i]+i+1;
          V(y,r)<+q[0]+q[1];""")
        result=run(program)
        # One ordered update yields [1,12], sum 13; executing twice yields 133.
        self.assertEqual(values(result),[1,1,1,13,13])
        self.assertEqual(result['transient']['states'][-1],[1,12])
        self.assertEqual(len(result['transient']['events']),1)
        self.assertEqual(len(result['transient']['events'][0]['fired_triggers']),2)

    def test_original_minimal_and_duplicate_cross_leaves_do_not_duplicate_initialization(self):
        for trigger in ('initial_step or cross(V(u,r)-0.5,1)',
                        'cross(V(u,r)-0.5,1) or initial_step or cross(V(u,r)-0.5,1)'):
            program=compiled('@('+trigger+') for(i=0;i<2;i=i+1) q[i]=i; V(y,r)<+q[0]+q[1];')
            result=run(program)
            self.assertEqual(values(result),[1]*5)
            self.assertEqual(len(program.states),2)
            self.assertEqual(len(result['transient']['events']),1)
            self.assertEqual(result['transient']['events'][0]['before'],[0,1])
            self.assertEqual(result['transient']['events'][0]['after'],[0,1])

    def test_repeated_or_missing_element_initialization_remains_rejected(self):
        for body in (
            '@(initial_step) for(i=0;i<2;i=i+1) begin q[i]=i; q[0]=4; end',
            '@(initial_step) for(i=0;i<2;i=i+1) q[0]=i;',
            '@(initial_step) for(i=0;i<1;i=i+1) q[i]=i; @(timer(0.25)) q[1]=5;',
        ):
            with self.subTest(body=body),self.assertRaises(CompileError):
                compiled(body+' V(y,r)<+q[0]+q[1];')

    def test_initial_loop_admission_does_not_enable_conditions_or_dynamic_indices(self):
        for body in ('if(V(u,r)>0) q[i]=i;', 'q[V(u,r)]=i;', 'q[i]=V(u,r);',
                     'q[i]=q[0];', '@(timer(1)) q[i]=i;'):
            for count in (0,2):
                with self.subTest(body=body,count=count),self.assertRaises(CompileError):
                    compiled('@(initial_step or cross(V(u,r)-0.5,1)) for(i=0;i<'+str(count)+';i=i+1) '+body+' V(y,r)<+1;')

    def test_initial_and_analog_expansion_share_statement_budget(self):
        body='@(initial_step) for(i=0;i<2048;i=i+1) q[i]=i; for(i=0;i<2048;i=i+1) V(y,r)<+q[0];'
        compiled(body,'real q[0:2047]; genvar i;')
        with self.assertRaisesRegex(CompileError,'statement budget'):
            compiled(body+' V(y,r)<+0;','real q[0:2047]; genvar i;')


if __name__=='__main__': unittest.main()
