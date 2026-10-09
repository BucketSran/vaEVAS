"""Held-threshold roots from piecewise equations, not an EVAS snapshot.

u=t, threshold=0.75 before 0.25 and 0.5 afterward: the only cross is 0.5.
The timer changes both future guards and state-dependent voltage projections.
"""
GUARDS = ["CROSS", "TIMER", "EVENT-ORDER", "EVENT-CONDITIONS", "case:event_relocalization"]

from pathlib import Path
import unittest
from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

DUT = (Path(__file__).with_name("fixtures") / "event_relocalization.va").read_text()


def run(source=DUT, *, module="event_relocalization", times=None, step=1):
    program = compile_sources({"relocalization.va": source}, [instance(module=module)])
    return transient(program, {"u": [[0,0],[1,1]]}, times or [0,.25,.5,.75,1],
                     stop=1, max_step=step, kernel=KERNEL)


class EventRelocalization(unittest.TestCase):
    def test_changed_threshold_invalidates_original_root(self):
        result = run()
        hits = result["transient"]["events"]
        self.assertEqual([hit["time"] for hit in hits], [.25,.5])
        self.assertEqual([row[-1] for row in result["transient"]["states"]], [0,0,1,1,1])

    def test_internal_voltage_projection_is_relocalized(self):
        source = model('''
          @(initial_step) q=0.75;
          @(initial_step) n=0;
          @(timer(0.25,0,1e-12)) q=0.5;
          @(cross(V(z,r),1,1e-9,1e-8)) n=n+1;
          V(z,r)<+V(u,r)-q;
          V(y,r)<+n;
        ''', 'real q; integer n; electrical z;')
        self.assertEqual([e["time"] for e in run(source, module="m")["transient"]["events"]], [.25,.5])

    def test_observations_and_steps_do_not_rearm_consumed_roots(self):
        a = run()
        b = run(times=[0,.125,.25,.375,.5,.625,.75,.875,1], step=.0625)
        self.assertEqual(a["transient"]["events"], b["transient"]["events"])
        self.assertEqual(b["transient"]["states"][-1][-1], 1)

    def test_removed_future_root_does_not_fire(self):
        source = DUT.replace('threshold=0.5;', 'threshold=2;')
        result = run(source)
        self.assertEqual([e["time"] for e in result["transient"]["events"]], [.25])
        self.assertEqual(result["transient"]["states"][-1][-1], 0)

    def test_initial_zero_of_held_guard_does_not_fire(self):
        source = model('''@(initial_step) n=0;
          @(cross(V(u,r)-n,1)) n=n+1; V(y,r)<+n;''', 'integer n;')
        result = run(source, module='m')
        self.assertEqual(result['transient']['events'], [])
        self.assertEqual(result['transient']['states'][-1], [0])

    def test_nonrepresentable_root_is_consumed_once(self):
        source = DUT.replace('threshold=0.5;', 'threshold=1.0/3.0;')
        result = run(source)
        hits = result['transient']['events']
        self.assertEqual(len(hits), 2)
        self.assertAlmostEqual(hits[1]['time'], 1/3, delta=1e-9)
        self.assertEqual(result['transient']['states'][-1][-1], 1)

    def test_moved_later_root_and_stop_arrival(self):
        for threshold in ('0.875', '1'):
            with self.subTest(threshold=threshold):
                result = run(DUT.replace('threshold=0.5;', f'threshold={threshold};'))
                self.assertEqual([e['time'] for e in result['transient']['events']],
                                 [.25, float(threshold)])

    def test_jump_across_zero_requires_separate_same_time_event_contract(self):
        source = DUT.replace('threshold=0.5;', 'threshold=0.125;')
        with self.assertRaisesRegex(KernelError, "unsupported_cross"):
            run(source)

    def test_history_dependent_relocalization_updates_the_root(self):
        source = DUT.replace('V(u,r)-threshold', 'idt(V(u,r),0)-threshold')
        result = run(source)
        self.assertEqual([event['time'] for event in result['transient']['events']], [.25, 1])

    def test_relocalization_with_unrelated_history_preserves_joint_frames(self):
        from test_continuous_dynamics import compile_model, run as run_history, values
        for guard, root in (('V(u,r)-q', .5), ('pow(V(u,r),2)-q', 2**-.5)):
            program=compile_model('''@(initial_step) begin q=0.75; n=0; end
              @(timer(0.25,0,1e-12)) q=0.5;
              @(cross('''+guard+''',1,1e-9,1e-8)) n=n+1;
              V(y,r)<+n; V(z,r)<+idt(-pow(V(z,r),2),1);''',
              'real q; integer n;',ports='u,y,z,r',directions='input u; output y,z; inout r;')
            times=[0,.25,.5,.75,1]
            r=run_history(program,{'u':[[0,0],[1,1]]},times,stop=1,vabstol=1e-9,reltol=0)
            self.assertEqual(len(r['transient']['events']),2)
            self.assertAlmostEqual(r['transient']['events'][1]['time'],root,delta=1e-9)
            for t,z in zip(times,values(r,'z')):
                self.assertAlmostEqual(z,1/(1+t),delta=1e-9)

    def test_polynomial_held_threshold_uses_the_same_epoch_and_commit_rule(self):
        source=DUT.replace('V(u,r)-threshold', 'pow(V(u,r),2)-threshold')
        a=run(source,times=[0,1])
        b=run(source,times=[0,.125,.25,.5,.75,1],step=.0625)
        self.assertEqual(a['transient']['events'],b['transient']['events'])
        events=a['transient']['events']
        self.assertEqual(len(events),2)
        self.assertEqual(events[0]['time'],.25)
        self.assertAlmostEqual(events[1]['time'],2**-.5,delta=1e-9)
        self.assertEqual(a['transient']['states'][-1][-1],1)

    def test_polynomial_relocalization_follows_internal_voltage_projection(self):
        source=model('''@(initial_step) begin q=0.75; n=0; end
          @(timer(0.125,0,1e-12)) q=0.5;
          @(cross(pow(V(z,r),2)-1,1,1e-9,1e-8)) n=n+1;
          V(z,r)<+V(u,r)+q; V(y,r)<+n;''', 'real q; integer n; electrical z;')
        # u+q reaches 1 at .25 in the initial epoch; q changes at .125,
        # where both guard values remain negative. The new root is .5.
        result=run(source,module='m')
        events=result['transient']['events']
        self.assertEqual(len(events),2)
        self.assertEqual(events[0]['time'],.125)
        self.assertGreaterEqual(events[1]['time'],.5)
        self.assertLessEqual(events[1]['time']-.5,1e-9)


if __name__ == '__main__':
    unittest.main()
