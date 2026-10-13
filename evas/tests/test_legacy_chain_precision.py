"""Positive/negative controls for the independent legacy-chain Q contract."""
GUARDS = ['QUALIFICATION', 'COMPOSE', 'TIMER', 'CROSS']
import copy
from decimal import localcontext
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'evas/validation/paper'),str(ROOT/'experiments/backends/support')]
import legacy_chain_precision as q
import legacy_chain_run as runner


def fixture(card):
    with localcontext() as ctx:
        ctx.prec=80
        records=[dict(label=label,index=i,time_s=t,sample_V=float(q.sample_reference(card,label,t,i)),time_bounds_s=[t,t],origin='synthetic calibration')
                 for label,times in q.callback_specs(card).items() for i,t in enumerate(times,1)]
        reference,polys=q.references(card,records)
        boundaries={0.,card['stop_s'],*[t for pts in card['inputs'].values() for t,v in pts],*[r['time_s'] for r in records],*[float(k[0]) for poly in polys.values() for k in poly.knots]}
        times=sorted(set(card['times'])|boundaries|{t+d for t in boundaries for d in [-.9*card['boundary_distance_s'],.9*card['boundary_distance_s']] if 0<=t+d<=card['stop_s']})
        rows=[dict(time=t,**{n:float(q.pwl(pts,t)) for n,pts in card['inputs'].items()},**{n:float(v) for n,v in reference(t).items()}) for t in times if 0<=t<=card['stop_s']]
        return rows,records


