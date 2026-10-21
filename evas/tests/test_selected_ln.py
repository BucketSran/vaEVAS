"""Stateless selected Ln: analytic clamp, original source and strict admission."""
GUARDS = ['ANALOG', 'DYNAMICS', 'COMPOSE']
from decimal import Decimal, localcontext
import os
from pathlib import Path
import unittest
from evas import compile_sources, transient, KernelError
from test_affine import instance, model, KERNEL as DEFAULT_KERNEL
KERNEL=Path(os.environ.get('EVAS_TEST_KERNEL',DEFAULT_KERNEL))
class SelectedLn(unittest.TestCase):
    def program(self):
        return compile_sources({'selected.va':model('x=abs(V(u)-0.2);if(x<0.1)x=0.1;V(y)<+ln(x);','real x;')},[instance()])
    def test_hidden_interior_clamp_uses_original_source_at_every_query(self):
        p=self.program();r=transient(p,{'u':[[0,0.7],[1,-0.3]]},[0,.25,.5,.75,1],stop=1,max_step=1,kernel=KERNEL)
        # Both endpoint magnitudes are0.5; the hidden center is clamped0.1.
        y=r['nodes'].index('y')
        with localcontext() as c:
            c.prec=90
            for t,row,b in zip([0,.25,.5,.75,1],r['solutions'],r['observation_evidence']['voltage_bounds_V']):
                v=Decimal.from_float(.7)+(Decimal.from_float(-.3)-Decimal.from_float(.7))*Decimal.from_float(t)
                x=max(abs(v-Decimal.from_float(.2)),Decimal.from_float(.1));want=x.ln()
                self.assertLess(abs(row['voltages'][y]-float(want)),1e-10)
                self.assertLessEqual(Decimal.from_float(b[y][0]),want);self.assertGreaterEqual(Decimal.from_float(b[y][1]),want)
    def test_extra_queries_preserve_common_physical_values(self):
        p=self.program();a=transient(p,{'u':[[0,.7],[1,-.3]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)
        b=transient(p,{'u':[[0,.7],[1,-.3]]},[0,.125,.5,.875,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([x['voltages'] for x in a['solutions']],[b['solutions'][i]['voltages']for i in [0,2,4]])

    def reject_raw(self, value):
        import json, subprocess
        request=dict(program=value,driven=['u'],samples=[],transient=dict(pwl=[[[0,.7],[1,-.3]]],output_times=[0,.5,1],stop=1,max_step=1))
        result=subprocess.run([str(KERNEL)],input=json.dumps(request),text=True,capture_output=True,timeout=10)
        self.assertNotEqual(result.returncode,0,result.stdout)
        return json.loads(result.stderr)

    def test_raw_inactive_zero_weight_and_history_dependencies_still_reject(self):
        import json, copy
        value=json.loads(json.dumps(self.program().to_dict()))
        for leaf in [dict(op='affine',constant=0,terms=[dict(node=value['nodes'].index('y'),coefficient=0)]),dict(op='state',state=0),dict(op='operator',operator=0)]:
            with self.subTest(leaf=leaf):
                raw=copy.deepcopy(value);raw['operators'][0]['input']['then_value']=leaf
                self.reject_raw(raw)
        raw=copy.deepcopy(value);raw['operators'][0]['input']['origin']['instance']='foreign';self.reject_raw(raw)

    def test_selected_ln_does_not_gain_event_state_or_extra_relation_scope(self):
        import json,copy
        value=json.loads(json.dumps(self.program().to_dict()))
        raw=copy.deepcopy(value);raw['states']=[dict(instance='dut',name='hidden',kind='real',initial=0)];self.reject_raw(raw)
        raw=copy.deepcopy(value);raw['contributions'].append(copy.deepcopy(raw['contributions'][0]));self.reject_raw(raw)

    def test_selected_nonpositive_domain_is_rejected(self):
        import json,copy
        value=json.loads(json.dumps(self.program().to_dict()))
        for number in [0,-1]:
            raw=copy.deepcopy(value);raw['operators'][0]['input']['then_value']=dict(op='affine',constant=number,terms=[])
            self.assertIn('strictly positive',str(self.reject_raw(raw)))

    def test_true_input_uncertainty_must_pass_existing_voltage_acceptance(self):
        with self.assertRaises(KernelError) as caught:
            transient(self.program(),{'u':[[0,.7],[1,.7]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL,
                      source_errors={'u':1e-6},vabstol=1e-12,reltol=1e-10)
        self.assertEqual(caught.exception.detail['kind'],'waveform_accuracy')
