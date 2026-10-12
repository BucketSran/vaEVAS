import copy
import unittest
from callback_evidence import callbacks


def fixture():
    card=dict(id='F07-base',stop_s=1.,counter_channels={'n':dict(initial=0,final=2)},events=[
        dict(id='t',counter='n',index=1,kind='timer',nominal_s=.25,early_s=.01,late_s=.01),
        dict(id='c',counter='n',index=2,kind='cross',nominal_s=.5,early_s=0.,late_s=.01,
             input='u',slope_V_s=1.,expression_tolerance_V=.02)])
    origin=dict(instance='dut',source='dut.va',line=10,column=1)
    program=dict(schema_version=18,nodes=['0','n','u'],states=[dict(initial=0.,instance='dut')],
                 contributions=[dict(positive=1,negative=0,rhs=dict(op='state',state=0))],events=[
                     dict(origin=origin,trigger=dict(kind='timer')),
                     dict(origin=dict(origin,line=11),trigger=dict(kind='cross',direction=1,expression_tolerance=.02,
                          guard=dict(op='affine',constant=-.5,terms=[dict(node=2,coefficient=1.)])))])
    events=[dict(event=0,origin='dut.va:10:1 (dut)',kind='timer',time=.25,before=[0.],after=[1.]),
            dict(event=1,origin='dut.va:11:1 (dut)',kind='cross',time=.5,before=[1.],after=[2.],guard_value=0.)]
    response=dict(schema_version=18,nodes=program['nodes'],observation_evidence=dict(initial_settled=True),transient=dict(events=events))
    rows=[dict(time=0.,n=0.),dict(time=.25,n=1.),dict(time=.5,n=2.),dict(time=1.,n=2.)]
    return card,program,response,rows


class CallbackCalibration(unittest.TestCase):
    def assess(self,f=None,trust=True):
        values=fixture()
        if f:f(*values)
        return callbacks(*values,producer_qualified=trust)
    def reject(self,f):self.assertEqual(self.assess(f)['status'],'unknown')
    def test_complete_history(self):
        result=self.assess();self.assertEqual(result['status'],'qualified')
        self.assertEqual(result['event_bounds_s'],{'t':[.25,.25],'c':[.5,.5]})
    def test_unreviewed_producer(self):self.assertEqual(self.assess(trust=False)['status'],'unknown')
    def test_missing_callback(self):self.reject(lambda c,p,r,w:r['transient']['events'].pop())
    def test_extra_callback(self):self.reject(lambda c,p,r,w:r['transient']['events'].append(copy.deepcopy(r['transient']['events'][-1])))
    def test_wrong_instance(self):self.reject(lambda c,p,r,w:r['transient']['events'][0].update(origin='dut.va:10:1 (other)'))
    def test_wrong_counter_mapping(self):self.reject(lambda c,p,r,w:p['contributions'][0]['rhs'].update(state=1))
    def test_reversed_order(self):self.reject(lambda c,p,r,w:r['transient']['events'].reverse())
    def test_missing_state_update(self):self.reject(lambda c,p,r,w:r['transient']['events'][0].update(after=[0.]))
    def test_broken_commit_chain(self):self.reject(lambda c,p,r,w:r['transient']['events'][1].update(before=[0.]))
    def test_box_crosses_legal_endpoint(self):self.reject(lambda c,p,r,w:r['transient']['events'][1].update(observation_time_bounds=[.499,.5]))
    def test_incomplete_box_not_clipped(self):self.reject(lambda c,p,r,w:r['transient']['events'][1].update(observation_time_bounds=[.5,.52]))
    def test_guard_wrong_sign_or_size(self):self.reject(lambda c,p,r,w:r['transient']['events'][1].update(guard_value=.03))
    def test_wrong_direction(self):self.reject(lambda c,p,r,w:p['events'][1]['trigger'].update(direction=-1))
    def test_initial_not_settled(self):self.reject(lambda c,p,r,w:r['observation_evidence'].update(initial_settled=False))
    def test_waveform_does_not_commit(self):self.reject(lambda c,p,r,w:w[-1].update(n=1.))
    def test_OR_leaf_and_own_box(self):
        c,p,r,w=fixture();trigger=p['events'][1]['trigger']
        p['events'][1]['trigger']=dict(kind='or',triggers=[trigger,dict(trigger,direction=-1)])
        r['transient']['events'][1].update(kind='or',fired_triggers=[dict(trigger=0,kind='cross',time_bounds=[.5,.5],guard_value=0.)])
        self.assertEqual(callbacks(c,p,r,w,producer_qualified=True)['status'],'qualified')
        r['transient']['events'][1]['fired_triggers'][0]['trigger']=1
        self.assertEqual(callbacks(c,p,r,w,producer_qualified=True)['status'],'unknown')
    def test_OR_multiple_leaves_not_guessed(self):
        c,p,r,w=fixture();trigger=p['events'][1]['trigger']
        p['events'][1]['trigger']=dict(kind='or',triggers=[trigger,trigger])
        r['transient']['events'][1].update(kind='or',fired_triggers=[dict(trigger=0,kind='cross',time_bounds=[.5,.5],guard_value=0.),dict(trigger=1,kind='cross',time_bounds=[.5,.5],guard_value=0.)])
        self.assertEqual(callbacks(c,p,r,w,producer_qualified=True)['status'],'unknown')
    def test_OR_full_box_is_not_replaced_by_leaf(self):
        c,p,r,w=fixture();trigger=p['events'][1]['trigger']
        p['events'][1]['trigger']=dict(kind='or',triggers=[trigger])
        event=r['transient']['events'][1]
        event.update(kind='or',observation_time_bounds=[.499,.5],
                     fired_triggers=[dict(trigger=0,kind='cross',time_bounds=[.5,.5],guard_value=0.)])
        self.assertEqual(callbacks(c,p,r,w,producer_qualified=True)['status'],'unknown')
        event['observation_time_bounds']=[.5,.505]
        result=callbacks(c,p,r,w,producer_qualified=True)
        self.assertEqual(result['event_bounds_s']['c'],[.5,.505])
        event['fired_triggers'][0]['kind']='timer'
        self.assertEqual(callbacks(c,p,r,w,producer_qualified=True)['status'],'unknown')
    def test_missing_guard_is_not_zero(self):
        self.reject(lambda c,p,r,w:r['transient']['events'][1].pop('guard_value'))
    def test_nonfinite_box(self):
        self.reject(lambda c,p,r,w:r['transient']['events'][1].update(observation_time_bounds=[.5,float('nan')]))

if __name__=='__main__':unittest.main()
