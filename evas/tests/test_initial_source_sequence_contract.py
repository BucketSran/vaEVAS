"""Calibration: reject missing/forged initial records and source-order snapshots."""
GUARDS = ['EVENT-ORDER', 'COMPOSE']
import copy
from dataclasses import dataclass
import unittest
from initial_source_sequence_contract import check_initial_source_sequence
from initial_record_contract import check_initial_record_batch
from initial_named_batches_contract import check_named_initial_batches


@dataclass
class StructuralProgram:
    states: list
    events: list

    def to_dict(self):
        raise AssertionError("test-only structural inspection must not invoke production validation")


class InitialSourceSequenceCalibration(unittest.TestCase):
    def fixture(self):
        wire={'states':[{'initial':0},{'initial':0}], 'events':[
            {'expanded_statement_ordinal':0,'trigger':{'kind':'initial_step'},
             'origin':{'source':'source.va','line':3,'column':2,'instance':'dut'}},
            {'expanded_statement_ordinal':1,'trigger':{'kind':'held_timer'},
             'origin':{'source':'source.va','line':4,'column':2,'instance':'dut'}}]}
        events=[dict(time=0,event=0,kind='initial_step',origin='source.va:3:2 (dut)',before=[0,0],after=[.5,0]),
                dict(time=0,event=1,kind='timer',origin='source.va:4:2 (dut)',before=[.5,0],after=[.5,1])]
        result={'transient':dict(state_names=['p','n'],times=[0,1],states=[[.5,1],[.5,2]],events=events)}
        expected=[(0,'initial_step',[0,0],[.5,0]),(1,'timer',[.5,0],[.5,1])]
        return wire,result,expected

    def test_valid_sequence_retains_zero_timer(self):
        wire,result,expected=self.fixture()
        view=check_initial_source_sequence(result,wire,[0,0],expected)
        self.assertEqual(view['transient']['events'],result['transient']['events'][1:])
        self.assertEqual(len(result['transient']['events']),2)

    def test_inspection_does_not_invoke_production_serialization(self):
        wire,result,expected=self.fixture()
        program=StructuralProgram(**wire)
        check_initial_source_sequence(result,program,[0,0],expected)
        # The batch helper also accepts a structural snapshot with no audit calls.
        wire['events']=wire['events'][:1]
        result['transient']['events']=result['transient']['events'][:1]
        result['transient']['states']=[[.5,0],[.5,0]]
        check_initial_record_batch(result,StructuralProgram(**wire),[0,0],[.5,0],1)

    def test_batch_helper_rejects_forged_initial_records(self):
        for mutation in ['missing','wrong_before','wrong_after','forged_source','wrong_index',
                         'wrong_kind','wrong_bounds','guard','fired','query_state']:
            with self.subTest(mutation=mutation):
                wire,result,_=self.fixture()
                wire['events']=wire['events'][:1]
                result['transient']['events']=result['transient']['events'][:1]
                result['transient']['states']=[[.5,0],[.5,0]]
                e=result['transient']['events'][0]
                if mutation=='missing':result['transient']['events']=[]
                elif mutation=='wrong_before':e['before']=[.5,0]
                elif mutation=='wrong_after':e['after']=[0,0]
                elif mutation=='forged_source':e['origin']='source.va:4:2 (dut)'
                elif mutation=='wrong_index':e['event']=1
                elif mutation=='wrong_kind':e['kind']='timer'
                elif mutation=='wrong_bounds':e['observation_time_bounds']=[0,1]
                elif mutation=='guard':e['guard_value']=0
                elif mutation=='fired':e['fired_triggers']=[{'kind':'timer'}]
                elif mutation=='query_state':result['transient']['states'][0]=[0,0]
                with self.assertRaises(AssertionError):
                    check_initial_record_batch(result,wire,[0,0],[.5,0],1)

    def test_named_source_states_reject_wrong_initial_or_zero_batch(self):
        for initial,changes,valid in [({'p':.5,'n':0},{'n':1},True),
                                      ({'p':.25,'n':0},{'n':1},False),
                                      ({'p':.5,'n':0},{'n':2},False)]:
            wire,result,_=self.fixture()
            for state,name in zip(wire['states'],['dut:p','dut:n']):state['name']=name
            if valid:
                check_named_initial_batches(result,wire,initial,[(1,'timer',changes)])
            else:
                with self.assertRaises(AssertionError):
                    check_named_initial_batches(result,wire,initial,[(1,'timer',changes)])

    def test_or_zero_leaves_keep_source_ids_and_exact_bounds(self):
        for mutation in [None,'missing_leaf','reordered_leaf','wrong_bound','guard','wrong_kind']:
            with self.subTest(mutation=mutation):
                wire,result,expected=self.fixture()
                wire['events'][1]['trigger']={'kind':'or','triggers':[{'kind':'held_timer'},{'kind':'timer'}]}
                expected[1]=(1,'or',[.5,0],[.5,1],[0,1])
                event=result['transient']['events'][1]
                event['kind']='or'
                fired=[dict(trigger=0,kind='timer'),dict(trigger=1,kind='timer',time_bounds=[0,0])]
                event['fired_triggers']=fired
                if mutation=='missing_leaf':fired.pop()
                elif mutation=='reordered_leaf':fired.reverse()
                elif mutation=='wrong_bound':fired[0]['time_bounds']=[0,1e-9]
                elif mutation=='guard':fired[0]['guard_value']=0
                elif mutation=='wrong_kind':fired[0]['kind']='cross'
                if mutation is None:
                    check_initial_source_sequence(result,wire,[0,0],expected)
                else:
                    with self.assertRaises(AssertionError):
                        check_initial_source_sequence(result,wire,[0,0],expected)

    def test_rejects_initial_and_source_order_counterexamples(self):
        for mutation in ['missing','duplicate','wrong_before','wrong_after','forged_source',
                         'wrong_index','wrong_kind','wrong_bounds','guard','fired','order',
                         'timer_before','timer_after','query_state','declaration']:
            with self.subTest(mutation=mutation):
                wire,result,expected=self.fixture();e=result['transient']['events']
                if mutation=='missing':e.pop(0)
                elif mutation=='duplicate':e.insert(0,copy.deepcopy(e[0]))
                elif mutation=='wrong_before':e[0]['before']=[7,0]
                elif mutation=='wrong_after':e[0]['after']=[.5,1]
                elif mutation=='forged_source':e[0]['origin']='source.va:7:2 (dut)'
                elif mutation=='wrong_index':e[0]['event']=1
                elif mutation=='wrong_kind':e[0]['kind']='timer'
                elif mutation=='wrong_bounds':e[0]['observation_time_bounds']=[0,1e-9]
                elif mutation=='guard':e[0]['guard_value']=0
                elif mutation=='fired':e[0]['fired_triggers']=[{'kind':'timer'}]
                elif mutation=='order':e.reverse()
                elif mutation=='timer_before':e[1]['before']=[0,0]
                elif mutation=='timer_after':e[1]['after']=[.5,2]
                elif mutation=='query_state':result['transient']['states'][0]=[.5,0]
                elif mutation=='declaration':wire['states'][0]['initial']=.5
                with self.assertRaises(AssertionError):check_initial_source_sequence(result,wire,[0,0],expected)


if __name__=='__main__':unittest.main()
