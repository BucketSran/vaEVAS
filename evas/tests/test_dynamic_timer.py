"""Dynamic timer answers from held absolute-time schedules, not backend logs."""
GUARDS = ["TIMER", "EVENT-ORDER", "LANG", "DYNAMICS"]

import unittest
import copy
import json
import subprocess
from evas import CompileError, KernelError
from evas import compile_sources
from test_affine import KERNEL, instance, model
from test_timer import run_timer


class DynamicTimer(unittest.TestCase):
    def test_self_scheduled_one_shot_clock_and_query_invariance(self):
        for arguments in ['next,0,1e-12', 'next', 'next,,,1']:
            with self.subTest(arguments=arguments):
                source=model('''@(initial_step) begin next=0.25; n=0; end
                  @(timer('''+arguments+''')) begin next=next+0.25; n=n+1; end
                  V(y,r)<+n;''', 'real next; integer n;')
                a=run_timer(source,stop=1,times=[0,1],step=1)
                b=run_timer(source,stop=1,times=[0,.25,.375,.5,.75,1],step=.0625)
                self.assertEqual(a['transient']['events'], b['transient']['events'])
                self.assertEqual([e['time'] for e in a['transient']['events']],[.25,.5,.75,1])
                self.assertEqual(a['transient']['states'][-1],[1.25,4])

    def test_start_change_replaces_the_old_future_occurrence(self):
        source=model('''@(initial_step) begin next=0.75; n=0; end
          @(timer(0.25,0,1e-12)) next=0.5;
          @(timer(next,0,1e-12)) n=n+1;
          V(y,r)<+n;''', 'real next; integer n;')
        r=run_timer(source,stop=1,times=[0,1])
        self.assertEqual([e['time'] for e in r['transient']['events']],[.25,.5])
        self.assertEqual(r['transient']['states'][-1],[.5,1])

    def test_period_change_and_enable_preserve_absolute_phase(self):
        source=model('''@(initial_step) begin period=0.5; n=0; end
          @(timer(0.125,0,1e-12)) period=0.25;
          @(timer(0,period,1e-12)) n=n+1;
          V(y,r)<+n;''', 'real period; integer n;')
        r=run_timer(source,stop=1,times=[0,1])
        self.assertEqual([e['time'] for e in r['transient']['events']],[0,.125,.25,.5,.75,1])
        self.assertEqual(r['transient']['states'][-1],[.25,5])
        source=model('''@(initial_step) begin enable=0; n=0; end
          @(timer(0.375,0,1e-12)) enable=1;
          @(timer(0,0.25,1e-12,enable)) n=n+1;
          V(y,r)<+n;''', 'integer enable,n;')
        r=run_timer(source,stop=1,times=[0,1])
        self.assertEqual([e['time'] for e in r['transient']['events']],[.375,.5,.75,1])
        self.assertEqual(r['transient']['states'][-1],[1,3])

    def test_unchanged_and_past_one_shot_times_do_not_rearm(self):
        for assignment in ('next=next;', 'next=0;'):
            source=model('''@(initial_step) begin next=0.25; n=0; end
              @(timer(next,0,1e-12)) begin '''+assignment+''' n=n+1; end
              V(y,r)<+n;''', 'real next; integer n;')
            r=run_timer(source,stop=1,times=[0,1])
            self.assertEqual([e['time'] for e in r['transient']['events']],[.25])

    def test_dynamic_timer_or_exact_cross_executes_once(self):
        source=model('''@(initial_step) begin next=0.5; n=0; end
          @(timer(next,0,1e-12) or cross(V(u,r)-0.5,1,1e-12,1e-9)) n=n+1;
          V(y,r)<+n;''', 'real next; integer n;')
        r=run_timer(source,stop=1,times=[0,1])
        event,=r['transient']['events']
        self.assertEqual(event['time'],.5)
        self.assertEqual([leaf['kind'] for leaf in event['fired_triggers']],['timer','cross'])
        self.assertEqual(r['transient']['states'][-1],[.5,1])

    def test_uncertainty_and_raw_dependency_are_not_silently_dropped(self):
        source=model('''@(initial_step) begin next=0.75; n=0; end
          @(timer(0.25,0,1e-12)) next=(1.0/3.0)*V(u,r)+5.0/12.0;
          @(timer(next,0,1e-30)) n=n+1; V(y,r)<+n;''', 'real next; integer n;')
        with self.assertRaisesRegex(KernelError,'event_resolution'):
            run_timer(source,stop=1,times=[0,1])
        program=compile_sources({'timer.va':source},[instance()]).to_dict()
        for expression, kind in ((dict(op='state',state=99),'invalid_ir'),
                                 (dict(op='affine',constant=.5,terms=[dict(node=program['nodes'].index('u'),coefficient=0)]),'unsupported_timer')):
            raw=copy.deepcopy(program)
            raw['events'][1]['trigger']['start']=expression
            payload=dict(program=raw,driven=['u'],samples=[],transient=dict(
                pwl=[[[0,0],[1,1]]],output_times=[0,1],stop=1,max_step=1))
            result=subprocess.run([str(KERNEL)],input=json.dumps(payload),text=True,capture_output=True)
            self.assertEqual(result.returncode,2)
            self.assertEqual(result.stdout,'')
            self.assertEqual(json.loads(result.stderr)['kind'],kind)

    def test_continuous_voltage_parameters_stay_explicit(self):
        for setting in ('V(u,r)', 'idt(V(u,r),0)'):
            source=model('@(initial_step) n=0; @(timer('+setting+',0,1e-12)) n=n+1; V(y,r)<+n;', 'integer n;')
            with self.assertRaises((CompileError,KernelError)):
                run_timer(source,stop=1,times=[0,1])
    def test_dynamic_timer_preserves_independent_integral_history(self):
        source=model('''@(initial_step) next=0.25;
          @(timer(next,0,1e-12)) next=next+0.25;
          V(y,r)<+idt(V(u,r),0);''','real next;')
        result=run_timer(source,stop=1,times=[0,.25,.5,.75,1])
        self.assertEqual([e['time'] for e in result['transient']['events']],[.25,.5,.75,1])
        for t,row in zip([0,.25,.5,.75,1],result['solutions']):
            self.assertAlmostEqual(row['voltages'][result['nodes'].index('y')],.5*t*t,delta=1e-9)

    def test_new_dynamic_deadline_bounds_nonlinear_flow_before_blowup(self):
        from test_continuous_dynamics import compile_model, run, values
        # Initially y'=y^2. The first timer moves from .75 to .5 at .25;
        # it then changes q to -1. Prediction beyond the old .75 deadline
        # using the old growing field would be wrong, and could blow up.
        source='''@(initial_step) begin next=0.75; q=1; end
          @(timer(0.25,0,1e-12)) next=0.5;
          @(timer(next,0,1e-12)) q=-1;
          V(y,r)<+idt(q*pow(V(y,r),2),1);'''
        program=compile_model(source,'real next; integer q;')
        common=[0,.25,.5,.75,1,2]
        a=run(program,times=common,stop=2,max_step=2,vabstol=1e-9,reltol=0)
        dense=[i/16 for i in range(33)]
        b=run(program,times=dense,stop=2,max_step=2,vabstol=1e-9,reltol=0)
        self.assertEqual(a['transient']['events'],b['transient']['events'])
        self.assertEqual(values(a),[values(b)[dense.index(t)] for t in common])
        # A different internal step ceiling may change rounding, while the
        # physical deadline and independent voltage budget stay the same.
        smaller=run(program,times=dense,stop=2,max_step=.0625,vabstol=1e-9,reltol=0)
        self.assertEqual(a['transient']['events'],smaller['transient']['events'])
        for times,result in [(common,a),(dense,b),(dense,smaller)]:
            for t,value in zip(times,values(result)):
                self.assertAlmostEqual(value,1/(1-t) if t<=.5 else 1/t,delta=1e-9)


if __name__ == '__main__': unittest.main()
