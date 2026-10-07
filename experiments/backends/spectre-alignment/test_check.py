import unittest,math
import check

class Calibration(unittest.TestCase):
    def setUp(self):
        self.card={'ic':'1/8','layer':'constant','observer':True,'segments':[{'left':'0','right':'1/131072','frequency_left_cycles_per_s':'524288','slope_cycles_per_s2':'0'}],'roots_decimal':[str(x/524288) for x in [.875,1.875,2.875,3.875]],'pwl':[]}
        roots=[float(x) for x in self.card['roots_decimal']]
        self.times=[0]+[t for root in roots for t in [root-2**-40,root,root+2**-40]]+[2**-17]
        self.rows=[dict(time=t,**{k:v for k,v in check.reference(self.card,t).items() if not k.startswith('exact')}) for t in self.times]
    def test_exact_binary_reference_and_wraps(self):
        self.assertEqual(check.reference(self.card,0)['accum'],.125)
        self.assertEqual(check.reference(self.card,2**-17)['accum'],4.125)
        self.assertEqual(check.reference(self.card,float(self.card['roots_decimal'][0]))['phase'],0.)
        self.assertTrue(check.check_layer(self.rows,self.card,self.times)['pass_'])
    def test_initial_sign_frequency_integral_and_sine(self):
        for key in ['freq','accum','phase','out']:
            rows=[dict(r) for r in self.rows];rows[0][key]+=.1
            self.assertFalse(check.check_layer(rows,self.card,self.times)['pass_'])
    def test_ordinary_phase_is_not_masked(self):
        rows=[dict(r) for r in self.rows];rows[2]['phase']=math.nextafter(1.,0.)
        r=check.check_layer(rows,self.card,self.times)
        self.assertTrue(any(f.get('signal')=='phase_ordinary' for f in r['failures']))
        self.assertLess(r['maxima']['phase_circular']['error'],.001)
    def test_missing_duplicate_outside_and_invalid(self):
        for rows in [self.rows[1:],self.rows+[dict(self.rows[-1])],self.rows+[dict(self.rows[-1],time=2**-17+2**-40)],self.rows+[dict(self.rows[-1],time=float('nan'))]]:
            self.assertFalse(check.check_layer(rows,self.card,self.times)['pass_'])
    def test_observer_effect_and_missing_common_time(self):
        self.assertTrue(check.observer_compare(self.rows,self.rows,self.times,['freq','phase','out'])['pass_'])
        changed=[dict(r) for r in self.rows];changed[2]['phase']=.999999
        self.assertFalse(check.observer_compare(self.rows,changed,self.times,['phase'])['pass_'])
        self.assertFalse(check.observer_compare(self.rows[1:],self.rows,self.times,['phase'])['pass_'])
    def test_event_time_and_sample_are_distinct(self):
        root=3*2**-23;card=dict(math_root_s=root,allowed_delay_s=2**-24,ramp_slope_V_per_s=2**20,ports=['x','samplevalue','count','firedtime'])
        rows=[dict(time=0.,x=0.,count=0,firedtime=-1,samplevalue=-1),dict(time=2**-20,x=1.,count=1,firedtime=root,samplevalue=.375)]
        self.assertTrue(check.check_event(rows,card,[0.,2**-20])['pass_'])
        late=[dict(r) for r in rows];late[-1].update(firedtime=root+2**-25,samplevalue=(root+2**-25)*2**20)
        result=check.check_event(late,card,[0.,2**-20]);kinds={f['kind'] for f in result['failures']}
        self.assertIn('physical_event_time',kinds);self.assertIn('physical_samplevalue',kinds);self.assertNotIn('callback_time_sample_inconsistent',kinds)
    def test_missing_event_and_inconsistent_sample(self):
        root=3*2**-23;card=dict(math_root_s=root,allowed_delay_s=2**-24,ramp_slope_V_per_s=2**20,ports=['x','samplevalue','count','firedtime'])
        rows=[dict(time=0.,x=0.,count=0,firedtime=-1,samplevalue=-1),dict(time=2**-20,x=1.,count=0,firedtime=-1,samplevalue=-1)]
        self.assertFalse(check.check_event(rows,card,[0.,2**-20])['pass_'])
        rows[-1].update(count=1,firedtime=root,samplevalue=.4)
        self.assertTrue(any(f['kind']=='callback_time_sample_inconsistent' for f in check.check_event(rows,card,[0.,2**-20])['failures']))



