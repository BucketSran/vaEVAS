"""Physical event phases and dense forced grids, with exact area answers."""
GUARDS = ["DYNAMICS", "TIMER", "EVENT-ORDER", "COMPOSE"]

from fractions import Fraction as F
from decimal import Decimal, localcontext
import math
import unittest

from evas import compile_sources, transient
from test_affine import KERNEL, instance, model


class SampledIntegralStrobe(unittest.TestCase):
    def assert_request_accuracy(self, actual, exact, absolute, relative):
        # Compare the exported value with the independent exact rational,
        # rather than rounding the answer before forming the error.
        exact = F(exact)
        error = abs(F(actual)-exact)
        budget = F(absolute)+F(relative)*abs(exact)
        self.assertLessEqual(error, budget,
                             f"voltage error {float(error)} exceeds {float(budget)}")

    def test_dense_forced_grid_does_not_accumulate_near_zero_area_error(self):
        period = 2**-20
        source = model('''@(initial_step) h=-0.25;
            @(timer(T,T,1e-10)) h=V(u,r);
            V(y,r)<+idt(h/T,0.125);''', 'parameter real T=9.5367431640625e-7; real h;')
        program = compile_sources({'sample.va': source}, [instance()])
        times = [period*k/1024 for k in range(4097)]
        result = transient(program, {'u':[[0,0],[4*period,1]]}, [0,4*period],
                           stop=4*period, max_step=period/2048, strobetimes=times,
                           vabstol=1e-14, reltol=1e-10, kernel=KERNEL)
        index = result['nodes'].index('y')
        for t, row in zip(times, result['strobe_evidence']['voltages_V']):
            tau = F(t)/F(period)
            exact = F(1,8)-min(tau,F(1))/4
            for k in (1,2,3):
                exact += F(k,4)*max(F(0), min(tau,F(k+1))-k)
            self.assert_request_accuracy(row[index], exact, 1e-14, 1e-10)
        self.assertEqual(result['strobe_evidence']['sample_origins'],
                         ['accepted_controller_frame']*len(times))

    def test_local_clock_phase_can_be_an_accepted_forced_point(self):
        source = model('''@(initial_step) begin n=0; m=0; s=0; end
            @(timer(2e-6,2e-6,1e-10)) n=n+1;
            @(timer(3e-6,3e-6,1e-10)) begin m=m+1; s=V(z,r); end
            V(z,r)<+idt(1e6*n,0); V(y,r)<+s;''',
            'integer n,m; real s; electrical z;')
        program = compile_sources({'clock.va':source},[instance()])
        times=[0, math.nextafter(6e-6,-math.inf), 6e-6,
               math.nextafter(6e-6,math.inf), 7e-6]
        result=transient(program,{'u':[[0,0],[7e-6,0]]},times,stop=7e-6,
                         max_step=7e-6,strobetimes=times,vabstol=1e-14,
                         reltol=1e-10,kernel=KERNEL)
        a,b=F(2e-6),F(3e-6)
        for t, row, state in zip(times,result['solutions'],result['transient']['states']):
            exact=F(1e6)*sum(max(F(0),F(t)-k*a) for k in (1,2,3))
            self.assert_request_accuracy(row['voltages'][result['nodes'].index('dut:z')],exact,1e-14,1e-10)
            self.assertEqual(state[:2],[sum(k*a<=F(t) for k in (1,2,3)),
                                         sum(k*b<=F(t) for k in (1,2))])
        self.assertEqual(result['strobe_evidence']['sample_origins'],
                         ['accepted_controller_frame']*len(times))

    def test_forced_point_between_distinct_near_events_keeps_future_sample_pending(self):
        source=model('''@(initial_step) begin n=0; m=0; s=0; end
            @(timer(0.1,0.2,1e-6)) begin n=n+1; s=V(z,r); end
            @(timer(0.3,0,1e-6)) m=m+1;
            V(z,r)<+idt(n,0); V(y,r)<+s;''',
            'integer n,m; real s; electrical z;')
        program=compile_sources({'prefix.va':source},[instance()])
        times=[0,.1,math.nextafter(.3,-math.inf),.3,
               math.nextafter(.3,math.inf),.4]
        result=transient(program,{'u':[[0,0],[.4,0]]},times,stop=.4,max_step=.4,
                         strobetimes=times,vabstol=1e-12,reltol=1e-10,kernel=KERNEL)
        for t, state, row in zip(times,result['transient']['states'],result['solutions']):
            q=F(t); clocks=[F(.1),F(.1)+F(.2)]
            self.assertEqual(state[:2],[sum(c<=q for c in clocks),int(F(.3)<=q)])
            area=sum(max(F(0),q-c) for c in clocks)
            self.assert_request_accuracy(row['voltages'][result['nodes'].index('dut:z')],area,1e-12,1e-10)
        self.assertEqual(result['strobe_evidence']['sample_origins'],
                         ['accepted_controller_frame']*len(times))

    def test_nonlinear_source_root_uses_exact_query_phase(self):
        period=2**-20
        source=model('''@(initial_step) begin h=2; n=0; end
            @(cross(V(u,r)*V(u,r)-2,1,1e-10,0.0005)) begin h=V(u,r); h=2*h+1; n=n+1; end
            V(z,r)<+idt(h*h/T,5); V(y,r)<+n;''',
            'parameter real T=9.5367431640625e-7; real h; integer n; electrical z;')
        program=compile_sources({'nonlinear.va':source},[instance()])
        center=math.sqrt(2)*period
        times=[0,math.nextafter(center,-math.inf),center,math.nextafter(center,math.inf),2.25*period]
        result=transient(program,{'u':[[0,0],[2.25*period,2.25]]},times,
                         stop=2.25*period,max_step=period/64,strobetimes=times,
                         vabstol=1e-14,reltol=1e-10,kernel=KERNEL)
        event,=result['transient']['events']
        te=F(event['time']);sample=te/F(period)
        self.assertGreater(sample*sample,2)
        self.assertLessEqual(sample*sample-2,F(0.0005))
        self.assertLessEqual(((te-F(1e-10))/F(period))**2,2)
        for t,state,row in zip(times,result['transient']['states'],result['solutions']):
            self.assertEqual(state[1],int(F(t)>=te))
            # h=2 before te; afterwards h=2*u(te)+1, in VA statement order.
            exact=5+4*min(F(t),te)/F(period)+(2*sample+1)**2*max(F(0),F(t)-te)/F(period)
            self.assert_request_accuracy(row['voltages'][result['nodes'].index('dut:z')],exact,1e-14,1e-10)
        self.assertEqual(result['strobe_evidence']['sample_origins'],
                         ['accepted_controller_frame']*len(times))
