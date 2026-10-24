"""Source-position phase inputs retain RN area and original error admission."""
GUARDS = ['LANG', 'DYNAMICS', 'EVENT-ORDER', 'TIMED-OPERATOR', 'COMPOSE']
from fractions import Fraction as F
import unittest
from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

class PhaseInputCaptures(unittest.TestCase):
    def run_phase(self, body, points, times, *, absolute=1e-10, errors=None):
        program=compile_sources({'phase-input.va':model(body,'real a,b;')},[instance()])
        return transient(program,{'u':points},times,stop=1,max_step=.125,
                         vabstol=absolute,reltol=0,source_errors=errors,kernel=KERNEL)

    def test_actual_constant_rn_capture_preserves_exact_wrap_and_later_overwrite(self):
        body='a=V(u,r)+1.1102230246251565e-16; V(y,r)<+idtmod(a,0.25,1,0); a=9;'
        sparse=[0,.25,.5,.75,1];dense=[i/16 for i in range(17)]
        a=self.run_phase(body,[[0,1],[1,1]],sparse)
        b=self.run_phase(body,[[0,1],[1,1]],dense)
        y=a['nodes'].index('y')
        for i,t in enumerate(sparse):
            expected=(F(1,4)+F(t))%1
            self.assertEqual(F(a['solutions'][i]['voltages'][y]),expected)
            lo,hi=a['observation_evidence']['voltage_bounds_V'][i][y]
            self.assertLessEqual(F(lo),expected);self.assertGreaterEqual(F(hi),expected)
            self.assertEqual(a['solutions'][i],b['solutions'][dense.index(t)])

    def test_rn_staircase_area_is_enclosed_instead_of_endpoint_interpolation(self):
        body='a=4503599627370496+V(u,r); a=a-4503599627370496; V(y,r)<+idtmod(a,0,64,-32);'
        times=[0,.25,.75,1]
        result=self.run_phase(body,[[0,0],[1,1]],times,absolute=16)
        y=result['nodes'].index('y')
        # RN(2^52+t)-2^52 is zero on the first half, one on the second.
        for row,exact in zip(result['observation_evidence']['voltage_bounds_V'],[F(0),F(0),F(1,4),F(1,2)]):
            self.assertLessEqual(F(row[y][0]),exact);self.assertGreaterEqual(F(row[y][1]),exact)
        with self.assertRaises(KernelError) as caught:
            self.run_phase(body,[[0,0],[1,1]],times,absolute=1e-10)
        self.assertEqual(caught.exception.diagnostic['kind'],'waveform_accuracy')

    def test_nonzero_source_error_never_receives_exact_phase_certificate(self):
        with self.assertRaises(KernelError) as caught:
            self.run_phase('a=V(u,r); V(y,r)<+idtmod(a,0,1,0);',[[0,1],[1,1]],[0,.5,1],errors={'u':1e-6})
        self.assertEqual(caught.exception.diagnostic['kind'],'unsupported_source_uncertainty')

class IndependentEventVoltages(unittest.TestCase):
    def test_conditional_capture_rows_do_not_form_a_pre_event_voltage_proof(self):
        body='''@(initial_step) q=0;
        @(timer(0.5)) begin if(V(z,r)>1.5) q=1; else q=2; end
        if(V(u,r)>0) V(z,r)<+1; else V(z,r)<+2; V(y,r)<+q;'''
        p=compile_sources({'conditional-provider.va':model(body,'integer q; electrical z;')},[instance()])
        with self.assertRaisesRegex(KernelError,'event_condition'):
            transient(p,{'u':[[0,1],[1,1]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)

    def test_ordinary_statement_write_is_not_a_pre_activation_state_certificate(self):
        from evas.runtime import _invoke
        import json
        body='@(initial_step) begin s=0; q=0; end\n        @(timer(0.5)) begin if(V(z,r)>1.75) q=1; else q=2; end\n        V(z,r)<+s; V(y,r)<+q;'
        p=json.loads(json.dumps(compile_sources({'ordinary-provider.va':model(body,'real s,q; electrical z;')},[instance()]).to_dict()))
        def shift(value):
            if isinstance(value,dict):
                if value.get('expanded_statement_ordinal',-1)>=1:
                    value['expanded_statement_ordinal']+=1
                for child in value.values():shift(child)
            elif isinstance(value,list):
                for child in value:shift(child)
        shift(p)
        state=next(i for i,s in enumerate(p['states']) if s['name']=='s')
        p['procedures'][0]['body'].insert(1,dict(expanded_statement_ordinal=1,action=dict(
            kind='assign',state=state,rhs=dict(op='affine',constant=0,terms=[dict(node=p['nodes'].index('u'),coefficient=2)]))))
        request=dict(program=p,driven=['u'],samples=[],transient=dict(
            pwl=[[[0,0],[.5,1],[1,1]]],output_times=[0,.5,1],stop=1,max_step=.125),
            tolerances=dict(absolute=1e-10,relative=0))
        with self.assertRaisesRegex(KernelError,'event_condition'):
            _invoke(request,KERNEL,timeout=None)

    def test_final_certificate_rebuilds_independent_internal_state_sample(self):
        body='''@(initial_step) begin n=1; held=-1; end
        @(timer(0.5001)) held=V(y,r); V(y,r)<+n; V(z,r)<+held;'''
        p=compile_sources({'state-provider-replay.va':model(body,'integer n; real held; electrical z;')},[instance()])
        result=transient(p,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=1,
                         vabstol=1e-12,reltol=0,kernel=KERNEL)
        self.assertEqual(result['transient']['states'][-1],[1,1])
        y=p.nodes.index('y');z=next(i for i,n in enumerate(p.nodes) if n=='z' or n.endswith(':z'))
        self.assertEqual([r['voltages'][y] for r in result['solutions']],[1,1])
        self.assertEqual([r['voltages'][z] for r in result['solutions']],[-1,1])
