"""Synthetic calibration controls, never backend execution records."""
import math
import unittest
import hashlib
from pathlib import Path
from criteria import assess as raw_assess

Q = {'time_unit': 's', 'voltage_unit': 'V', 'time_error_s': 1e-11,
     'voltage_error_V': 5e-5, 'input_error_V': 1e-5,
     'qualified': True, 'native_counters': True, 'native_phase': True, 'source_validated': True,
     'input_bounds_qualified': True, 'native_initial': True,
     'qualification_evidence': {role: {'method':'Independent analytical calibration control', 'artifact_path':str(Path(__file__).resolve()), 'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()} for role in ('source','time','voltage','inputs','native_initial','native_counters','native_phase')}}


CENTERS={'EV-SH-01':[2,4,6,8], 'EV-HC-01':[1.375,3.375],
         'EV-HC-02':[2.75,5.375], 'TM-01':[2,6], 'SI-01':[2,3,4,6],
         'CO-SH-01':[2,3,4,6,8], 'CO-HC-01':[1.375,3.375],
         'CP-02':[7/6,2.5,23/6,31/6],
         'CO-VCO-01':[2+(-.4+math.sqrt(.555))/.5,3.755,4.755,6+(.4-math.sqrt(.1025))/.25]}


def cohort_qualification(name, rows, q=Q):
    evidence=dict(q.get('qualification_evidence',{}))
    evidence['boundary_cohort']=Q['qualification_evidence']['time']
    records=[]
    for j,x in enumerate(CENTERS.get(name,[])):
        matches=[i for i,r in enumerate(rows) if r.get('time_s') is not None and abs(r['time_s']-x*1e-6)<=1e-18]
        if matches:records.append({'nominal_time_s':x*1e-6,'row_index':matches[0],'request_id':'independent-center-'+str(j)})
    return dict(q, qualification_evidence=evidence,
                boundary_cohort={'serialization_error_s':1e-18,'records':records})


def assess(name, rows, q, execution_state='completed'):
    return raw_assess(name, rows, cohort_qualification(name, rows, q), execution_state)


def rows_for(name, event_shift=0):
    """Independent hand formulas for the conditions, not runtime oracle imports."""
    stops = {'VR-01':6, 'EX-01':8, 'EV-SH-01':9, 'EV-HC-01':4,
             'EV-HC-02':6, 'TM-01':8, 'CP-01':6, 'CP-02':6,
             'SI-01':7, 'CO-SH-01':9, 'CO-HC-01':4, 'CO-VCO-01':8}
    events = {'EV-SH-01':[2,4,6,8], 'EV-HC-01':[1.375,3.375],
              'EV-HC-02':[2.75,5.375], 'TM-01':[2,6], 'SI-01':[2,3,4,6],
              'CO-SH-01':[2,3,4,6,8], 'CO-HC-01':[1.375,3.375],
              'CP-02':[7/6,2.5,23/6,31/6],
              'CO-VCO-01':[2+(-.4+math.sqrt(.555))/.5,3.755,4.755,6+(.4-math.sqrt(.1025))/.25]}
    def interp(points,x):
        for (a,va),(b,vb) in zip(points,points[1:]):
            if a<=x<=b:
                return va+(vb-va)*(x-a)/(b-a)
        raise ValueError(x)
    def clip(x):return min(1,max(0,x))
    ts={i*.0002 for i in range(round(stops[name]/.0002)+1)}
    for e in events.get(name,[]):
        ts.update(e+i*.00002 for i in range(-100,101))
    out=[]
    for x in sorted({round(t,12) for t in ts}):
        z={'time_s':x*1e-6}
        if name=='VR-01':
            z.update(ref=interp([(0,.2),(2,.4),(4,-.1),(6,.3)],x),ip=interp([(0,.6),(2,.8),(4,.8),(6,.1)],x),im=interp([(0,.2),(2,.2),(4,.5),(6,.3)],x))
            z['out']=z['ref']+1.5*(z['ip']-z['im'])-.125
        elif name in ('EX-01','CO-VCO-01'):
            u=interp([(0,-1),(2,0),(4,2),(6,0),(8,-1)],x)
            z.update(ctl=u,freq=min(1,max(.2,.4+.5*u)))
            if name=='CO-VCO-01':
                breaks=[0,1.2,2,3.2,4,4.8,6,6.8,8]; starts=[.125,.365,.605,1.445,2.245,3.045,3.885,4.125]; rates=[.2,.2,.4,1,1,1,.4,.2]; slopes=[0,.25,.5,0,0,-.5,-.25,0]
                j=next(i for i in range(8) if breaks[i]<=x<=breaks[i+1]); d=x-breaks[j]; p=starts[j]+rates[j]*d+slopes[j]*d*d/2
                z.update(phase=p%1,out=math.sin(2*math.pi*p))
        elif name in ('EV-HC-01','EV-HC-02','CO-HC-01'):
            high_start=name=='EV-HC-02'
            z['in']=interp([(0,.9),(2,.5),(4,.1),(6,.9)] if high_start else [(0,.1),(2,.9),(4,.1)],x)
            ev=events[name]; n=sum(x>=e+event_shift for e in ev); q=(1-n%2) if high_start else n%2
            z.update(count=n,out=.1+.8*q)
            if name=='CO-HC-01':
                z.update(state=q,out=.1+.8*(clip((x-ev[0]-event_shift-.125)/.25)-clip((x-ev[1]-event_shift-.125)/.5)))
        elif name=='EV-SH-01':
            z['in']=interp([(0,-.4),(6,.8),(9,-.1)],x); ev=[e+event_shift for e in events[name]]; n=sum(x>=e for e in ev)
            q=-.25 if n==0 else interp([(0,-.4),(6,.8),(9,-.1)],ev[n-1]); z.update(count=n,out=q)
        elif name=='TM-01':
            n=sum(x>=e+event_shift for e in events[name]);z.update(count=n,state=n%2,out=clip((x-2-event_shift-.25)/.5)-clip(x-6-event_shift-.25))
        elif name=='CP-01':
            ctl=.3 if x<=2 else .3+.3*(x-2) if x<=4 else .9
            p=.125+.3*x if x<=2 else .725+.3*(x-2)+.15*(x-2)**2 if x<=4 else 1.925+.9*(x-4)
            z.update(ctl=ctl,phase=p)
        elif name=='CP-02':
            p=.125+.75*x;z.update(phase=p%1,out=math.sin(2*math.pi*p))
        elif name=='SI-01':
            na=sum(x>=e+event_shift for e in (2,4,6));nb=sum(x>=e+event_shift for e in (3,6))
            z.update(a=.1*x,b=1-.1*x,na=na,nb=nb,oa=-.25 if na==0 else .1*((2,4,6)[na-1]+event_shift),ob=.75 if nb==0 else 1-.1*((3,6)[nb-1]+event_shift))
        elif name=='CO-SH-01':
            clock=[(0,0),(1.8,0),(2.2,1),(2.5,1),(2.9,0),(3.8,0),(4.2,1),(4.5,1),(4.9,0),(5.8,0),(6.2,1),(6.5,1),(6.9,0),(7.8,0),(8.2,1),(8.5,1),(8.9,0),(9,0)]
            z.update(**{'in':-.4+.2*x,'clk':interp(clock,x),'reset':interp([(0,0),(2.8,0),(3.2,1),(4.8,1),(5.2,0),(9,0)],x)})
            ev=[e+event_shift for e in events[name]]; n=sum(x>=e for e in ev); levels=[-.25,.2*event_shift,-.25,-.25,.8+.2*event_shift,1.2+.2*event_shift]
            y=levels[0]
            for j,e in enumerate(ev): y+=(levels[j+1]-levels[j])*clip((x-e)/.1)
            z.update(count=n,state=levels[n],out=y)
        out.append(z)
    return out


class Calibration(unittest.TestCase):
    def test_legal_all_conditions(self):
        for name in ('VR-01','EX-01','EV-SH-01','EV-HC-01','EV-HC-02','TM-01','CP-01','CP-02','SI-01','CO-SH-01','CO-HC-01','CO-VCO-01'):
            with self.subTest(case=name): self.assertEqual(assess(name,rows_for(name),Q)['status'],'P')

    def test_legal_common_event_shifts(self):
        for name, shift in [('EV-SH-01',-.0005),('EV-SH-01',.0005),('EV-HC-01',.00025),('EV-HC-02',.0005),('TM-01',-.0005),('TM-01',.0005),('SI-01',-.0005),('SI-01',.0005),('CO-SH-01',.00004),('CO-HC-01',.00025)]:
            with self.subTest(case=name,shift=shift): self.assertEqual(assess(name,rows_for(name,shift),Q)['status'],'P')

    def test_distinct_voltage_and_history_faults(self):
        for name,port,change in [('VR-01','out',.2),('EX-01','freq',.1),('EV-SH-01','out',.05),('EV-HC-01','out',.8),('EV-HC-02','out',-.8),('TM-01','out',.15),('CP-01','phase',-.125),('CP-02','phase',.1),('SI-01','ob',.2),('CO-SH-01','state',.25),('CO-HC-01','out',.1),('CO-VCO-01','phase',.1)]:
            rows=rows_for(name)
            for row in rows:row[port]+=change
            with self.subTest(case=name): self.assertEqual(assess(name,rows,Q)['status'],'F')

    def test_nominal_event_rows_preserve_shared_history(self):
        for shift in (-.0005,.0005):
            result=assess('EV-SH-01',rows_for('EV-SH-01',shift),Q)
            self.assertEqual(result['status'],'P')
            self.assertEqual(len(result['event_boundary_observations']),4)
            relation='post-event' if shift<0 else 'pre-event'
            self.assertTrue(all(r['relation']==relation for r in result['event_boundary_observations']))

    def test_duplicate_count(self):
        rows=rows_for('EV-HC-01')
        for r in rows:
            if r['count']>=1:r['count']+=1
        self.assertEqual(assess('EV-HC-01',rows,Q)['status'],'F')

    def test_missing_units_columns_and_unqualified_counter(self):
        self.assertEqual(assess('EV-SH-01',rows_for('EV-SH-01'),dict(Q,native_counters=False))['status'],'I')
        self.assertEqual(assess('CP-01',rows_for('CP-01'),dict(Q,time_unit='ns'))['status'],'I')
        self.assertEqual(assess('EV-HC-02',rows_for('EV-HC-02'),dict(Q,native_initial=False))['status'],'I')
        rows=rows_for('VR-01'); del rows[10]['out']
        self.assertEqual(assess('VR-01',rows,Q)['status'],'I')

    def test_observation_uncertainty_and_sparse_records(self):
        self.assertEqual(assess('CP-01',rows_for('CP-01'),dict(Q,voltage_error_V=.002))['status'],'I')
        self.assertEqual(assess('EV-HC-01',rows_for('EV-HC-01')[::10],Q)['status'],'I')

    def test_malformed_records_are_undecided(self):
        rows=rows_for('VR-01')
        variants=[rows[:-1],[rows[0],rows[2],rows[1]]+rows[3:],
                  [dict(r,out=float('nan')) if i==10 else r for i,r in enumerate(rows)]]
        for trace in variants:self.assertEqual(assess('VR-01',trace,Q)['status'],'I')
        self.assertEqual(assess('VR-01',rows,dict(Q,time_error_s='unknown'))['status'],'I')

    def test_counter_uncertainty_overlap_is_undecided(self):
        rows=rows_for('EV-HC-01')
        for r in rows:r['count']+=.001
        self.assertEqual(assess('EV-HC-01',rows,Q)['status'],'I')

    def test_execution_states_are_separate(self):
        for state in ('T','U','X'):
            answer=assess('CP-01',[],{},execution_state=state)
            self.assertEqual(answer['status'],state); self.assertFalse(answer['properties'])

    def test_incoherent_history_not_envelope_pass(self):
        rows=rows_for('TM-01',.0009)
        for row in rows:
            x=row['time_s']/1e-6
            if 2.25<x<2.75: row['out']=min(1,max(0,(x-2+.0009-.25)/.5))
        self.assertNotEqual(assess('TM-01',rows,Q)['status'],'P')

    def test_named_engineering_fault_controls(self):
        controls = [
            ('VR-01','single_ended'),('VR-01','reference_missing'),
            ('EX-01','clamp_missing'),('EX-01','startup_only'),
            ('EV-SH-01','tracks_input'),('EV-SH-01','late_timer'),
            ('EV-HC-01','no_hysteresis'),('EV-HC-02','initial_low'),
            ('TM-01','instant_edge'),('TM-01','equal_edges'),
            ('CP-01','frequency_times_t'),('CP-02','phase_clamp'),
            ('CP-02','missing_2pi'),('SI-01','shared_slot'),
            ('CO-SH-01','sample_during_reset'),('CO-HC-01','delay_missing'),
            ('CO-VCO-01','unclamped_phase'),('CO-VCO-01','phase_restart'),('CO-VCO-01','missing_2pi')]
        for name,fault in controls:
            rows=rows_for(name,.002 if fault=='late_timer' else 0)
            for r in rows:
                x=r['time_s']/1e-6
                if fault=='single_ended':r['out']=r['ref']+1.5*r['ip']-.125
                elif fault=='reference_missing':r['out']-=r['ref']
                elif fault=='clamp_missing':r['freq']=.4+.5*r['ctl']
                elif fault=='startup_only':r['freq']=.2
                elif fault=='tracks_input':r['out']=r['in']
                elif fault=='no_hysteresis':r['out']=.9 if r['in']>.5 else .1
                elif fault=='initial_low' and x<2.75:r['out']=.1
                elif fault=='instant_edge':r['out']=r['state']
                elif fault=='equal_edges' and 6.25<x<7.25:r['out']=max(0,1-(x-6.25)/.5)
                elif fault=='frequency_times_t':r['phase']=.125+r['ctl']*x
                elif fault=='phase_clamp':r['phase']=min(1,.125+.75*x)
                elif fault=='missing_2pi':r['out']=math.sin(r['phase'])
                elif fault=='shared_slot':r['ob']=r['oa']
                elif fault=='sample_during_reset' and 4.1<x<6:r['state']=.4;r['out']=.4
                elif fault=='delay_missing':r['out']=.1+.8*(min(1,max(0,(x-1.375)/.25))-min(1,max(0,(x-3.375)/.5)))
                elif fault=='unclamped_phase' and x<1.2:r['phase']=(.125-.1*x+.125*x*x)%1
                elif fault=='phase_restart' and x>4:r['phase']=(r['phase']-.245)%1
            with self.subTest(case=name,fault=fault):self.assertEqual(assess(name,rows,Q)['status'],'F')

    def test_budget_overlap_is_undecided(self):
        rows=rows_for('VR-01')
        for r in rows:r['out']+=.001
        self.assertEqual(assess('VR-01',rows,Q)['status'],'I')

    def test_no_evidence_boolean_does_not_qualify(self):
        self.assertEqual(assess('CP-01',rows_for('CP-01'),dict(Q,qualification_evidence={}))['status'],'I')

    def test_exact_boundary_diagnostic_is_retained(self):
        a=assess('CP-02',rows_for('CP-02'),Q)
        self.assertEqual(a['status'],'P')
        self.assertEqual(a['endpoint_semantics_status'],'I')
        self.assertEqual(len(a['exact_boundary_observations']),4)
        self.assertIn('phase_absolute_outside_wrap_windows',a['required_properties'])

    def test_short_pulse_observation_limit_is_explicit(self):
        answer=assess('CP-01',rows_for('CP-01'),Q)
        self.assertEqual(answer['status'],'P')
        self.assertIn('unobserved',answer['claim_limit'])
        rows=rows_for('CP-01')
        left,right=rows[10]['time_s'],rows[11]['time_s']
        center=(left+right)/2
        # A continuous triangular pulse between two records is exactly zero at
        # every saved record. Its absence cannot be established by this checker.
        def pulse(t):return max(0,1-abs(t-center)/((right-left)/4))
        self.assertEqual(pulse(center),1)
        altered=[dict(r,phase=r['phase']+.1*pulse(r['time_s'])) for r in rows]
        self.assertEqual(altered,rows)
        self.assertEqual(assess('CP-01',altered,Q)['status'],'P')

    def test_two_backends_same_wrong_answer_fail_independently(self):
        rows=rows_for('CP-01')
        for r in rows:r['phase']-=.125
        first=assess('CP-01',rows,Q)
        second=assess('CP-01',[dict(r) for r in rows],Q)
        self.assertEqual((first['status'],second['status']),('F','F'))

    def test_observation_envelope_bridge(self):
        from criteria import assess_observation
        rows=rows_for('CP-01')
        native=[dict({k:v for k,v in r.items() if k!='time_s'},time=r['time_s']) for r in rows]
        envelope={'condition':'CP-01','rows':native,'qualification':Q,
                  'metadata':{'sample_origins':['accepted']*len(rows)}}
        self.assertEqual(assess_observation(envelope)['status'],'P')
        del native[5]['time']
        self.assertEqual(assess_observation(envelope)['status'],'I')

    def test_row_paired_error_bounds_do_not_hide_failure(self):
        rows=rows_for('CP-01')
        for r in rows:r['phase']+=.0011 if r['time_s']<=2e-6 else .001005
        answer=assess('CP-01',rows,Q)
        self.assertEqual(answer['status'],'F')
        phase=next(p for p in answer['properties'] if p['name']=='voltage:phase')
        self.assertGreater(phase['max_error_lower_bound'],.001)

    def test_invalid_saved_input_is_observation_not_dut_failure(self):
        rows=rows_for('VR-01')
        for r in rows:r['ip']+=.0002
        answer=assess('VR-01',rows,Q)
        self.assertEqual(answer['status'],'I')
        p=next(p for p in answer['properties'] if p['name']=='input_consistency:ip')
        self.assertEqual(p['status'],'I');self.assertGreater(p['max_observed_error'],.0001)
        self.assertFalse(any(p['name'].startswith('voltage:') for p in answer['properties']))

    def test_boundary_cohort_missing_cannot_use_nearest_grid(self):
        rows=rows_for('CP-02')
        rows=[r for r in rows if abs(r['time_s']-2.5e-6)>1e-18]
        for x in (2.5-.000005,2.5+.000005):
            p=.125+.75*x;rows.append({'time_s':x*1e-6,'phase':p%1,'out':math.sin(2*math.pi*p)})
        rows.sort(key=lambda r:r['time_s'])
        answer=assess('CP-02',rows,Q)
        self.assertEqual(answer['status'],'I')
        self.assertFalse(any(r.get('raw_phase') is not None and r['nominal_T']==2.5 for r in answer.get('exact_boundary_observations',[])))

    def test_boundary_serialization_requires_bound_and_provenance(self):
        rows=rows_for('CP-02')
        x=2.49999;p=.125+.75*x
        rows.append({'time_s':x*1e-6,'phase':p%1,'out':math.sin(2*math.pi*p)})
        rows.sort(key=lambda r:r['time_s']);q=cohort_qualification('CP-02',rows)
        record=q['boundary_cohort']['records'][1];i=record['row_index']
        rows[i]=dict(rows[i],time_s=rows[i]['time_s']+1e-15)
        q['boundary_cohort']['serialization_error_s']=2e-15
        self.assertEqual(raw_assess('CP-02',rows,q)['status'],'P')
        q['boundary_cohort']['serialization_error_s']=1e-18
        self.assertEqual(raw_assess('CP-02',rows,q)['status'],'I')
        q=cohort_qualification('CP-02',rows);q['qualification_evidence'].pop('boundary_cohort')
        self.assertEqual(raw_assess('CP-02',rows,q)['status'],'I')

    def test_cross_limits_derive_from_source_stimulus(self):
        import copy
        from criteria import CARDS, event_limits
        card=copy.deepcopy(CARDS['EV-HC-01'])
        card['source']=card['source'].replace('2e-4','1e-4')
        for e in card['event_contract']:e['window_T'][1]=.00025
        limits=event_limits(card,'count')
        self.assertAlmostEqual(limits[0]['slope_V_per_T'],.4)
        self.assertAlmostEqual(limits[0]['window_T'][1],.00025)
        card['event_contract'][0]['window_T'][1]=.0005
        with self.assertRaises(ValueError):event_limits(card,'count')

    def test_independent_si_instance_shifts(self):
        rows=rows_for('SI-01')
        for r in rows:
            x=r['time_s']/1e-6;ea=[2-.0005,4-.0005,6-.0005];eb=[3+.0005,6+.0005]
            na=sum(x>=e for e in ea);nb=sum(x>=e for e in eb)
            r.update(na=na,nb=nb,oa=-.25 if na==0 else .1*ea[na-1],ob=.75 if nb==0 else 1-.1*eb[nb-1])
        self.assertEqual(assess('SI-01',rows,Q)['status'],'P')

    def test_history_pass_is_compatible_existence_not_actual_time_bound(self):
        answer=assess('EV-SH-01',rows_for('EV-SH-01',.001005),Q)
        self.assertEqual(answer['status'],'P')
        history=next(p for p in answer['properties'] if p['name']=='event_history')
        self.assertGreater(history['native_brackets_T'][0][1],history['legal_windows_T'][0][1])
        self.assertLessEqual(history['intervals_T'][0][1],history['legal_windows_T'][0][1])
        self.assertIn('Exists',history['rule'])

    def test_all_saved_values_reject_bool(self):
        rows=rows_for('VR-01');rows[5]['out']=True
        self.assertEqual(assess('VR-01',rows,Q)['status'],'I')
        with self.assertRaisesRegex(ValueError,'Unknown condition'):raw_assess('not-a-condition',[],Q)

    def test_legal_small_wrap_displacements(self):
        for name in ('CP-02','CO-VCO-01'):
            for displacement in (-.00003,.00003):
                rows=rows_for(name)
                # Independent perturbation: fixed roots move by local phase-rate
                # times 30 ps. The numerical phase deviation stays in budget.
                for r in rows:
                    x=r['time_s']/1e-6
                    rate=.75 if name=='CP-02' else min(1,max(.2,.4+.5*((-1+x/2) if x<=2 else x-2 if x<=4 else 6-x if x<=6 else -(x-6)/2)))
                    r['phase']=(r['phase']-rate*displacement)%1
                    r['out']=math.sin(2*math.pi*r['phase'])
                with self.subTest(case=name,shift=displacement):self.assertEqual(assess(name,rows,Q)['status'],'P')

    def test_freeze_refuses_dependency_replacement(self):
        import tempfile
        from criteria import freeze_checker
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'checker.json'
            first=freeze_checker(path)
            self.assertEqual(freeze_checker(path),first)
            path.write_text('{}')
            with self.assertRaises(ValueError):freeze_checker(path)


if __name__=='__main__': unittest.main()
