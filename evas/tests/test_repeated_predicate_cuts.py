"""Repeated source expressions share root analysis without dropping obligations."""
GUARDS=['DYNAMICS','COMPOSE','LANG']
import unittest
from evas import compile_sources,transient
from test_affine import KERNEL,instance,model

class RepeatedPredicateCuts(unittest.TestCase):
    def test_repeated_predicate_and_redundant_pwl_knots_do_not_exhaust_root_analysis(self):
        term='((V(u,r)>0.25?V(u,r):0)>0.5?1.0:0.0)'
        body='V(y,r)<+idt('+ '+'.join([term]*64)+',0);'
        p=compile_sources({'repeated.va':model(body)},[instance()])
        times=[0.,0.25,0.5,0.75,1.]
        r=transient(p,{'u':[[k/128,k/128] for k in range(129)]},times,
                    stop=1.,max_step=0.125,vabstol=1e-8,reltol=0.,kernel=KERNEL,timeout=15)
        y=r['nodes'].index('y')
        for t,row in zip(times,r['solutions']):self.assertAlmostEqual(row['voltages'][y],64*max(t-0.5,0),places=8)

if __name__=='__main__':unittest.main()
