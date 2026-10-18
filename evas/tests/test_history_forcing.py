"""Independent public controls; run only against an identified snapshot/kernel.

These are synthetic contracts, not original041 or an original checker substitute.
The expected answers use binary fractions and an elementary clipped mixer.
"""
GUARDS = ["LANG", "ANALOG", "EVENT-ORDER", "TIMED-OPERATOR", "COMPOSE"]
from fractions import Fraction
import os
from pathlib import Path
import unittest

from evas import Instance, compile_sources, transient


KERNEL = Path(os.environ.get(
    'EVAS_TEST_KERNEL', Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel'))
SOURCE = '''`include "disciplines.vams"
module mixer(u,lo,rst,y,metric);
input u,lo,rst; output y,metric; electrical u,lo,rst,y,metric;
parameter real gain=1.25;
real z,pol,mix; integer q;
analog begin
  @(initial_step) q=0;
  @(timer(0.25)) q=1;
  if(V(rst)>0.5) mix=0.5;
  else begin
    pol=(V(lo)>0.5)?1.0:-1.0;
    z=0.5+gain*(V(u)-0.5)*pol;
    if(z>0.875) z=0.875;
    if(z<0.125) z=0.125;
    mix=z;
  end
  V(y)<+mix;
  V(metric)<+transition(q,0,0.125,0.125);
end
endmodule
'''


class HistoryForcingRed(unittest.TestCase):
    def program(self, instances=None):
        return compile_sources({'synthetic_mixer.va': SOURCE}, instances or [
            Instance('one', 'mixer', dict(u='u',lo='lo',rst='rst',y='y',metric='metric'), {})])

    def run_values(self, program, times, reset=0):
        return transient(program, {'u': [[0,0],[1,.5]], 'lo': [[0,0],[1,1]],
            'rst': [[0,reset],[1,reset]]}, times, stop=1,max_step=1,kernel=KERNEL)

    def expected(self, t, gain=Fraction(5,4)):
        t = Fraction.from_float(t)
        sign = 1 if t>Fraction(1,2) else -1
        value = Fraction(1,2)+gain*(t/2-Fraction(1,2))*sign
        return min(Fraction(7,8),max(Fraction(1,8),value))

    def assert_point_and_box(self, result, times, name, expected):
        node = result['nodes'].index(name)
        for t,row,box in zip(times,result['solutions'],result['observation_evidence']['voltage_bounds_V']):
            want=expected(t)
            self.assertLess(abs(row['voltages'][node]-float(want)),1e-10,(name,t))
            lo,hi=box[node]
            self.assertLessEqual(Fraction.from_float(lo),want,(name,t,lo,want))
            self.assertGreaterEqual(Fraction.from_float(hi),want,(name,t,hi,want))

    def test_clipped_source_forcing_and_independent_history(self):
        times=[0,.25,.3125,.375,.5,.75,1]
        r=self.run_values(self.program(),times)
        self.assert_point_and_box(r,times,'y',self.expected)
        def metric(t):
            t=Fraction.from_float(t)
            return min(Fraction(1),max(Fraction(0),(t-Fraction(1,4))*8))
        self.assert_point_and_box(r,times,'metric',metric)

    def test_extra_queries_do_not_change_common_forcing_or_history(self):
        p=self.program(); sparse=[0,.25,.5,.75,1]
        dense=[0,.125,.25,.3125,.375,.5,.625,.75,.875,1]
        a=self.run_values(p,sparse); b=self.run_values(p,dense)
        for i,t in enumerate(sparse):
            j=dense.index(t)
            self.assertEqual(a['solutions'][i]['voltages'],b['solutions'][j]['voltages'])
            self.assertEqual(a['observation_evidence']['voltage_bounds_V'][i],
                             b['observation_evidence']['voltage_bounds_V'][j])
        self.assertEqual(a['transient']['events'],b['transient']['events'])

    def test_reset_forcing_does_not_replace_independent_history(self):
        times=[0,.25,.3125,.5,1]
        r=self.run_values(self.program(),times,reset=1)
        self.assert_point_and_box(r,times,'y',lambda t:Fraction(1,2))
        metric=r['nodes'].index('metric')
        self.assertAlmostEqual(r['solutions'][-1]['voltages'][metric],1,places=10)

    def test_owner_and_parameter_bindings_remain_distinct(self):
        inst=[]
        for name,gain in [('one',1.25),('two',.5)]:
            inst.append(Instance(name,'mixer',dict(u='u',lo='lo',rst='rst',
                y='y_'+name,metric='m_'+name),dict(gain=gain)))
        times=[0,.25,.5,.75,1];r=self.run_values(self.program(inst),times)
        self.assert_point_and_box(r,times,'y_one',self.expected)
        self.assert_point_and_box(r,times,'y_two',lambda t:self.expected(t,Fraction(1,2)))


    def raw(self, value, *, count=3, drivers=None, pwl=None, kernel=None):
        import json, subprocess, tempfile
        drivers=drivers or ['u','lo','rst']
        request=dict(program=value,driven=drivers,samples=[],transient=dict(
            pwl=pwl or [[[0,0],[1,0]] for _ in drivers],
            output_times=[i/(count-1) for i in range(count)],stop=1,max_step=1))
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'diagnostics.json'
            env=dict(os.environ,EVAS_DIAGNOSTICS_PATH=str(path))
            result=subprocess.run([str(kernel or KERNEL)],input=json.dumps(request),text=True,
                capture_output=True,timeout=20,env=env)
            report=json.loads(path.read_text())
        return result,report

    def test_raw_all_arms_zero_dependencies_owner_and_output_partition(self):
        import copy, json
        base=json.loads(json.dumps(self.program().to_dict()))
        forcing=next(i for i,c in enumerate(base['contributions']) if c['rhs']['op']=='forcing')
        legacy=next(i for i,c in enumerate(base['contributions']) if c['rhs']['op']!='forcing')
        ynode=base['nodes'].index('y')
        def zero_read(): return dict(op='affine',constant=0,terms=[dict(node=ynode,coefficient=0)])
        cases=[]
        raw=copy.deepcopy(base);raw['contributions'][legacy]['rhs']=zero_read();cases.append(('legacy-zero-read',raw))
        raw=copy.deepcopy(base);raw['events'][0]['body'][0]['rhs']=zero_read();cases.append(('event-zero-read',raw))
        raw=copy.deepcopy(base);raw['operators'][0]['input']=zero_read();cases.append(('history-zero-read',raw))
        raw=copy.deepcopy(base);raw['contributions'][forcing]['rhs']['origin']['instance']='foreign';cases.append(('foreign-owner',raw))
        for leaf in [zero_read(),dict(op='state',state=0),dict(op='operator',operator=0),
                dict(op='multiply',left=dict(op='affine',constant=1e308,terms=[]),right=dict(op='affine',constant=1e308,terms=[]))]:
            raw=copy.deepcopy(base)
            marker=raw['contributions'][forcing]['rhs']
            marker['value']=dict(op='select',relation='gt',left=dict(op='affine',constant=1,terms=[]),
                right=dict(op='affine',constant=0,terms=[]),then_value=marker['value'],else_value=leaf,
                origin=copy.deepcopy(marker['origin']))
            cases.append(('inactive-'+leaf['op'],raw))
        for leaf in [zero_read(),dict(op='state',state=0),dict(op='operator',operator=0),
                dict(op='multiply',left=dict(op='affine',constant=1e308,terms=[]),right=dict(op='affine',constant=1e308,terms=[]))]:
            raw=copy.deepcopy(base);raw['contributions'][forcing]['rhs']['checked']=[leaf]
            cases.append(('checked-'+leaf['op'],raw))
        raw=copy.deepcopy(base);raw['contributions'].append(copy.deepcopy(raw['contributions'][forcing]));cases.append(('duplicate-output',raw))
        raw=copy.deepcopy(base);raw['contributions'][forcing]['negative']=base['nodes'].index('u');cases.append(('nongrounded',raw))
        for name,raw in cases:
            with self.subTest(name=name):
                result,_=self.raw(raw)
                self.assertNotEqual(result.returncode,0,(name,result.stdout))
                self.assertRegex(result.stderr,'unsupported_forcing_scope|nonfinite_arithmetic')

    def test_each_actual_exact_near_tie_call_has_one_prepaid_reservation(self):
        import json
        result,report=self.raw(self.program().to_dict(),pwl=[[[0,0],[1,.5]],[[0,.1],[1,.9]],[[0,0],[1,0]]])
        self.assertEqual(result.returncode,0,result.stderr)
        counters=report['counters'];calls=counters.get('forcing_actual_exact_calls',0)
        self.assertGreater(calls,0)
        self.assertEqual(calls,counters['selected_ln_exact_calls'])
        self.assertEqual(calls,counters['selected_ln_exact_reservations'])
        self.assertEqual(calls*200_000,counters['selected_ln_exact_debit'])
        row=json.loads(result.stdout);y=row['nodes'].index('y')
        self.assertGreater((Fraction.from_float(.1)+Fraction.from_float(.9))/2,Fraction(1,2))
        self.assertEqual(row['solutions'][1]['voltages'][y],.1875)
        print('exact_tie_accounting',calls,counters['selected_ln_exact_debit'])

    def test_original_discarded_alias_and_zero_loop_reads_reject(self):
        from evas import CompileError
        # These reads would disappear during ordinary lowering/scalarization.
        for read in ['unused=V(y);', 'for(i=0;i<0;i=i+1) unused=V(y);',
                     'if(0>1) unused=0*V(y);']:
            source=SOURCE.replace('real z,pol,mix; integer q;',
                'real z,pol,mix,unused; integer q,i;').replace('V(y)<+mix;',read+' V(y)<+mix;')
            with self.subTest(read=read),self.assertRaises(CompileError) as caught:
                compile_sources({'original_read.va':source},[Instance('one','mixer',dict(u='u',lo='lo',rst='rst',y='y',metric='metric'),{})])
            self.assertEqual(caught.exception.diagnostic['code'],'unsupported_forcing_scope')

    def test_legacy_route_has_zero_forcing_factory_and_proof_work(self):
        old=SOURCE.replace('pol=(V(lo)>0.5)?1.0:-1.0;','pol=1.0;').replace('if(z>0.875) z=0.875;','').replace('if(z<0.125) z=0.125;','')
        # Retain the formerly accepted affine/reset Select and existing history.
        p=compile_sources({'legacy.va':old},[Instance('one','mixer',dict(u='u',lo='lo',rst='rst',y='y',metric='metric'),{})])
        result,report=self.raw(p.to_dict())
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(report['counters'].get('forcing_factory_calls',0),0)
        self.assertFalse(any(k.startswith('forcing_') for k in report['counters']),report['counters'])

    def test_unused_new_checked_predicate_retains_original_domain_audit(self):
        source=SOURCE.replace('real z,pol,mix; integer q;',
            'real z,pol,mix,unused,discarded; integer q;').replace('V(y)<+mix;',
            'unused=1e308*V(u)*((V(lo)>0.5)?1.0:-1.0); if(unused>0) discarded=1; else discarded=0; V(y)<+mix;')
        p=compile_sources({'unused.va':source},[Instance('one','mixer',dict(u='u',lo='lo',rst='rst',y='y',metric='metric'),{})])
        self.assertTrue(any(c['rhs'].get('checked') for c in p.to_dict()['contributions']))
        result,_=self.raw(p.to_dict(),pwl=[[[0,0],[1,4]],[[0,0],[1,1]],[[0,0],[1,0]]])
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertIn('nonfinite_arithmetic',result.stderr)

    # Mandatory identified local reference gate, selected by this full method
    # name. Portable discovery has no dependency on an archived Mac binary.
    def check_fixed_baseline_old_routes_have_identical_full_responses(self):
        import copy, json, hashlib
        baseline=os.environ.get('EVAS_TEST_BASELINE_KERNEL')
        if not baseline:
            self.fail('identified C8 baseline kernel is required for this explicit reference gate')
        baseline=Path(baseline)
        expected=os.environ['EVAS_TEST_BASELINE_SHA256']
        self.assertEqual(expected,'9c8c9fdf469c7347f2b507ad231bd3a70e355d192b648fec6e6eecd25dfc6e98')
        self.assertNotEqual(baseline.resolve(),KERNEL.resolve())
        self.assertEqual(hashlib.sha256(baseline.read_bytes()).hexdigest(),expected)
        old=SOURCE.replace('pol=(V(lo)>0.5)?1.0:-1.0;','pol=1.0;').replace('if(z>0.875) z=0.875;','').replace('if(z<0.125) z=0.125;','')
        affine=compile_sources({'legacy.va':old},[Instance('one','mixer',dict(u='u',lo='lo',rst='rst',y='y',metric='metric'),{})])
        alias=compile_sources({'alias.va':"""`include "disciplines.vams"
module alias(u,y);input u;output y;electrical u,y;real selected,q;
analog begin selected=(V(u)>0.5)?V(u):0;
@(initial_step)q=selected;@(timer(0.25))q=selected;
V(y)<+transition(q,0,0.125,0.125);end endmodule"""},
            [Instance('one','alias',dict(u='u',y='y'),{})])
        from test_selected_ln import SelectedLn
        for name,p,drivers,pwl in [
            ('affine-held',affine,['u','lo','rst'],[[[0,0],[1,.5]],[[0,0],[1,1]],[[0,0],[1,0]]]),
            ('selected-body-alias377',alias,['u'],[[[0,.75],[1,.25]]]),
            ('selected-ln135',SelectedLn().program(),['u'],[[[0,.7],[1,-.3]]])]:
            with self.subTest(name=name):
                value=json.loads(json.dumps(p.to_dict()))
                self.assertNotIn('"op": "forcing"',json.dumps(value))
                new,diag=self.raw(value,drivers=drivers,pwl=pwl,count=9)
                value['schema_version']=28
                before,prior=self.raw(value,drivers=drivers,pwl=pwl,count=9,kernel=baseline)
                self.assertEqual(new.returncode,0,new.stderr);self.assertEqual(before.returncode,0,before.stderr)
                current=json.loads(new.stdout);previous=json.loads(before.stdout)
                # IR/package identity changes are the two intentional transport
                # differences. Every physical/certificate/record field stays.
                current_engine=current.pop('engine');previous_engine=previous.pop('engine')
                self.assertEqual(current_engine.rsplit('-',1)[0],previous_engine.rsplit('-',1)[0])
                self.assertTrue(current_engine.endswith('-0.23.0'))
                self.assertTrue(previous_engine.endswith('-0.21.0'))
                self.assertEqual(current.pop('schema_version'),30)
                self.assertEqual(previous.pop('schema_version'),28)
                self.assertEqual(current,previous)
                self.assertFalse(any(k.startswith('forcing_') for k in diag['counters']))
                for k,v in prior['counters'].items():
                    if k.startswith('selected_ln_'):
                        self.assertEqual(diag['counters'].get(k),v,(name,k))
                print('full_old_route_differential',name,hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest(),expected)

    def test_default_request_budget_exhausts_naturally_after_real_queries(self):
        # Public raw IR uses the real default 1e9 budget: no lowered cap or fake
        # debit. Every forced output query evaluates and certifies 100 sources.
        import copy, json
        raw=json.loads(json.dumps(self.program().to_dict()));drivers=['u','lo','rst']
        for i in range(97):
            drivers.append('extra'+str(i));raw['nodes'].append(drivers[-1])
        forced=next(c for c in raw['contributions'] if c['rhs']['op']=='forcing')
        forced['rhs']['value']=dict(op='affine',constant=0,
            terms=[dict(node=raw['nodes'].index(n),coefficient=1) for n in drivers])
        result,report=self.raw(raw,count=256,drivers=drivers)
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertIn('step_budget',result.stderr)
        self.assertEqual(report['counters']['forcing_factory_calls'],1)
        self.assertGreater(report['counters']['forcing_dense_work'],100_000_000)
        self.assertGreater(report['counters']['forcing_operator_copy'],0)
        print('natural_default_exhaustion',report['error'],report['counters'])


if __name__=='__main__':
    unittest.main(verbosity=2)
