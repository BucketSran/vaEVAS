"""Analog $strobe shares accepted-iteration measurement semantics with $display."""
GUARDS = ['LANG', 'EVENT-ORDER', 'EVENT-CONDITIONS']
import unittest
from evas import CompileError, compile_sources, transient
from test_affine import KERNEL, instance, model


class StrobeTask(unittest.TestCase):
    def test_alias_preserves_source_order_sequential_state_and_settled_voltage(self):
        body='''@(initial_step) n=2;
          @(timer(0.25,0.5)) begin
            $display("before %.17g %d %.17g",$abstime,n,V(y,r));
            n=n+1;
            $strobe("after %.17g %d %.17g",$abstime,n,V(y,r));
          end
          @(final_step) $strobe("final %.17g %d %.17g",$abstime,n,V(y,r));
          V(y,r)<+n;'''
        outputs=[]
        for source in [body,body.replace('$strobe','$display'),body.replace('$display','$strobe')]:
            program=compile_sources({'records.va':model(source,'integer n;')},[instance()])
            r=transient(program,{'u':[[0,1],[1.25,1]]},[0,.25,.75,1.25],stop=1.25,max_step=.5,kernel=KERNEL)
            records=r['transient']['display_records']
            outputs.append([(v['time'],v['text']) for v in records])
            self.assertEqual([v['text'] for v in records],[
                'before 0.25 2 3','after 0.25 3 3','before 0.75 3 4',
                'after 0.75 4 4','before 1.25 4 5','after 1.25 5 5','final 1.25 5 5'])
        self.assertEqual(outputs[0],outputs[1]);self.assertEqual(outputs[1],outputs[2])

    def test_passive_initial_zero_timer_and_final_retain_statement_order(self):
        text=model('''@(initial_step) begin $strobe("initial %d",n);n=2;$strobe("updated %d",n);end
          @(timer(0)) $strobe("zero %d",n);
          @(final_step) $strobe("final %d",n);''','integer n;')
        p=compile_sources({'passive.va':text},[instance(connections=dict(u='u',y='u',r='0'))])
        r=transient(p,{'u':[[0,1],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([v['text'] for v in r['transient']['display_records']],['initial 0','updated 2','zero 2','final 2'])

    def test_discarded_trial_does_not_publish_strobe_twice(self):
        text=model('@(timer(0.5)) begin n=n+1;$strobe("n=%d",n);end V(y,r)<+n;','integer n;')
        p=compile_sources({'records.va':text},[instance()])
        r=transient(p,{'u':[[0,1],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertGreater(r['transient']['discarded_trials'],0)
        self.assertEqual([v['text'] for v in r['transient']['display_records']],['n=1'])

    def test_alias_keeps_format_and_contributing_initial_restrictions(self):
        for statement in ['$strobe("bad=%s",n);','$strobe("bad=%d");','$strobe(n);','$strobe;']:
            with self.subTest(statement=statement),self.assertRaises(CompileError):
                compile_sources({'bad.va':model('@(timer(0.5)) '+statement+' V(y,r)<+n;','integer n;')},[instance()])
        with self.assertRaises(CompileError):
            compile_sources({'initial.va':model('@(initial_step) $strobe("n=%d",n); V(y,r)<+n;','integer n;')},[instance()])

if __name__=='__main__':unittest.main()
