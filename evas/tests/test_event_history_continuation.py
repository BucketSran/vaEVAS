"""Physical history at ordered near-clock events, with independent integral answers."""
GUARDS = ["TIMER", "EVENT-ORDER", "DYNAMICS", "CROSS", "COMPOSE"]
from fractions import Fraction as Q
import math
import unittest
from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model
NONLINEAR = 'module m(u,y,r); input u; output y; inout r; electrical u,y,r; integer n,m,h;real s;electrical z; analog begin @(initial_step) begin n=0;m=0;h=0;s=1;end\n@(timer(2e-6,2e-6,1e-9)) n=n+1;\n@(timer(3e-6,3e-6,1e-9)) begin m=m+1;s=V(z,r);end\nV(z,r)<+idt(-1e6*(n+10*m)*V(z,r)*V(z,r),1);\n@(cross(V(z,r)-100,1,1e-12,1e-7)) h=h+1; V(y,r)<+s; end endmodule'
LINEAR_PWL = 'module m(u,y,r); input u; output y; inout r; electrical u,y,r; integer n,m,h;real s;electrical z; analog begin @(initial_step) begin n=0;m=0;h=0;s=1;end\n@(timer(2e-6,2e-6,1e-9)) n=n+1;\n@(timer(3e-6,3e-6,1e-9)) begin m=m+1;s=V(z,r);end\nV(z,r)<+idt(1e6*(n+10*m+V(u,r)),0);\n@(cross(V(z,r)-1000,1,1e-12,1e-7)) h=h+1;V(y,r)<+s; end endmodule'

