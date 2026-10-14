"""An exactly represented switch remains usable at an integration boundary."""
GUARDS=['DYNAMICS','COMPOSE','LANG']
import unittest
import math
from fractions import Fraction
from evas import KernelError,compile_sources,transient
from test_affine import KERNEL,instance,model

class ExactPredicateEndpoints(unittest.TestCase):
    def test_ordinary_endpoint_uncertainty_never_erases_a_finite_integral(self):
        endpoint = math.nextafter(1/3, math.inf)
        exact = Fraction(10**10) * (1 - 1/(3*Fraction(endpoint)))
        self.assertGreater(exact, Fraction(1e-9))
        # The ordinary predicate used to bypass the complete root scan and
        # certify zero. Equivalent nesting must not change this safety rule.
        for predicate in ('3*V(u,r)>1', '(3*V(u,r)>1?1:0)>0.5'):
            p = compile_sources({'uncertain-endpoint.va': model(
                'V(y,r)<+idt(('+predicate+')?1e10:0,0);')}, [instance()])
            # The triangular source has the same area, split around an
            # interior PWL corner. Both endpoints and corners need evidence.
            for source in ([[0.,0.],[1.,endpoint]],
                           [[0.,0.],[.5,endpoint],[1.,0.]]):
              for times in ([0.,1.], [0.,.5,1.]):
                with self.subTest(predicate=predicate,times=times,source=source):
                    try:
                        r=transient(p,{'u':source},times,
                            stop=1.,max_step=.125,vabstol=1e-9,reltol=1e-6,
                            kernel=KERNEL,timeout=15)
                    except KernelError as error:
                        self.assertIn('condition_precision',str(error))
                    else:
                        y=r['nodes'].index('y')
                        lo,hi=r['observation_evidence']['voltage_bounds_V'][-1][y]
                        self.assertLessEqual(Fraction(lo),exact)
                        self.assertGreaterEqual(Fraction(hi),exact)
                        error=abs(Fraction(r['solutions'][-1]['voltages'][y])-exact)
                        self.assertLessEqual(error,Fraction(1e-9)+Fraction(1e-6)*abs(exact))

    def test_ordinary_exact_zero_endpoint_and_held_mode_remain_usable(self):
        p=compile_sources({'exact-endpoint.va':model('''
            @(initial_step) q=1;
            V(y,r)<+idt((q>0 && V(u,r)>0)?2:0,0);
        ''','integer q;')},[instance()])
        times=[0.,.25,.5,1.]
        r=transient(p,{'u':[[0.,0.],[1.,1.]]},times,stop=1.,
            max_step=.125,vabstol=1e-9,reltol=0.,kernel=KERNEL,timeout=15)
        y=r['nodes'].index('y')
        for t,row in zip(times,r['solutions'],strict=True):
            self.assertLessEqual(abs(row['voltages'][y]-2*t),1e-9)

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
