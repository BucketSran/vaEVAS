"""Cross event bodies observe the right limit of the crossing (LRM 2.4 5.10.3.1).

The standard says the event "shall occur after the threshold crossing", inside
the time/expression tolerance box. A body read of the crossing signal therefore
sees the post-crossing side, not g(tau)=0. Inputs here are exact PWL ramps, so
each expected branch is decided by hand from the ramp directions alone.
"""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["CROSS", "EVENT-CONDITIONS"]

import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

UP = [[0, 0], [1, 1]]
DOWN = [[0, 1], [1, 0]]


def run(body, *, trigger, u=UP, w=None, **tolerances):
    ports, directions = ('u,w,y,r', 'input u,w; output y; inout r;') if w else ('u,y,r', 'input u; output y; inout r;')
    text = model(f'@(initial_step) q=0; @({trigger}) begin {body} end V(y,r)<+q;',
                 'real q;', ports=ports, directions=directions)
    connections = dict(u='u', y='y', r='0', **({'w': 'w'} if w else {}))
    program = compile_sources({'right.va': text}, [instance(connections=connections)])
    sources = {'u': u, **({'w': w} if w else {})}
    result = transient(program, sources, [0, .25, .75, 1], stop=1, max_step=2, kernel=KERNEL, **tolerances)
    events = result['transient']['events']
    return [e['after'][0] for e in events]


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
        # Plateau exactly at threshold: no right slope, so equality holds.
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


if __name__ == '__main__':
    unittest.main()
