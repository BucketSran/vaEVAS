"""Near-clock/history composition, with exact Fraction count and area answers."""
GUARDS = ["TIMER", "EVENT-ORDER", "DYNAMICS", "CROSS", "COMPOSE"]

from fractions import Fraction as Q
import math
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model



def clocks_with_history(threshold=100.0):
    return model(f'''@(initial_step) begin n=0; m=0; h=0; end
        @(timer(2e-6,2e-6,1e-9)) n=n+1;
        @(timer(3e-6,3e-6,1e-9)) m=m+1;
        V(z,r)<+idt(1e6*n,0);
        @(cross(V(z,r)-{threshold!r},1,1e-12,1e-7)) h=h+1;
        V(y,r)<+n+10*m+100*h;''', 'integer n,m,h; electrical z;')


def run_history(source, *, stop=7e-6, times=None, step=7e-6):
    program = compile_sources({'history.va':source},[instance()])
    return transient(program, {'u':[[0,0],[stop,stop]]},times or [0,stop],
                     stop=stop,max_step=step,vabstol=1e-7,reltol=1e-8,kernel=KERNEL)


class TimerHistoryOrder(unittest.TestCase):
    def test_monitor_does_not_discard_certified_fixed_timer_order(self):
        result = run_history(clocks_with_history(), stop=7e-6, times=[0,7e-6])
        events = result['transient']['events']
        expected = sorted([(Q(2e-6)*(k+1), 0) for k in range(3)]
                          + [(Q(3e-6)*(k+1), 1) for k in range(2)])
        self.assertEqual([e['event'] for e in events], [i for _,i in expected])
        self.assertEqual(result['transient']['states'][-1], [3,2,0])
        z = result['solutions'][-1]['voltages'][result['nodes'].index('dut:z')]
        area = Q(1e6)*sum(Q(7e-6)-Q(2e-6)*(k+1) for k in range(3))
        self.assertAlmostEqual(z, float(area), delta=1e-7)

    def test_changed_history_still_finds_later_cross(self):
        result = run_history(clocks_with_history(8.0), stop=7e-6, times=[0,7e-6])
        self.assertEqual(result['transient']['states'][-1], [3,2,1])
        cross = [e for e in result['transient']['events'] if e['kind']=='cross']
        self.assertEqual(len(cross),1)
        # z(t)=1e6*(3*t - (1+2+3)*binary64(2us)).
        root = (Q(8)/Q(1e6)+6*Q(2e-6))/3
        bounds = cross[0]['observation_time_bounds']
        self.assertLessEqual(Q(bounds[0]), root)
        self.assertGreaterEqual(Q(bounds[1]), root)
        self.assertAlmostEqual(cross[0]['time'],float(root),delta=1e-10)

    def test_three_near_clocks_retain_the_entire_order_proof(self):
        third = math.nextafter(6e-6,math.inf)
        source = clocks_with_history().replace('integer n,m,h;', 'integer n,m,h,p;')
        source = source.replace('n=0; m=0; h=0;', 'n=0; m=0; h=0; p=0;')
        source = source.replace('V(y,r)<+', f'@(timer({third!r},0,1e-9)) p=p+1; V(y,r)<+')
        result = run_history(source)
        self.assertEqual(result['transient']['states'][-1], [3,2,0,1])
        # The added timer is declared after the cross, hence event leaf 3.
        expected = sorted([(Q(2e-6)*k,0) for k in (1,2,3)]
                          +[(Q(3e-6)*k,1) for k in (1,2)]+[(Q(third),3)])
        self.assertEqual([e['event'] for e in result['transient']['events']], [i for _,i in expected])

    def test_overlapping_timer_observes_history_and_changes_future_flow(self):
        source = model('''@(initial_step) begin n=0; m=0; h=0; s=0; end
          @(timer(2e-6,2e-6,1e-9)) n=n+1;
          @(timer(3e-6,3e-6,1e-9)) begin m=m+1; s=V(z,r); end
          V(z,r)<+idt(1e6*(n+10*m),0);
          @(cross(V(z,r)-100,1,1e-12,1e-7)) h=h+1;
          V(y,r)<+s;''', 'integer n,m,h; real s; electrical z;')
        baseline = None
        for times, step in [([0,7e-6],7e-6), ([0,2.5e-6,3.5e-6,6.5e-6,7e-6],1.1e-7)]:
            result = run_history(source, stop=7e-6, times=times, step=step)
            a,b,stop = Q(2e-6),Q(3e-6),Q(7e-6)
            sample = Q(1e6)*(sum(2*b-k*a for k in (1,2,3)) + 10*b)
            area = Q(1e6)*(sum(stop-k*a for k in (1,2,3))
                           +10*sum(stop-k*b for k in (1,2)))
            self.assertEqual(result['transient']['states'][-1][:3], [3,2,0])
            self.assertAlmostEqual(result['transient']['states'][-1][3],float(sample),delta=1e-7)
            z = result['solutions'][-1]['voltages'][result['nodes'].index('dut:z')]
            self.assertAlmostEqual(z,float(area),delta=1e-7)
            if baseline is not None:
                self.assertEqual(result['transient']['events'],baseline)
            baseline = result['transient']['events']

    def test_cross_inside_representative_delay_is_not_silently_lost(self):
        # The second timer changes q from zero to one at exact .1+.2.
        # Its root is tau + 1e-18, strictly before the rounded representative.
        tau = Q(.1)+Q(.2)
        root = tau+Q(1e-18)
        self.assertLess(tau,root)
        self.assertLess(root,Q(math.nextafter(.3,math.inf)))
        for extra in ['', '@(timer(0.30000000000000004,0,1e-6)) m=m+1;']:
            source = model(f'''@(initial_step) begin n=0; q=0; h=0; m=0; end
              @(timer(.1,.2,1e-6)) begin n=n+1; q=n-1; end
              {extra}
              V(z,r)<+idt(q,0);
              @(cross(V(z,r)-1e-18,1,1e-20,1e-20)) h=h+1;
              V(y,r)<+h;''','integer n,q,h,m; electrical z;')
            program = compile_sources({'hidden.va':source},[instance()])
            # A deliberately broad voltage budget isolates calendar safety;
            # the tight guard contract must still prevent a skipped crossing.
            with self.assertRaisesRegex(KernelError,'event_resolution.*timer observation window'):
                transient(program, {'u':[[0,0],[.31,.31]]},[0,.31],stop=.31,
                          max_step=.31, vabstol=1, reltol=0, kernel=KERNEL)

    def test_linear_filter_preserves_state_between_near_clocks(self):
        source = clocks_with_history().replace('idt(1e6*n,0)',
                                               "laplace_nd(n,'{1e6},'{1e6,1})")
        result = run_history(source)
        expected = sum(1-math.exp(-1e6*float(Q(7e-6)-k*Q(2e-6))) for k in (1,2,3))
        z = result['solutions'][-1]['voltages'][result['nodes'].index('dut:z')]
        self.assertAlmostEqual(z,expected,delta=1e-7)
        self.assertEqual(result['transient']['states'][-1], [3,2,0])

    def test_uncertified_history_and_source_corner_still_refuse(self):
        cases = [
            (clocks_with_history().replace('idt(1e6*n,0)', 'idt(n+V(z,r)*V(z,r),0)'),
             [[0,0],[7e-6,7e-6]], 'nonlinear history query outside accepted trajectory'),
            (clocks_with_history(), [[0,0],[6e-6,1],[7e-6,1]], 'PWL slope boundary'),
        ]
        for source,pwl,message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(KernelError,message):
                transient(compile_sources({'boundary.va':source},[instance()]),
                          {'u':pwl},[0,7e-6],stop=7e-6,max_step=7e-6,
                          vabstol=1e-7,reltol=1e-8,kernel=KERNEL)


if __name__ == '__main__':
    unittest.main()
