"""Explicit zero timer tolerance; exact clocks, not backend rounded callbacks.

The clock is start+k*period on submitted binary64 constants. Zero tolerance is
admitted only for fixed clocks whose in-domain events are representable. This
is an EVAS numerical contract, not a claim about a mandated LRM algorithm.
"""
GUARDS = ['TIMER', 'EVENT-ORDER', 'TIMED-OPERATOR']
import copy
from fractions import Fraction as F
import json
import math
import subprocess
import unittest
from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model
from initial_source_sequence_contract import check_initial_source_sequence


def run(body, stop=1., times=None, strobes=False, declarations='integer n;', instances=None,
        initial_sequence=None):
    times = [0., stop] if times is None else times
    p = compile_sources({'zero.va': model(body, declarations)}, instances or [instance()])
    result = transient(p, {'u': [[0., 0.], [stop, stop]]}, times, stop=stop,
                     max_step=stop, strobetimes=times if strobes else [], kernel=KERNEL)
    return (check_initial_source_sequence(result,p,[0],initial_sequence)
            if initial_sequence is not None else result)


class ZeroTimer(unittest.TestCase):
    def test_dyadic_clock_includes_zero_and_stop_independent_of_queries(self):
        body = '@(initial_step) n=7; @(timer(0,0.125,0)) n=n+1; V(y,r)<+n;'
        for times in [[0., 1.], [0., 0.125, 0.5, 1.], [0.25]]:
            for forced in [False, True]:
                with self.subTest(times=times, forced=forced):
                    r=run(body,times=times,strobes=forced,initial_sequence=[
                        (0,"initial_step",[0],[7]),(1,"timer",[7],[8])])
                    self.assertEqual([e['time'] for e in r['transient']['events']], [k/8 for k in range(9)])
                    self.assertEqual(r['transient']['states'], [[8+int(t*8)] for t in times])
                    self.assertEqual(r['transient']['events'][0]['before'], [7])

    def test_decimal_domain_is_decided_before_nonpoint_rejection(self):
        self.assertGreater(3*F(0.1),F(0.3)); self.assertLess(3*F(0.1),F(math.nextafter(0.3,math.inf)))
        body='@(timer(0.1,0.1,0)) n=n+1; V(y,r)<+n;'
        for stop in [0.1,0.2,0.3]:
            for forced in [False,True]:
                r=run(body,stop=stop,strobes=forced)
                self.assertEqual([e['time'] for e in r['transient']['events']], [0.1] if stop==0.1 else [0.1,0.2])
        for stop in [math.nextafter(0.3,math.inf),0.31,1.]:
            for forced in [False,True]:
                with self.subTest(stop=stop,forced=forced),self.assertRaisesRegex(KernelError,'event_resolution'):
                    run(body,stop=stop,strobes=forced)

    def test_disabled_and_outside_clocks_do_not_require_in_domain_precision(self):
        for args in ['0.1,0.1,0,0','2,0.1,0']:
            self.assertEqual(run(f'@(timer({args})) n=n+1; V(y,r)<+n;')['transient']['events'],[])
        for args in ['0.1,0,0','0.1,-1,-0.0']:
            self.assertEqual([e['time'] for e in run(f'@(timer({args})) n=n+1; V(y,r)<+n;')['transient']['events']],[0.1])

    def test_equal_mixed_clocks_contract_only_with_exact_clock_certificate(self):
        self.assertEqual(F(0.19999999999999998)+3*F(0.1),F(0.5))
        blocks=['@(timer(0.5,0,0)) n=n+1;', '@(timer(0.19999999999999998,0.1,1e-9)) m=m+1;']
        for order in [blocks,list(reversed(blocks))]:
            for forced in [False,True]:
                r=run(''.join(order)+'V(y,r)<+1.0*n+m;',stop=0.75,strobes=forced,declarations='integer n,m;')
                events=r['transient']['events']; middle=[e for e in events if e['time']==0.5]
                self.assertEqual(len(middle),2)
                self.assertEqual(r['transient']['states'][-1],[1,6])
                self.assertEqual([e['time'] for e in events],sorted(e['time'] for e in events))

    def test_earlier_nonpoint_clock_cannot_occupy_zero_clock_time(self):
        body='@(timer(0.25,0.24999999999999997,1e-9)) m=m+1; @(timer(0.5,0,0)) n=n+1; V(y,r)<+1.0*n+m;'
        self.assertLess(F(0.25)+F(0.24999999999999997),F(0.5))
        for forced in [False,True]:
            with self.assertRaisesRegex(KernelError,'event_resolution'):
                run(body,stop=0.6,strobes=forced,declarations='integer n,m;')

    def test_zero_clock_drives_integral_and_records_at_accepted_state(self):
        body='@(timer(0.25,0.25,0)) begin n=n+1; $display("n=%d",n); end V(y,r)<+idt(n,0);'
        times=[0.,0.125,0.25,0.375,0.5,0.75,1.]
        expected=[float(sum(max(F(t)-F(k,4),F(0)) for k in range(1,5))) for t in times]
        for forced in [False,True]:
            r=run(body,times=times,strobes=forced)
            y=r['nodes'].index('y')
            for row,value in zip(r['solutions'],expected,strict=True):self.assertAlmostEqual(row['voltages'][y],value,places=13)
            self.assertEqual([v['text'] for v in r['transient']['display_records']],['n=1','n=2','n=3','n=4'])

    def test_negative_and_held_zero_remain_rejected(self):
        for args in ['0.1,0.1,-1','n,0.25,0','0,n,0','0,0.25,0,n']:
            with self.subTest(args=args), self.assertRaises(CompileError):
                compile_sources({'zero.va':model(f'@(timer({args})) n=n+1; V(y,r)<+n;','integer n;')},[instance()])

    def test_raw_ir_validation_and_no_partial_failure_response(self):
        p=compile_sources({'zero.va':model('@(timer(0.1,0.1,1e-9)) begin n=n+1;$display("n=%d",n);end V(y,r)<+n;','integer n;')},[instance()]).to_dict()
        base=dict(program=p,driven=['u'],samples=[],transient=dict(pwl=[[[0,0],[1,1]]],output_times=[0,1],stop=1,max_step=1))
        for tol,kind in [(0.,'event_resolution'),(-1.,'invalid_ir')]:
            request=copy.deepcopy(base);request['program']['events'][0]['trigger']['time_tolerance']=tol
            result=subprocess.run([str(KERNEL)],input=json.dumps(request),text=True,capture_output=True)
            self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'')
            self.assertEqual(json.loads(result.stderr)['kind'],kind)
        request=copy.deepcopy(base);request['program']['events'][0]['trigger'].update(start=0.125,period=0.125,time_tolerance=-0.0)
        result=subprocess.run([str(KERNEL)],input=json.dumps(request),text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(json.loads(result.stdout)['transient']['events']),8)

if __name__=='__main__':unittest.main()
