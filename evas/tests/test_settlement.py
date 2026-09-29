"""Independent affine simultaneous-event equations and rejection controls."""
from fractions import Fraction as Q
import unittest
from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model
from test_timer import run_timer


class SettlementContracts(unittest.TestCase):
    def test_two_stage_chain_is_independent_of_block_order(self):
        blocks=['@(timer(0.5,0,0.001)) n=n+1;',
                '@(timer(0.5,0,0.001)) a=V(y,r);',
                '@(timer(0.5,0,0.001)) b=V(z,r);']
        for order in [blocks,blocks[::-1]]:
            source=model('''@(initial_step) begin n=0; a=0; b=0; end
                '''+''.join(order)+'V(y,r)<+n; V(z,r)<+a; V(w,r)<+b;',
                'integer n; real a,b; electrical z,w;')
            result=run_timer(source,stop=1,times=[0,0.5,1])
            self.assertEqual(result['transient']['states'],[[0,0,0],[1,1,1],[1,1,1]])

    def test_cross_instance_chain_is_independent_of_instance_order(self):
        producer=model('''@(initial_step) n=0; @(timer(0.5,0,0.001)) n=n+1;
                            V(y,r)<+n;''','integer n;')
        receiver=model('''@(initial_step) s=0; @(timer(0.5,0,0.001)) s=V(u,r);
                            V(y,r)<+s;''','real s;').replace('module m(', 'module reader(')
        inst=[instance('a',connections=dict(u='u',y='a',r='0')),
              instance('b','reader',dict(u='a',y='b',r='0')),
              instance('c','reader',dict(u='b',y='c',r='0'))]
        for order in [inst,inst[::-1]]:
            p=compile_sources({'a.va':producer,'b.va':receiver},order)
            r=transient(p,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)
            volts=dict(zip(r['nodes'],r['solutions'][-1]['voltages']))
            self.assertEqual([volts[n] for n in ['a','b','c']],[1,1,1])

    def test_unique_feedback_including_noncontractive_has_closed_form(self):
        for gain in [0.5,-0.5,2.0]:
            source=model(f'''@(initial_step) begin n=0; s=0; end
                @(timer(0.5,0.5,0.001)) begin n=n+1; s={gain}*V(y,r)+n; end
                V(y,r)<+s;''','integer n; real s;')
            r=run_timer(source,stop=1,times=[0,0.5,1])
            for count,states in enumerate(r['transient']['states']):
                self.assertEqual(states[0],count)
                self.assertAlmostEqual(states[1],float(Q(count)/(1-Q(gain))),places=12)
            self.assertEqual(len(r['transient']['events']),2)

    def test_repeated_writes_preserve_statement_order(self):
        for kind in ['integer','real']:
            for trigger in ['timer(0.5,0,0.001)','cross(V(u,r)-0.5,+1,0.001,0.001)']:
                for initial in [0,7]:
                    for count in [2,3]:
                        with self.subTest(kind=kind,trigger=trigger,initial=initial,count=count):
                            actions='n=n+1;'*count
                            source=model(f'''@(initial_step) n={initial};
                                @({trigger}) begin {actions} end V(y,r)<+n;''',f'{kind} n;')
                            r=run_timer(source,stop=1,times=[0,0.5,1])
                            self.assertEqual(r['transient']['states'],
                                             [[initial],[initial+count],[initial+count]])
                            self.assertEqual(len(r['transient']['events']),1)

    def test_repeated_integer_writes_expose_intermediate_values(self):
        cases=[('n=n+1; tmp=n; n=n+1;', [2,1]),
               ('n=n+1; n=1+n;', [2,0]),
               ('tmp=n+1; n=tmp+1;', [2,1]),
               ('n=n+1; tmp=n+1; n=tmp;', [2,2]),
               ('n=1; n=2;', [2,0])]
        for actions,expected in cases:
            with self.subTest(actions=actions):
                source=model(f'''@(initial_step) begin n=0; tmp=0; end
                    @(timer(0.5,0,0.001)) begin {actions} end
                    V(y,r)<+n; V(z,r)<+tmp;''','integer n,tmp;',
                    ports='u,y,z,r',directions='input u; output y,z; inout r;')
                r=run_timer(source,stop=1,times=[0,1],
                            instances=[instance(connections=dict(u='u',y='y',z='z',r='0'))])
                self.assertEqual(r['transient']['states'][-1],expected)
                self.assertEqual([r['solutions'][-1]['voltages'][r['nodes'].index(n)]
                                  for n in ['y','z']],expected)

    def test_repeated_integer_writes_in_periodic_voltage_feedback(self):
        # Each event adds two once. s=0.5*s+n gives s=2*n independently.
        source=model('''@(initial_step) begin n=0; s=0; end
            @(timer(0.25,0.25,0.001)) begin n=n+1; n=n+1; s=V(y,r); s=0.5*s+n; end
            V(y,r)<+s;''','integer n; real s;')
        for step in [1,0.07]:
            for times in [[0,1],[0,0.25,0.5,0.75,1]]:
                with self.subTest(step=step,times=times):
                    r=run_timer(source,stop=1,times=times,step=step)
                    self.assertEqual(r['transient']['states'],[[int(8*t),int(16*t)] for t in times])
                    self.assertEqual(len(r['transient']['events']),4)
                    self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],16)

    def test_repeated_integer_writes_check_each_intermediate_range(self):
        # A later assignment back into range must not hide an earlier overflow.
        cases=[(2147483647,'n=n+1; n=n-1;'),
               (-2147483648,'n=n-1; n=n+1;'),
               (2147483646,'n=n+1; n=n+1;')]
        for initial,actions in cases:
            with self.subTest(initial=initial,actions=actions):
                source=model(f'''@(initial_step) n={initial};
                    @(timer(0.5,0,0.001)) begin {actions} end V(y,r)<+n;''','integer n;')
                with self.assertRaises(KernelError) as caught:
                    run_timer(source,stop=1,times=[0,1])
                self.assertEqual(caught.exception.detail['kind'],'state_range')

    def test_single_integer_update_and_real_sequence_are_preserved(self):
        source=model('''@(initial_step) begin n=0; s=0; end
            @(timer(0.5,0,0.001)) begin n=n+2; s=V(y,r); s=0.5*s+n; end
            V(y,r)<+s;''','integer n; real s;')
        r=run_timer(source,stop=1,times=[0,1])
        self.assertEqual(r['transient']['states'][-1],[2,4])

    def test_no_unique_same_time_solution_is_rejected(self):
        for bias in [0,1]:
            source=model(f'''@(initial_step) s=0;
                @(timer(0.5,0,0.001)) s=V(y,r)+{bias}; V(y,r)<+s;''','real s;')
            with self.assertRaises(KernelError) as caught:
                run_timer(source,stop=1,times=[0,1])
            self.assertEqual(caught.exception.detail['kind'],'singular_system')

    def test_inactive_event_state_is_held_during_another_event(self):
        source=model('''@(initial_step) begin n=0; s=-1; end
            @(timer(0.5,0,0.001)) n=n+1;
            @(timer(0.75,0,0.001)) s=V(y,r);
            V(y,r)<+n; V(z,r)<+s;''','integer n; real s; electrical z;')
        r=run_timer(source,stop=1,times=[0,0.5,0.75,1])
        self.assertEqual(r['transient']['states'],[[0,-1],[1,-1],[1,1],[1,1]])

    def test_ill_conditioned_substitution_cannot_hide_large_forward_error(self):
        # True denominator 3*2^-54 is rounded to 2^-52 by float collection.
        gain = .49999999999999983
        self.assertEqual(1/(1-Q(.5)-Q(gain)),Q(2**54,3))
        source=model(f'''@(initial_step) s=0;
            @(timer(0.5,0,0.01)) begin s=0.5*V(y,r); s=s+{gain!r}*V(y,r)+1; end
            V(y,r)<+s;''','real s;')
        with self.assertRaises(KernelError) as caught:
            run_timer(source,stop=1,times=[0,1])
        self.assertEqual(caught.exception.detail['kind'],'event_accuracy')

    def test_generic_state_error_has_no_voltage_absolute_floor(self):
        for exponent in [-80,0,80]:
            unit,delta=2.**exponent,2.**(exponent-55)
            self.assertEqual((Q(unit)+Q(delta))-Q(unit),Q(delta))
            source=model(f'''@(initial_step) s=0;
                @(timer(0.5,0,0.01)) begin s={unit!r}; s=s+{delta!r}; s=s-{unit!r}; end
                V(y,r)<+0;''','real s;')
            with self.assertRaises(KernelError) as caught:
                run_timer(source,stop=1,times=[0,1])
            self.assertEqual(caught.exception.detail['kind'],'event_accuracy')

    def test_exact_scaled_states_are_accepted_in_their_own_units(self):
        for exponent in [-80,0,80]:
            unit=2.**exponent
            source=model(f'''@(initial_step) s=0;
                @(timer(0.5,0,0.01)) begin s={unit!r}*V(y,r); s=0.5*s+{unit!r}; end
                V(y,r)<+s/{unit!r};''','real s;')
            r=run_timer(source,stop=1,times=[0,1])
            self.assertEqual(r['transient']['states'][-1],[2*unit])
            self.assertEqual(r['solutions'][-1]['voltages'][r['nodes'].index('y')],2.)

    def test_coupled_closure_matches_independent_rational_equations(self):
        import random
        rng=random.Random(121205)
        for _ in range(24):
            a,b,c,d=[Q(rng.randrange(-4,5),8) for _ in range(4)]
            f,g=[Q(rng.randrange(1,5),4) for _ in range(2)]
            determinant=(1-a)*(1-d)-b*c
            x=((1-d)*f+b*g)/determinant
            y=(c*f+(1-a)*g)/determinant
            source=model(f'''@(initial_step) begin s=0; h=0; end
                @(timer(0.5,0,0.01)) begin
                s={float(a)!r}*V(y,r)+{float(b)!r}*V(z,r)+{float(f)!r};
                h={float(c)!r}*V(y,r)+{float(d)!r}*V(z,r)+{float(g)!r}; end
                V(y,r)<+s; V(z,r)<+h;''','real s,h; electrical z;')
            r=run_timer(source,stop=1,times=[0,1])
            for actual,expected in zip(r['transient']['states'][-1],[x,y]):
                self.assertLessEqual(abs(Q(actual)-expected),abs(expected)*Q(1e-10))
