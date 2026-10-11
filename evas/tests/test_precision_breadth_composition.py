"""Hand-calculated composition reference anchors through the agreed public API."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'validation/paper/precision_breadth_composition.py'

def load():
    spec = importlib.util.spec_from_file_location('breadth_composition', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class CompositionReferences(unittest.TestCase):
    def test_all_group_slots_and_hand_calculated_reset_anchor(self):
        module = load()
        items = module.cards()
        self.assertEqual({c['group_id'] for c in items}, {f'EC{i:02d}' for i in range(1,25)})
        card = next(c for c in items if c['group_id'] == 'EC06')
        bounds = {e['id']: [e['nominal_s']]*2 for e in card['events']}
        answer = module.reference(card, card['unit_s'], bounds)['outputs']
        self.assertLessEqual(answer['a'][0], .375)
        self.assertGreaterEqual(answer['a'][1], .375)
        self.assertLessEqual(answer['b'][0], .75)
        self.assertGreaterEqual(answer['b'][1], .75)

    def test_joint_feedback_and_reset_area_hand_anchors(self):
        m=load(); cs={c['group_id']:c for c in m.cards()}
        checks=[('EC07',1.,{'z':.5,'y':.53125}),('EC09',1.5,{'z':1.5,'y':2.25}),
                ('EC15',3.,{'a':1.,'b':1.5}),('EC18',1.,{'phase':-.125})]
        for group,x,expected in checks:
            card=cs[group]; history={e['id']:[e['nominal_s']]*2 for e in card['events']}
            out=m.reference(card,x*m.UNIT,history)['outputs']
            for channel,value in expected.items():
                with self.subTest(group=group,channel=channel):
                    self.assertLessEqual(out[channel][0],value)
                    self.assertGreaterEqual(out[channel][1],value)
                    self.assertLess(out[channel][1]-out[channel][0],1e-10)

    def test_whole_callback_interval_reaches_future_integral(self):
        m=load(); card=next(c for c in m.cards() if c['group_id']=='EC04')
        event=card['events'][0]; root=event['nominal_s']
        wide={event['id']:[root,root+1e-10]}
        interval=m.reference(card,2*m.UNIT,wide)['outputs']['y']
        # Previously sampled uncertainty must survive into future q*q area.
        for shift in [0.,.5e-10,1e-10]:
            exact=m.reference(card,2*m.UNIT,{event['id']:[root+shift]*2})['outputs']['y']
            self.assertLessEqual(interval[0],exact[0])
            self.assertGreaterEqual(interval[1],exact[1])
        self.assertGreater(interval[1]-interval[0],1e-5)

    def test_phase_half_open_exact_endpoint_and_continuous_sine(self):
        m=load(); card=next(c for c in m.cards() if c['group_id']=='EC18')
        answer=m.reference(card,2.5*m.UNIT,{})
        out=answer['outputs']
        self.assertEqual(answer['point_reference']['phase'],-.5)
        self.assertGreater(out['phase'][1]-out['phase'][0],.99)
        self.assertLessEqual(out['phase'][0],-.5)
        self.assertGreaterEqual(out['phase'][1],-.5)
        self.assertLess(abs(sum(out['out'])/2),1e-12)

    def test_complete_common_models_compile_and_cards_generate_four_decks(self):
        import json
        import sys
        m=load(); root=PATH.parents[3]
        sys.path.insert(0,str(root/'evas/src'))
        # Frontend syntax binding only, no kernel is built or invoked.
        from evas import Instance, compile_sources
        spec=importlib.util.spec_from_file_location('breadth_decks',root/'experiments/backends/paper/inputs.py')
        decks_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(decks_module)
        for c in m.cards():
            with self.subTest(card=c['id']):
                json.dumps(c,allow_nan=False)
                compile_sources({'dut.va':c['source']},[Instance('dut',c['top'],{p:p for p in c['ports']},c['parameters'])])
                physical={**c,'stimulus':{k:{'points_s_V':v} for k,v in c['inputs'].items()}}
                bind={'ports':c['ports'],'parameters':c['parameters'],'top_module':c['top']}
                settings={'stop_s':c['stop_s'],'maxstep_s':m.UNIT/32,'spice_maxstep_s':m.UNIT/32,
                          'reltol':1e-6,'vabstol_V':1e-10,'iabstol_A':1e-14}
                d=decks_module.decks(physical,settings,bind,[0,c['stop_s']],{'records':[{'time_s':0},{'time_s':c['stop_s']}]})
                self.assertEqual(set(d),set(decks_module.BACKENDS))

    def test_independent_instance_histories_are_actual_submodule_instances(self):
        m=load(); cards={c['group_id']:c for c in m.cards()}
        self.assertIn('reset_cell acell',cards['EC06']['source'])
        self.assertIn('fixed_cell bcell',cards['EC06']['source'])
        self.assertIn('phase_cell #',cards['EC19']['source'])

    def test_missing_illegal_and_reordered_history_are_rejected(self):
        m=load(); card=next(c for c in m.cards() if c['group_id']=='EC06')
        history={e['id']:[e['nominal_s']]*2 for e in card['events']}
        with self.assertRaises(ValueError):m.reference(card,m.UNIT,{})
        illegal={**history,card['events'][0]['id']:[0.,0.]}
        with self.assertRaises(ValueError):m.reference(card,m.UNIT,illegal)
        with self.assertRaises(ValueError):m.reference(card,float('nan'),history)
        self.assertEqual(m.reference(card,m.UNIT,history)['undefined'],{})

    def test_probe_slots_never_manufacture_precision_answers(self):
        m=load();probes=[c for c in m.cards() if c.get('support_probe_only')]
        self.assertEqual({c['group_id'] for c in probes},{'EC05','EC22','EC23','EC24'})
        for c in probes:
            with self.assertRaises(NotImplementedError):m.reference(c,0.,{})

    def test_all_ready_groups_have_independent_handwritten_anchors(self):
        m=load();cs={c['group_id']:c for c in m.cards()}
        # Values were derived from state tables, rectangle/trapezoid areas,
        # modulo arithmetic and the specified closed-form ODE solutions.
        anchors=[
            ('EC01',7.,{'q':.8,'out':.8}),
            ('EC02',4.25,{'state':0.,'out':.09375}),
            ('EC03',3.5,{'q':.75,'y':1.}),
            ('EC04',1.,{'q':2.,'y':9.}),
            ('EC06',1.,{'a':.375,'b':.75,'sum':1.125}),
            ('EC07',1.,{'z':.5,'y':.53125}),
            ('EC08',1.,{'y':.801499479994506,'other':.875}),
            ('EC09',1.5,{'z':1.5,'y':2.25}),
            ('EC10',1.25,{'y':1.2}),
            ('EC11',1.,{'y':.103638323514327,'d':.264241117657115}),
            ('EC12',1.,{'h':1.625}),
            ('EC13',1.5,{'z':1.09375,'delayed':1.0546875,'q':.8984375}),
            ('EC14',1.,{'a':1.125,'b':.75,'other':1.}),
            ('EC15',3.,{'a':1.,'b':1.5}),
            ('EC16',2.,{'d':1.,'y':.816060279414279}),
            ('EC17',1.,{'freq':.75,'phase':.75,'out':-1.}),
            ('EC18',1.,{'freq':-.25,'phase':-.125,'out':-.707106781186548}),
            ('EC19',.5,{'phase_a':.375,'phase_b':.125,'out_a':.707106781186548,
                         'out_b':.707106781186548,'sum':1.414213562373095,'diff':0.}),
            ('EC20',7e-6/m.UNIT,{'q':3.,'z':9e-6/m.UNIT,'sample':6e-6/m.UNIT}),
            ('EC21',1.,{'y':.631578947368421})]
        self.assertEqual({g for g,_,_ in anchors},{g for g,c in cs.items() if not c.get('support_probe_only')})
        for group,x,channels in anchors:
            c=cs[group];history={e['id']:[e['nominal_s']]*2 for e in c['events']}
            answer=m.reference(c,x*m.UNIT,history)
            for name,value in channels.items():
                lo,hi=answer['outputs'][name]
                with self.subTest(group=group,channel=name):
                    # Literal anchors have <=5e-15 presentation rounding.
                    self.assertLessEqual(lo-5e-15,value)
                    self.assertGreaterEqual(hi+5e-15,value)
                    self.assertLess(hi-lo,1e-9)
                    self.assertFalse(lo<=value+.01<=hi)
                    self.assertFalse(lo<=value-.01<=hi)

    def test_interrupted_edge_replays_one_history_box(self):
        import itertools
        m=load();c=next(c for c in m.cards() if c['group_id']=='EC02')
        boxes={e['id']:[e['nominal_s'],e['nominal_s']+.5*e['late_s']] for e in c['events']}
        whole=m.reference(c,4.25*m.UNIT,boxes)['outputs']['out']
        # Accept all coherent endpoint/interior histories and retain uncertainty
        # after reversal; no per-query callback value can be selected to fit DUT.
        for choices in itertools.product((0.,.5,1.),repeat=len(c['events'])):
            h={e['id']:[boxes[e['id']][0]+choice*(boxes[e['id']][1]-boxes[e['id']][0])]*2
               for e,choice in zip(c['events'],choices)}
            point=m.reference(c,4.25*m.UNIT,h)['outputs']['out']
            self.assertLessEqual(whole[0],point[0])
            self.assertGreaterEqual(whole[1],point[1])
        self.assertGreater(whole[1]-whole[0],1e-5)

    def test_qualified_counter_phase_excludes_impossible_current_sample_state(self):
        m=load();c=next(c for c in m.cards() if c['group_id']=='EC03')
        history={e['id']:[e['nominal_s']-1e-10,e['nominal_s']+1e-10] for e in c['events']}
        before={**c,'reference_counter_stages':{'n':0}}
        after={**c,'reference_counter_stages':{'n':1}}
        pre=m.reference(before,m.UNIT,history)['outputs']
        post=m.reference(after,m.UNIT,history)['outputs']
        self.assertLess(pre['q'][1],-.249999999)
        self.assertGreater(post['q'][0],.2499)
        # Integral is continuous and uses the same callback box, not a
        # fitted per-row callback value chosen to explain a DUT waveform.
        self.assertLessEqual(pre['y'][0],-.125)
        self.assertGreaterEqual(pre['y'][1],-.125)
        self.assertGreater(post['y'][1]-post['y'][0],1e-5)

    def test_nonlinear_sample_reference_contains_interior_time_extremum(self):
        from fractions import Fraction as F
        m=load();c=next(c for c in m.cards() if c['group_id']=='EC04');e=c['events'][0]
        lo=e['nominal_s'];hi=lo+.9*e['late_s'];mid=(lo+hi)/2
        rho=F(mid)/F(m.UNIT);q=2*rho+1
        # Select the future time at which dy/d(rho)=0 in the callback box.
        x=rho+(q*q-4)/(4*q)
        query=float(x)*m.UNIT
        whole=m.reference(c,query,{e['id']:[lo,hi]})['outputs']['y']
        center=m.reference(c,query,{e['id']:[mid,mid]})['outputs']['y']
        self.assertLessEqual(whole[0],center[0])
        self.assertGreaterEqual(whole[1],center[1])

    def test_late_callback_deltas_respect_both_cross_tolerances(self):
        m=load();cards={c['group_id']:c for c in m.cards()}
        self.assertEqual(cards['EC03']['events'][0]['early_s'],m.TIME_TOL)
        for e in cards['EC02']['events']:
            self.assertEqual(e['early_s'],0.)
            self.assertLessEqual(e['late_s'],m.TIME_TOL)
            self.assertLessEqual(e['late_s']*abs(e['slope_V_s']),e['expression_tolerance_V']*(1+1e-14))

    def test_stage_metadata_rejects_invalid_counts_and_contradictory_flags(self):
        m=load();c=next(c for c in m.cards() if c['group_id']=='EC03')
        history={e['id']:[e['nominal_s']]*2 for e in c['events']}
        flags={e['id']:False for e in c['events']}
        for counts in ({}, {'n':True}, {'n':100}):
            with self.assertRaises(ValueError):
                m.reference({**c,'reference_counter_stages':counts,
                             'reference_event_stages':flags},m.UNIT,history)
        with self.assertRaises(ValueError):
            m.reference({**c,'reference_counter_stages':{'n':1},
                         'reference_event_stages':flags},m.UNIT,history)
