"""Calibration binds advisory semantics before test-only record reindexing."""
import copy
import unittest
from initial_record_contract import check_initial_record_batch
from initial_source_sequence_contract import check_initial_source_sequence
from initial_union_contract import check_initial_union_batch
from test_initial_source_sequence_contract import InitialSourceSequenceCalibration
from test_initial_union_contract import InitialUnionCalibration


class InitialAdvisoryCalibration(unittest.TestCase):
    def fixture(self,owner,source='output_times',version=2):
        if owner=='sequence':
            wire,result,expected=InitialSourceSequenceCalibration().fixture()
            check=lambda:check_initial_source_sequence(result,wire,[0,0],expected)
            code='timer_observation_boundary';bounds=[0,0];query=0
        elif owner=='union':
            wire,result=InitialUnionCalibration().fixture()
            result['transient']['times']=[0,2,3]
            result['transient']['states']=[[7],[7],[7]]
            check=lambda:check_initial_union_batch(result,wire,[0],[7],1)
            code='cross_observation_boundary';bounds=[2,2];query=1
        else:
            origin=lambda line:dict(source='batch.va',line=line,column=1,instance='dut')
            wire=dict(states=[dict(initial=0)],events=[
                dict(trigger=dict(kind='initial_step'),expanded_statement_ordinal=0,origin=origin(3)),
                dict(trigger=dict(kind='cross'),expanded_statement_ordinal=1,origin=origin(4))])
            initial=dict(time=0,event=0,kind='initial_step',origin='batch.va:3:1 (dut)',before=[0],after=[7])
            runtime=dict(time=2,event=1,kind='cross',origin='batch.va:4:1 (dut)',before=[7],after=[8])
            result=dict(transient=dict(times=[0,2,3],state_names=['dut:n'],states=[[7],[8],[8]],events=[initial,runtime]))
            check=lambda:check_initial_record_batch(result,wire,[0],[7],1)
            code='cross_observation_boundary';bounds=[2,2];query=1
        runtime=result['transient']['events'][1]
        if source=='strobetimes':result['strobe_evidence']={'times':list(result['transient']['times'])}
        item=dict(event_record=1,event=runtime['event'],origin=runtime['origin'],code=code,
                  trigger=0,query_index=query,query_time_s=result['transient']['times'][query],
                  query_source=source,nonblocking=True,message='source fixture boundary')
        item['time_bounds_s' if version==2 else 'root_time_bounds_s']=bounds
        result['portability_advisories']=dict(schema_version=version,record_limit=128,
            records=[item],model_records=[],dropped_records=0,truncated=False)
        return wire,result,item,check

    def test_valid_advisories_keep_original_referents_and_do_not_mutate_input(self):
        for owner in ['sequence','union','batch']:
            for source in ['output_times','strobetimes']:
                for version in [1,2]:
                    with self.subTest(owner=owner,source=source,version=version):
                        _,result,item,check=self.fixture(owner,source,version)
                        original=copy.deepcopy(result)
                        view=check();renumbered=view['portability_advisories']['records'][0]
                        self.assertEqual(result,original)
                        self.assertEqual(renumbered,{**item,'event_record':0})
                        before=original['transient']['events'][item['event_record']]
                        after=view['transient']['events'][renumbered['event_record']]
                        self.assertEqual(before,after)

    def test_each_forged_advisory_field_is_rejected_before_reindexing(self):
        mutations=['code','unknown_code','trigger','negative_trigger','bool_trigger','bounds',
                   'reverse_bounds','query_time','query_index','query_source','event_record',
                   'event','origin','fired_kind','schema','requested_kind','reviewer_all_fields']
        for owner in ['sequence','union','batch']:
            for mutation in mutations:
                with self.subTest(owner=owner,mutation=mutation):
                    wire,result,item,check=self.fixture(owner)
                    record=result['transient']['events'][1]
                    if mutation=='code':item['code']=('cross_observation_boundary' if owner=='sequence' else 'timer_observation_boundary')
                    elif mutation=='unknown_code':item['code']='unknown_observation_boundary'
                    elif mutation=='trigger':item['trigger']=99
                    elif mutation=='negative_trigger':item['trigger']=-1
                    elif mutation=='bool_trigger':item['trigger']=False
                    elif mutation=='bounds':item['time_bounds_s']=[8,9]
                    elif mutation=='reverse_bounds':item['time_bounds_s']=[9,8]
                    elif mutation=='query_time':item['query_time_s']=3
                    elif mutation=='query_index':item['query_index']=99
                    elif mutation=='query_source':item['query_source']='invented_grid'
                    elif mutation=='event_record':item['event_record']=0
                    elif mutation=='event':item['event']=0 if owner!='union' else 1
                    elif mutation=='origin':item['origin']='forged source'
                    elif mutation=='fired_kind':
                        if owner=='union':record['fired_triggers'][0]['kind']='timer'
                        else:record['kind']='or';record['fired_triggers']=[]
                    elif mutation=='schema':result['portability_advisories']['schema_version']=3
                    elif mutation=='requested_kind':
                        requested=wire['events'][record['event']]['trigger']
                        leaf=requested['triggers'][0] if requested['kind']=='or' else requested
                        leaf['kind']='cross' if owner=='sequence' else 'timer'
                        if leaf['kind']=='timer':leaf.update(start=2,period=0,enabled=True)
                    elif mutation=='reviewer_all_fields':
                        item.update(code=('cross_observation_boundary' if owner=='sequence' else 'timer_observation_boundary'),
                                    trigger=99,time_bounds_s=[8,9],query_index=0,query_time_s=3)
                    original=copy.deepcopy(result)
                    with self.assertRaises(AssertionError):check()
                    self.assertEqual(result,original)

    def test_strobe_grid_query_mismatch_is_rejected(self):
        for owner in ['sequence','union','batch']:
            with self.subTest(owner=owner):
                _,result,_,check=self.fixture(owner,'strobetimes')
                result['strobe_evidence']['times']=[4,5,6]
                with self.assertRaises(AssertionError):check()


if __name__=='__main__':unittest.main()
