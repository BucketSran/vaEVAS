"""Model timestep requests affect accepted advancement, never query-only history."""
GUARDS = ["LANG", "TIMER", "DYNAMICS"]

import copy
from fractions import Fraction
import json
import math
from pathlib import Path
import tempfile
import unittest
from evas import CompileError, KernelError, compile_sources, solve, transient
from evas.runtime import _invoke
from evas.protocol import validate_response
from test_affine import KERNEL, instance, model


def program(body, declarations=''):
    return compile_sources({'bound.va':model(body, declarations)}, [instance()])


def run(p, points=None, times=None, step=1):
    return transient(p, {'u':points or [[0,0],[1,0]]}, times or [0,1],
                     stop=1, max_step=step, kernel=KERNEL)


class BoundStepContracts(unittest.TestCase):
    def test_minimum_across_calls_and_instances(self):
        text=model('$bound_step(a); $bound_step(0.25); V(y,r)<+idt(1,0);', 'parameter real a=0.5;')
        p=compile_sources({'bound.va':text}, [instance(parameters={'a':.125}),
            instance(name='second',connections={'u':'u','y':'z','r':'0'},parameters={'a':.0625})])
        r=run(p)
        self.assertEqual(r['transient']['accepted_steps'],16)
        for name in ('y','z'):
            self.assertAlmostEqual(r['solutions'][-1]['voltages'][r['nodes'].index(name)],1)

    def test_conditional_bound_releases_on_next_accepted_evaluation(self):
        p=program('if(V(u,r)>0) $bound_step(0.125); V(y,r)<+idt(1,0);')
        r=run(p,[[0,1],[.5,0],[1,0]])
        self.assertEqual(r['transient']['accepted_steps'],5)
        # The analytic integral is t; certified piecewise propagation may
        # choose an adjacent floating-point representative inside its bound.
        self.assertAlmostEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],1,places=12)

    def test_bound_reads_state_after_same_time_event_settlement(self):
        p=program('''@(initial_step) q=0.25;
            @(timer(0.5,0,0.001)) q=0.125;
            $bound_step(q); V(y,r)<+idt(1,0);''','real q;')
        r=run(p)
        self.assertEqual(r['transient']['accepted_steps'],6)
        self.assertEqual(r['transient']['states'],[[.25],[.125]])
        finer=run(p,times=[0,.125,.5,.625,1],step=.0625)
        self.assertEqual(finer['solutions'][-1]['voltages'],r['solutions'][-1]['voltages'])
        self.assertEqual(finer['transient']['events'],r['transient']['events'])

    def test_stateless_bound_and_program_order(self):
        p=program('h=0.125; $bound_step(h); h=1; V(y,r)<+2*V(u,r);','real h;')
        r=run(p,[[0,0],[1,1]])
        self.assertEqual(r['transient']['accepted_steps'],8)
        self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],2)
        self.assertTrue(r['observation_evidence']['effective_controls']['max_step_applied'])
        # Non time-domain analyses ignore a valid timestep request.
        self.assertEqual(solve(p,['u'],[[.5]],kernel=KERNEL)['solutions'][0]['voltages'][-1],1)

    def test_inactive_outer_condition_skips_inner_numeric_request(self):
        p=program('if(V(u,r)<0) if(V(u,r)==0.5) $bound_step(V(u,r)-2); V(y,r)<+V(u,r);')
        r=run(p,[[0,.1],[1,.9]],times=[0,.5,1])
        self.assertEqual(r['transient']['accepted_steps'],2)

    def test_zero_request_uses_the_minimum_representable_timestep(self):
        stop=2*math.ulp(0.)
        p=program('$bound_step(0); V(y,r)<+1;')
        result=transient(p, {'u':[[0,0],[stop,0]]}, [0,stop],
                         stop=stop,max_step=stop,kernel=KERNEL)
        self.assertEqual(result['transient']['accepted_steps'],2)
        self.assertEqual(result['solutions'][-1]['voltages'][result['nodes'].index('y')],1)

    def test_invalid_values_and_contexts_reject(self):
        for body in ('$bound_step(-1); V(y,r)<+0;',
                     '@(initial_step) $bound_step(1); V(y,r)<+0;',
                     '$bound_step(idt(1,0)); V(y,r)<+0;'):
            with self.subTest(body=body),self.assertRaises(CompileError):
                program(body)
        with self.assertRaisesRegex(KernelError,'invalid_bound_step'):
            run(program('$bound_step(V(u,r)); V(y,r)<+0;'), [[0,-1],[1,-1]])

    def test_raw_ir_rejects_old_version_invalid_nodes_and_state_indices(self):
        p=program('$bound_step(0.125); V(y,r)<+0;').to_dict()
        for mutation,kind in [('version','unsupported_ir_version'),('node','invalid_ir'),('state','invalid_ir')]:
            data=copy.deepcopy(p)
            if mutation=='version': data['schema_version']=19
            elif mutation=='node': data['step_bounds'][0]['value']={'op':'affine','constant':0,'terms':[{'node':99,'coefficient':1}]}
            else: data['step_bounds'][0]['value']={'op':'state','state':0}
            with self.subTest(mutation=mutation),self.assertRaisesRegex(KernelError,kind):
                _invoke({'program':data,'driven':['u'],'samples':[[0]]},KERNEL)

    def test_raw_ir_rejects_malformed_bound_source_expansion(self):
        payload = program('$bound_step(0.125); V(y,r)<+V(u,r);').to_dict()
        for expansion in [[['not valid identifier', 0]], [['i', 0]] * 65]:
            with self.subTest(expansion=expansion):
                data = copy.deepcopy(payload)
                data['step_bounds'][0]['origin']['expansion'] = expansion
                with self.assertRaisesRegex(KernelError, 'invalid_ir'):
                    _invoke({'program': data, 'driven': ['u'], 'samples': [[0.5]]}, KERNEL)
        payload['step_bounds'][0]['origin']['expansion'] = [['i', 0]] * 64
        result = _invoke({'program': payload, 'driven': ['u'], 'samples': [[0.5]]}, KERNEL)
        self.assertEqual(result['solutions'][0]['voltages'][-1], 0.5)

    def test_bound_caps_actual_nonlinear_integration_segments(self):
        p=program('$bound_step(0.01); V(y,r)<+idt(pow(V(y,r),2),1);')
        request=dict(program=p.to_dict(),driven=['u'],samples=[],
            transient=dict(pwl=[[[0,0],[.5,0]]],output_times=[0,.5],stop=.5,max_step=.5),
            tolerances=dict(absolute=1e-8,relative=0))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'diagnostics.json'
            result=_invoke(request,KERNEL,diagnostics_path=path)
            records=json.loads(path.read_text())['records']
        validate_response(result,p,len(request['transient']['output_times']),request['transient']['output_times'])
        segments=[r for r in records if r['kind']=='nonlinear_candidate' and r['outcome']=='certified']
        self.assertTrue(segments)
        self.assertEqual(segments[-1]['end'],.5)
        for r in segments:
            self.assertLessEqual(Fraction(r['end'])-Fraction(r['start']),Fraction(.01))
        # Independent Riccati solution y(t)=1/(1-t), so y(.5)=2.
        self.assertLessEqual(abs(result['solutions'][-1]['voltages'][result['nodes'].index('y')]-2),1e-8)

    def test_rounded_held_activation_matches_linear_and_nonlinear_paths(self):
        prefix="""@(initial_step) q=0;
            @(timer(0.5,0)) q=V(u,r);
            if(q>0.5) $bound_step(0.01);"""
        times=[0,.5,1]
        points=[[0,.1],[1,.9]]
        # At exact t=.5 the binary64 endpoints give .5+2**-56.
        # Sampling rounds this to exact .5, so the request is inactive.
        # Move only the endpoint by one ulp to get .5+5*2**-56,
        # which instead samples to nextafter(.5,+inf) and activates it.
        active_points=[[0,.1],[1,math.nextafter(.9,math.inf)]]

        def same_physics(actual,reference):
            self.assertEqual(actual['nodes'],reference['nodes'])
            self.assertEqual(len(actual['solutions']),len(reference['solutions']))
            for row,base in zip(actual['solutions'],reference['solutions']):
                self.assertEqual(len(row['voltages']),len(base['voltages']))
                for value,expected in zip(row['voltages'],base['voltages']):
                    self.assertAlmostEqual(value,expected,places=8)

        for flow,expected in [
                ('1',lambda t:t),
                ('1/(1+V(u,r)*V(u,r))',lambda t:(math.atan(.1+.8*t)-math.atan(.1))/.8)]:
            with self.subTest(flow=flow):
                suffix=' V(y,r)<+idt('+flow+',0);'
                p=program(prefix+suffix,'real q;')
                r=run(p,points,times=times)
                baseline=run(program(prefix.replace('if(q>0.5) $bound_step(0.01);','')
                    +suffix,'real q;'),points,times=times)
                y=r['nodes'].index('y')
                for solution,t in zip(r['solutions'],times):
                    self.assertAlmostEqual(solution['voltages'][y],expected(t),places=8)
                self.assertEqual([row[0].hex() for row in r['transient']['states'][1:]],
                    [.5.hex(),.5.hex()])
                same_physics(r,baseline)
                self.assertEqual(r['transient']['accepted_steps'],
                    baseline['transient']['accepted_steps'])

                active=run(p,active_points,times=times)
                self.assertEqual([row[0].hex() for row in active['transient']['states'][1:]],
                    [math.nextafter(.5,math.inf).hex()]*2)
                self.assertGreaterEqual(active['transient']['accepted_steps'],51)
                for solution,t in zip(active['solutions'],times):
                    self.assertAlmostEqual(solution['voltages'][y],expected(t),places=8)

                # The invalid value is not evaluated in the inactive source arm.
                # Keep both flows: an unbound-frame refusal is still a failure.
                negative=program(prefix.replace('$bound_step(0.01)','$bound_step(V(u,r)-1)')
                    +suffix,'real q;')
                inactive=run(negative,points,times=times)
                self.assertEqual([row[0].hex() for row in inactive['transient']['states'][1:]],
                    [.5.hex(),.5.hex()])
                same_physics(inactive,baseline)
                self.assertEqual(inactive['transient']['accepted_steps'],
                    baseline['transient']['accepted_steps'])

    def test_sampled_clock_activation_preserves_physics_and_caps_inner_segments(self):
        p=program("""@(initial_step) q=-1;
            @(cross(V(u,r)-0.7,+1)) q=$abstime;
            if(q>=0) if($abstime-q<0.2) $bound_step(0.01);
            V(y,r)<+idt(1/(1+V(u,r)*V(u,r)),0);""",'real q;')
        times=[0,.7/3,.7/3+.2,1]
        request=dict(program=p.to_dict(),driven=['u'],samples=[],
            transient=dict(pwl=[[[0,0],[1,3]]],output_times=times,stop=1,max_step=.1))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'diagnostics.json'
            r=_invoke(request,KERNEL,diagnostics_path=path)
            records=json.loads(path.read_text())['records']
        validate_response(r,p,len(request['transient']['output_times']),request['transient']['output_times'])
        y=r['nodes'].index('y')
        for solution,t in zip(r['solutions'],times):
            self.assertAlmostEqual(solution['voltages'][y],math.atan(3*t)/3,places=8)
        active_segments=[x for x in records if x['kind']=='nonlinear_candidate'
            and x['outcome']=='certified' and x['start']>=.24 and x['end']<=.42]
        self.assertTrue(active_segments)
        for x in active_segments:
            self.assertLessEqual(Fraction(x['end'])-Fraction(x['start']),Fraction(.01))
        dense=run(p,[[0,0],[1,3]],times=[i/40 for i in range(41)],step=.1)
        self.assertAlmostEqual(dense['solutions'][-1]['voltages'][dense['nodes'].index('y')],
            r['solutions'][-1]['voltages'][y],places=9)

    def test_dynamic_bound_caps_nonlinear_history_after_initial_event(self):
        p=program('@(initial_step) h=0.01; $bound_step(h); V(y,r)<+idt(pow(V(y,r),2),1);','real h;')
        result=transient(p, {'u':[[0,0],[.5,0]]}, [0,.5], stop=.5, max_step=.5, kernel=KERNEL)
        self.assertAlmostEqual(result['solutions'][-1]['voltages'][result['nodes'].index('y')],2,places=7)
        self.assertGreaterEqual(result['transient']['accepted_steps'],50)


if __name__=='__main__': unittest.main()
