"""Fixed timer ordering against exact binary64 Fraction schedules.

These development cases retain each clock's time tolerance and test ordering,
same-time settlement and refusal when no representable legal schedule exists.
"""
GUARDS = ["TIMER", "EVENT-ORDER", "COMPOSE"]

from fractions import Fraction as Q
import unittest

from evas import KernelError
from test_affine import model
from test_timer import run_timer


def clocks(a=2e-6, b=3e-6, tol=1e-9):
    return model(f'''@(initial_step) begin n=0; m=0; end
        @(timer({a!r},{a!r},{tol!r})) n=n+1;
        @(timer({b!r},{b!r},{tol!r})) m=m+1;
        V(y,r)<+n+10*m;''', 'integer n,m;')


class TimerOrdering(unittest.TestCase):
    def test_nearby_nominal_clocks_preserve_order_count_and_query_invariance(self):
        # 3*binary64(2us) < 2*binary64(3us), despite both printing as 6us.
        expected = sorted([(Q(2e-6)*(k+1), 0) for k in range(3)]
                          + [(Q(3e-6)*(k+1), 1) for k in range(2)])
        self.assertLess(expected[-2][0], expected[-1][0])
        baseline = None
        for times, step in [([0, 7e-6], 7e-6),
                            ([0, 2.5e-6, 3.5e-6, 4.5e-6, 6e-6, 7e-6], 1.1e-7)]:
            result = run_timer(clocks(), stop=7e-6, times=times, step=step)
            events = result['transient']['events']
            self.assertEqual([e['event'] for e in events], [i for _, i in expected])
            for event, (nominal, _) in zip(events, expected):
                self.assertGreaterEqual(Q(event['time']), nominal)
                self.assertLessEqual(Q(event['time'])-nominal, Q(1e-9))
            self.assertTrue(all(a['time'] < b['time'] for a, b in zip(events, events[1:])))
            self.assertEqual(result['transient']['states'][-1], [3, 2])
            if baseline is None:
                baseline = events
            else:
                self.assertEqual(events, baseline)

    def test_declaration_order_does_not_change_physical_order(self):
        source = clocks()
        first = '@(timer(2e-06,2e-06,1e-09)) n=n+1;'
        second = '@(timer(3e-06,3e-06,1e-09)) m=m+1;'
        self.assertIn(first, source)
        self.assertIn(second, source)
        swapped = source.replace(first, 'SWAP').replace(second, first).replace('SWAP', second)
        original = run_timer(source, stop=7e-6, times=[0, 7e-6])
        reverse = run_timer(swapped, stop=7e-6, times=[0, 7e-6])
        self.assertEqual(original['transient']['states'], reverse['transient']['states'])
        self.assertEqual([(e['time'], e['event']) for e in original['transient']['events']],
                         [(e['time'], 1-e['event']) for e in reverse['transient']['events']])

    def test_equal_exact_nominals_with_different_periods_share_settlement(self):
        # .1 + 2*.1 == .1 + .2 exactly, but the rounded interval is non-point.
        self.assertEqual(Q(.1)+2*Q(.1), Q(.1)+Q(.2))
        source = model('''@(initial_step) begin n=0; held=0; end
          @(timer(.1,.2,1e-6)) held=V(y,r);
          @(timer(.1,.1,1e-6)) n=n+1;
          V(y,r)<+n;''', 'integer n; real held;')
        result = run_timer(source, stop=.35, times=[0, .35])
        events = result['transient']['events']
        self.assertEqual(len(events), 5)
        self.assertEqual(events[-2]['time'], events[-1]['time'])
        self.assertEqual(result['transient']['states'][-1], [3, 3])

    def test_ordering_cannot_relax_original_timer_tolerance(self):
        with self.assertRaises(KernelError) as caught:
            run_timer(clocks(tol=1e-23), stop=7e-6, times=[0, 7e-6])
        self.assertEqual(caught.exception.detail['kind'], 'event_resolution')

    def test_exact_equal_writers_still_fail_same_batch_ownership(self):
        source = model('''@(initial_step) n=0;
          @(timer(.1,.1,1e-6)) n=n+1;
          @(timer(.3,0,1e-6)) n=n+2;
          V(y,r)<+n;''', 'integer n;')
        # Use the same exact decomposition so a literal .3 rounding difference
        # cannot accidentally turn the ownership obligation into ordering.
        source = source.replace('timer(.3,0,', 'timer(.1,.2,')
        with self.assertRaises(KernelError) as caught:
            run_timer(source, stop=.35, times=[0, .35])
        # PR102 alone rejects cross-block shared reads while preparing the
        # event model; the PR101 composition defers ownership to settlement.
        # Both paths reject the same competing writers, with these two kinds.
        self.assertIn(caught.exception.detail['kind'], ['unsupported_cross', 'event_conflict'])

    def test_mixed_timer_cross_overlap_remains_uncertified(self):
        # The binary64 .3 ramp threshold is before 3*binary64(.1), although
        # the timer's outward interval includes the representable cross root.
        self.assertLess(Q(.3), 3*Q(.1))
        source = model("""@(initial_step) begin n=0; m=0; end
          @(timer(.1,.1,1e-6)) n=n+1;
          @(cross(V(u,r)-.3,1,1e-9,1e-8)) m=m+1;
          V(y,r)<+n+10*m;""", 'integer n,m;')
        with self.assertRaisesRegex(KernelError,
                'event_resolution.*overlapping time bounds'):
            run_timer(source, stop=.35, times=[0,.35])

    def test_mixed_timer_held_timer_overlap_remains_uncertified(self):
        # q is held and exact. Both clocks have the same exact .3 nominal,
        # but its non-point time enclosure cannot certify mixed simultaneity.
        self.assertEqual(Q(.1)+Q(.2), 3*Q(.1))
        source = model("""@(initial_step) begin q=.1; n=0; m=0; end
          @(timer(.1,.2,1e-6)) n=n+1;
          @(timer(q,q,1e-6)) m=m+1;
          V(y,r)<+n+10*m;""", 'real q; integer n,m;')
        with self.assertRaisesRegex(KernelError,
                'event_resolution.*overlapping time bounds'):
            run_timer(source, stop=.35, times=[0,.35])

    def test_near_timer_history_rebuild_preserves_after_boundary_refusal(self):
        # The first near-6us event's representative reaches the next event's
        # nominal window. The integral guard selects history calendar rebuild;
        # z(t)=integral(n) stays below 1 here and produces no competing root.
        # That future timer window cannot be certified after acceptance.
        source = clocks().replace('integer n,m;', 'integer n,m; electrical z;').replace(
            'V(y,r)<+n+10*m;', 'V(y,r)<+n+10*m; V(z,r)<+idt(n,0); '
            '@(cross(V(z,r)-1,1,1e-9,1e-8));')
        prefix = run_timer(source, stop=5e-6, times=[0,5e-6])
        self.assertEqual(prefix['transient']['states'][-1], [2,1])
        self.assertEqual(len(prefix['transient']['events']), 3)
        with self.assertRaisesRegex(KernelError,
                'event_resolution.*accepted.*boundary'):
            run_timer(source, stop=7e-6, times=[0,7e-6])


if __name__ == '__main__':
    unittest.main()
