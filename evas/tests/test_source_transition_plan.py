"""Source-target schedules use independent ramp, integral and filter answers.

These are development obligations for N08d, not revised historical scores.
"""
GUARDS = ['TRANSITION', 'DYNAMICS', 'COMPOSE', 'EVENT-ORDER']
import math
import unittest
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL


def program(body, declarations=''):
    source = ('`include "disciplines.vams"\n'
              'module m(u,y,z,r); input u; output y,z; inout r; '
              'electrical u,y,z,r; ' + declarations + ' analog begin '
              + body + ' end endmodule')
    return compile_sources({'source-target.va': source},
                           [Instance('dut', 'm', {'u':'u', 'y':'y', 'z':'z', 'r':'0'})])


def evaluate(p, times, *, stop=1., step=1., forced=False, pwl=None):
    return transient(p, {'u': pwl or [[0.,0.],[stop,stop]]}, times,
                     stop=stop, max_step=step, vabstol=1e-8, reltol=0.,
                     strobetimes=times if forced else None, kernel=KERNEL, timeout=30)


def ramp(t, start=.25, duration=.125):
    t, start, duration = map(Fraction, (t, start, duration))
    return min(Fraction(1), max(Fraction(0), (t-start)/duration))


def integral(t, start=.25, duration=.125):
    t, start, duration = map(Fraction, (t, start, duration))
    s=max(Fraction(0), t-start)
    return s*s/(2*duration) if s <= duration else s-duration/2


def filtered(t, start=.25, duration=.125, tau=.125):
    s=max(0.,t-start); a=min(s,duration)
    rising=(a+tau*math.expm1(-a/tau))/duration
    return rising if s <= duration else 1+(rising-1)*math.exp(-(s-duration)/tau)


def exp_enclosure(x):
    """Enclose exp of an exact rational, independently of kernel arithmetic."""
    x = Fraction(x)
    if not x:
        return Fraction(1), Fraction(1)
    with localcontext() as ctx:
        ctx.prec = 90
        ctx.rounding = ROUND_FLOOR
        lo = Decimal(x.numerator) / Decimal(x.denominator)
        ctx.rounding = ROUND_CEILING
        hi = Decimal(x.numerator) / Decimal(x.denominator)
        # Decimal.exp is correctly rounded with HALF_EVEN. One adjacent
        # Decimal on each side encloses that rounding error. Exp is monotone.
        ctx.rounding = ROUND_HALF_EVEN
        return Fraction(lo.exp().next_minus()), Fraction(hi.exp().next_plus())


def filtered_enclosure(t, start=.25, duration=.125, tau=.125, offset=0):
    """Exact rational propagation around a 90-digit exponential enclosure."""
    t, start, duration, tau, offset = map(Fraction, (t, start, duration, tau, offset))
    s = max(Fraction(0), t-start)
    if not s:
        return offset, offset
    a = min(s, duration)
    elo, ehi = exp_enclosure(-a/tau)
    lo, hi = ((a-tau+tau*e)/duration for e in (elo, ehi))
    if s > duration:
        tail = exp_enclosure(-(s-duration)/tau)
        products = [(value-1)*e for value in (lo, hi) for e in tail]
        lo, hi = 1+min(products), 1+max(products)
    return lo+offset, hi+offset


