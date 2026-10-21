"""Cross event bodies observe the right limit of the crossing (LRM 2.4 5.10.3.1).

The standard says the event "shall occur after the threshold crossing", inside
the time/expression tolerance box. A body read of the crossing signal therefore
sees the post-crossing side, not g(tau)=0. Inputs here are exact PWL ramps, so
each expected branch is decided by hand from the ramp directions alone. When
no one-sided certificate exists, a condition that is exactly zero at tau and
varies with time must be refused instead of reusing g(tau)=0.
"""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["CROSS", "EVENT-CONDITIONS"]

import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

UP = [[0, 0], [1, 1]]
DOWN = [[0, 1], [1, 0]]
# The same functions as UP and DOWN, with an extra knot exactly at the threshold.
KNOT_UP = [[0, 0], [.5, .5], [1, 1]]
KNOT_DOWN = [[0, 1], [.5, .5], [1, 0]]


def events(text, u=UP, w=None, **tolerances):
    ports, directions = ('u,w,y,r', 'input u,w; output y; inout r;') if w else ('u,y,r', 'input u; output y; inout r;')
    text = model(text, 'real q, p;', ports=ports, directions=directions)
    connections = dict(u='u', y='y', r='0', **({'w': 'w'} if w else {}))
    program = compile_sources({'right.va': text}, [instance(connections=connections)])
    sources = {'u': u, **({'w': w} if w else {})}
    result = transient(program, sources, [0, .25, .75, 1], stop=1, max_step=2, kernel=KERNEL, **tolerances)
    names = result['transient']['state_names']
    return [dict(zip(names, e['after'])) for e in result['transient']['events']]


def run(body, *, trigger, u=UP, w=None, **tolerances):
    text = f'@(initial_step) begin q=0; p=0; end @({trigger}) begin {body} end V(y,r)<+q;'
    return [e['dut:q'] for e in events(text, u, w, **tolerances)]


