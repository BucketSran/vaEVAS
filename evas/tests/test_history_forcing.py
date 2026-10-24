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
    'EVAS_TEST_KERNEL', Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel')).resolve()
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

    # Explicit two-gate migration. Portable discovery needs no archived binary.
    def history_reference_identity(self):
        from history_migration_contract import C8_SHA, sha
        baseline = Path(os.environ['EVAS_TEST_BASELINE_KERNEL']).resolve()
        self.assertEqual(os.environ['EVAS_TEST_BASELINE_SHA256'], C8_SHA)
        self.assertEqual(sha(baseline), C8_SHA)
        self.assertNotEqual(baseline.resolve(), KERNEL.resolve())
        self.assertEqual(sha(KERNEL), os.environ['EVAS_TEST_CANDIDATE_SHA256'])
        return baseline, os.environ['EVAS_TEST_CANDIDATE_ENGINE']

    def check_fixed_baseline_old_routes_have_identical_full_responses(self):
        import copy
        from history_migration_contract import C8_SHA, legacy_program, response_body, run_case, source_cases, strict_equal
        baseline, engine = self.history_reference_identity()
        evidence = Path(os.environ['EVAS_TEST_HISTORY_EVIDENCE_DIR']) / 'legacy'
        try:
            for case in source_cases():
                with self.subTest(name=case['name']):
                    old = legacy_program(case['name'])
                    lifted = copy.deepcopy(old)
                    # Audited C8 transport only. No native IR33 producer is used.
                    lifted['schema_version'] = 33
                    before, prior = run_case(baseline, old, case, evidence / case['name'] / 'c8', expected_sha=C8_SHA)
                    current, diag = run_case(KERNEL, lifted, case, evidence / case['name'] / 'candidate',
                        expected_sha=os.environ['EVAS_TEST_CANDIDATE_SHA256'])
                    strict_equal(response_body(before, 28, 'evas-events-0.21.0'),
                                 response_body(current, 33, engine))
                    self.assertFalse(any(k.startswith('forcing_') for k in diag['counters']))
                    strict_equal({k:v for k,v in prior['counters'].items() if k.startswith('selected_ln_')},
                                 {k:v for k,v in diag['counters'].items() if k.startswith('selected_ln_')},
                                 '/counters/selected_ln_*')
        finally:
            self.history_reference_identity()

    def check_native_source_initialization_and_history_migration(self):
        import json
        from history_migration_contract import (audit_native_program, compare_native_response,
            C8_SHA, legacy_program, run_case, source_cases)
        baseline, engine = self.history_reference_identity()
        evidence = Path(os.environ['EVAS_TEST_HISTORY_EVIDENCE_DIR']) / 'native'
        try:
            for case in source_cases():
                with self.subTest(name=case['name']):
                    old = legacy_program(case['name'])
                    program = json.loads(json.dumps(compile_sources(case['sources'], [Instance(**i) for i in case['instances']]).to_dict()))
                    audit_native_program(case['name'], old, program)
                    before, _ = run_case(baseline, old, case, evidence / case['name'] / 'c8', expected_sha=C8_SHA)
                    current, _ = run_case(KERNEL, program, case, evidence / case['name'] / 'candidate',
                        expected_sha=os.environ['EVAS_TEST_CANDIDATE_SHA256'])
                    compare_native_response(self, case['name'], before, current, program, engine)
                    if case['name'] == 'selected-ln135':
                        from history_migration_contract import assert_voltage, selected_ln_oracle, strict_equal
                        fine, _ = run_case(KERNEL, program, case, evidence / case['name'] / 'candidate-small-step',
                            expected_sha=os.environ['EVAS_TEST_CANDIDATE_SHA256'], max_step=1/32)
                        assert_voltage(self, fine, 'y', selected_ln_oracle)
                        self.assertIs(fine['observation_evidence']['effective_controls']['max_step_applied'], True)
                        self.assertEqual(fine['transient']['accepted_steps'], 32)
                        self.assertEqual(fine['observation_evidence']['effective_controls']['max_step_s'], 1/32)
                        fine['transient']['accepted_steps'] = current['transient']['accepted_steps']
                        fine['observation_evidence']['effective_controls']['max_step_s'] = 1.0
                        strict_equal(current, fine)
        finally:
            self.history_reference_identity()

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
