"""Execute shipped timer guards against public near-timeout event histories.

This finite guard trace is a source regression, not a VA simulator or full POR
calibration. Literal expected times follow the public 100us hold contract.
"""
from pathlib import Path
import re,unittest

ROOT=Path(__file__).resolve().parent

def first_transition(source,state,event):
    guard=next(re.search(r'if\((.*)\) begin',line)[1]
               for line in source.splitlines() if 'if(state=='+str(state)+' ' in line)
    expression=guard.replace('$abstime','time').replace('1f','1e-15').replace('&&',' and ').replace('||',' or ')
    expression=re.sub(r'!(?!=)', ' not ',expression)
    context=dict(state=state,ramp=.002,hold=.0001,timeout=.001,phase_time=event.get('phase_time',0),saw_fall=event.get('saw_fall',[0,0]),pf=event.get('pf',[0.,0.]),lost=event.get('lost',0),lost_time=event.get('lost_time',0.))
    for step in range(6001):
        context['time']=step*1e-6
        if eval(expression,{'__builtins__':{}},context):return context['time']
    raise AssertionError('no transition')

class TimeoutContract(unittest.TestCase):
    def sources(self):
        return [(ROOT/'por_bench.va').read_text(),(ROOT/'candidates/v2-test-por-sequence/alternate/dut.va').read_text()]
    def test_first_events_cannot_be_completed_by_brownout(self):
        for source in self.sources():
            blocks=re.findall(r'@\(cross\(V\((osc|por)\).*?\n (.*?)\n end',source,re.S)
            self.assertEqual(len(blocks),3)
            for port,block in blocks:
                guard=re.search(r'if\((.*?)\) begin',block)[1]
                expression=guard.replace('V(power)','power').replace('&&',' and ').replace('||',' or ')
                expression=re.sub(r'!(?!=)', ' not ',expression)
                context=dict(state=1,cycle=0,power=1.8,saw_rise=[1,0],saw_fall=[0,0])
                self.assertFalse(eval(expression,{'__builtins__':{}},context),port)

    def test_same_edge_events_are_excluded_in_either_callback_order(self):
        for source in self.sources():
            # Execute the shipped boundary cleanup guards/actions on histories
            # with a callback immediately before the timer; the other order is
            # rejected by the state guard tested above. Expectations are the
            # literal half-open public window, not computed by the checker.
            rules=re.findall(r'if\((.*?)\) (saw_rise\[0\]|saw_fall\[0\]|n\[0\])=(.*?);',source)
            for delta,expected in [(-1e-12,(1,1,9)),(0.,(0,0,8)),(1e-12,(0,0,8))]:
                context=dict(saw_rise=[1,0],saw_fall=[1,0],n=[9,0],
                             pr=[.003+delta,0.],pf=[.003+delta,0.],
                             last_clock=[.003+delta,0.],phase_time=.003)
                self.assertEqual(len(rules),3)
                for guard,target,value in rules:
                    if eval(guard.replace('&&',' and '),{'__builtins__':{}},context):
                        name=target.split('[')[0]
                        context[name][0]=eval(value,{'__builtins__':{}},context)
                self.assertEqual((context['saw_rise'][0],context['saw_fall'][0],context['n'][0]),expected)

    def test_seen_first_fall_keeps_full_hold_near_timeout(self):
        for source in self.sources():
            self.assertAlmostEqual(first_transition(source,0,dict(saw_fall=[1,0],pf=[.00295,0.])),.00305,places=12)

    def test_seen_power_loss_keeps_full_hold_near_timeout(self):
        for source in self.sources():
            self.assertAlmostEqual(first_transition(source,2,dict(phase_time=.0031,lost=1,lost_time=.00405)),.00415,places=12)

    def test_seen_recovery_fall_keeps_full_hold_near_timeout(self):
        for source in self.sources():
            self.assertAlmostEqual(first_transition(source,4,dict(phase_time=.00425,saw_fall=[0,1],pf=[0.,.0052])),.0053,places=12)

    def test_deadline_and_later_events_do_not_extend_timeout(self):
        for source in self.sources():
            for delta in [0.,50e-6]:
                self.assertAlmostEqual(first_transition(source,0,dict(saw_fall=[1,0],pf=[.003+delta,0.])),.003,places=12)
                self.assertAlmostEqual(first_transition(source,2,dict(phase_time=.0031,lost=1,lost_time=.0041+delta)),.0041,places=12)
                self.assertAlmostEqual(first_transition(source,4,dict(phase_time=.00425,saw_fall=[0,1],pf=[0.,.00525+delta])),.00525,places=12)
    def test_missing_events_use_timeout(self):
        for source in self.sources():
            self.assertAlmostEqual(first_transition(source,0,{}),.003,places=12)
            self.assertAlmostEqual(first_transition(source,2,dict(phase_time=.0031)),.0041,places=12)
            self.assertAlmostEqual(first_transition(source,4,dict(phase_time=.00425)),.00525,places=12)

if __name__=='__main__':unittest.main()