class EventHistoryContinuation(unittest.TestCase):
    def check_case(self, source, pwl, nonlinear):
        a,b,c,T = map(Q,[2e-6,3e-6,6e-6,7e-6])
        area = Q(1e6)*(sum(T-k*a for k in (1,2,3))+10*sum(T-k*b for k in (1,2)))
        sample_area = Q(1e6)*(sum(2*b-k*a for k in (1,2,3))+10*b)
        def source_area(end):
            total=Q(0)
            for (ta,ua),(tb,ub) in zip(pwl,pwl[1:]):
                ta,ua,tb,ub=map(Q,[ta,ua,tb,ub])
                if ta >= end:break
                duration=min(tb,end)-ta
                total+=ua*duration+(ub-ua)*duration*duration/(2*(tb-ta))
            return Q(1e6)*total
        uses_source = 'n+10*m+V(u,r)' in source
        final_area = area+(source_area(T) if uses_source else 0)
        sampled_area = sample_area+(source_area(2*b) if uses_source else 0)
        final = 1/(1+final_area) if nonlinear else final_area
        sampled = 1/(1+sampled_area) if nonlinear else sampled_area
        baseline = None
        for times,step in [([0,float(T)],float(T)),([0,2.5e-6,3.5e-6,6.5e-6,float(T)],1.1e-7)]:
            result = transient(compile_sources({'continuation.va':source},[instance()]),
                {'u':pwl},times,stop=float(T),max_step=step,vabstol=1e-7,reltol=1e-8,kernel=KERNEL)
            self.assertEqual(result['transient']['states'][-1][:3],[3,2,0])
            self.assertAlmostEqual(result['transient']['states'][-1][3],float(sampled),delta=1e-7)
            self.assertAlmostEqual(result['solutions'][-1]['voltages'][result['nodes'].index('dut:z')],float(final),delta=1e-7)
            events=result['transient']['events']
            self.assertEqual([e['event'] for e in events],[i for _,i in sorted([(k*a,0) for k in (1,2,3)]+[(k*b,1) for k in (1,2)])])
            if baseline is not None:
                for actual,expected in zip(events,baseline):
                    for key in ('event','kind','time','observation_time_bounds'):
                        self.assertEqual(actual.get(key),expected.get(key))
                    for key in ('before','after'):
                        for x,y in zip(actual[key],expected[key]):
                            self.assertAlmostEqual(x,y,delta=1e-7)
            baseline=events
    def test_nonlinear_physical_state_across_ordered_timer_windows(self):
        self.check_case(NONLINEAR,[[0,0],[7e-6,1]],True)
    def test_linear_physical_state_across_pwl_corner(self):
        self.check_case(LINEAR_PWL,[[0,0],[6e-6,1],[7e-6,1]],False)

    def test_three_clock_nonlinear_chain_preserves_physical_sampling(self):
        import math
        source=NONLINEAR.replace('integer n,m,h;', 'integer n,m,h,p;')
        source=source.replace('n=0;m=0;h=0;s=1;', 'n=0;m=0;h=0;p=0;s=1;')
        source=source.replace('V(y,r)<+', f'@(timer({math.nextafter(6e-6,math.inf)!r},0,1e-9)) p=p+1;V(y,r)<+')
        result=transient(compile_sources({'three.va':source},[instance()]),{'u':[[0,0],[7e-6,1]]},[0,7e-6],stop=7e-6,max_step=7e-6,vabstol=1e-7,reltol=1e-8,kernel=KERNEL)
        self.assertEqual(result['transient']['states'][-1][:3],[3,2,0])
        self.assertEqual(result['transient']['states'][-1][3],1)
        expected=sorted([(Q(2e-6)*k,0) for k in (1,2,3)]+[(Q(3e-6)*k,1) for k in (1,2)]+[(Q(math.nextafter(6e-6,math.inf)),3)])
        self.assertEqual([e['event'] for e in result['transient']['events']],[i for _,i in expected])

    def test_nonlinear_sample_uncertainty_cannot_hide_after_amplification(self):
        from evas import KernelError
        source=NONLINEAR.replace('V(y,r)<+s;', 'V(y,r)<+1e6*s;')
        with self.assertRaisesRegex(KernelError,'waveform_accuracy|state_accuracy|numerical_accuracy'):
            transient(compile_sources({'amplified.va':source},[instance()]),{'u':[[0,0],[7e-6,1]]},[0,7e-6],stop=7e-6,max_step=7e-6,vabstol=1e-7,reltol=0,kernel=KERNEL)

    def test_nonlinear_ordered_history_with_pwl_forcing(self):
        source=NONLINEAR.replace('(n+10*m)', '(n+10*m+V(u,r))')
        self.check_case(source,[[0,0],[6e-6,1],[7e-6,1]],True)

    def test_linear_event_window_spans_two_source_corners(self):
        import math
        self.check_case(LINEAR_PWL,[[0,0],[math.nextafter(6e-6,-math.inf),1],
            [6e-6,0.5],[math.nextafter(6e-6,math.inf),1],[7e-6,1]],False)

    def test_linear_corner_uncertainty_cannot_bypass_voltage_budget(self):
        program = compile_sources({'corner-budget.va': LINEAR_PWL}, [instance()])
        corner = math.nextafter(6e-6, -math.inf)
        # Both sources are zero before the corner, so the unchanged prefix
        # must pass. The amplified slope makes the later event enclosure too
        # wide for the same absolute voltage budget; it cannot be discarded.
        for amplitude in (1.0, 1e6):
            source = {'u': [[0, 0], [corner, 0], [6e-6, amplitude], [7e-6, amplitude]]}
            prefix = transient(program, source, [0, 5e-6], stop=5e-6,
                max_step=7e-6, vabstol=1e-7, reltol=0, kernel=KERNEL)
            expected = Q(1e6) * (sum(Q(5e-6)-k*Q(2e-6) for k in (1, 2))
                                      + 10*(Q(5e-6)-Q(3e-6)))
            self.assertAlmostEqual(prefix['solutions'][-1]['voltages'][
                prefix['nodes'].index('dut:z')], float(expected), delta=1e-7)
            if amplitude == 1:
                transient(program, source, [0, 7e-6], stop=7e-6,
                    max_step=7e-6, vabstol=1e-7, reltol=0, kernel=KERNEL)
            else:
                with self.assertRaisesRegex(KernelError,
                        'waveform_accuracy.*same-time forward error at dut:z'):
                    transient(program, source, [0, 7e-6], stop=7e-6,
                        max_step=7e-6, vabstol=1e-7, reltol=0, kernel=KERNEL)

    def test_near_clock_reset_release_preserves_downstream_filter(self):
        tau = Q(.1) + Q(.2)
        rho = Q(math.nextafter(.3, math.inf))
        self.assertLess(tau, rho)
        duration = float(Q(.31)-rho)
        # y'+y=z, y(0)=z(0)=2. Before reset z=2+t; during
        # [tau,rho] z=2; after release z=2+(t-rho). The filter
        # retains its own state through both reset and release.
        y_tau = 1 + float(tau) + math.exp(-float(tau))
        y_rho = 2 + (y_tau-2)*math.exp(-float(rho-tau))
        expected = {'dut:z': 2+duration,
                    'y': 1+duration+(y_rho-1)*math.exp(-duration)}
        for nonlinear in (False, True):
            with self.subTest(nonlinear=nonlinear):
                flow = '1+pow(V(u,r),2)' if nonlinear else '1+V(u,r)'
                source = model(f'''@(initial_step) begin n=0;rst=0;h=0;end
                    @(timer(.1,.2,1e-6)) begin n=n+1;rst=n-1;end
                    @(timer({float(rho)!r},0,1e-6)) rst=0;
                    V(z,r)<+idt({flow},2,rst);
                    V(y,r)<+laplace_nd(V(z,r),'{{1}},'{{1,1}});
                    @(cross(V(y,r)-100,1,1e-12,1e-9)) h=h+1;''',
                    'integer n,rst,h; electrical z;')
                program = compile_sources({'reset-release.va': source}, [instance()])
                reference_events = None
                for times, step in (([0, .31], .31),
                                    ([0, .05, .15, .25, .305, .31], .01)):
                    result = transient(program,
                        {'u': [[0, 0], [.3, 0], [float(rho), 0], [.31, 0]]}, times,
                        stop=.31, max_step=step, vabstol=1e-8, reltol=0, kernel=KERNEL)
                    for node, value in expected.items():
                        self.assertAlmostEqual(result['solutions'][-1]['voltages'][
                            result['nodes'].index(node)], value, delta=1e-8)
                    self.assertEqual(result['transient']['states'][-1], [2, 0, 0])
                    events = result['transient']['events']
                    self.assertEqual([e['event'] for e in events], [0, 0, 1])
                    for event in events[1:]:
                        self.assertIn('observation_time_bounds', event)
                    identities = [(e['event'], e['time'], e.get('observation_time_bounds'))
                                  for e in events]
                    if reference_events is not None:
                        self.assertEqual(identities, reference_events)
                    reference_events = identities
