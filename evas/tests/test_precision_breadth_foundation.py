"""Handwritten calibration anchors through the frozen foundation API."""
import importlib.util
from pathlib import Path
import unittest
import copy
import math
import sys

sys.path.insert(0, str(PATH_DIR := Path(__file__).parents[1] / 'validation/paper'))
from precision_breadth import assess, load_contract

PATH = Path(__file__).parents[1] / 'validation/paper/precision_breadth_foundation.py'
spec = importlib.util.spec_from_file_location('foundation', PATH)
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


class FoundationReferences(unittest.TestCase):
    def card(self, group, variant=None):
        return next(c for c in f.cards() if c['group_id'] == group
                    and (variant is None or c['id'] == variant))

    def contains(self, result, name, expected, width=1e-10):
        lo, hi = result['outputs'][name]
        self.assertLessEqual(lo, expected)
        self.assertGreaterEqual(hi, expected)
        self.assertLessEqual(hi-lo, width)

    def test_contribution_reads_value_before_reassignment(self):
        c=self.card('F02')
        # Initial u=-.5, r=.25: 3v+.125+r=-1.875; final local gives -1.125.
        out=f.reference(c, 0, {})
        self.contains(out, 'y', -1.875)
        self.contains(out, 'z', -1.125)
        self.assertFalse(out['outputs']['y'][0] <= -2.5 <= out['outputs']['y'][1])


    def test_pure_relations_against_handwritten_initial_answers(self):
        anchors={'F01':{'yA':-1.875,'yB':.75},
                 'F06':{'y':-4.25,'first':-.5,'last':-2.},
                 'F08':{'b0':-.5,'b1':1.75,'y':1.},
                 'F09':{'z':-1.125,'y':1.0625},
                 'F10':{'y':-1.125},'F11':{'y':-1/12}}
        for group, answers in anchors.items():
            with self.subTest(group=group):
                out=f.reference(self.card(group),0,{})
                for name, answer in answers.items(): self.contains(out,name,answer)

    def test_dc_equality_and_case_do_not_truncate_real_inputs(self):
        for c in (c for c in f.cards() if c['group_id'] in ('F03','F04')):
            u=c['inputs']['u'][0][1]
            out=f.reference(c,0,{})
            if c['group_id']=='F03':
                for n, answer in dict(lt=int(u<.5),le=int(u<=.5),
                                     gt=int(u>.5),ge=int(u>=.5)).items():
                    self.contains(out,n,answer)
            else:
                self.contains(out,'y',3 if u in (0,1) else 7 if u==2 else 9)

    def test_logical_expression_uses_spectre_compatible_port_name(self):
        # Actual VACOMP-2259 located the unescaped `logic` port declaration.
        for c in (c for c in f.cards() if c['group_id']=='F03'):
            self.assertIn('logic_out',c['ports'])
            self.assertNotIn('logic',c['ports'])
            self.assertIn('V(logic_out)<+',c['source'])
            a,b,d=(c['inputs'][n][0][1]!=0 for n in ('a','b','c'))
            self.contains(f.reference(c,0,{}),'logic_out',int(a or b and d))

    def test_functions_include_threshold_and_both_branches(self):
        for variant, expected in [('F05-dc-0',0),('F05-dc-1',.5),('F05-dc-2',.75)]:
            out=f.reference(self.card('F05',variant),0,{})
            self.contains(out,'y',expected)
            self.contains(out,'z',expected if expected<=.5 else 1-expected)


    def test_non_idempotent_array_events_cannot_hide_repeated_update(self):
        c=self.card('F07')
        bounds={e['id']:[e['nominal_s'],e['nominal_s']] for e in c['events']}
        for t,first,last,total,count in [(0,0,1,1,0),(.4e-6,1,12,13,1),(.75e-6,11,122,133,2)]:
            out=f.reference(c,t,bounds)
            for name,val in [('first',first),('last',last),('y',total),('count',count)]:
                self.contains(out,name,val)
        out=f.reference(c,.4e-6,bounds)
        self.assertFalse(out['outputs']['y'][0]<=133<=out['outputs']['y'][1])

    def test_unknown_event_time_preserves_entire_window(self):
        c=self.card('F07');e=c['events'][0]
        out=f.reference(c,e['nominal_s'],{})
        self.assertLessEqual(out['outputs']['y'][0],1)
        self.assertGreaterEqual(out['outputs']['y'][1],13)
        with self.assertRaises(ValueError):f.reference(c,0,{e['id']:[2.,1.]})

    def test_integral_initial_value_and_full_return_are_preserved(self):
        c=self.card('F13')
        for t,v in [(0,.125),(1e-6,.375),(2e-6,.375),(3e-6,.125)]:
            interval=f.reference(c,t,{})['outputs']['y']
            self.assertLess(max(abs(x-v) for x in interval),1e-14)

    def test_ddt_defined_sides_and_undefined_corner(self):
        c=self.card('F14')
        point=copy.deepcopy(c);point['reference_time_uncertainty_s']=0
        self.contains(f.reference(point,0,{}),'y',0)
        self.contains(f.reference(c,.5e-6,{}),'y',.5)
        self.contains(f.reference(c,1.5e-6,{}),'y',-1)
        self.assertIn('y',f.reference(c,1e-6,{})['undefined'])
        self.assertNotIn('y',f.reference(c,1e-6-2e-12,{})['undefined'])

    def test_delay_and_slew_handwritten_mode_anchors(self):
        c=self.card('F17')
        for t,v in [(0,-.25),(.75e-6,-.25),(1.75e-6,.75),(3e-6,-.25)]:
            self.contains(f.reference(c,t,{}),'y',v)
        c=self.card('F18')
        for t,v in [(0,0),(1e-6,.25),(1.2e-6,.3),(2.8e-6,-.5),(3e-6,-.5)]:
            self.contains(f.reference(c,t,{}),'y',v)

    def test_transition_complete_asymmetric_edges_use_one_history(self):
        c=self.card('F19');bounds={e['id']:[e['nominal_s'],e['nominal_s']] for e in c['events']}
        for t,v in [(0,0),(1.5e-6,.25),(2e-6,.5),(3.75e-6,.25),(c['stop_s'],0)]:
            self.contains(f.reference(c,t,bounds),'y',v)

    def test_filter_encodings_have_same_dyadic_ode_and_nonzero_initial(self):
        a,b=self.card('F15'),self.card('F16')
        self.assertEqual(a['unit_s'],2**-20)
        self.assertEqual(a['inputs'],b['inputs'])
        self.contains(f.reference(a,0,{}),'y',.25)
        self.contains(f.reference(b,0,{}),'y',.25)
        # u=.25+.5x, y(1)=.25+.5/e = .43393972058572116.
        for c in (a,b):self.contains(f.reference(c,2**-20,{}),'y',.43393972058572117)

    def test_phase_halfopen_wrapping_and_sine_are_distinct_obligations(self):
        c=self.card('F20')
        self.contains(f.reference(c,0,{}),'phase',.125)
        self.contains(f.reference(c,0,{}),'y',.7071067811865476)
        # At t=.5us phase=.5, sin=0; at t=1.5us rawphase=.25.
        self.contains(f.reference(c,.5e-6,{}),'phase',.5)
        self.contains(f.reference(c,.5e-6,{}),'y',0)
        self.contains(f.reference(c,1.5e-6,{}),'phase',.25)
        root=c['critical_times_s'][1]
        out=f.reference(c,root,{})
        self.assertFalse(out['undefined'])
        self.assertGreater(out['outputs']['phase'][1]-out['outputs']['phase'][0],.9)


    def test_cubic_roots_include_exact_dc_anchors(self):
        for i,answer in enumerate((-1.,0.,1.)):
            out=f.reference(self.card('F12',f'F12-dc-{i}'),0,{})
            self.contains(out,'y',answer)
            self.assertFalse(out['outputs']['y'][0]<=answer+.001<=out['outputs']['y'][1])

    def test_all_groups_have_complete_json_cards_and_finite_references(self):
        import json
        cs=f.cards()
        self.assertEqual({c['group_id'] for c in cs},{f'F{i:02d}' for i in range(1,21)})
        self.assertEqual(len({c['id'] for c in cs}),len(cs))
        json.dumps(cs,allow_nan=False)
        required={'source','top','ports','parameters','inputs','outputs','scale_V',
                  'unit_s','stop_s','critical_times_s','events','counter_channels',
                  'input_gain_bound','output_slope_bound_V_s','reference_kind','reference_parameters'}
        for c in cs:
            with self.subTest(card=c['id']):
                self.assertTrue(required<=c.keys())
                self.assertTrue(c['source'].endswith('endmodule\n'))
                for t in [0,c['stop_s']/2,c['stop_s']]:
                    out=f.reference(c,t,{})
                    self.assertEqual(set(out['outputs'])|set(out['undefined']),set(c['outputs']))
                    json.dumps(out,allow_nan=False)
                    self.assertLess(out['numerical_uncertainty_V'],1e-9)
                    self.assertTrue(all(lo<=hi for lo,hi in out['outputs'].values()))

    def test_bad_times_and_event_identity_do_not_produce_golden_answers(self):
        c=self.card('F07')
        for t in (float('nan'),float('inf'),-1,c['stop_s']+1):
            with self.assertRaises(ValueError):f.reference(c,t,{})
        with self.assertRaises(ValueError):f.reference(c,0,{'wrong-id':[0,0]})
        events=c['events']
        with self.assertRaises(ValueError):
            f.reference(c,0,{events[0]['id']:[.7e-6,.7e-6],events[1]['id']:[.4e-6,.4e-6]})

    def test_time_uncertainty_and_serialization_cannot_erase_phase_side(self):
        c=self.card('F20');root=c['wrap_times_s'][0]
        before=f.reference(c,root-2e-12,{})['outputs']['phase']
        after=f.reference(c,root+2e-12,{})['outputs']['phase']
        self.assertGreater(before[0],.99)
        self.assertLess(after[1],.01)

    def test_derivative_serialization_cell_includes_dc_and_right_limit(self):
        c=self.card('F14');ut=16*math.ulp(c['stop_s'])
        for t in (0,math.ulp(c['stop_s']),ut):
            interval=f.reference(c,t,{})['outputs']['y']
            self.assertLessEqual(interval[0],0)
            self.assertGreaterEqual(interval[1],.5)
        self.contains(f.reference(c,2*ut,{}),'y',.5)

    def test_callback_point_is_right_continuous_at_upper_bound(self):
        for group in ('F07','F19'):
            c=copy.deepcopy(self.card(group));c['reference_time_uncertainty_s']=0
            e=c['events'][0];hi=e['nominal_s']+e['late_s']
            bounds={ev['id']:[ev['nominal_s']-ev['early_s'],ev['nominal_s']+ev['late_s']] for ev in c['events']}
            out=f.reference(c,hi,bounds)
            self.contains(out,'count',1)
            self.contains(out,'y' if group=='F07' else 'state',13 if group=='F07' else .5)

    def calibration_trace(self, group, rise_s=.5e-6, fall_s=1e-6):
        c=self.card(group);unit=1e-6
        points={i*unit/32 for i in range(round(c['stop_s']/unit*32)+1)}
        for t in c['critical_times_s']:points.update((t-2e-12,t,t+2e-12))
        callbacks=[unit+50e-12,3*unit+50e-12]
        if group=='F19':
            for t in callbacks:points.update((t-1e-14,t+1e-14))
        rows=[]
        for t in sorted(t for t in points if 0<=t<=c['stop_s']):
            if group=='F20':
                phase=(.125+750000*t)%1
                rows.append({'time':t,'phase':phase,'y':math.sin(6.2831853071795862*phase)})
            else:
                n=sum(t>=e for e in callbacks)
                rise=min(1.,max(0.,(t-callbacks[0]-unit/4)/rise_s))
                fall=min(1.,max(0.,(t-callbacks[1]-unit/4)/fall_s))
                rows.append({'time':t,'y':.5*(rise-fall),'state':.5 if n==1 else 0.,'count':float(n)})
        return c,rows

    def test_correct_sine_cannot_hide_raw_phase_shift_through_grader(self):
        c,rows=self.calibration_trace('F20');contract=load_contract(cards=[c])
        correct=assess(c,rows,contract,reference=f.reference)
        self.assertLess(correct['outputs']['y']['error_upper_V'],1e-10)
        self.assertLess(correct['outputs']['phase']['error_lower_V'],1e-10)
        for row in rows:row['phase']+=1
        wrong=assess(c,rows,contract,reference=f.reference)
        self.assertLess(wrong['outputs']['y']['error_upper_V'],1e-10)
        self.assertGreater(wrong['outputs']['phase']['error_lower_V'],.99)
        self.assertTrue(all(q['status']=='numerical_error' for q in wrong['tiers'].values()))

    def test_transition_wrong_complete_rise_and_fall_fail_grader(self):
        c,rows=self.calibration_trace('F19');contract=load_contract(cards=[c])
        good=assess(c,rows,contract,reference=f.reference)
        self.assertTrue(all(q['status']=='pass' for q in good['tiers'].values()),good)
        for rise,fall in ((.4e-6,1e-6),(.5e-6,.5e-6)):
            _,bad=self.calibration_trace('F19',rise,fall)
            wrong=assess(c,bad,contract,reference=f.reference)
            self.assertEqual(wrong['behavior']['status'],'pass')
            self.assertGreater(wrong['outputs']['y']['error_lower_V'],.01)
            self.assertTrue(all(q['status']=='numerical_error' for q in wrong['tiers'].values()))

    def test_nonfinite_output_does_not_qualify(self):
        c,rows=self.calibration_trace('F19');rows[len(rows)//2]['y']=math.nan
        result=assess(c,rows,load_contract(cards=[c]),reference=f.reference)
        self.assertTrue(all(q['status']=='evidence_insufficient' for q in result['tiers'].values()))

    def test_all_function_corner_values_and_l1_input_amplification(self):
        c=self.card('F05')
        for t,val in [(.5e-6,0),(1.5e-6,.5),(2e-6,.75),(2.5e-6,.5),(3.5e-6,0)]:
            self.contains(f.reference(c,t,{}),'y',val)
        self.assertEqual(self.card('F01')['input_gain_bound'],5)
        self.assertEqual(self.card('F06')['input_gain_bound'],11)
        self.assertTrue(self.card('F14')['phase_obligations']['requires_actual_phase_evidence'])


    def test_stop_scaled_serialization_uncertainty_is_not_a_wrap_slope_patch(self):
        import math
        c=self.card('F20');root=c['wrap_times_s'][0]
        # One ULP away is inside the 16*ulp(stop) serialization cell.
        for t in (math.nextafter(root,-math.inf),math.nextafter(root,math.inf)):
            out=f.reference(c,t,{})
            self.assertGreater(out['outputs']['phase'][1]-out['outputs']['phase'][0],.9)
            self.assertFalse(out['undefined'])


    def test_verified_counter_stage_conditions_discrete_values_without_clipping_history(self):
        import copy
        c=copy.deepcopy(self.card('F07'));c['reference_counter_stages']={'count':1}
        e=c['events'][0];out=f.reference(c,e['nominal_s'],{})
        self.contains(out,'y',13)
        self.contains(out,'count',1)
        c=copy.deepcopy(self.card('F19'));c['reference_counter_stages']={'count':1}
        e=c['events'][0];out=f.reference(c,e['nominal_s'],{})
        self.contains(out,'state',.5)
        # Later edge value still includes the full legal event-time range.
        out=f.reference(c,1.5e-6,{})
        self.assertGreater(out['outputs']['y'][1]-out['outputs']['y'][0],.00019)
        c['reference_counter_stages']={'count':3}
        with self.assertRaises(ValueError):f.reference(c,0,{})

    def test_event_metadata_offsets_bind_to_source_nominal_times(self):
        for group in ('F07','F19'):
            c=self.card(group)
            for e in c['events']:
                self.assertEqual(e['late_s'],1e-10)
                self.assertEqual(e['early_s'],0 if e['kind']=='cross' else 1e-10)


    def test_mandatory_declaration_and_contribution_order_variants(self):
        for group,variant in [('F09','F09-reordered'),('F10','F10-reordered')]:
            base=self.card(group,group+'-base');other=self.card(group,variant)
            self.assertNotEqual(base['source'],other['source'])
            for t in (0,base['stop_s']/2,base['stop_s']):
                self.assertEqual(f.reference(base,t,{}),f.reference(other,t,{}))


    def test_derivative_undefined_points_match_shared_card_obligations(self):
        import math
        c=self.card('F14')
        self.assertEqual([p['time_s'] for p in c['undefined_points']],[1e-6,2e-6])
        # A nearby serialized row has uncertain sided values, not a fabricated
        # mathematically undefined point at a different physical time.
        out=f.reference(c,math.nextafter(1e-6,math.inf),{})
        self.assertFalse(out['undefined'])
        self.assertLessEqual(out['outputs']['y'][0],-1)
        self.assertGreaterEqual(out['outputs']['y'][1],.5)


    def test_derivative_requires_input_slope_evidence_but_constant_phase_does_not(self):
        derivative=self.card('F14')
        self.assertTrue(derivative['input_gain_evidence_required'])
        self.assertIn('maxnorm',derivative['input_gain_qualification_note'])
        phase=self.card('F20')
        self.assertEqual(phase['inputs'],{})
        self.assertFalse(phase.get('input_gain_evidence_required',False))
        for group in ('F03','F04'):
            self.assertTrue(self.card(group)['input_exact_evidence_required'])


if __name__ == '__main__':
    unittest.main()
