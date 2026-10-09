"""Each statically expanded operator occurrence owns its integral history."""
GUARDS = ['LANG','DYNAMICS','COMPOSE']
import unittest
import copy
import json
import subprocess
from evas import compile_sources, transient
from test_affine import KERNEL, instance, model


class LoopHistories(unittest.TestCase):
    def test_independent_integral_initial_values_and_input_gains(self):
        source = model('for(i=0;i<2;i=i+1) V(y,r)<+idt((i+1)*V(u,r),i);', 'genvar i;')
        p = compile_sources({'loop-history.va':source}, [instance()])
        self.assertEqual(len(p.operators),2)
        for grid, step in (([0,1,2],2),([0,.125,.5,1,1.5,2],.17)):
            r=transient(p, {'u':[[0,0],[2,2]]}, grid, stop=2, max_step=step, kernel=KERNEL)
            for t,row in zip(grid,r['solutions']):
                self.assertAlmostEqual(row['voltages'][r['nodes'].index('y')],1+1.5*t*t,delta=1e-9)

    def test_nested_occurrences_have_four_distinct_histories(self):
        source=model('for(i=0;i<2;i=i+1) for(j=0;j<2;j=j+1) V(y,r)<+idt(i+j,2*i+j);', 'genvar i,j;')
        p=compile_sources({'loop-history.va':source},[instance()])
        self.assertEqual(len(p.operators),4)
        r=transient(p, {'u':[[0,0],[1,0]]}, [0,.5,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual([row['voltages'][r['nodes'].index('y')] for row in r['solutions']], [6,8,10])

    def test_array_receivers_do_not_define_operator_identity(self):
        source=model('for(i=0;i<2;i=i+1) a[i]=idt((i+1)*V(u,r),i); V(y,r)<+a[0]+a[1];',
                     'genvar i; real a[0:1];')
        p=compile_sources({'loop-history.va':source},[instance()])
        self.assertEqual(len(p.operators),2)
        r=transient(p,{'u':[[0,0],[2,2]]},[0,2],stop=2,max_step=2,kernel=KERNEL)
        self.assertAlmostEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],7,delta=1e-9)

    def test_implicit_integral_feedback_uses_the_same_expanded_identity(self):
        # y+y^2=z0+z1, z0'=z1'=.5+y => y'=1, y(0)=0.
        source=model('for(i=0;i<2;i=i+1) V(y,r)<+idt(0.5+V(y,r),0); V(y,r)<+-pow(V(y,r),2);', 'genvar i;')
        p=compile_sources({'loop-history.va':source},[instance()])
        r=transient(p,{'u':[[0,0],[1,0]]},[0,.25,.5,1],stop=1,max_step=1,kernel=KERNEL,vabstol=1e-10,reltol=0)
        for t,row in zip([0,.25,.5,1],r['solutions']):
            self.assertAlmostEqual(row['voltages'][r['nodes'].index('y')],t,delta=1e-10)

    def test_duplicate_and_malformed_expansion_identities_still_reject(self):
        p=compile_sources({'loop-history.va':model('for(i=0;i<2;i=i+1) V(y,r)<+idt(i+1,0);','genvar i;')},[instance()]).to_dict()
        self.assertEqual(p['operators'][0]['origin']['expansion'], (('i',0),))
        for expansion in ((('i',0),), (('',1),), (('i',1),)*65):
            raw=copy.deepcopy(p)
            raw['operators'][1]['origin']['expansion']=expansion
            request=dict(program=raw,driven=['u'],samples=[],transient=dict(pwl=[[[0,0],[1,0]]],output_times=[0,1],stop=1,max_step=1))
            result=subprocess.run([str(KERNEL)],input=json.dumps(request),text=True,capture_output=True)
            self.assertEqual(result.returncode,2)
            self.assertEqual(json.loads(result.stderr)['kind'],'invalid_ir')
