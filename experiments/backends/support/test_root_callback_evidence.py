import copy
import json
import math
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'evas/src'))
sys.path.insert(0,str(ROOT/'evas/validation/paper'))
from evas import compile_sources,Instance
from precision_v2 import load_contract
from root_windows import reference_roots
from root_callback_evidence import qualify
from callback_evidence import _counter_state, _origin_label


def fixture():
    c=next(c for c in load_contract()['cards'] if c['id']=='SH-X-RAMP')
    p=json.loads(json.dumps(compile_sources({'dut.va':c['source']},
        [Instance('dut',c['top'],{n:n for n in c['ports']},c['parameters'])]).to_dict()))
    counter=_counter_state(p,'count');sample=_counter_state(p,'y');previous=[s['initial'] for s in p['states']]
    events=[];rows=[{'time':0.,'count':0.}]
    for i,root in enumerate(reference_roots(c),1):
        before=previous[:];previous[sample]=.1*i;previous[counter]=float(i)
        t=root.bounds[1]
        events.append({'event':0,'origin':_origin_label(p['events'][0]['origin']), 'kind':'cross',
            'time':t,'observation_time_bounds':list(root.bounds),'guard_value':0.,'before':before,'after':previous[:]})
        rows.append({'time':math.nextafter(t,math.inf)+1e-12,'count':float(i)})
    rows.append({'time':c['stop_s'],'count':8.})
    r={'schema_version':p['schema_version'],'nodes':p['nodes'],
       'observation_evidence':{'initial_settled':True},'transient':{'events':events}}
    return c,p,r,rows


class LedgerCalibration(unittest.TestCase):
    def test_complete_real_compiled_state_chain_retains_boxes(self):
        c,p,r,w=fixture();old=copy.deepcopy(r)
        q=qualify(c,p,r,w,producer_qualified=True)
        self.assertEqual(q['status'],'qualified')
        self.assertEqual(list(q['committed_callback_boxes'].values()),[e['observation_time_bounds'] for e in r['transient']['events']])
        self.assertEqual(r,old)
    def test_unreviewed_producer_is_not_qualified(self):
        self.assertEqual(qualify(*fixture())['status'],'unknown')
    def test_corrupt_history_and_waveform_are_rejected(self):
        mutations=[lambda c,p,r,w:r['transient']['events'].pop(),
            lambda c,p,r,w:r['transient']['events'][1]['before'].__setitem__(0,99.),
            lambda c,p,r,w:r['transient']['events'][0].update(origin='other.va:1:1 (dut)'),
            lambda c,p,r,w:r['transient']['events'][0].update(guard_value=1.),
            lambda c,p,r,w:r['transient']['events'][0].update(observation_time_bounds=[0.,0.]),
            lambda c,p,r,w:p['events'][0]['trigger'].update(direction=-1),
            lambda c,p,r,w:w[-1].update(count=7.),
            lambda c,p,r,w:r['transient']['events'].reverse()]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                values=fixture();mutate(*values)
                self.assertEqual(qualify(*values,producer_qualified=True)['status'],'unknown')

    def test_standalone_ledger_rejects_wrong_guard_structure_and_input(self):
        # These corrupt only program trigger semantics. The record still has
        # matching origin, zero guard_value, legal boxes and intact state chain.
        mutations=[
            lambda g,p:g['left']['terms'][1].update(node=p['nodes'].index('u')),
            lambda g,p:g['left']['terms'][1].update(node=p['nodes'].index('count')),
            lambda g,p:g['left']['terms'][1].update(coefficient=-1.),
            lambda g,p:g['left']['terms'][1].update(coefficient=2.),
            lambda g,p:g['right'].update(constant=-.25),
            lambda g,p:g.update(op='multiply'),
            lambda g,p:g.update(op='power',base=g['left'],exponent=2),
            lambda g,p:g['left']['terms'][1].update(node=-1),
            lambda g,p:g['left']['terms'][1].update(node=True),
            lambda g,p:g['left']['terms'][1].update(coefficient=float('nan')),
            lambda g,p:g.update(left=None)]
        for mutate in mutations:
            values=fixture();c,p,r,w=values
            mutate(p['events'][0]['trigger']['guard'],p)
            with self.subTest(mutation=mutate):
                self.assertEqual(qualify(*values,producer_qualified=True)['status'],'unknown')

    def test_guard_direction_tolerance_and_instance_cannot_be_substituted(self):
        for field,value in [('direction',-1),('direction',True),('expression_tolerance',1.),
                            ('expression_tolerance',float('inf')),('time_tolerance',1.)]:
            c,p,r,w=fixture();p['events'][0]['trigger'][field]=value
            with self.subTest(field=field,value=value):
                self.assertEqual(qualify(c,p,r,w,producer_qualified=True)['status'],'unknown')
        c,p,r,w=fixture();p['events'][0]['origin']['instance']='other'
        for record in r['transient']['events']:
            record['origin']=_origin_label(p['events'][0]['origin'])
        self.assertEqual(qualify(c,p,r,w,producer_qualified=True)['status'],'unknown')

    def test_equivalent_affine_guard_keeps_actual_positive_slope(self):
        c,p,r,w=fixture();clock=p['nodes'].index('clk')
        p['events'][0]['trigger']['guard']={'op':'affine','constant':-.5,
            'terms':[{'node':clock,'coefficient':1.}]}
        result=qualify(c,p,r,w,producer_qualified=True)
        self.assertEqual(result['status'],'qualified')

    def test_native_counter_timing_allowance_reads_frozen_budget(self):
        c,p,r,w=fixture();t=r['transient']['events'][0]['observation_time_bounds'][0]
        w.insert(1,{'time':t-8*math.ulp(c['stop_s']),'count':1.})
        accepted=qualify(c,p,r,w,producer_qualified=True)
        self.assertEqual(accepted['status'],'qualified')
        self.assertEqual(accepted['time_serialization_ulps'],load_contract()['budgets']['time_serialization_ulps'])
        self.assertEqual(accepted['time_serialization_bound_s'],
                         load_contract()['budgets']['time_serialization_ulps']*math.ulp(c['stop_s']))
        contract=copy.deepcopy(load_contract());contract['budgets']['time_serialization_ulps']=0
        with patch('root_callback_evidence.load_contract',return_value=contract):
            self.assertEqual(qualify(c,p,r,w,producer_qualified=True)['status'],'unknown')
        for invalid in (-1,True,.5):
            contract['budgets']['time_serialization_ulps']=invalid
            with self.subTest(invalid=invalid),patch('root_callback_evidence.load_contract',return_value=contract):
                self.assertEqual(qualify(c,p,r,w,producer_qualified=True)['status'],'unknown')


if __name__=='__main__':unittest.main()
