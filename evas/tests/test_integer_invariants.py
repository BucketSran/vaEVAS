"""Source-derived integer ranges require complete inductive certificates."""
GUARDS = ['LANG', 'TIMER', 'EVENT-ORDER', 'COMPOSE']

import unittest
from evas import CompileError, compile_sources, transient
from test_affine import KERNEL, model, instance


def program(body, declarations):
    return compile_sources({'invariant.va':model(body, declarations)},[instance()])


class IntegerInvariants(unittest.TestCase):
    def test_guarded_clamp_keeps_finite_output_without_bounding_counter(self):
        p = program('@(initial_step)begin n=0;code=0;end @(timer(0.1,0.1))begin '
                    'n=n+1;code=(n>15)?15:n;end V(y,r)<+transition((code&1)?0.9:0,0,0.01,0.01);',
                    'integer n,code;')
        r = transient(p,{'u':[[0,0],[2,0]]},[0,.15,.25,1.45,1.55,1.65,1.75],
                      stop=1.8,max_step=.025,kernel=KERNEL)
        self.assertEqual([s['voltages'][r['nodes'].index('y')] for s in r['solutions']],
                         [0,.9,0,0,.9,.9,.9])

    def test_downcounter_source_guard_proves_nonnegative_range(self):
        p = program('@(initial_step)n=127;@(timer(0.1,0.1))begin '
                    'if(n!=0)n=n-1;else n=127;end V(y,r)<+transition((n&1)?0.9:0,0,0.01,0.01);',
                    'integer n;')
        r = transient(p,{'u':[[0,0],[13,0]]},[0,.15,.25,12.75,12.85],
                      stop=12.9,max_step=.025,kernel=KERNEL)
        self.assertEqual([s['voltages'][r['nodes'].index('y')] for s in r['solutions']],
                         [.9,0,.9,0,.9])

    def test_copy_array_certificate_propagates_all64_slots(self):
        p = program('@(initial_step)for(j=0;j<64;j=j+1)q[j]=0;'
                    '@(timer(0.1,0.1))begin for(j=63;j>0;j=j-1)q[j]=q[j-1];'
                    'q[0]=(V(u,r)>0.5)?1:0;end '
                    'V(y,r)<+transition(q[63]?0.9:0,0,0.01,0.01);',
                    'integer q[0:63];integer j;')
        r = transient(p,{'u':[[0,1],[7,1]]},[0,6.35,6.45],stop=6.5,max_step=.025,kernel=KERNEL)
        self.assertEqual([row['voltages'][r['nodes'].index('y')] for row in r['solutions']],[0,0,.9])

    def test_parameter_and_instance_certificates_do_not_mix(self):
        text = model('@(initial_step)n=CAP;@(timer(0.1,0.1))begin '
                     'if(n!=0)n=n-1;else n=CAP;end V(y,r)<+transition(n,0,0.01,0.01);',
                     'parameter integer CAP=127;integer n;')
        objects = [instance('a',connections=dict(u='u',y='a',r='0'),parameters={'CAP':7}),
                   instance('b',connections=dict(u='u',y='b',r='0'),parameters={'CAP':127})]
        for order in (objects,objects[::-1]):
            p = compile_sources({'instances.va':text},order)
            r = transient(p,{'u':[[0,0],[1,0]]},[0,.15],stop=.2,max_step=.025,kernel=KERNEL)
            row = dict(zip(r['nodes'],r['solutions'][-1]['voltages']))
            self.assertEqual((row['a'],row['b']),(6,126))

    def test_false_cutpoint_and_unbounded_lower_endpoint_do_not_gain_small_domain(self):
        for update in ['n=n+1;if(n>200)flag=1;code=n;',
                       'n=n+1;code=n&1;',
                       'n=n+1;code=n%8;',
                       'n=n-1;code=(n>15)?15:n;',
                       'n=n+1;code=(n>256)?256:n;']:
            with self.subTest(update=update),self.assertRaises(CompileError):
                program('@(initial_step)begin n=0;flag=0;code=0;end '
                        '@(timer(0.1,0.1))begin '+update+'end '
                        'V(y,r)<+transition((code&1)?0.9:0,0,0.01,0.01);',
                        'integer n,flag,code;')

    def test_dead_original_errors_and_overflow_before_clamp_still_reject(self):
        for suffix in ['if(n<0)tmp=1/0;',
                       'if(n<0)tmp=V(missing,r);',
                       'if(n<0)a[n+2147483647]=0;',
                       'if(n<0)tmp=2147483647+1;',
                       'n=(2147483647+1)-2147483647;if(n>7)n=7;']:
            with self.subTest(suffix=suffix),self.assertRaises(CompileError):
                program('@(initial_step)n=127;@(timer(0.1,0.1))begin '
                        'if(n!=0)n=n-1;else n=127;'+suffix+'end V(y,r)<+n;',
                        'integer n;real tmp;integer a[0:1];')

    def test_candidate_requires_initialization_and_every_callback(self):
        from evas.frontend import parse_sources
        from evas.integer_invariants import verify_candidate
        def bodies(body):
            from evas.syntax import Event
            m = parse_sources({'proof.va':model(body,'integer n,other;')})['m']
            return [e.body for e in (*m.events,*m.analog) if isinstance(e,Event)]
        options = dict(arrays={},parameters=lambda name:0)
        bounded = bodies('@(timer(1))if(n<7)n=n+1;else n=0;')
        self.assertTrue(verify_candidate(bounded,{'n':(0,0)},{'n':(0,7)},**options))
        self.assertFalse(verify_candidate(bounded,{'n':(8,8)},{'n':(0,7)},**options))
        self.assertFalse(verify_candidate(bodies('@(timer(1))n=n+1;'),
                                         {'n':(0,0)},{'n':(0,7)},**options))
        self.assertFalse(verify_candidate(bounded+bodies('@(timer(2))n=8;'),
                                         {'n':(0,0)},{'n':(0,7)},**options))
        self.assertFalse(verify_candidate(bodies('@(timer(1))n=other;'),
            {'n':(0,0),'other':(0,0)},{'n':(0,1),'other':(-2147483648,2147483647)},**options))

    def test_candidate_verification_is_charged_and_bottom_does_not_prune_read_audit(self):
        from evas.frontend import parse_sources
        from evas.integer_invariants import ProofWork,proof_parameters,verify_candidate
        from evas import event_index_domains as domains
        body = parse_sources({'proof.va':model('@(timer(1))n=n+1;','integer n;')})['m'].analog[0].body
        work = ProofWork()
        for _ in range(100000):
            work.charge()
        with self.assertRaisesRegex(ValueError,'source proof budget'):
            verify_candidate([body],{'n':(0,0)},{'n':(0,7)},arrays={},
                             parameters=proof_parameters(lambda name:0,work))
        text = model('@(timer(1))if(n<0)n=a[n];','integer n;integer a[0:1];')
        body = parse_sources({'reads.va':text})['m'].analog[0].body
        reads=[]
        domains.flow(body,{'n':(0,7),'a[0]':(0,0),'a[1]':(0,0)},
            arrays={'a':(0,1)},parameters=lambda name:0,
            on_use=lambda *args:reads.append(args))
        self.assertTrue(reads)


    def test_array_proof_work_counts_every_slot_and_stays_exhausted(self):
        from evas.frontend import parse_sources
        from evas.integer_invariants import ProofWork,proof_parameters,verify_candidate
        from evas import event_index_domains as domains
        env = {'n':(0,0), **{f'q[{k}]':(0,0) for k in range(128)}}
        for statement in ('n=q[0];', 'q[n]=0;'):
            text = model('@(timer(1))begin '+statement*1000+'end',
                         'integer n;integer q[0:127];')
            body = parse_sources({'budget.va':text})['m'].analog[0].body
            work = ProofWork()
            lookup = proof_parameters(lambda name:0,work)
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(ValueError,'source proof budget'):
                    verify_candidate([body],env,env,arrays={'q':tuple(range(128))},parameters=lookup)
                self.assertEqual(work.used,100001)
                with self.assertRaisesRegex(ValueError,'source proof budget'):
                    domains.entry_domains([],{'n':(0,0)},arrays={},parameters=lookup,states={'n'})
                self.assertEqual(work.used,100002)
                with self.assertRaisesRegex(ValueError,'source proof budget'):
                    domains.entry_domains([],{},arrays={},parameters=lookup,states=set())
                self.assertEqual(work.used,100003)
        # Standalone callers get the same cap without supplying a work object.
        with self.assertRaisesRegex(ValueError,'source proof budget'):
            verify_candidate([body],env,env,arrays={'q':tuple(range(128))},parameters=lambda name:0)

    def test_nested_ternary_does_not_replay_complex_condition_tree(self):
        from evas.frontend import parse_sources
        from evas import event_index_domains as domains
        from evas.integer_invariants import ProofWork,proof_parameters
        from unittest.mock import patch
        expression = '0'
        for _ in range(14):
            expression = f'((n<({expression}))?n:0)'
        body = parse_sources({'nested.va':model('@(timer(1))n='+expression+';',
                                               'integer n;')})['m'].analog[0].body
        work = ProofWork()
        original = domains.evaluate
        calls = []
        def counted(*args,**kwargs):
            calls.append(1)
            return original(*args,**kwargs)
        with patch.object(domains,'evaluate',counted):
            result = domains.entry_domains([body],{'n':(0,0)},arrays={},states={'n'},
                         parameters=proof_parameters(lambda name:0,work))
        self.assertEqual(result,({'n':(0,0)},False))
        self.assertLess(len(calls),200)
        self.assertGreaterEqual(work.used,len(calls))
        # Index reads still occur even in an unselected complex arm.
        indexed = parse_sources({'reads.va':model('@(timer(1))n=(n<0)?q[n]:0;',
                       'integer n;integer q[0:1];')})['m'].analog[0].body[0].rhs
        reads = []
        domains.evaluate(indexed,{'n':(0,0),'q[0]':(0,0),'q[1]':(0,0)},
                         lambda name:0,{'q':(0,1)},reads.append)
        self.assertEqual(len(reads),1)


if __name__=='__main__':
    unittest.main()