class LayerInvariants(unittest.TestCase):
    def test_piecewise_integrals_and_clamp_bounds(self):
        import json
        from pathlib import Path
        cards={c['id']:c for c in json.loads((Path(__file__).resolve().parent/'cases.json').read_text())['cases']}
        # This calibration uses the frozen new case cards, never DUT output.
        for name,final in [('pwl',4.375),('clip',4.3125)]:
            card=cards[name+'--observer-on']
            self.assertEqual(check.reference(card,2**-17)['accum'],final)
            for k in range(65):
                r=check.reference(card,k*2**-23)
                if name=='clip':self.assertTrue(.25<=r['freq']<=.75)

class ReviewedNegativeControls(unittest.TestCase):
    def setUp(self):
        self.root=3*2**-23
        self.card=dict(math_root_s=self.root,allowed_delay_s=2**-24,ramp_slope_V_per_s=2**20,ports=['x','samplevalue','count','firedtime'])
        self.rows=[dict(time=0.,x=0.,count=0,samplevalue=-1),dict(time=2**-20,x=1.,count=1,samplevalue=.375)]
    def verdict(self,rows):return check.check_event(rows,self.card,[0.,2**-20],projection=True)['pass_']
    def test_projection_sample_and_ramp_are_independent(self):
        self.assertTrue(self.verdict(self.rows))
        for signal,value in [('samplevalue',100.),('x',-99.)]:
            rows=[dict(r) for r in self.rows];rows[-1][signal]=value
            self.assertFalse(self.verdict(rows))
    def test_event_missing_columns_and_nonfinite_values(self):
        for signal in ['x','samplevalue','count']:
            for value in [None,float('nan'),float('inf'),float('-inf')]:
                rows=[dict(r) for r in self.rows];rows[-1][signal]=value
                self.assertFalse(self.verdict(rows),(signal,value))
            rows=[dict(r) for r in self.rows];del rows[-1][signal]
            self.assertFalse(self.verdict(rows),signal)
    def test_initial_sample_and_count_values(self):
        for index,signal,value in [(0,'samplevalue',0.),(0,'count',1),(-1,'count',2)]:
            rows=[dict(r) for r in self.rows];rows[index][signal]=value
            self.assertFalse(self.verdict(rows))
    def test_event_time_required_and_native_time_finite(self):
        self.assertFalse(check.check_event(self.rows,self.card,[0.,2**-20])['pass_'])
        rows=[dict(self.rows[0],firedtime=-1),dict(self.rows[1],firedtime=self.root)]
        self.assertTrue(check.check_event(rows,self.card,[0.,2**-20],[dict(time=self.root)])['pass_'])
        for value in [None,float('nan'),float('inf')]:
            self.assertFalse(check.check_event(rows,self.card,[0.,2**-20],[dict(time=value)])['pass_'])
            bad=[dict(r) for r in rows];bad[-1]['firedtime']=value
            self.assertFalse(check.check_event(bad,self.card,[0.,2**-20])['pass_'])
    def test_read_time_count_consistency_away_from_root(self):
        late=self.root+2e-10
        rows=[dict(self.rows[0]),dict(time=late,x=late*2**20,count=0,samplevalue=-1),dict(self.rows[1])]
        self.assertFalse(self.verdict(rows))
        early=self.root-2e-10
        rows=[dict(self.rows[0]),dict(time=early,x=early*2**20,count=1,samplevalue=.375),dict(self.rows[1])]
        self.assertFalse(self.verdict(rows))
        # Exact-root reads intentionally have no forced before/after convention.
        for count,sample in [(0,-1),(1,.375)]:
            rows=[dict(self.rows[0]),dict(time=self.root,x=.375,count=count,samplevalue=sample),dict(self.rows[1])]
            self.assertTrue(self.verdict(rows))
    def test_observer_nonfinite_missing_and_duplicate_rejected(self):
        rows=[dict(time=0.,phase=.125),dict(time=1.,phase=.625)]
        self.assertTrue(check.observer_compare(rows,rows,[0.,1.],['phase'])['pass_'])
        for value in [None,float('nan'),float('inf')]:
            bad=[dict(r) for r in rows];bad[-1]['phase']=value
            self.assertFalse(check.observer_compare(rows,bad,[0.,1.],['phase'])['pass_'])
        bad=[dict(r) for r in rows];del bad[-1]['phase']
        self.assertFalse(check.observer_compare(rows,bad,[0.,1.],['phase'])['pass_'])
        self.assertFalse(check.observer_compare(rows,rows+[dict(rows[-1])],[0.,1.],['phase'])['pass_'])
        bad=[dict(r) for r in rows];bad[-1]['time']=float('nan')
        self.assertFalse(check.observer_compare(rows,bad,[0.,1.],['phase'])['pass_'])