class SourceTransitionPlan(unittest.TestCase):
    def assert_node(self, result, times, node, oracle, *, enclosure=None):
        self.assertEqual(len(result['solutions']),len(times))
        self.assertIn('observation_evidence', result)
        evidence = result['observation_evidence']
        self.assertEqual(evidence['nodes'], result['nodes'])
        bounds = evidence['voltage_bounds_V']
        self.assertEqual(len(bounds), len(times))
        i=result['nodes'].index(node)
        for t,row,intervals in zip(times,result['solutions'],bounds,strict=True):
            self.assertAlmostEqual(row['voltages'][i],oracle(t),delta=1e-8)
            self.assertLessEqual(row['max_residual_ratio'],1)
            self.assertIsNotNone(intervals)
            self.assertEqual(len(intervals), len(result['nodes']))
            interval = intervals[i]
            self.assertEqual(len(interval), 2)
            self.assertTrue(all(math.isfinite(value) for value in interval))
            lo, hi = map(Fraction, interval)
            value = Fraction(row['voltages'][i])
            self.assertLessEqual(lo, value)
            self.assertLessEqual(value, hi)
            expected_lo, expected_hi = (enclosure(t) if enclosure is not None
                                       else (Fraction(oracle(t)), Fraction(oracle(t))))
            self.assertLessEqual(expected_lo, expected_hi)
            self.assertLessEqual(lo, expected_lo)
            self.assertLessEqual(expected_hi, hi)
            self.assertLessEqual(max(value-lo, hi-value), Fraction(1e-8))

    def test_source_only_delay_and_query_grid_invariance(self):
        for delay in (0.,.25):
            p=program(f'V(y,r)<+transition(V(u,r)>0.25?1.0:0.0,{delay},0.125,0.125); V(z,r)<+0;')
            sparse=[0.,.25,.28125,.3125,.375,.5,.5625,.625,1.]
            dense=sorted(set(sparse+[i/64 for i in range(65)]))
            # No observation or controller step at the source cut or delayed
            # activation. A query-driven target update misses these ramps.
            blind=[0.,.3125+delay,1.]
            hidden=evaluate(p,blind,step=1.)
            self.assert_node(hidden,blind,'y',lambda t:ramp(t,.25+delay))
            baseline=evaluate(p,sparse)
            self.assert_node(baseline,sparse,'y',lambda t:ramp(t,.25+delay))
            self.assertEqual(baseline['transient']['events'],[])
            for step,forced in [(1.,True),(.03125,False)]:
                result=evaluate(p,dense,step=step,forced=forced)
                self.assert_node(result,dense,'y',lambda t:ramp(t,.25+delay))
                self.assertEqual(result['transient']['events'],[])
                self.assertEqual(baseline['solutions'],[result['solutions'][dense.index(t)] for t in sparse])

    def test_same_time_timer_disables_source_before_future_target(self):
        times=[0.,.25,.28125,.375,.5,1.]
        for order in (False,True):
            events=['@(timer(0.25,0,0)) enable=0;', '@(timer(0.25,0,0)) n=n+1;']
            if order: events.reverse()
            p=program('@(initial_step) begin enable=1; n=0; end '+''.join(events)+
                      'V(y,r)<+transition(enable?(V(u,r)>0.25?1.0:0.0):0.0,0,0.125,0.125); V(z,r)<+n;',
                      'integer enable,n;')
            r=evaluate(p,times)
            self.assert_node(r,times,'y',lambda t:0.)
            self.assert_node(r,times,'z',lambda t:float(t>=.25))

    def test_root_zero_point_seed_and_right_mode(self):
        times=[0.,.03125,.0625,.125,.5,1.]
        for relation in ('>','>='):
            p=program(f'V(y,r)<+transition(V(u,r){relation}0?1.0:0.0,0,0.125,0.125); V(z,r)<+0;')
            r=evaluate(p,times)
            self.assert_node(r,times,'y',lambda t:1. if relation=='>=' else ramp(t,0.))
        p=program('@(initial_step) enable=1; @(timer(0,0,0)) enable=0; '
                  'V(y,r)<+transition(enable?(V(u,r)>0?1.0:0.0):0.0,0,0.125,0.125); V(z,r)<+0;',
                  'integer enable;')
        self.assert_node(evaluate(p,times),times,'y',lambda t:0.)

    def test_masked_old_cuts_do_not_replay_when_enabled(self):
        p=program('@(initial_step) enable=0; @(timer(0.75,0,0)) enable=1; '
                  'V(y,r)<+transition(enable?(V(u,r)>0.25?1.0:0.0):0.0,0,0.125,0.125); V(z,r)<+0;',
                  'integer enable;')
        times=[0.,.25,.5,.75,.78125,.8125,.875,1.]
        self.assert_node(evaluate(p,times),times,'y',lambda t:ramp(t,.75))

    def test_affine_held_leaves_and_value_only_update(self):
        p=program('@(initial_step) a=1; @(timer(0.5,0,0)) a=2; '
                  'V(y,r)<+transition(V(u,r)>0.25?2*a+0.5:a-0.25,0,0.125,0.125); '
                  'V(z,r)<+a;', 'integer a;')
        times=[0.,.3125,.375,.5,.5625,.625,1.]
        # Seed 3/4; source cut raises target by 7/4; the later held update
        # raises it by 2 without changing any source-predicate dependency.
        def expected(t):
            return Fraction(3,4)+Fraction(7,4)*ramp(t)+2*ramp(t,.5)
        self.assertEqual(expected(.3125), Fraction(13,8))
        self.assertEqual(expected(.5625), Fraction(7,2))
        r=evaluate(p,times)
        self.assert_node(r,times,'y',expected)
        self.assert_node(r,times,'z',lambda t:1+int(t>=.5))

    def test_root_zero_final_closure_seed_after_timer_disable(self):
        p=program('@(initial_step) enable=1; @(timer(0,0,0)) enable=0; '
                  'V(y,r)<+transition(enable?(V(u,r)>=0?1.0:0.0):0.0,0,0.125,0.125); '
                  'V(z,r)<+enable;', 'integer enable;')
        times=[0.,.03125,.0625,.125,.5,1.]
        # Versioned semantic correction from actual evidence in the daily
        # checkout: runs/evas-night-20261014/remote/n18-initialization-v1/ANALYSIS-v1.json
        # Ordinary timer(0) closes held state before the point seed is chosen.
        # The old pre-timer seed expectation is archived in
        # runs/evas-night-20261014/review/astra-n18-actual/test-update/.
        r=evaluate(p,times)
        self.assert_node(r,times,'y',lambda t:0)
        self.assert_node(r,times,'z',lambda t:0)

    def test_source_history_drives_integral_and_filter(self):
        times=[0.,.25,.28125,.3125,.375,.5,1.]
        edge='V(e,r)<+transition(V(u,r)>0.25?1.0:0.0,0,0.125,0.125);'
        p=program(edge+"V(y,r)<+laplace_nd(V(e,r),'{1},'{1,0.125}); V(z,r)<+idt(V(e,r),0);",'electrical e;')
        for forced in (False,True):
            r=evaluate(p,times,forced=forced)
            self.assert_node(r,times,'y',filtered,enclosure=filtered_enclosure)
            self.assert_node(r,times,'z',integral)

    def test_forward_filter_uses_same_nonzero_seed(self):
        times=[0.,.25,.3125,.375,.5,1.]
        edge='V(e,r)<+transition(V(u,r)>0.25?3.0:2.0,0,0.125,0.125);'
        filt="V(y,r)<+laplace_nd(V(e,r),'{1},'{1,0.125});"
        for forward in (False,True):
            p=program((filt+edge if forward else edge+filt)+'V(z,r)<+V(e,r);','electrical e;')
            r=evaluate(p,times)
            self.assert_node(r,times,'y',lambda t:2+filtered(t),
                             enclosure=lambda t:filtered_enclosure(t,offset=2))
            self.assert_node(r,times,'z',lambda t:2+ramp(t))

    def test_source_cut_at_old_edge_end_consumes_old_history(self):
        p=program('V(y,r)<+transition((V(u,r)>0.25 && V(u,r)<0.5)?1.0:0.0,0,0.25,0.25); '
                  'V(z,r)<+idt(V(y,r),0);')
        times=[0.,.25,.375,.5,.625,.75,1.]
        def triangle(t):return ramp(t,.25,.25)-ramp(t,.5,.25)
        def area(t):return integral(t,.25,.25)-integral(t,.5,.25)
        r=evaluate(p,times)
        self.assert_node(r,times,'y',triangle);self.assert_node(r,times,'z',area)

    def test_isolated_point_and_third_value_are_not_two_sided_steps(self):
        for target in ['V(u,r)==0.25?1.0:0.0',
                       'V(u,r)==0.25?2.0:(V(u,r)>0.25?1.0:0.0)']:
            with self.subTest(target=target),self.assertRaises(KernelError):
                evaluate(program(f'V(y,r)<+transition({target},0,0.125,0.125); V(z,r)<+0;'),[0.,.25,1.])

    def test_boundary_left_target_uses_old_held_epoch(self):
        # Before t=.25 q=0 gives L=0. Final q=1 gives P=2 and R=1.
        # Recomputing old L using new q would silently turn this into 2/2/1.
        p=program('@(initial_step) q=0; @(timer(0.25,0,0)) q=1; '
                  'V(y,r)<+transition(V(u,r)<=0.25?2*q:q,0,0.125,0.125); V(z,r)<+0;',
                  'integer q;')
        with self.assertRaises(KernelError): evaluate(p,[0.,.25,.5,1.])

    def test_unproved_source_cuts_and_structural_dependencies_reject(self):
        for target in ['3*V(u,r)>1?1.0:0.0',
                       'V(u,r)>0.25?V(u,r):0.0',
                       '(V(u,r)>0.25?1.0:0.0)+0*V(z,r)',
                       'V(u,r)*V(u,r)>0.25?1.0:0.0']:
            with self.subTest(target=target),self.assertRaises((CompileError,KernelError)):
                evaluate(program(f'V(y,r)<+transition({target},0,0.125,0.125); V(z,r)<+0;'),[0.,.5,1.])

