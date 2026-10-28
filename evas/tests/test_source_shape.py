"""Rational pulse geometry supplies shape while voltage error remains charged."""
GUARDS = ["DEV:scs-input", "CROSS", "EVENT-ORDER", "TIMED-OPERATOR"]

from fractions import Fraction as Q
import copy
from pathlib import Path
import tempfile
import unittest

from evas import KernelError, compile_sources, transient
from evas.scs import load_scs, simulate_scs
from test_affine import KERNEL, instance, model
from initial_record_contract import check_initial_record_batch


class SourceShapeContracts(unittest.TestCase):
    def test_output_after_timer_root_before_representative_keeps_source_history(self):
        # 3*binary64(1ns) < 6*binary64(500ps) < the timer's upper
        # representative. This is a post-callback observation, not a new event.
        period=Q(1e-9); query=6*500e-12; stop=4e-9; rise=Q(300e-12)
        self.assertLess(3*period,Q(query))
        for target in ['($abstime>120n)?q:0','(V(u,r)>0.5)?q:0']:
            with self.subTest(target=target):
                program=compile_sources({'observation.va':model(f'''@(initial_step) q=0;
                    @(timer(1n,1n)) q=q+1;
                    V(y,r)<+transition({target},0,300p,300p);
                    V(z,r)<+q;''','integer q; electrical z;')},[instance()])
                common=[0,3e-9,query,3.15e-9,stop]
                def run(times,forced=False):
                    return transient(program,{'u':[[0,1],[stop,1]]},times,
                                     stop=stop,max_step=500e-12,kernel=KERNEL,
                                     strobetimes=times if forced else [])
                sparse=run([0,stop]); result=run(common)
                self.assertEqual(sparse['transient']['events'],result['transient']['events'])
                self.assertEqual(sparse['solutions'][-1],result['solutions'][-1])
                forced=run(common,True)
                # Forced points may refine the representative/window. The
                # physical clock, callback state and voltage oracle stay fixed.
                for response in [result,forced]:
                    events=response['transient']['events']
                    self.assertEqual([e['after'] for e in events],[[1],[2],[3],[4]])
                    for k,event in enumerate(events,1):
                        lo,hi=event.get('observation_time_bounds',[event['time']]*2)
                        self.assertLessEqual(Q(lo),k*period)
                        self.assertLessEqual(k*period,Q(hi))
                yi=program.nodes.index('y'); zi=program.nodes.index('dut:z')
                for response in [result,forced]:
                    for t,row in zip(common,response['solutions']):
                        count=min(4,int(Q(t)//period))
                        expected=Q(0) if '$abstime' in target or count==0 else Q(count-1)+min(Q(1),(Q(t)-count*period)/rise)
                        self.assertEqual(row['voltages'][zi],count)
                        self.assertLessEqual(abs(Q(row['voltages'][yi])-expected),Q(1e-12)+Q(1e-10)*abs(expected))

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root/'dut.va').write_text(model('''@(initial_step) q=0;
            @(cross(V(u,r)-0.4,1,1e-14,1e-9)) q=1-q;
            V(y,r)<+transition(q,0,8e-11,1.2e-10);''', 'real q;'))
        self.path = self.root/'tb.scs'

    def deck(self, step='5e-11'):
        self.path.write_text('simulator lang=spectre\nahdl_include "dut.va"\n'
            'Vin (u 0) vsource type=pulse val0=0 val1=1 delay=1e-10 '
            'rise=3e-11 fall=4e-11 width=3e-10 period=1e-9\n'
            'DUT (u y 0) m\nopts options reltol=1e-10 vabstol=1e-12\n'
            f'tran tran stop=3.4e-9 maxstep={step} '
            'strobetimes=[0 1.5e-10 2.5e-10 1.15e-9 1.25e-9 2.15e-9 2.25e-9] strobeoutput=all\n'
            'save u y\n')
        return self.path

    def test_original_pulse_cross_transition_keeps_error_and_rational_time_enclosures(self):
        # Distinct from a point-only pass: source voltage uncertainty stays
        # nonzero and each physical edge is checked against rational geometry.
        path=self.deck()
        self.assertGreater(load_scs(path).manifest['transient']['source_errors']['u'],0)
        result=simulate_scs(path,kernel=KERNEL)
        events=[e for e in result['transient']['events'] if e['kind']=='cross']
        roots=[Q(1e-10)+k*Q(1e-9)+Q(.4)*Q(3e-11) for k in range(4)]
        self.assertEqual(len(events),len(roots))
        for event,root in zip(events,roots):
            bounds=event.get('observation_time_bounds',[event['time'],event['time']])
            self.assertLessEqual(Q(bounds[0]),root)
            self.assertGreaterEqual(Q(bounds[1]),root)
        saved=result['saved'];y=saved['nodes'].index('y')
        for t,values in zip(saved['times'],saved['values']):
            time=Q(t);k=sum(root<=time for root in roots)-1
            if k<0:expected=Q(0)
            elif k%2==0:expected=min(Q(1),(time-roots[k])/Q(8e-11))
            else:expected=max(Q(0),1-(time-roots[k])/Q(1.2e-10))
            error=abs(Q(values[y])-expected)
            self.assertLessEqual(error,Q(1e-12)+Q(1e-10)*abs(Q(values[y])))

    def test_cross_condition_reads_exact_physical_root_before_another_source_threshold(self):
        # The pulse root precedes the enable threshold by 5.41e-24s.
        # Evaluating at the rounded root or a later output row changes this
        # branch; the existing event contract explicitly samples at tau.
        (self.root/'dut.va').write_text(model('''@(initial_step) q=0;
            @(cross(V(u,r)-0.45,+1,1e-12,1e-9)) begin
              if(V(en,r)>0.45) q=1; else q=0;
            end V(y,r)<+q;''','integer q;',ports='u,en,y,r',
            directions='input u,en; output y; inout r;'))
        self.path.write_text('simulator lang=spectre\nahdl_include "dut.va"\n'
            'Vclk (u 0) vsource type=pulse val0=0 val1=.9 period=10n '
            'width=4n delay=5n rise=100p fall=100p\n'
            'Ven (en 0) vsource type=pwl wave=[0 .9 135n .9 135.1n 0 136n 0]\n'
            'DUT (u en y 0) m\n'
            'opts options reltol=1e-10 vabstol=1e-12\n'
            'tran tran stop=136n maxstep=100p\nsave u en y\n')
        root=Q(5e-9)+13*Q(10e-9)+Q(100e-12)/2
        en=Q(.9)*(Q(135.1e-9)-root)/(Q(135.1e-9)-Q(135e-9))
        self.assertGreater(en,Q(.45))
        result=simulate_scs(self.path,kernel=KERNEL)
        y=result['saved']['nodes'].index('y')
        self.assertEqual(result['saved']['values'][-1][y],1)

    def test_equivalent_shape_keeps_internal_affine_root_sample_and_strict_tie(self):
        # B1: z=2u has its unique rising root at 1/2. An identical source
        # description must preserve that root, z(tau)=1, and the rising side
        # u>0.5 just after it (LRM 2.4 5.10.3.1 cross right limit).
        program=compile_sources({'internal.va':model('''@(initial_step) begin q=0; sample=0; tie=0; end
            @(cross(V(z,r)-1,+1,1e-9,1e-9)) begin
              q=q+1; sample=V(z,r); tie=(V(u,r)>0.5)?1:0;
            end V(z,r)<+2*V(u,r); V(y,r)<+q+sample+tie;''',
            'real q,sample; integer tie; electrical z;')},[instance()])
        shape=[dict(time_numerator=str(t),time_denominator='1',value_V=t) for t in [0,1]]
        observations=[]
        for extra in [{},{'source_shapes':{'u':shape}}]:
            result=transient(program,{'u':[[0,0],[1,1]]},[0,.5,1],
                             stop=1,max_step=1,kernel=KERNEL,**extra)
            # IR33 records the initial_step batch first, at t=0.
            records=[e for e in result['transient']['events'] if e['kind']!='initial_step']
            event=records[0]
            self.assertEqual(len(records),1)
            self.assertEqual(event['time'],.5)
            self.assertEqual(dict(zip(result['transient']['state_names'],event['after'])),
                             {'dut:q':1,'dut:sample':1,'dut:tie':1})
            y=program.nodes.index('y')
            values=[row['voltages'][y] for row in result['solutions']]
            self.assertEqual(values,[0,3,3]);observations.append(values)
        self.assertEqual(*observations)

    def test_shaped_pulse_internal_affine_guard_reaches_transition_history(self):
        # Real SCS pulses automatically attach nonzero projection-error shapes.
        # The root u=.2 drives a finite ramp; verify all saved outputs against
        # rational pulse geometry and show that extra queries do not move it.
        (self.root/'dut.va').write_text(model('''@(initial_step) q=0;
            @(cross(V(z,r)-0.4,+1,1e-14,1e-9)) q=1-q;
            V(z,r)<+2*V(u,r); V(y,r)<+transition(q,0,8e-11,1.2e-10);''',
            'real q; electrical z;'))
        path=self.deck();bench=load_scs(path)
        self.assertGreater(bench.manifest['transient']['source_errors']['u'],0)
        result=simulate_scs(path,kernel=KERNEL)
        roots=[Q(1e-10)+k*Q(1e-9)+Q(.4)/2*Q(3e-11) for k in range(4)]
        events=result['transient']['events'];self.assertEqual(len(events),4)
        for event,root in zip(events,roots):
            lo,hi=event.get('observation_time_bounds',[event['time']]*2)
            self.assertLessEqual(Q(lo),root);self.assertGreaterEqual(Q(hi),root)
        y=result['saved']['nodes'].index('y')
        for t,values in zip(result['saved']['times'],result['saved']['values']):
            time=Q(t);k=sum(root<=time for root in roots)-1
            expected=Q(0) if k<0 else min(Q(1),(time-roots[k])/Q(8e-11)) if k%2==0 else max(Q(0),1-(time-roots[k])/Q(1.2e-10))
            self.assertLessEqual(abs(Q(values[y])-expected),Q(1e-12)+Q(1e-10)*abs(Q(values[y])))
        path.write_text(path.read_text().replace('strobetimes=[0 ','strobetimes=[0 1.07e-10 1.11e-10 '))
        queried=simulate_scs(path,kernel=KERNEL)
        self.assertEqual(events,queried['transient']['events'])

    def test_shaped_internal_affine_projection_keeps_branch_sign_and_feedback(self):
        # Equivalent branch equations still give V(z,w)=2u. This exercises
        # the certified circuit solve, not just substitution of one RHS.
        branches=[
            'V(r,z)<+-2*V(u,r); V(w,r)<+0;',
            'V(z,r)<+0.5*V(z,r)+V(u,r); V(w,r)<+0;',
            'V(z,w)<+2*V(u,r); V(w,r)<+0.25;',
        ]
        shape=[dict(time_numerator=str(t),time_denominator='1',value_V=t) for t in [0,1]]
        for branch in branches:
            with self.subTest(branch=branch):
                program=compile_sources({'branches.va':model('''@(initial_step) q=0;
                    @(cross(V(z,w)-1,+1,1e-9,1e-9)) q=q+1;
                    V(y,r)<+q;'''+branch,'real q; electrical z,w;')},[instance()])
                result=transient(program,{'u':[[0,0],[1,1]]},[0,.5,1],stop=1,
                                 max_step=1,kernel=KERNEL,source_shapes={'u':shape})
                self.assertEqual([e['time'] for e in result['transient']['events']],[.5])
                self.assertEqual([row['voltages'][program.nodes.index('y')] for row in result['solutions']],[0,1,1])

    def test_shaped_internal_guard_does_not_round_uncertain_network_projection(self):
        # z=u-2z gives z=u/3. Its certified projection coefficient is an
        # interval: choosing a midpoint would invent exact source provenance.
        program=compile_sources({'uncertain-map.va':model('''@(initial_step) q=0;
            @(cross(V(z,r)-0.25,+1,1e-9,1e-9)) q=1;
            V(z,r)<+V(u,r)-2*V(z,r); V(y,r)<+q;''',
            'real q; electrical z;')},[instance()])
        shape=[dict(time_numerator=str(t),time_denominator='1',value_V=t) for t in [0,1]]
        with self.assertRaisesRegex(KernelError,'event_resolution'):
            transient(program,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=1,
                      kernel=KERNEL,source_shapes={'u':shape})

    def test_physical_corner_partition_replaces_displaced_nominal_crossing(self):
        # The nominal ramp ends at .3; the actual ramp ends at 1/3. Its
        # 15/16 crossing is exactly 5/16, after the nominal corner.
        program=compile_sources({'partition.va':model('''@(initial_step) q=0;
            @(cross(V(u,r)-0.9375,1,1e-9,1e-9)) q=1; V(y,r)<+q;''','real q;')},[instance()])
        sources={'u':[[0,0],[.3,1],[1,1]]}
        shape=[dict(time_numerator=n,time_denominator=d,value_V=v)
               for n,d,v in [('0','1',0),('1','3',1),('1','1',1)]]
        args=dict(stop=1,max_step=.2,kernel=KERNEL,vabstol=.2,reltol=0,source_errors={'u':.125})
        with self.assertRaisesRegex(KernelError,'unsupported_source_uncertainty'):
            transient(program,sources,[0,.29,.3125,.4,1],**args)
        result=transient(program,sources,[0,.29,.3125,.4,1],source_shapes={'u':shape},**args)
        self.assertEqual([e['time'] for e in result['transient']['events']],[.3125])
        y=program.nodes.index('y')
        self.assertEqual([row['voltages'][y] for row in result['solutions']],[0,0,1,1,1])
        # Original-curve evaluation still has a nonzero rounding enclosure.
        # A large network gain must charge that error at the downstream node.
        gained=compile_sources({'gain.va':model('V(y,r)<+1099511627776*V(u,r);')},[instance()])
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            transient(gained,sources,[0,.1,1],source_shapes={'u':shape},
                      **dict(args,vabstol=1e-9))
        result=transient(gained,sources,[0,.1,1],source_shapes={'u':shape},
                         **dict(args,vabstol=1e-3))
        actual=result['solutions'][1]['voltages'][gained.nodes.index('y')]
        self.assertLessEqual(abs(Q(actual)-Q(1099511627776)*3*Q(.1)),Q(1e-3))

    def test_reverse_ground_zero_width_instances_and_query_grid_preserve_history(self):
        # A zero-width triangle drives two independent call sites. Feedback
        # y=.5*y+transition(q) gives exactly twice the transition level.
        source=model('@(initial_step) q=0;\n            @(cross(V(r,u)-0.5,1,1e-12,1e-9)) q=1-q;\n            V(y,r)<+0.5*V(y,r)+transition(q,0,0.125,0.125);', 'real q;')
        (self.root/'dut.va').write_text(source)
        def run(step,extra):
            self.path.write_text('simulator lang=spectre\nahdl_include "dut.va"\n'
                'Vin (0 u) vsource type=pulse val0=0 val1=1 delay=.1 '
                'rise=.1 fall=.2 width=0 period=1\n'
                'A (u ya 0) m\nB (u yb 0) m\n'
                'opts options reltol=1e-9 vabstol=1e-11\n'
                f'tran tran stop=1.5 maxstep={step} strobetimes=[{extra}] strobeoutput=all\n'
                'save u ya yb\n')
            return simulate_scs(self.path,kernel=KERNEL)
        coarse=run('.5','0 .25 .5 1.25 1.5')
        fine=run('.03125','0 .15625 .25 .5 1.15625 1.25 1.5')
        self.assertEqual(coarse['transient']['events'],fine['transient']['events'])
        roots=[Q(.1)+k*Q(1)+Q(.5)*Q(.1) for k in range(2)]
        for result in [coarse,fine]:
            for t,row in zip(result['saved']['times'],result['saved']['values']):
                values=dict(zip(result['saved']['nodes'],row));time=Q(t)
                k=sum(root<=time for root in roots)-1
                expected=Q(0) if k<0 else min(Q(1),(time-roots[k])/Q(.125)) if k==0 else max(Q(0),1-(time-roots[k])/Q(.125))
                for node in ['ya','yb']:
                    self.assertLessEqual(abs(Q(values[node])-2*expected),Q(1e-11)+Q(1e-9)*abs(Q(values[node])))

    def test_shaped_clock_coexists_with_held_timer_reset_and_transition(self):
        # A fixed held absolute-time schedule and a shaped source share the
        # calendar. Cross callbacks toggle q; the timer resets it between edges.
        source=model('@(initial_step) begin next=0.5; q=0; end\n            @(cross(V(u,r)-0.5,1,1e-12,1e-9)) q=1;\n            @(timer(next,0,1e-12)) begin q=0; next=next+1; end\n            V(y,r)<+transition(q,0,0.125,0.125);','real next,q;')
        program=compile_sources({'timer.va':source},[instance()])
        sources={'u':[[0,0],[.1,0],[.2,1],[.3,0],[1.1,0],[1.2,1],[1.3,0],[2,0]]}
        shape=[dict(time_numerator=str(Q(t).numerator),time_denominator=str(Q(t).denominator),value_V=v)
               for t,v in sources['u']]
        result=transient(program,sources,[0,.25,.75,1.25,1.75,2],stop=2,max_step=.5,
                         source_errors={'u':1e-12},source_shapes={'u':shape},kernel=KERNEL)
        y=program.nodes.index('y')
        for row,expected in zip(result['solutions'],[0,.8,0,.8,0,0]):
            self.assertAlmostEqual(row['voltages'][y],expected,delta=1e-10)
        result=check_initial_record_batch(result,program,[0,0],[.5,0],1)
        events=result['transient']['events']
        self.assertEqual([e['kind'] for e in events],['cross','timer','cross','timer'])

    def test_corner_root_uses_outgoing_slope_for_expression_tolerance(self):
        # At 1/3 the incoming slope is tiny and the outgoing slope is 1.5.
        # The upper binary64 representative lies in the outgoing segment.
        import math
        points=[(Q(0),math.nextafter(1.,0.)),(Q(1,3),1.),(Q(1),2.)]
        shape=[dict(time_numerator=str(t.numerator),time_denominator=str(t.denominator),value_V=v)
               for t,v in points]
        program=compile_sources({'corner.va':model('@(initial_step) q=0;\n            @(cross(V(u,r)-1,1,1e-12,1e-30)) q=1; V(y,r)<+q;','real q;')},[instance()])
        t=math.nextafter(float(Q(1,3)),math.inf)
        self.assertGreater((Q(t)-Q(1,3))/(1-Q(1,3)),Q(1e-30))
        with self.assertRaisesRegex(KernelError,'event_resolution'):
            transient(program,{'u':[[float(t),v] for t,v in points]},[0,t,1],stop=1,max_step=1,
                source_errors={'u':1e-15},source_shapes={'u':shape},kernel=KERNEL,vabstol=1e-8,reltol=0)

    def test_invalid_shape_or_understated_band_is_rejected(self):
        program=compile_sources({'shape.va':model('V(y,r)<+V(u,r);')},[instance()])
        shape=[dict(time_numerator=n,time_denominator=d,value_V=v)
               for n,d,v in [('0','1',0),('1','3',1),('1','1',1)]]
        bad=[]
        for key,value in [('time_denominator','0'),('time_denominator','-3'),
                          ('time_numerator','9'*1251),('value_V',True),('unknown',1)]:
            candidate=copy.deepcopy(shape);candidate[1][key]=value;bad.append(candidate)
        bad += [shape[:1],[shape[0],shape[2],shape[1]],[shape[0],shape[0],shape[2]]]
        for candidate in bad:
            with self.subTest(candidate=str(candidate)[:100]),self.assertRaises(KernelError):
                transient(program,{'u':[[0,0],[.3,1],[1,1]]},[0,1],stop=1,max_step=1,
                          source_errors={'u':.125},source_shapes={'u':candidate},kernel=KERNEL)
        for error in (0,.0625):
            with self.subTest(error=error),self.assertRaisesRegex(KernelError,'invalid source shape'):
                transient(program,{'u':[[0,0],[.3,1],[1,1]]},[0,1],stop=1,max_step=1,
                          source_errors={'u':error},source_shapes={'u':shape},kernel=KERNEL)

    def test_other_dynamic_operators_keep_the_unproved_shape_boundary(self):
        program=compile_sources({'integral.va':model('V(y,r)<+idt(V(u,r),0);')},[instance()])
        shape=[dict(time_numerator=n,time_denominator=d,value_V=v)
               for n,d,v in [('0','1',0),('1','3',1),('1','1',1)]]
        with self.assertRaisesRegex(KernelError,'unsupported_source_uncertainty'):
            transient(program,{'u':[[0,0],[.3,1],[1,1]]},[0,1],stop=1,max_step=1,
                      source_errors={'u':.125},source_shapes={'u':shape},kernel=KERNEL)


if __name__=='__main__':
    unittest.main()