class LegacyChainPrecision(unittest.TestCase):
    def test_all_twelve_conditions_and_three_tiers_accept_independent_reference(self):
        for card in runner.cards():
            rows,records=fixture(card)
            for tier in q.TIERS:
                with self.subTest(case=card['id'],tier=tier):
                    self.assertEqual(q.assess(card,rows,records,tier)['status'],'pass')

    def test_dut_log_value_never_becomes_gold(self):
        card=next(c for c in runner.cards() if c['kind']=='c2');rows,records=fixture(card)
        records[0]['sample_V']+=1e-3
        self.assertEqual(q.assess(card,rows,records,'Q1')['status'],'numerical_error')

    def test_propagated_error_not_hidden_by_correct_sample(self):
        card=next(c for c in runner.cards() if c['kind']=='integral');rows,records=fixture(card)
        rows[-1]['i']+=2e-5
        self.assertEqual(q.assess(card,rows,records,'Q1')['status'],'numerical_error')

    def test_extra_error_tiers_are_fixed(self):
        card=next(c for c in runner.cards() if c['kind']=='integral');rows,records=fixture(card)
        rows[-1]['i']+=2e-6
        self.assertEqual(q.assess(card,rows,records,'Q1')['status'],'pass')
        self.assertEqual(q.assess(card,rows,records,'Q2')['status'],'numerical_error')

    def test_missing_duplicate_callback_or_time_box_is_insufficient(self):
        card=runner.cards()[0];rows,records=fixture(card)
        for broken in [records[:-1],records+[records[-1]], [dict(r,time_bounds_s=None) for r in records]]:
            self.assertEqual(q.assess(card,rows,broken,'Q1')['status'],'evidence_insufficient')

    def test_original_time_window_not_shrunk_by_q(self):
        card=next(c for c in runner.cards() if c['kind']=='integral');rows,records=fixture(card)
        records[0]['time_s']+=card['event_late_s']*2;records[0]['time_bounds_s']=[records[0]['time_s']]*2
        self.assertEqual(q.assess(card,rows,records,'Q1')['status'],'behavior_error')

    def test_complete_callback_box_not_nominal_point_controls_history_uncertainty(self):
        card=runner.cards()[0];rows,records=fixture(card)
        records[0]['time_bounds_s']=[records[0]['time_s']-1e-13,records[0]['time_s']+1e-13]
        result=q.assess(card,rows,records,'Q3')
        self.assertEqual(result['status'],'evidence_insufficient')
        self.assertEqual(result['reason'],'unresolved callback history influence exceeds tier bound')
        self.assertGreater(result['callback_history_uncertainty_V'],q.TIERS['Q3']/10)

    def test_small_nonpoint_callback_boxes_are_proved_at_native_rows(self):
        card=runner.cards()[0];rows,records=fixture(card)
        for record in records:
            record['time_bounds_s']=[record['time_s']-1e-18,record['time_s']+1e-18]
        result=q.assess(card,rows,records,'Q3')
        self.assertEqual(result['status'],'pass',result.get('reason'))
        self.assertEqual(result['history_enclosure']['status'],'proved_finite_intervals')

    def test_original_input_rule_and_q_input_budget_both_apply(self):
        card=runner.cards()[0];rows,records=fixture(card)
        rows[0]['u']+=2e-8
        self.assertEqual(q.assess(card,rows,records,'Q1')['status'],'input_mismatch')

    def test_interrupt_polygon_differs_from_independent_ramp_superposition(self):
        with localcontext() as ctx:
            ctx.prec=80
            polygon=q.Polygon(0,[(1.,1.),(1.5,2.)],0,1.,1.,4.)
            self.assertAlmostEqual(float(polygon.value(1.75)),1.)
            self.assertNotAlmostEqual(float(polygon.value(2.1)),1.+.6)
            # A reversal starts from the former destination, giving a distinct slope.
            reverse=q.Polygon(0,[(1.,1.),(1.5,0.)],0,1.,1.,4.)
            self.assertAlmostEqual(float(reverse.value(1.75)),.25)

    def test_bit_equality_requires_complete_scientific_time_set(self):
        rows=[dict(time=0.,y=1.),dict(time=1.,y=2.)]
        self.assertEqual(q.scientific_identity(rows,copy.deepcopy(rows),['y'])['status'],'identical_complete_scientific_waveform')
        self.assertEqual(q.scientific_identity(rows,rows[:1],['y'])['status'],'common_points_identical')
        changed=copy.deepcopy(rows);changed[0]['y']+=1e-15
        self.assertEqual(q.scientific_identity(rows,changed,['y'])['status'],'different')

    def test_trace_only_adds_strobes_and_retains_no_counter_c2(self):
        for card in runner.cards():
            trace=q.trace_source(card)
            self.assertIn('$strobe(',trace)
            self.assertEqual(trace.count('integer'),card['source'].count('integer'))
        records=q.parse_trace('LEGACY_Q sample 0 1.5e-6 .22\nLEGACY_Q sample 0 2.5e-6 .44')
        self.assertEqual([r['index'] for r in records],[1,2])
        self.assertLess(records[0]['time_bounds_s'][0],records[0]['time_s'])

    def test_evas_committed_state_read_and_full_time_box_preserved(self):
        card=runner.cards()[0]
        response={'transient':{'state_names':['dut/a:q','dut/a:count'], 'events':[{'time':1e-6,'before':[.25,0],'after':[.75,1],'event':0,'observation_time_bounds':[1e-6,1e-6+1e-15]}]}}
        records=q.evas_callbacks(card,response)
        self.assertEqual(records[0]['sample_V'],.75)
        self.assertEqual(records[0]['time_bounds_s'],[1e-6,1e-6+1e-15])

    def test_hand_calculated_anchors_do_not_call_reference_generator(self):
        import math
        with localcontext() as ctx:
            ctx.prec=80
            # Unit ramp filtered by tau=1: y(1)=exp(-1).
            self.assertAlmostEqual(float(q.filtered_pwl([[0.,0.],[1.,1.],[2.,1.]],1.,1.)),math.exp(-1),places=15)
            # DC one until t=1, then DC three until t=2, plus offset 0.5.
            self.assertEqual(float(q.rectangles(2.,1.,[(1.,3.)],offset=.5)),4.5)
            # First-order response after ramp ends at t=1.
            expected=1-(1-math.exp(-1))*math.exp(-1)
            self.assertAlmostEqual(float(q.filtered_pwl([[0.,0.],[1.,1.],[2.,1.]],2.,1.)),expected,places=15)
            poly=q.Polygon(0,[(1.,1.),(1.5,2.)],0,1.,1.,4.)
            self.assertAlmostEqual(float(poly.value(2.1)),1.7,places=15)
            self.assertAlmostEqual(float(poly.filtered(1.5,1.)),.5-1+math.exp(-.5),places=15)

    def test_duplicate_native_time_is_protocol_failure(self):
        card=runner.cards()[0];rows,records=fixture(card);rows.insert(1,dict(rows[0]))
        verdict=q.assess(card,rows,records,'Q1')
        self.assertEqual(verdict['status'],'evidence_insufficient')
        self.assertEqual(verdict['failure_owner'],'protocol_fail')

    def test_c2_frozen_one_ns_condition_restores_original_40ps(self):
        card=next(c for c in runner.cards() if c['kind']=='c2')
        rows,records=fixture(card);card={**card,'event_late_s':1e-9}
        records[0]['time_s']+=5e-10;records[0]['time_bounds_s']=[records[0]['time_s']]*2
        verdict=q.assess(card,rows,records,'Q1')
        self.assertEqual(verdict['status'],'behavior_error')
        self.assertEqual(verdict['contract_delta'][0]['analysis'],4e-11)
        self.assertEqual(verdict['analysis_identity'],'legacy-chain-Q-v2')

    def test_nt_original_tt_does_not_admit_early_state(self):
        card=next(c for c in runner.cards() if c['id']=='NT:fixed')
        rows,records=fixture(card);t=.1-5e-7
        rows.append(dict(time=t,u=0.,y=10.));rows.sort(key=lambda r:r['time'])
        verdict=q.assess(card,rows,records,'Q1')
        self.assertEqual(verdict['status'],'numerical_error')
        self.assertGreater(verdict['error_lower_V'],q.TIERS['Q1'])

    def test_nt_same_time_common_prefix_retains_recorded_order(self):
        card=next(c for c in runner.cards() if c['id']=='NT:fixed')
        rows,records=fixture(card)
        for c in records:
            if c['label']=='b' and c['index']==2:c['time_s']=.3;c['time_bounds_s']=[.3,.3]
        # Actual order b2 then a. Intermediate y=20 is legal; y=11 is not.
        records.sort(key=lambda c:(c['time_s'],0 if c['label']=='b' else 1))
        rows=[r for r in rows if r['time']!=.3]+[dict(time=.3,u=0.,y=20.)];rows.sort(key=lambda r:r['time'])
        self.assertEqual(q.assess(card,rows,records,'Q1')['status'],'pass')
        next(r for r in rows if r['time']==.3)['y']=11.
        self.assertEqual(q.assess(card,rows,records,'Q1')['status'],'numerical_error')

    def test_nt_serialization_neighborhood_cannot_reverse_common_prefix(self):
        import math
        card=next(c for c in runner.cards() if c['id']=='NT:fixed')
        rows,records=fixture(card)
        next(r for r in rows if r['time']==.1)['y']=0.
        rows.append(dict(time=math.nextafter(.1,-math.inf),u=0.,y=10.));rows.sort(key=lambda r:r['time'])
        self.assertEqual(q.assess(card,rows,records,'Q1')['status'],'numerical_error')

    def test_integral_bound_has_checkable_area_derivation(self):
        card=next(c for c in runner.cards() if c['kind']=='integral');rows,records=fixture(card)
        records[0]['time_bounds_s']=[records[0]['time_s']-1e-15,records[0]['time_s']+1e-15]
        with localcontext() as ctx:
            ctx.prec=80
            bound,proof=q.history_bound(card,records)
        self.assertGreater(bound,0);self.assertEqual(proof['status'],'proved_integral_rectangles')
        self.assertAlmostEqual(float(bound),sum(t['timing_integral_bound_V']+t['sample_propagation_bound_V'] for t in proof['terms']),places=18)

    def test_nt_original_ground_binding_and_calibrated_transres_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'inputs';plan=runner.freeze(output,['NT:chain'],['Q1'])
            e=next(r for r in plan if r['backend']=='evas');s=next(r for r in plan if r['backend']=='spectre')
            request=runner.load(output/e['work']/'request.json')
            self.assertEqual(request['instances'][0]['ports']['r'],'0')
            self.assertEqual(set(request['inputs']),{'u'})
            deck=(output/s['work']/'tb.scs').read_text()
            self.assertIn('dut (u y 0)',deck);self.assertNotIn('Vr ',deck)
            self.assertIn('transres=1e-20',deck)
            self.assertEqual(s['physical_variant'],'original-ground-binding-v2')

    def test_threshold_straddle_is_inconclusive_instead_of_false_failure(self):
        card=next(c for c in runner.cards() if c['kind']=='integral');rows,records=fixture(card)
        rows[-1]['i']+=q.TIERS['Q2']
        verdict=q.assess(card,rows,records,'Q2')
        self.assertEqual(verdict['status'],'evidence_insufficient')
        self.assertLessEqual(verdict['error_lower_V'],q.TIERS['Q2'])
        self.assertGreater(verdict['error_upper_V'],q.TIERS['Q2'])

    def test_final_qualification_uses_unnormalized_scientific_rows(self):
        from unittest.mock import patch
        import precision_report
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'inputs';plan=runner.freeze(output,['NT:chain'],['Q1'],['original'])
            record=next(r for r in plan if r['backend']=='evas');work=output/record['work']
            (work/'waveform.csv').write_text('synthetic wiring control')
            runner.save(work/'raw-response.json',{})
            raw=[{'time':0.,'u':0.,'y':0.,**{'dut:'+n:0. for n in 'hefi'}}]
            observed=[]
            def gate(work,backend,receipt,rows,**kwargs):
                observed.append(rows)
                return dict(status='evidence_insufficient',issues=['invalid observation provenance'])
            with patch.object(runner,'read_native',return_value=raw), patch.object(q,'evas_callbacks',return_value=[]), patch.object(q,'assess',return_value=dict(status='pass')), patch.object(runner.execution,'effective_settings',return_value=dict(actual={'stop':1.})), patch.object(precision_report,'qualification',side_effect=gate):
                result=runner.analyze_work(work,dict(record,waveform='waveform.csv'),dict(kernel_sha256='synthetic'),persist=False)
            self.assertEqual(observed,[raw])
            self.assertNotIn('h',observed[0][0])
            self.assertEqual(result['Q_qualification']['status'],'evidence_insufficient')

    def test_actual_source_build_kernel_chain_rejects_mismatch(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            snapshot=Path(tmp)/'snapshot';snapshot.mkdir();work=snapshot/'work';work.mkdir()
            names=['evas/rust_core/Cargo.lock','evas/rust_core/src/lib.rs','evas/src/evas/__init__.py',
                   'experiments/backends/support/precision_run.py']
            for name in names:
                p=snapshot/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(name)
            all_sources={n:runner.sha(snapshot/n) for n in names}
            sources={n:h for n,h in all_sources.items() if n!=names[-1]}
            # Historic wide manifests may include bench/fuzz and old Python.
            historical={**sources,'evas/src/evas/__init__.py':'old-python',
                        'evas/rust_core/fuzz/fuzz_targets/run.rs':'not-a-normal-kernel-input'}
            runner.save(snapshot.parent/'BUILD_SOURCE_MANIFEST.json',historical)
            build=dict(returncode=0,source_manifest_sha256=runner.sha(snapshot.parent/'BUILD_SOURCE_MANIFEST.json'),
                       kernel_sha256='kernel',cargo_lock_sha256=sources[names[0]],
                       stage=dict(status='completed',returncode=0,timeout=False,cleanup=dict(complete=True)),
                       compiler_identity={n:dict(actual_binary_sha256=n+'-binary') for n in ('cargo','rustc')})
            runner.save(snapshot.parent/'BUILD.json',build)
            provenance=dict(production_source_sha256=historical,kernel_sha256='kernel',
                            previous_build_record_sha256=runner.sha(snapshot.parent/'BUILD.json'))
            binding=dict(production_sources=sources,source_identity=all_sources,provenance=provenance)
            runner.save(work/'SOURCE_BINDING.json',binding)
            record=dict(source_binding_sha256=runner.sha(work/'SOURCE_BINDING.json'))
            with patch.object(runner,'production_dependencies',return_value=sources):
                def gate(kernel='kernel'):
                    return runner.build_identity(work,record,dict(kernel_sha256=kernel),producer_repo=snapshot)
                # BUILD's Python can differ: current runtime is independently bound.
                self.assertTrue(gate()['verified'],gate()['issues'])
                self.assertFalse(gate('other')['verified'])
                for name in ('evas/src/evas/__init__.py','experiments/backends/support/precision_run.py'):
                    original=(snapshot/name).read_text();(snapshot/name).write_text('changed')
                    self.assertFalse(gate()['verified']);(snapshot/name).write_text(original)
                for changed in [{**sources,names[1]:'changed'},
                                {k:v for k,v in sources.items() if k!=names[1]},
                                {**sources,'evas/rust_core/src/new.rs':'unbuilt'},
                                {**sources,names[0]:'changed-cargo'}]:
                    with patch.object(runner,'production_dependencies',return_value=changed):
                        self.assertFalse(gate()['verified'])
                broken={**build,'stage':dict(status='failed',returncode=1,timeout=False,cleanup=dict(complete=True))}
                (snapshot.parent/'BUILD.json').unlink()
                runner.save(snapshot.parent/'BUILD.json',broken)
                self.assertIn('BUILD did not complete successfully',gate()['issues'])
                (snapshot.parent/'BUILD.json').unlink()
                self.assertFalse(gate()['verified'])

    def test_failure_owner_does_not_label_pass_or_numeric_error_protocol_fail(self):
        card=next(c for c in runner.cards() if c['kind']=='integral');rows,records=fixture(card)
        self.assertEqual(q.assess(card,rows,records,'Q1')['failure_owner'],'none')
        rows[-1]['i']+=2e-5
        self.assertEqual(q.assess(card,rows,records,'Q1')['failure_owner'],'numerical_error')

    def test_timer_serialization_preserves_root_boxes_and_cross_requires_box(self):
        card=next(c for c in runner.cards() if c['kind']=='c2')
        event=dict(time=1.5e-6,kind='timer',before=[.1],after=[.2])
        response=dict(transient=dict(state_names=['dut/sampler:held'],events=[event]))
        result=q.evas_callbacks(card,response)[0]
        self.assertLess(result['time_bounds_s'][0],event['time'])
        box=[event['time']-1e-12,event['time']+1e-12]
        event['observation_time_bounds']=box
        self.assertEqual(q.evas_callbacks(card,response)[0]['time_bounds_s'],box)
        del event['observation_time_bounds'];event['kind']='cross'
        self.assertIsNone(q.evas_callbacks(card,response)[0]['time_bounds_s'])

    def test_freeze_binds_only_actual_dependencies_and_preserves_trace_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'inputs'
            plan=runner.freeze(output,['STROBE-TIMER-IDT'],['Q1'])
            self.assertEqual(len(plan),3);runner.verify(output)
            sources=runner.load(output/'SOURCE_IDENTITY.json')
            self.assertNotIn('evas/validation/paper/precision_breadth.py',sources)
            original=next(r for r in plan if r['variant']=='original' and r['backend']=='spectre');trace=next(r for r in plan if r['variant']=='trace')
            self.assertEqual(original['original_source_sha256'],trace['original_source_sha256'])
            self.assertNotEqual(original['executed_source_sha256'],trace['executed_source_sha256'])
            self.assertEqual(original['deck_sha256'],trace['deck_sha256'])
            (output/'extra').write_text('drift')
            with self.assertRaisesRegex(ValueError,'file set drift'):runner.verify(output)

    def test_spectre_settings_conflict_is_rejected_before_execution(self):
        text='simulatorOptions options digits=17 notation=sci precision="%.17g"\ntran tran transres=1e-20 errpreset=conservative method=traponly\n'
        runner.validate_spectre_controls(text)
        for broken in [text.replace('digits=17','digits=6'),
                       text.replace('method=traponly','method=gear2only'),
                       text.replace('transres=1e-20','transres=1e-20 transres=1e-3')]:
            with self.assertRaisesRegex(ValueError,'inconsistent frozen Spectre control'):
                runner.validate_spectre_controls(broken)

    def test_bad_record_does_not_hide_remaining_reanalysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane=Path(tmp)/'lane';lane.mkdir()
            runner.save(lane/'FILE_MANIFEST.json',{})
            runner.save(lane/'EXECUTION.json',[
                dict(status='waveform_available',label='missing-condition'),
                dict(status='not_run',label='remaining')])
            output=Path(tmp)/'analysis.json';runner.analyze([lane],output)
            records=runner.load(output)['records']
            self.assertEqual(len(records),2)
            self.assertEqual(records[0]['Q_qualification']['status'],'evidence_insufficient')
            self.assertEqual(records[1]['status'],'not_run')

    def test_pending_reference_never_claims_proved_history(self):
        from unittest.mock import patch
        card=runner.cards()[0];rows,records=fixture(card)
        pending=lambda time:dict(status='pending',reason='independent control',outputs={},reference_error_V=0)
        with patch.object(q.interval_math,'prepare',return_value=pending):
            result=q.assess(card,rows,records,'Q1')
        self.assertEqual(result['status'],'evidence_insufficient')
        self.assertEqual(result['history_enclosure']['status'],'pending')

    def test_unproved_monotone_phase_never_falls_back_to_gold(self):
        card=next(c for c in runner.cards() if c['kind']=='nt');rows,records=fixture(card)
        with self.assertRaisesRegex(q.interval_math.BoundsPending,'no monotone callback prefix'):
            q.nt_phase_reference(rows[0],{'y':q.dec(0)},records,len(records),{'y'},0.)
        from unittest.mock import patch
        with patch.object(q,'nt_phase_reference',side_effect=q.interval_math.BoundsPending('independent phase control')):
            result=q.assess(card,rows,records,'Q1')
        self.assertEqual(result['status'],'evidence_insufficient')
        self.assertEqual(result['history_enclosure']['status'],'pending')
        self.assertIn('callback phase enclosure pending',result['reason'])


if __name__=='__main__':unittest.main()