class SourceTransitionOracleCalibration(unittest.TestCase):
    """Checker controls run without a simulator or any implementation oracle."""

    @staticmethod
    def response(value, interval):
        return {'nodes':['y'],
                'solutions':[{'voltages':[value], 'max_residual_ratio':0.}],
                'observation_evidence':{'nodes':['y'], 'voltage_bounds_V':[[interval]]}}

    def test_exact_ramp_and_integral_controls(self):
        self.assertEqual(ramp(.3125), Fraction(1,2))
        self.assertEqual(integral(.3125), Fraction(1,64))
        self.assertEqual(integral(1.), Fraction(11,16))
        checker=SourceTransitionPlan()
        checker.assert_node(self.response(.5,[.5,.5]),[.3125],'y',ramp)
        checker.assert_node(self.response(.5,[math.nextafter(.5,-math.inf),
                                               math.nextafter(.5,math.inf)]),
                            [.3125],'y',ramp)

    def test_wrong_narrow_interval_previously_passed_point_check(self):
        value=.500000001
        # The previous two assertions both accept this response. It has a
        # finite ordered interval containing its representative, but not 1/2.
        self.assertAlmostEqual(value,.5,delta=1e-8)
        self.assertLessEqual(0.,1)
        with self.assertRaises(AssertionError):
            SourceTransitionPlan().assert_node(self.response(value,[value,value]),
                                               [.3125],'y',ramp)

    def test_missing_nonfinite_and_overbudget_bounds_reject(self):
        checker=SourceTransitionPlan()
        for interval in ([.4,.6], [math.nan,.5], [.5,math.inf]):
            with self.subTest(interval=interval),self.assertRaises(AssertionError):
                checker.assert_node(self.response(.5,interval),[.3125],'y',ramp)
        missing=self.response(.5,[.5,.5]);del missing['observation_evidence']
        null=self.response(.5,[.5,.5]);null['observation_evidence']['voltage_bounds_V']=[None]
        for response in (missing,null):
            with self.subTest(response=response),self.assertRaises(AssertionError):
                checker.assert_node(response,[.3125],'y',ramp)

    def test_decimal_exp_enclosure_against_exact_alternating_series(self):
        for x in (Fraction(-1),Fraction(-1,3)):
            # For -1 <= x < 0 the decreasing alternating terms give an
            # exact rational bracket: partial sum 81 <= exp(x) <= sum 80.
            term=Fraction(1);upper=term
            for n in range(1,81):
                term*=x/n
                upper+=term
            lower=upper+term*x/81
            lo,hi=exp_enclosure(x)
            self.assertLessEqual(lo,lower)
            self.assertLessEqual(upper,hi)
            self.assertLess(hi-lo,Fraction(1,10**85))
            if x == -1:
                # At the end of a unit ramp with tau=duration, y=exp(-1).
                flo,fhi=filtered_enclosure(.375)
                self.assertLessEqual(flo,lower)
                self.assertLessEqual(upper,fhi)
        self.assertEqual(filtered_enclosure(0.),(0,0))
        self.assertEqual(filtered_enclosure(0.,offset=2),(2,2))
        value=filtered(.375)
        interval=[math.nextafter(value,-math.inf),math.nextafter(value,math.inf)]
        SourceTransitionPlan().assert_node(self.response(value,interval),[.375],
                                           'y',filtered,enclosure=filtered_enclosure)
        with self.assertRaises(AssertionError):
            SourceTransitionPlan().assert_node(self.response(value,[value,value]),[.375],
                                               'y',filtered,enclosure=filtered_enclosure)


if __name__=='__main__':unittest.main()