class CrossRightLimit(unittest.TestCase):
    def test_fired_guard_predicate_sees_crossing_side(self):
        # Rising u crosses 0.5 at tau=0.5; just after, u>0.5.
        self.assertEqual(run('if (V(u,r)>0.5) q=2; else q=3;', trigger='cross(V(u,r)-0.5,0)'), [2])
        # Falling u: just after, u<0.5.
        self.assertEqual(run('if (V(u,r)>0.5) q=2; else q=3;', trigger='cross(V(u,r)-0.5,0)', u=DOWN), [3])
        self.assertEqual(run('if (V(u,r)<0.5) q=2; else q=3;', trigger='cross(V(u,r)-0.5,0)', u=DOWN), [2])
        # Negated scale k=-1 of the guard: 0.5-u<0 just after a rising crossing.
        self.assertEqual(run('if (0.5-V(u,r)<0) q=2; else q=3;', trigger='cross(V(u,r)-0.5,1)'), [2])

    def test_or_leaves_with_opposite_simultaneous_crossings(self):
        # u rises and w falls through 0.5 at the same exact root.
        body = 'q=0; if (V(u,r)>0.5) q=q+1; if (V(w,r)>0.5) q=q+2;'
        trigger = 'cross(V(u,r)-0.5,0) or cross(V(w,r)-0.5,0)'
        self.assertEqual(run(body, trigger=trigger, w=DOWN), [1])

    def test_coincident_unfired_input_uses_its_right_slope(self):
        # w is not a fired guard; it is exactly 0.5 at tau and moving.
        body = 'if (V(w,r)>0.5) q=2; else q=3;'
        self.assertEqual(run(body, trigger='cross(V(u,r)-0.5,1)', w=UP), [2])
        self.assertEqual(run(body, trigger='cross(V(u,r)-0.5,1)', w=DOWN), [3])

    def test_negative_controls_keep_value_without_side_certificate(self):
        # Plateau exactly at threshold: a proven zero slope keeps equality.
        flat = [[0, .5], [1, .5]]
        self.assertEqual(run('if (V(w,r)>0.5) q=2; else q=3;', trigger='cross(V(u,r)-0.5,1)', w=flat), [3])
        self.assertEqual(run('if (V(w,r)>=0.5) q=2; else q=3;', trigger='cross(V(u,r)-0.5,1)', w=flat), [2])
        # A distinct later crossing of w is still below threshold at tau.
        late = [[0, 0], [1, .9]]
        self.assertEqual(run('if (V(w,r)>0.5) q=2; else q=3;', trigger='cross(V(u,r)-0.5,1)', w=late), [3])
        # An amplitude band has no certified crossing side; still refused.
        with self.assertRaisesRegex(KernelError, 'unsupported_source_uncertainty'):
            run('if (V(u,r)>0.5) q=2; else q=3;', trigger='cross(V(u,r)-0.5,0)',
                source_errors={'u': 1e-12})
        # Point timers execute at their time; no crossing side exists.
        self.assertEqual(run('if (V(u,r)>0.5) q=2; else q=3;', trigger='timer(0.5)'), [3])

    def test_knot_at_the_threshold_takes_the_leaving_segment_side(self):
        # KNOT_UP is UP pointwise. The root arrives exactly at the knot u=0.5;
        # the following affine segment decides the side just after tau.
        cross = 'cross(V(u,r)-0.5,0)'
        self.assertEqual(run('if (V(u,r)>0.5) q=2; else q=3;', trigger=cross, u=KNOT_UP), [2])
        self.assertEqual(run('if (V(u,r)>0.5) q=2; else q=3;', trigger=cross, u=KNOT_DOWN), [3])
        self.assertEqual(run('if (V(u,r)<0.5) q=2; else q=3;', trigger=cross, u=KNOT_DOWN), [2])
        # Touching 0.5 and turning back: u<0.5 just after tau, so u>=0.5 is false.
        touch = [[0, 0], [.5, .5], [1, 0]]
        self.assertEqual(run('if (V(u,r)>=0.5) q=2; else q=3;', trigger=cross, u=touch), [3])
        # Arriving on a plateau at 0.5: the right limit is exactly 0.5.
        plateau = [[0, 0], [.5, .5], [1, .5]]
        self.assertEqual(run('if (V(u,r)>0.5) q=2; else q=3;', trigger=cross, u=plateau), [3])
        self.assertEqual(run('if (V(u,r)>=0.5) q=2; else q=3;', trigger=cross, u=plateau), [2])

    def test_arrival_at_stop_has_no_right_limit(self):
        # u reaches 0.5 exactly at stop=1; nothing after tau can be observed.
        ends = [[0, 0], [1, .5]]
        with self.assertRaisesRegex(KernelError, 'event_condition'):
            run('if (V(u,r)>0.5) q=2; else q=3;', trigger='cross(V(u,r)-0.5,0)', u=ends)
        # Identical arms need no side.
        self.assertEqual(run('if (V(u,r)>0.5) q=2; else q=2;', trigger='cross(V(u,r)-0.5,0)', u=ends), [2])

    def test_unrelated_simultaneous_timer_keeps_the_crossing_side(self):
        # The timer block shares the batch at t=0.5 but cannot move the cross
        # body's observation away from tau+.
        text = ('@(initial_step) begin q=0; p=0; end '
                '@(cross(V(u,r)-0.5,0)) begin if (V(u,r)>0.5) q=2; else q=3; end '
                '@(timer(0.5)) p=1; V(y,r)<+q;')
        observed = events(text)
        self.assertEqual([e['dut:q'] for e in observed], [2, 2])
        self.assertEqual([e['dut:p'] for e in observed], [1, 1])
        # An OR body fired by its timer leaf executes at the timer's exact time.
        self.assertEqual(run('if (V(u,r)>0.5) q=2; else q=3;', trigger='cross(V(u,r)-0.5,0) or timer(0.5)'), [3])

    def test_latched_crossing_value_needs_a_side_certificate(self):
        # q=V(u) is read at te>tau, so q>0.5 holds for every admissible te. The
        # root enclosure stores q=0.5 exactly and has no side for q-0.5: refuse.
        cross = 'cross(V(u,r)-0.5,0)'
        with self.assertRaisesRegex(KernelError, 'event_condition'):
            run('q=V(u,r); if (q>0.5) p=2; else p=3;', trigger=cross)
        # The live read still has its side, and identical arms need no side.
        self.assertEqual(run('q=V(u,r); if (V(u,r)>0.5) q=2; else q=3;', trigger=cross), [2])
        self.assertEqual(run('q=V(u,r); if (q>0.5) q=2; else q=2;', trigger=cross), [2])
        # A time-invariant exact tie keeps its value.
        self.assertEqual(run('q=0.5; if (q>0.5) q=2; else q=3;', trigger=cross), [3])

    def test_state_dependent_guard_reads_its_side(self):
        # The guard u-q holds the accepted state q=0.5; u>q is the same zero set.
        def held(body, u):
            text = ('@(initial_step) begin q=0.5; p=0; end '
                    f'@(cross(V(u,r)-q,0)) begin {body} end V(y,r)<+p;')
            return [e['dut:p'] for e in events(text, u)]
        self.assertEqual(held('if (V(u,r)>q) p=2; else p=3;', UP), [2])
        self.assertEqual(held('if (V(u,r)>q) p=2; else p=3;', DOWN), [3])
        self.assertEqual(held('if (V(u,r)>=q) p=2; else p=3;', DOWN), [3])

    def test_negated_scale_on_a_falling_crossing(self):
        # 0.5-u = -(u-0.5): after a falling crossing, 0.5-u>0.
        cross = 'cross(V(u,r)-0.5,-1)'
        self.assertEqual(run('if (0.5-V(u,r)>0) q=2; else q=3;', trigger=cross, u=DOWN), [2])
        self.assertEqual(run('if (0.5-V(u,r)<=0) q=2; else q=3;', trigger=cross, u=DOWN), [3])


if __name__ == '__main__':
    unittest.main()