class RemainingFailurePaths(unittest.TestCase):
    setUp=Calibration.setUp
    def test_layer_wrap_count_bracket_range_and_invalid_signal(self):
        rows=[dict(r) for r in self.rows]
        rows[2]['phase']=float('nan')
        self.assertIn('invalid_signal',{f['kind'] for f in check.check_layer(rows,self.card,self.times)['failures']})
        rows=[dict(r) for r in self.rows];rows[0]['phase']=1.
        self.assertIn('phase_range',{f['kind'] for f in check.check_layer(rows,self.card,self.times)['failures']})
        rows=[dict(r,phase=.125) for r in self.rows]
        self.assertIn('wrap_count',{f['kind'] for f in check.check_layer(rows,self.card,self.times)['failures']})
        card=dict(self.card,roots_decimal=[str(float(t)+1e-8) for t in self.card['roots_decimal']])
        self.assertIn('wrap_bracket',{f['kind'] for f in check.check_layer(self.rows,card,self.times)['failures']})
    def test_event_window_native_count_and_nominal_time(self):
        root=3*2**-23;card=dict(math_root_s=root,allowed_delay_s=2**-40,ramp_slope_V_per_s=2**20,ports=['x','samplevalue','count','firedtime'])
        rows=[dict(time=0.,x=0.,count=0,samplevalue=-1,firedtime=-1),dict(time=2**-20,x=1.,count=1,samplevalue=.375,firedtime=root+2e-12)]
        self.assertIn('allowed_event_window',{f['kind'] for f in check.check_event(rows,card,[0.,2**-20])['failures']})
        rows[-1]['firedtime']=root
        self.assertIn('native_event_count',{f['kind'] for f in check.check_event(rows,card,[],[])['failures']})
        self.assertIn('native_nominal_event_time',{f['kind'] for f in check.check_event(rows,card,[],[dict(time=root+2e-10)])['failures']})
        self.assertIn('invalid_observation_time_bounds',{f['kind'] for f in check.check_event(rows,card,[],[dict(time=root,observation_time_bounds=[float('nan'),root])])['failures']})
    def test_observer_grid_change_and_invalid_requested_time(self):
        self.assertIn('native_grid_changed',{f['kind'] for f in check.observer_compare(self.rows,self.rows[:-1],[0.],['phase'])['failures']})
        self.assertIn('invalid_required_times',{f['kind'] for f in check.observer_compare(self.rows,self.rows,[float('nan')],['phase'])['failures']})



class ExplicitEventContract(unittest.TestCase):
    def setUp(self):
        self.card=dict(math_root_s=3*2**-23,allowed_delay_s=2**-24,ramp_slope_V_per_s=2**20,ports=['x','samplevalue','count'])
        self.rows=[dict(time=0.,x=0.,samplevalue=-1.,count=0),dict(time=2**-20,x=1.,samplevalue=.375,count=1)]
    def test_missing_or_illegal_ports_rejected_even_for_projection(self):
        for ports in [None,[],['x','samplevalue'],['x','samplevalue','count','count'],'x samplevalue count',['x','samplevalue','count',1],['x','samplevalue','count','unmodeled']]:
            card=dict(self.card,ports=ports)
            for projection in [False,True]:
                report=check.check_event(self.rows,card,[0.,2**-20],projection=projection)
                self.assertEqual(report['failures'][0]['kind'],'invalid_event_contract')
        card=dict(self.card);del card['ports']
        self.assertEqual(check.check_event(self.rows,card,[])['failures'][0]['kind'],'invalid_event_contract')
    def test_declared_on_missing_whole_firedtime_column_rejected(self):
        card=dict(self.card,ports=['x','samplevalue','count','firedtime'])
        report=check.check_event(self.rows,card,[0.,2**-20])
        self.assertFalse(report['pass_']);self.assertIn('firedtime',report['required_signals'])
        self.assertTrue(check.check_event(self.rows,card,[0.,2**-20],projection=True)['pass_'])
    def test_declared_off_accepts_correct_observed_signals(self):
        report=check.check_event(self.rows,self.card,[0.,2**-20])
        self.assertTrue(report['pass_']);self.assertEqual(report['required_signals'],['x','samplevalue','count'])

if __name__=='__main__':unittest.main()
