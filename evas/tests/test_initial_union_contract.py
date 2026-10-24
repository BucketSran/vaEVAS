"""Independent negative controls for explicit initial/cross OR leaf records."""
import copy
import unittest
from initial_union_contract import check_initial_union_batch


class InitialUnionCalibration(unittest.TestCase):
    def fixture(self):
        wire=dict(states=[dict(instance='dut',name='n',initial=0)],events=[
            dict(trigger=dict(kind='or',triggers=[dict(kind='cross'),dict(kind='initial_step')]),
                 expanded_statement_ordinal=0,origin=dict(source='initial.va',line=3,column=1,instance='dut'))])
        initial=dict(time=0,event=0,origin='initial.va:3:1 (dut)',kind='or',
                     fired_triggers=[dict(trigger=1,kind='initial_step')],before=[0],after=[7])
        runtime=dict(time=2,event=0,origin='initial.va:3:1 (dut)',kind='or',
                     fired_triggers=[dict(trigger=0,kind='cross',time_bounds=[2,2],guard_value=0)],before=[7],after=[7])
        result=dict(transient=dict(state_names=['dut:n'],times=[0,3],states=[[7],[7]],events=[initial,runtime]))
        return wire,result

    def test_initial_union_preserves_runtime_leaf_identity(self):
        wire,result=self.fixture()
        view=check_initial_union_batch(result,wire,[0],[7],1)
        self.assertEqual(view['transient']['events'],result['transient']['events'][1:])
        self.assertEqual(view['transient']['events'][0]['fired_triggers'][0]['trigger'],0)
        self.assertEqual(len(result['transient']['events']),2)

    def test_zero_timer_has_its_own_certified_batch_snapshot(self):
        for mutation in [None,'before','after','source','bounds','guard','order']:
            with self.subTest(mutation=mutation):
                wire,result=self.fixture()
                wire['events'].append(dict(trigger=dict(kind='timer',start=0,period=0),
                    expanded_statement_ordinal=1,origin=dict(source='initial.va',line=4,column=1,instance='dut')))
                zero=dict(time=0,event=1,origin='initial.va:4:1 (dut)',kind='timer',before=[7],after=[2])
                result['transient']['events'].insert(1,zero)
                result['transient']['states'][0]=[2]
                if mutation=='before':zero['before']=[0]
                elif mutation=='after':zero['after']=[3]
                elif mutation=='source':zero['origin']='initial.va:5:1 (dut)'
                elif mutation=='bounds':zero['observation_time_bounds']=[0,1]
                elif mutation=='guard':zero['guard_value']=0
                elif mutation=='order':result['transient']['events'][:2]=result['transient']['events'][1::-1]
                if mutation is None:
                    check_initial_union_batch(result,wire,[0],[7],1,(1,[7],[2]))
                else:
                    with self.assertRaises(AssertionError):
                        check_initial_union_batch(result,wire,[0],[7],1,(1,[7],[2]))

    def test_rejects_forged_or_missing_initial_leaf_records(self):
        for mutation in ['missing','duplicate','leaf_index','leaf_kind','extra_leaf','wrong_before',
                         'wrong_after','wrong_source','wrong_id','late_initial','wrong_bounds','guard',
                         'query_state','wrong_name','declaration']:
            with self.subTest(mutation=mutation):
                wire,result=self.fixture();e=result['transient']['events'][0]
                if mutation=='missing':result['transient']['events'].pop(0)
                elif mutation=='duplicate':result['transient']['events'].insert(0,copy.deepcopy(e))
                elif mutation=='leaf_index':e['fired_triggers'][0]['trigger']=0
                elif mutation=='leaf_kind':e['fired_triggers'][0]['kind']='cross'
                elif mutation=='extra_leaf':e['fired_triggers'].append(dict(trigger=0,kind='cross'))
                elif mutation=='wrong_before':e['before']=[7]
                elif mutation=='wrong_after':e['after']=[8]
                elif mutation=='wrong_source':e['origin']='initial.va:4:1 (dut)'
                elif mutation=='wrong_id':e['event']=1
                elif mutation=='late_initial':e['time']=1
                elif mutation=='wrong_bounds':e['observation_time_bounds']=[0,1]
                elif mutation=='guard':e['guard_value']=0
                elif mutation=='query_state':result['transient']['states'][0]=[0]
                elif mutation=='wrong_name':result['transient']['state_names']=['dut:q']
                elif mutation=='declaration':wire['states'][0]['initial']=1
                with self.assertRaises(AssertionError):check_initial_union_batch(result,wire,[0],[7],1)


if __name__=='__main__':unittest.main()
