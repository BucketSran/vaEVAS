"""Independent voltage-tube obligations for rounded pulse corners."""
GUARDS = ["DEV:scs-input", "TIMER", "EVENT-CONDITIONS"]
import copy
import json
import math
import subprocess
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


class SourceUncertainty(unittest.TestCase):
    def program(self, body='V(y,r)<+3*V(u,r);'):
        return compile_sources({'uncertain.va':model(body)},[instance()])

    def test_static_gain_propagates_error_and_rejects_tight_budget(self):
        p=self.program()
        result=transient(p,{'u':[[0,0],[1,1]]},[0,.5,1],stop=1,max_step=1,
                         source_errors={'u':1e-4},vabstol=1e-3,reltol=0,kernel=KERNEL)
        self.assertEqual([r['voltages'][p.nodes.index('y')] for r in result['solutions']],[0,1.5,3])
        bounds=result['observation_evidence']['voltage_bounds_V'][1][p.nodes.index('y')]
        self.assertLessEqual(bounds[0],1.5-3e-4)
        self.assertGreaterEqual(bounds[1],1.5+3e-4)
        with self.assertRaisesRegex(KernelError,'at y'):
            transient(p,{'u':[[0,0],[1,1]]},[0,.5,1],stop=1,max_step=1,
                      source_errors={'u':1e-4},vabstol=2e-4,reltol=0,kernel=KERNEL)

    def test_fixed_timer_sample_retains_error_after_input_returns_to_zero(self):
        p=compile_sources(
            {'sample.va':model('''@(initial_step) q=0;
                @(timer(0.5)) q=V(u,r);
                @(timer(0.75)) q=100*q;
                V(y,r)<+q;''','real q;')},[instance()])
        args=dict(stop=1,max_step=1,source_errors={'u':1e-4},reltol=0,kernel=KERNEL)
        result=transient(p,{'u':[[0,0],[.5,1],[1,0]]},[0,.5,1],vabstol=.02,**args)
        self.assertEqual(result['solutions'][-1]['voltages'][p.nodes.index('y')],100)
        with self.assertRaisesRegex(KernelError,'at y'):
            transient(p,{'u':[[0,0],[.5,1],[1,0]]},[0,.5,1],vabstol=.001,**args)

    def test_derivative_cross_and_dynamic_consumers_reject_uncertified_time_shape(self):
        for body in ('V(y,r)<+ddt(V(u,r));','V(y,r)<+idt(V(u,r),0);',
                     "V(y,r)<+laplace_nd(V(u,r),'{1},'{1,1});",
                     '@(cross(V(u,r)-0.5,+1)) q=1; V(y,r)<+q;'):
            with self.subTest(body=body):
                p=compile_sources({'uncertain.va':model(body,'real q;')},[instance()])
                with self.assertRaisesRegex(KernelError,'source.*uncertainty|uncertain.*source'):
                    transient(p,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=1,
                              source_errors={'u':1e-4},vabstol=1,kernel=KERNEL)

    def test_python_error_map_validation_and_default_zero_compatibility(self):
        p=self.program(); sources={'u':[[0,0],[1,1]]}
        args=dict(stop=1,max_step=1,kernel=KERNEL)
        expected=transient(p,sources,[0,1],**args)
        self.assertEqual(transient(p,sources,[0,1],source_errors={'u':0},**args),expected)
        for errors in ({'absent':.1},{'u':-1},{'u':True},{'u':math.inf},{'u':'1'},[]):
            with self.subTest(errors=errors),self.assertRaises(ValueError):
                transient(p,sources,[0,1],source_errors=errors,**args)

    def test_automatic_absolute_time_source_keeps_zero_error_and_input_order(self):
        p=self.program('V(y,r)<+3*V(u,r)+$abstime;')
        result=transient(p,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=1,
                         source_errors={'u':1e-4},vabstol=.001,reltol=0,kernel=KERNEL)
        self.assertEqual(result['solutions'][-1]['voltages'][p.nodes.index('y')],4)

    def test_raw_request_error_vector_is_strictly_validated(self):
        request=dict(program=self.program().to_dict(),driven=['u'],samples=[],
                     transient=dict(pwl=[[[0,0],[1,1]]],output_times=[0,1],stop=1,max_step=1))
        for errors in (None,[],[0,0],[-1],[True],['1'],[None]):
            bad=copy.deepcopy(request);bad['transient']['pwl_errors_V']=errors
            result=subprocess.run([str(KERNEL)],input=json.dumps(bad),text=True,capture_output=True)
            with self.subTest(errors=errors):
                self.assertEqual(result.returncode,2,result.stdout)


if __name__=='__main__':
    unittest.main()
