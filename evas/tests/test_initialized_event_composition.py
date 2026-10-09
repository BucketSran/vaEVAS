"""IR18 initialization and shared writes retain exact physical query phases."""
GUARDS = ['LANG', 'TIMER', 'EVENT-ORDER', 'CROSS', 'TRANSITION']

import unittest
import math
from fractions import Fraction

from evas import KernelError
from test_continuous_dynamics import compile_model, run, values


class InitializedEventComposition(unittest.TestCase):
    def test_source_roots_and_timer_keep_order_after_held_timer_replanning(self):
        low, high = Fraction(.1), Fraction(.9)
        roots = [(Fraction(threshold)-low)/(high-low)
                 for threshold in [.5, .5000000000000001]]
        fixed = math.nextafter(.5, math.inf)
        self.assertLess(roots[0], Fraction(fixed))
        self.assertLess(Fraction(fixed), roots[1])
        body = (
            '@(initial_step) begin n=0; m=0; k=0; h=0; due=0.9; end '
            '@(cross(V(u,r)-0.5,1,1e-12,1e-9)) begin n=n+1; due=0.75; end '
            f'@(timer({fixed!r},0,1e-12)) k=k+1; '
            '@(cross(V(u,r)-0.5000000000000001,1,1e-12,1e-9)) m=m+1; '
            '@(timer(due,0,1e-12)) h=h+1; '
            'V(y,r)<+n+10*k+100*m+1000*h; '
            'V(z,r)<+transition(n,0,0.125,0.125);')
        declarations = 'integer n,m,k,h; real due; electrical z;'
        program = compile_model(body, declarations)
        previous = None
        for times in [[0, 1], [0, .25, .625, .75, .875, 1]]:
            result = run(program, {'u': [[0,.1],[1,.9]]}, times,
                         stop=1, vabstol=1e-6, reltol=1e-8)
            events = result['transient']['events']
            self.assertEqual([event['event'] for event in events], [0, 1, 2, 3])
            for event, nominal in zip(events, [roots[0], Fraction(fixed), roots[1], Fraction(.75)]):
                self.assertGreaterEqual(Fraction(event['time']), nominal)
                self.assertLessEqual(Fraction(event['time'])-nominal, Fraction(1e-12))
            for event, threshold in zip([events[0], events[2]], [.5, .5000000000000001]):
                self.assertLessEqual(abs(low+(high-low)*Fraction(event['time'])-Fraction(threshold)), Fraction(1e-9))
            self.assertTrue(all(a['time'] < b['time'] for a,b in zip(events, events[1:])))
            self.assertEqual(values(result)[-1], 1111)
            self.assertEqual(values(result, 'dut:z')[-1], 1)
            if previous is not None:
                self.assertEqual(events, previous)
            previous = events
        # The first cluster's delayed timer representative reaches the second
        # root's enclosure. Exact proofs must extend the connected cluster,
        # preserving distinct callbacks and physical output phases.
        crowded = compile_model(body.replace(f'timer({fixed!r},', 'timer(0.5,'), declarations)
        previous = None
        for times in [[0, 1], [0, .5, fixed, math.nextafter(fixed, math.inf), .625, .75, 1]]:
            result = run(crowded, {'u': [[0,.1],[1,.9]]}, times, stop=1)
            events = result['transient']['events']
            self.assertEqual([event['event'] for event in events], [0, 1, 2, 3])
            self.assertTrue(all(a['time'] < b['time'] for a,b in zip(events, events[1:])))
            expected = [int(Fraction(t) >= roots[0]) + 10*int(t >= .5) +
                        100*int(Fraction(t) >= roots[1]) + 1000*int(t >= .75)
                        for t in times]
            self.assertEqual(values(result), expected)
            if previous is not None:
                self.assertEqual(events, previous)
            previous = events
        for tolerances in ['1e-20,1e-9', '1e-12,1e-20']:
            tight = compile_model(body.replace('1e-12,1e-9', tolerances), declarations)
            with self.assertRaises(KernelError) as caught:
                run(tight, {'u': [[0,.1],[1,.9]]}, [0,1], stop=1)
            self.assertEqual(caught.exception.detail['kind'], 'event_resolution')
            # Both budgets share this production certificate diagnostic.
            self.assertIn('event uncertainty or representable time exceeds tolerances',
                          caught.exception.detail['message'])

    def test_falling_source_root_and_equivalent_or_share_the_exact_time(self):
        root = (Fraction(0.7)-Fraction(3))/(Fraction(0)-Fraction(3))*Fraction(6e-6)
        before = math.nextafter(float(root), -math.inf)
        after = math.nextafter(float(root), math.inf)
        self.assertLess(Fraction(before), root)
        self.assertGreater(Fraction(after), root)
        for guard in ['cross(V(u,r)-0.7,-1,1e-12,1e-9)',
                      'cross(V(u,r)-0.7,-1,1e-12,1e-9) or cross(2*(V(u,r)-0.7),-1,1e-12,1e-9)']:
            with self.subTest(guard=guard):
                program = compile_model('@(initial_step) n=0; @('+guard+') n=n+1; V(y,r)<+n;', 'integer n;')
                result = run(program, {'u': [[0,3],[6e-6,0]]}, [0,before,after,6e-6], stop=6e-6)
                self.assertEqual(values(result), [0,0,1,1])
                self.assertEqual(len(result['transient']['events']), 1)

    def test_cluster_extension_does_not_invent_an_internal_root_certificate(self):
        for threshold, reason in [
                (.5000000000000001, 'cannot certify ordering of distinct events with overlapping time bounds'),
                (.5000000000000003, 'cannot certify exact ordering of the next event while extending the connected cluster')]:
            program = compile_model(
                '@(initial_step) begin n=0; m=0; k=0; end '
                '@(cross(V(u,r)-0.5,1,1e-12,1e-9)) n=n+1; '
                '@(timer(0.5,0,1e-12)) k=k+1; '
                'V(z,r)<+V(u,r); '
                f'@(cross(V(z,r)-{threshold!r},1,1e-12,1e-9)) m=m+1; '
                'V(y,r)<+n+m+k;', 'integer n,m,k; electrical z;')
            for times in [[0, 1], [0, .5, math.nextafter(.5, math.inf), 1]]:
                with self.assertRaises(KernelError) as caught:
                    run(program, {'u': [[0,.1],[1,.9]]}, times, stop=1)
                self.assertEqual(caught.exception.detail['kind'], 'event_resolution')
                self.assertEqual(caught.exception.detail['message'], reason)

    def test_cluster_construction_respects_existing_transaction_microevent_budget(self):
        # A source root represented at .5 pushes each subsequent exact clock
        # one ULP forward. The prebuilt calendar must enforce the controller's
        # existing first-batch + 64 subsequent-batch budget during construction.
        for clocks in [64, 65, 1000]:
            time = .5
            nominal = []
            for _ in range(clocks):
                nominal.append(time)
                time = math.nextafter(time, math.inf)
            body = ('@(initial_step) n=0; '
                    '@(cross(V(u,r)-0.5,1,1e-9,1e-9)) n=n+1; ' +
                    ''.join(f'@(timer({time!r},0,1e-9)) n=n+1; ' for time in nominal) +
                    'V(y,r)<+n;')
            program = compile_model(body, 'integer n;')
            baseline = None
            for times in [[0, 1], [0, .5, nominal[1], nominal[-1], 1]]:
                if clocks > 64:
                    with self.assertRaises(KernelError) as caught:
                        run(program, {'u': [[0,.1],[1,.9]]}, times, stop=1)
                    self.assertEqual(caught.exception.detail['kind'], 'event_budget')
                    self.assertEqual(caught.exception.detail['message'],
                                     'bounded exact event cluster exceeds 64 subsequent microevents')
                else:
                    result = run(program, {'u': [[0,.1],[1,.9]]}, times, stop=1)
                    events = result['transient']['events']
                    self.assertEqual(len(events), 65)
                    expected = [int(Fraction(t) >= (Fraction(.5)-Fraction(.1))/(Fraction(.9)-Fraction(.1))) +
                                sum(t >= clock for clock in nominal) for t in times]
                    self.assertEqual(values(result), expected)
                    if baseline is not None:
                        self.assertEqual(events, baseline)
                    baseline = events

    def test_simultaneous_clock_leaves_share_one_microevent_budget_group(self):
        names = [f'n{i}' for i in range(72)]
        body = ('@(initial_step) begin ' + ''.join(f'{name}=0;' for name in names) +
                ' end @(cross(V(u,r)-0.5,1,1e-9,1e-9)) n0=n0+1; '
                '@(timer(0.5,0,1e-9)) n1=n1+1; ' +
                ''.join(f'@(timer(0.5000000000000001,0,1e-9)) {name}={name}+1; ' for name in names[2:]) +
                'V(y,r)<+' + '+'.join(names) + ';')
        result = run(compile_model(body, 'integer ' + ','.join(names) + ';'),
                     {'u': [[0,.1],[1,.9]]}, [0,.5,.5000000000000001,1], stop=1)
        self.assertEqual(values(result), [0,2,72,72])
        self.assertEqual(len(result['transient']['events']), 72)

    def test_original_affine_cross_keeps_query_phase_and_transition_sample(self):
        # The original binary-rational root lies just after the nominal query;
        # rounded endpoint guards must not erase that provable ordering.
        root = Fraction(0.7) * Fraction(6e-6) / 3
        query = 1.4e-6
        self.assertLess(Fraction(query), root)
        self.assertLess(root, Fraction(math.nextafter(query, math.inf)))
        program = compile_model(
            '@(initial_step) q=0; '
            '@(cross(V(u,r)-0.7,1,1e-12,1e-9)) q=V(u,r); '
            'V(y,r)<+q; V(z,r)<+transition(q,2.5e-7,1e-6,1e-6);',
            'real q; electrical z;')
        times = [0, query, math.nextafter(query, math.inf), 2e-6, 6e-6]
        result = run(program, {'u': [[0, 0], [6e-6, 3]]}, times,
                     stop=6e-6, vabstol=1e-6, reltol=1e-8)
        self.assertEqual(values(result)[:2], [0, 0])
        for value in values(result)[2:]:
            self.assertAlmostEqual(value, 0.7, delta=1e-7)
        self.assertEqual(len(result['transient']['events']), 1)
        for t, value in zip(times, values(result, 'dut:z')):
            expected = 0.7 * min(1, max(0, float((Fraction(t)-root-Fraction(2.5e-7))/Fraction(1e-6))))
            self.assertAlmostEqual(value, expected, delta=1e-6)

    def test_input_initialization_shared_counter_and_neighbor_clocks_share_one_history(self):
        # Independent binary-rational ordering: the second periodic event lies
        # strictly between the two adjacent query values, before the single timer.
        periodic = Fraction(0.1) + Fraction(0.2)
        self.assertLess(Fraction(0.3), periodic)
        self.assertLess(periodic, Fraction(0.30000000000000004))
        body = ('@(initial_step) n=INITIAL; '
                '@(timer(0.1,0.2,1e-12)) n=n+1; '
                '@(timer(0.30000000000000004,0,1e-12)) n=n+1; V(y,r)<+n;')
        inputs = {'u': [[0, 0.9], [0.4, 0.9]]}
        dense = [0, 0.1, 0.3, 0.30000000000000004, 0.4]
        sparse = [0, 0.1, 0.30000000000000004, 0.4]
        for initial in ['(V(u,r)>0.65)', '1']:
            with self.subTest(initial=initial):
                program = compile_model(body.replace('INITIAL', initial), 'real n;')
                result = run(program, inputs, dense, stop=0.4)
                self.assertEqual(values(result), [1, 2, 2, 4, 4])
                self.assertEqual(len(result['transient']['events']), 3)
                result_sparse = run(program, inputs, sparse, stop=0.4)
                self.assertEqual(values(result_sparse), [1, 2, 4, 4])
                self.assertEqual(result_sparse['transient']['events'], result['transient']['events'])
