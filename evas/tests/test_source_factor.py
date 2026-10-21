"""Original-tree scalar factorization, exact binary oracles and strict gates."""
GUARDS = ['SLEW', 'TIMED-OPERATOR', 'ANALOG', 'DYNAMICS', 'COMPOSE']
import copy
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import unittest
from evas import compile_sources, transient, KernelError
from test_affine import instance, KERNEL as DEFAULT_KERNEL
KERNEL = Path(os.environ.get('EVAS_TEST_KERNEL', DEFAULT_KERNEL))

def program(n=15, coefficient='0.0625', gain='1.0'):
    inputs = ','.join('u'+str(k) for k in range(n))
    ports = inputs+',y'
    terms = '+'.join('(V(u'+str(k)+')>0.5?1.0:0.0)' for k in range(n))
    source = '`include "disciplines.vams"\nmodule m('+ports+'); input '+inputs+'; output y; electrical '+ports+'; analog begin V(y)<+'+gain+'*slew('+coefficient+'*('+terms+'),2.0,-2.0); end endmodule'
    return compile_sources({'factor-control.va':source},[instance(connections={n:n for n in ports.split(',')})])

class SourceFactor(unittest.TestCase):
    def test_fifteen_constant_bits_are_counted_without_cartesian_forms(self):
        p=program()
        sources={'u'+str(k):[[0.,0.9 if k<7 else 0.],[1.,0.9 if k<7 else 0.]] for k in range(15)}
        r=transient(p,sources,[0.,.5,1.],stop=1.,max_step=.1,kernel=KERNEL)
        y=r['nodes'].index('y');want=Fraction(7,16)
        for row,box in zip(r['solutions'],r['observation_evidence']['voltage_bounds_V'],strict=True):
            self.assertEqual(row['voltages'][y],float(want))
            self.assertLessEqual(Fraction(box[y][0]),want);self.assertGreaterEqual(Fraction(box[y][1]),want)

    def test_original_binary64_coefficient_and_nonthermometer_patterns_keep_real_box(self):
        p=program(coefficient='0.06666666666666667')
        for bits in [set(),set(range(15)),{0,2,5,7,11,14},{1,4,6}]:
            sources={'u'+str(k):[[0.,.9 if k in bits else 0.],[1.,.9 if k in bits else 0.]] for k in range(15)}
            r=transient(p,sources,[0.,.5,1.],stop=1.,max_step=1.,kernel=KERNEL)
            y=r['nodes'].index('y');want=len(bits)*Fraction(0.06666666666666667)
            for row,box in zip(r['solutions'],r['observation_evidence']['voltage_bounds_V'],strict=True):
                self.assertLessEqual(abs(Fraction(row['voltages'][y])-want),Fraction(1,10**14))
                self.assertLessEqual(Fraction(box[y][0]),want);self.assertGreaterEqual(Fraction(box[y][1]),want)

    def test_exact_roots_rate_limiter_and_extra_queries_keep_common_values(self):
        p=program();sources={'u'+str(k):[[0.,0.],[.5,1.],[1.,0.]] for k in range(15)}
        times=[0.,.125,.25,.5,.71875,.75,.875,1.]
        r=transient(p,sources,times,stop=1.,max_step=1.,kernel=KERNEL);y=r['nodes'].index('y')
        for t,row,box in zip(times,r['solutions'],r['observation_evidence']['voltage_bounds_V'],strict=True):
            t=Fraction(t)
            want=Fraction(0) if t<=Fraction(1,4) else min(Fraction(15,16),2*(t-Fraction(1,4))) if t<=Fraction(3,4) else Fraction(15,16)-2*(t-Fraction(3,4))
            self.assertLessEqual(abs(Fraction(row['voltages'][y])-want),Fraction(1,10**12))
            self.assertLessEqual(Fraction(box[y][0]),want);self.assertGreaterEqual(Fraction(box[y][1]),want)
        more=sorted(set(times+[.0625,.375,.625,.8125]))
        s=transient(p,sources,more,stop=1.,max_step=1.,kernel=KERNEL)
        self.assertEqual([x['voltages'] for x in r['solutions']],[s['solutions'][more.index(t)]['voltages'] for t in times])

    def raw(self,p,errors=None):
        request=dict(program=p,driven=['u'+str(k) for k in range(15)],samples=[],transient=dict(pwl=[[[0.,.9],[1.,.9]] for _ in range(15)],output_times=[0.,.5,1.],stop=1.,max_step=1.))
        if errors is not None:request['transient']['pwl_errors_V']=errors
        result=subprocess.run([str(KERNEL)],input=json.dumps(request),text=True,capture_output=True,timeout=30)
        self.assertNotEqual(result.returncode,0,result.stdout)
        return json.loads(result.stderr)

    def test_original_dormant_zero_dependency_owner_and_overflow_are_audited(self):
        p=json.loads(json.dumps(program().to_dict()));y=p['nodes'].index('y')
        for bad in [dict(op='affine',constant=0.,terms=[dict(node=y,coefficient=0.)]),dict(op='state',state=0),dict(op='operator',operator=0),dict(op='add',left=dict(op='affine',constant=1e308,terms=[]),right=dict(op='affine',constant=1e308,terms=[]))]:
            q=copy.deepcopy(p);q['operators'][0]['input']['right']['right']['else_value']=bad;self.raw(q)
        q=copy.deepcopy(p);q['operators'][0]['input']['right']['right']['origin']['instance']='foreign';self.raw(q)

    def test_nested_guard_new_grammar_and_true_error_still_refuse(self):
        p=json.loads(json.dumps(program().to_dict()));q=copy.deepcopy(p)
        q['operators'][0]['input']['right']['right']['left']=copy.deepcopy(q['operators'][0]['input']['right']['right'])
        self.raw(q)
        for op in ['divide','power']:
            q=copy.deepcopy(p)
            q['operators'][0]['input']['right']['right']['else_value']=dict(op=op,left=dict(op='affine',constant=1.,terms=[]),right=dict(op='affine',constant=2.,terms=[])) if op=='divide' else dict(op='power',base=dict(op='affine',constant=2.,terms=[]),exponent=2)
            self.raw(q)
        self.assertEqual(self.raw(p,[1e-6]*15)['kind'],'unsupported_source_uncertainty')

    def test_nonbinary_target_forward_error_survives_output_gain(self):
        p=program(coefficient='0.1',gain='1e12')
        sources={'u'+str(k):[[0.,0.],[.5,1.],[1.,0.]] for k in range(15)}
        with self.assertRaises(KernelError) as caught:
            transient(p,sources,[0.,.6,1.],stop=1.,max_step=1.,vabstol=1e-8,reltol=0.,kernel=KERNEL)
        self.assertEqual(caught.exception.detail['kind'],'waveform_accuracy')
