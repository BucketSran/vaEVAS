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
        m=load(); cs={c['group_id']:c for c in m.cards() if c['id'].endswith('-v1')}
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
        self.assertEqual(cards['EC06']['source'].count('integral_cell #'),2)
        self.assertIn('acell(a,n)',cards['EC06']['source'])
        self.assertIn('bcell(b,nb)',cards['EC06']['source'])
        self.assertIn('phase_cell #',cards['EC19']['source'])

    def test_missing_illegal_and_reordered_history_are_rejected(self):
        m=load(); card=next(c for c in m.cards() if c['group_id']=='EC06')
        history={e['id']:[e['nominal_s']]*2 for e in card['events']}
        with self.assertRaises(ValueError):m.reference(card,m.UNIT,{})
        illegal={**history,card['events'][0]['id']:[0.,0.]}
        with self.assertRaises(ValueError):m.reference(card,m.UNIT,illegal)
        with self.assertRaises(ValueError):m.reference(card,float('nan'),history)
        repeated={**history,'repeated-callback':[card['unit_s']]*2}
        with self.assertRaises(ValueError):m.reference(card,m.UNIT,repeated)
        # Broaden only this negative control's legal windows so the frozen
        # ordering check, rather than the individual-window check, rejects it.
        from copy import deepcopy
        reordered=deepcopy(card)
        for e in reordered['events']:e['early_s']=e['late_s']=m.UNIT
        e0,e1=reordered['events']
        backwards={e0['id']:[.8*m.UNIT]*2,e1['id']:[.4*m.UNIT]*2}
        with self.assertRaisesRegex(ValueError,'frozen event order'):
            m.reference(reordered,m.UNIT,backwards)
        self.assertEqual(m.reference(card,m.UNIT,history)['undefined'],{})

    def test_probe_slots_never_manufacture_precision_answers(self):
        m=load();probes=[c for c in m.cards() if c.get('support_probe_only')]
        self.assertEqual({c['group_id'] for c in probes},{'EC05','EC22','EC23','EC24'})
        for c in probes:
            with self.assertRaises(NotImplementedError):m.reference(c,0.,{})

    def test_interrupted_integral_probe_uses_legal_port_identifier(self):
        m=load();c=next(c for c in m.cards() if c['group_id']=='EC05')
        # VAMS 2.4 Annex B/C.16 reserves edge. This source revision keeps
        # the logical case/group count; frozen runs retain their old source.
        self.assertEqual(c['ports'],['edge_v','y','n'])
        self.assertIn('V(edge_v)<+transition',c['source'])
        self.assertIn('idt(V(edge_v)/T',c['source'])
        self.assertNotIn('V(edge)',c['source'])
        self.assertTrue(c['support_probe_only'])

    def test_all_ready_groups_have_independent_handwritten_anchors(self):
        m=load();cs={c['group_id']:c for c in m.cards() if c['id'].endswith('-v1')}
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

    def test_completed_transition_starts_fresh_same_direction_edge(self):
        m=load();c=next(c for c in m.cards() if c['group_id']=='EC01')
        history={e['id']:[e['nominal_s']]*2 for e in c['events']}
        # 6T edge has reached .8. The 8T edge rises .8->1.2 in .125T.
        for x,correct,stale in ((8.03125,.9,1.1625),(8.0625,1.,1.2)):
            lo,hi=m.reference(c,x*m.UNIT,history)['outputs']['out']
            self.assertLessEqual(lo,correct)
            self.assertGreaterEqual(hi,correct)
            self.assertLess(hi-lo,1e-9)
            self.assertFalse(lo<=stale<=hi)

    def test_transition_completion_uncertainty_contains_both_history_branches(self):
        m=load()
        from decimal import localcontext
        with localcontext() as ctx:
            ctx.prec=80
            t=m._I(.15);first=m._I(0);second=m._I(.115,.135)
            whole=m._transition(t,[first,second],[1,2],0,0,m._I(.125),m._I(.125)).floats()
            for e in (.115,.125,.135):
                point=m._transition(t,[first,m._I(e)],[1,2],0,0,m._I(.125),m._I(.125)).floats()
                self.assertLessEqual(whole[0],point[0])
                self.assertGreaterEqual(whole[1],point[1])

    def test_input_gains_cover_composed_consumers_and_unbounded_obligations(self):
        m=load();cs={c['group_id']:c for c in m.cards() if c['id'].endswith('-v1')}
        self.assertGreaterEqual(cs['EC03']['input_gain_bound'],4)
        self.assertGreaterEqual(cs['EC04']['input_gain_bound'],16)
        self.assertGreaterEqual(cs['EC12']['input_gain_bound'],13.502)
        self.assertGreaterEqual(cs['EC17']['input_gain_bound']['out'],2*__import__('math').pi)
        self.assertEqual(set(cs['EC16']['input_gain_evidence_required']),{'d','y'})
        self.assertEqual(set(cs['EC17']['input_gain_evidence_required']),{'phase'})

    def test_internal_input_corner_variants_preserve_states_and_direct_terms(self):
        m=load();cs={c['id']:c for c in m.cards()}
        self.assertEqual(len(cs),27)
        self.assertEqual(cs['EC06-v1']['source'].count('integral_cell #'),2)
        self.assertNotEqual(cs['EC06-v1']['source'],cs['EC06-v2']['source'])
        import math
        e2=math.exp(-2);r=1.
        anchors={'EC11-v2':{'y':2+(4*e2-2+(-1+e2)*r)*math.exp(-r),
                            'd':(1-3*e2-(-1+e2)*r)*math.exp(-r)},
                 'EC12-v2':{'h':3.125+math.exp(-2)}}
        for id,channels in anchors.items():
            c=cs[id];self.assertIn([2*m.UNIT,c['inputs']['u'][1][1]],c['inputs']['u'])
            out=m.reference(c,3*m.UNIT,{})['outputs']
            for channel,value in channels.items():
                lo,hi=out[channel];self.assertLessEqual(lo,value);self.assertGreaterEqual(hi,value)
                self.assertLess(hi-lo,1e-10)
                self.assertFalse(lo<=value+.01<=hi)
            at=m.reference(c,2*m.UNIT,{})['outputs']
            base=m.reference(cs[id.replace('-v2','-v1')],2*m.UNIT,{})['outputs']
            for channel in at:
                self.assertLessEqual(at[channel][0],base[channel][1])
                self.assertGreaterEqual(at[channel][1],base[channel][0])

    def test_dc_derivative_boundary_encloses_positive_serialization_times(self):
        import math
        m=load();c=next(c for c in m.cards() if c['group_id']=='EC16')
        # Laplace transfer (1+sT)/(1+2sT) has direct term 1/2.
        # A transient unit derivative step gives y=1-exp(-x/2)/2;
        # a DC derivative is zero. Timestamp zero alone selects neither.
        answer=m.reference(c,0.,{})
        for name,right in {'d':1.,'y':.5}.items():
            lo,hi=answer['outputs'][name]
            self.assertLessEqual(lo,0.)
            self.assertGreaterEqual(hi,right)
        radius=c['reference_time_uncertainty_s']
        for t in (radius/4,radius/2,radius):
            correct=1-.5*math.exp(-t/m.UNIT/2)
            lo,hi=answer['outputs']['y']
            self.assertLessEqual(lo,correct);self.assertGreaterEqual(hi,correct)
        self.assertTrue(answer['time_uncertainty_included'])
        right=m.reference(c,2e-12,{})['outputs']
        self.assertGreater(right['d'][0],.999999)
        self.assertGreater(right['y'][0],.5)
        self.assertFalse(right['y'][0]<=0.<=right['y'][1])

    def test_nonlast_transition_window_contains_independent_rational_replay(self):
        import itertools
        from fractions import Fraction as F
        m=load();c=next(c for c in m.cards() if c['group_id']=='EC02')
        boxes={e['id']:[e['nominal_s'],e['nominal_s']+e['late_s']] for e in c['events']}
        # Independent scalar state machine in exact fractions. Its state is
        # actual start, target, slope and origin, with no interval operations.
        def scalar(query,callbacks):
            start=target=origin=F(0);slope=F(0);when=F(0)
            def value(t):
                v=start+slope*max(F(0),t-when)
                return min(max(start,target),max(min(start,target),v))
            for e,newtarget in zip(callbacks,(1,0,1,0)):
                at=e+F(1,16)
                if query<at:return value(query)
                current=value(at)
                if current==target:origin=target
                duration=F(1,4) if newtarget>current else F(1,2)
                history=origin if (newtarget>current)==(slope>=0) else target
                start=current;slope=(newtarget-history)/duration
                origin=history;target=F(newtarget);when=at
            return value(query)
        for index in (1,2,3):
            e=c['events'][index];a,b=boxes[e['id']]
            for weight in (0.,.25,.5,.75,1.):
                query=a+(b-a)*weight+m.UNIT/16
                lo,hi=m.reference(c,query,boxes)['outputs']['out']
                for weights in itertools.product((0.,.5,1.),repeat=4):
                    callbacks=[F(boxes[e['id']][0]+w*(boxes[e['id']][1]-boxes[e['id']][0]))/F(m.UNIT)
                               for e,w in zip(c['events'],weights)]
                    expected=scalar(F(query)/F(m.UNIT),callbacks)
                    with self.subTest(index=index,weight=weight,history=weights):
                        self.assertLessEqual(F(lo),expected)
                        self.assertGreaterEqual(F(hi),expected)

    def test_vco_input_gain_bounds_integrated_voltage_perturbation(self):
        import math
        m=load();c=next(c for c in m.cards() if c['group_id']=='EC17')
        # f=.5+.25u, so delta phase=.25*integral(delta u dx).
        # The run lasts 4T. Voltage perturbation epsilon has phase gain 1,
        # then sine has global gain 2*pi. df/dx is a time sensitivity,
        # not the input-voltage gain.
        gain=c['input_gain_bound']['out']
        self.assertGreaterEqual(gain,2*math.pi)
        for x in (0.,1.,2.,3.,4.):
            phase=.125+.5*x+.125*x*x
            for epsilon in (-.001,-.00001,.00001,.001):
                actual=math.sin(2*math.pi*(phase+.25*epsilon*x))
                nominal=math.sin(2*math.pi*phase)
                self.assertLessEqual(abs(actual-nominal),gain*abs(epsilon)+1e-14)

    def test_nonlast_transition_keeps_old_branch_across_query_time_box(self):
        from decimal import localcontext
        from fractions import Fraction as F
        m=load()
        with localcontext() as ctx:
            ctx.prec=80
            query=m._I(.05-1e-9,.05+1e-9)
            events=[m._I(0),m._I(.05),m._I(1)]
            # At the left query endpoint the .05 reversal has not occurred,
            # so the old rise is still 8*t. At the right endpoint it has
            # reversed from 8*.05 with downward slope -4.
            old_left=8*F(.05-1e-9)
            new_right=8*F(.05)-4*(F(.05+1e-9)-F(.05))
            for stages in (None,[True,True,False]):
                lo,hi=m._transition(query,events,[1,0,1],0,0,
                                    m._I(.125),m._I(.25),stages).floats()
                self.assertLessEqual(F(lo),old_left)
                self.assertGreaterEqual(F(hi),new_right)
                # The incomplete-edge target value .5 is a wrong-state
                # control. Enclosing both branches must not accept it.
                self.assertFalse(lo<=.5<=hi)

    def test_completed_transition_encloses_uncertain_targets_in_both_directions(self):
        from decimal import localcontext
        m=load()
        with localcontext() as ctx:
            ctx.prec=80
            for initial,target in ((0,m._I(1,2)),(3,m._I(1,2))):
                lo,hi=m._transition(m._I(10),[m._I(0)],[target],initial,0,
                                    m._I(1),m._I(1)).floats()
                # Ten rise/fall durations later, each coherent target is
                # exactly its final voltage, regardless of direction.
                self.assertLessEqual(lo,1.);self.assertGreaterEqual(hi,2.)
                self.assertGreater(lo,.999999);self.assertLess(hi,2.000001)
                self.assertFalse(lo<=.9<=hi);self.assertFalse(lo<=2.1<=hi)
            # At a quarter duration, exact coherent targets give these
            # scalar ranges. Interval correlations may over-enclose them.
            for initial,expected in ((0,(.25,.5)),(3,(2.5,2.75))):
                lo,hi=m._transition(m._I(.25),[m._I(0)],[m._I(1,2)],initial,0,
                                    m._I(1),m._I(1)).floats()
                self.assertLessEqual(lo,expected[0]);self.assertGreaterEqual(hi,expected[1])
                self.assertFalse(lo<=expected[0]-.1<=hi)
                self.assertFalse(lo<=expected[1]+.1<=hi)

    def test_sample_transition_completed_stop_retains_nominal_callback_history(self):
        from fractions import Fraction as F
        m=load();c=next(c for c in m.cards() if c['group_id']=='EC01')
        boxes={e['id']:[e['nominal_s'],e['nominal_s']+e['late_s']] for e in c['events']}
        answer=m.reference(c,c['stop_s'],boxes)['outputs']
        # Final sample is u(8T), on the original two-endpoint affine ramp.
        # By stop=9T, the .125T edge is complete for every legal callback.
        a,b=c['inputs']['u'];nominal=c['events'][-1]['nominal_s']
        correct=F(a[1])+(F(b[1])-F(a[1]))*(F(nominal)-F(a[0]))/(F(b[0])-F(a[0]))
        for output in ('q','out'):
            lo,hi=answer[output]
            self.assertLessEqual(F(lo),correct);self.assertGreaterEqual(F(hi),correct)
            self.assertFalse(lo<=1.19<=hi);self.assertFalse(lo<=1.21<=hi)
        for weight in (0.,.5,1.):
            sampled=nominal+weight*c['events'][-1]['late_s']
            value=F(a[1])+(F(b[1])-F(a[1]))*(F(sampled)-F(a[0]))/(F(b[0])-F(a[0]))
            lo,hi=answer['out'];self.assertLessEqual(F(lo),value);self.assertGreaterEqual(F(hi),value)
