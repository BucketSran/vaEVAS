"""An exactly represented switch remains usable at an integration boundary."""
GUARDS=['DYNAMICS','COMPOSE','LANG']
import unittest
from evas import compile_sources,transient
from test_affine import KERNEL,instance,model

class ExactPredicateEndpoints(unittest.TestCase):
    def test_cross_horizon_matches_exact_nested_source_predicate(self):
        p=compile_sources({'endpoint.va':model('''
            @(initial_step) n=0;
            @(cross(V(u,r)-0.5,+1)) n=n+1;
            V(y,r)<+idt(((V(u,r)>0.25?V(u,r):0)>0.5?1.0:0.0),0)+0*n;
        ''','integer n;')},[instance()])
        times=[0.,0.25,0.5,0.75,1.]
        for forced in [False,True]:
            kwargs={'strobetimes':times} if forced else {}
            r=transient(p,{'u':[[0.,0.],[1.,1.]]},times,stop=1.,max_step=0.125,
                vabstol=1e-8,reltol=0.,kernel=KERNEL,timeout=15,**kwargs)
            y=r['nodes'].index('y')
            for t,row in zip(times,r['solutions']):
                self.assertAlmostEqual(row['voltages'][y],max(t-0.5,0),places=8)

    def test_decimal_knots_with_exactly_representable_midpoint(self):
        from fractions import Fraction
        a,b=3e-8,3.02e-8
        root=(Fraction(a)+Fraction(b))/2
        self.assertEqual(Fraction(3.01e-8),root)
        p=compile_sources({'endpoint-ns.va':model('''
            @(initial_step) n=0;
            @(cross(V(u,r)-0.9,+1)) n=n+1;
            V(y,r)<+idt(((V(u,r)>0.45?V(u,r):0)>0.9?1e8:0.0),0)+0*n;
        ''','integer n;')},[instance()])
        times=[0.,a,float(root),b,4e-8]
        for forced in [False,True]:
            kwargs={'strobetimes':times} if forced else {}
            r=transient(p,{'u':[[0.,0.],[a,0.],[b,1.8],[4e-8,1.8]]},times,
                stop=4e-8,max_step=1e-9,vabstol=1e-8,reltol=0.,kernel=KERNEL,timeout=15,**kwargs)
            y=r['nodes'].index('y')
            for t,row in zip(times,r['solutions']):
                expected=float(max(Fraction(t)-root,0)*100000000)
                self.assertAlmostEqual(row['voltages'][y],expected,places=8)

if __name__=='__main__':unittest.main()
