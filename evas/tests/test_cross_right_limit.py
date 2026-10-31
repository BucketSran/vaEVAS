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
from floor_rn_contract import floor_contract

import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

UP = [[0, 0], [1, 1]]
DOWN = [[0, 1], [1, 0]]
# The same functions as UP and DOWN, with an extra knot exactly at the threshold.
KNOT_UP = [[0, 0], [.5, .5], [1, 1]]
KNOT_DOWN = [[0, 1], [.5, .5], [1, 0]]


def body_records(result):
    """Event records after the IR33 initial_step batch.

    IR33 records the initial_step bodies first, at t=0. Expectations written
    for the later events read this view; the initial records are checked to be
    exactly that leading prefix, never silently dropped.
    """
    records = result['transient']['events']
    count = 0
    while count < len(records) and records[count]['kind'] == 'initial_step':
        assert records[count]['time'] == 0, records[count]
        count += 1
    assert all(r['kind'] != 'initial_step' for r in records[count:]), 'initial records form the leading batch'
    return records[count:]


def events(text, u=UP, w=None, *, return_program=False, initial=False, **tolerances):
    ports, directions = ('u,w,y,r', 'input u,w; output y; inout r;') if w else ('u,y,r', 'input u; output y; inout r;')
    text = model(text, 'real q, p;', ports=ports, directions=directions)
    connections = dict(u='u', y='y', r='0', **({'w': 'w'} if w else {}))
    program = compile_sources({'right.va': text}, [instance(connections=connections)])
    sources = {'u': u, **({'w': w} if w else {})}
    result = transient(program, sources, [0, .25, .75, 1], stop=1, max_step=2, kernel=KERNEL, **tolerances)
    if return_program:
        return program, result
    names = result['transient']['state_names']
    records = result['transient']['events'] if initial else body_records(result)
    return [dict(zip(names, e['after'])) for e in records]


def run(body, *, trigger, u=UP, w=None, **tolerances):
    text = f'@(initial_step) begin q=0; p=0; end @({trigger}) begin {body} end V(y,r)<+q;'
    return [e['dut:q'] for e in events(text, u, w, **tolerances)]


def check_rising_cross(result, program):
    # The UP source has exact tau=.5 and RN(u(tau))=.5. The body reads tau+,
    # where u>0.5, so q=2: the sample's rounding does not decide the side.
    from initial_record_contract import check_initial_record_batch
    view = check_initial_record_batch(result, program, [0., 0.], [0., 0.], 1)
    assert result['transient']['state_names'] == ['dut:q', 'dut:p']
    assert result['transient']['times'] == [0., .25, .75, 1.]
    assert result['transient']['states'] == [[0.,0.], [0.,0.], [2.,0.], [2.,0.]]
    assert len(result['solutions']) == 4
    records = view['transient']['events']
    assert len(records) == 1
    wire = program.to_dict()
    expected = [(i, e) for i,e in enumerate(wire['events']) if e['trigger']['kind'] == 'cross']
    assert len(expected) == 1
    index, event = expected[0]
    record = records[0]
    origin = event['origin']
    label = f"{origin['source']}:{origin['line']}:{origin['column']} ({origin['instance']})"
    assert type(record['event']) is int and record['event'] == index
    assert record['kind'] == 'cross' and record['origin'] == label
    assert record['time'] == .5 and record.get('observation_time_bounds', [.5,.5]) == [.5,.5]
    assert record['guard_value'] == 0.
    assert not record.get('fired_triggers')
    assert record['before'] == [0.,0.] and record['after'] == [2.,0.]

class CrossRightLimit(unittest.TestCase):
    def test_fired_guard_predicate_sees_crossing_side(self):
        # Rising u crosses 0.5 at tau=0.5; just after, u>0.5.
        self.assertEqual(run('if (V(u,r)>0.5) q=2; else q=3;', trigger='cross(V(u,r)-0.5,0)'), [2])
        text = '@(initial_step) begin q=0; p=0; end @(cross(V(u,r)-0.5,0)) begin if (V(u,r)>0.5) q=2; else q=3; end V(y,r)<+q;'
        program, result = events(text, return_program=True)
        check_rising_cross(result, program)
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


def sampled(body, *, w, trigger='cross(V(u,r)-0.5,1)', u=UP, initial=True):
    """Body reads p after one rising crossing of u at tau=0.5 with input w.

    The floor expectations carry the IR33 initial_step record (their RN
    contract checks every t=0 record); initial=False reads the later events.
    """
    text = f'@(initial_step) begin q=0; p=0; end @({trigger}) begin {body} end V(y,r)<+p;'
    return [e['dut:p'] for e in events(text, u, w, initial=initial)]


class CrossRightWindow(unittest.TestCase):
    """Exact zeros decided on the right window W=[lo, next_up(hi)] of the root.

    W contains (tau, tau+e] for the root tau. A difference that stays exactly
    zero there (a plateau) is read as zero at tau+; a difference whose window
    enclosure still meets both branches is refused, never guessed.
    """

    def test_floor_inside_one_bin_is_a_plateau(self):
        with floor_contract(self, 'right'):
            # w=0.5 at tau and moving; 3*w stays in (1,2), so floor(3*w)=1 just after tau.
            floor = 'q=floor(3*V(w,r)); '
            self.assertEqual(sampled(floor + 'if (q<1) p=2; else p=3;', w=UP), [0, 3])
            self.assertEqual(sampled(floor + 'if (q>=1) p=2; else p=3;', w=UP), [0, 2])
            self.assertEqual(sampled(floor + 'if (q>1) p=2; else p=3;', w=DOWN), [0, 3])
            self.assertEqual(sampled(floor + 'if (q<=1) p=2; else p=3;', w=DOWN), [0, 2])

    def test_floor_argument_on_an_integer_needs_its_bin_after_tau(self):
        with floor_contract(self, 'right'):
            # 2*w is exactly 1 at tau. A falling w enters floor bin 0 just after
            # tau, where q<1 holds, but the root value is 1: refuse rather than guess.
            floor = 'q=floor(2*V(w,r)); '
            with self.assertRaisesRegex(KernelError, 'event_condition'):
                sampled(floor + 'if (q<1) p=2; else p=3;', w=DOWN)
            # A rising w stays in bin 1 over the whole window: q<1 is false.
            self.assertEqual(sampled(floor + 'if (q<1) p=2; else p=3;', w=UP), [0, 3])

    def test_latched_input_cancels_exactly(self):
        # q=V(w) at te, so V(w)-q is identically zero although w moves.
        self.assertEqual(sampled('q=V(w,r); if (V(w,r)-q>0) p=2; else p=3;', w=UP, initial=False), [3])
        self.assertEqual(sampled('q=V(w,r); if (V(w,r)-q>=0) p=2; else p=3;', w=UP, initial=False), [2])
        # u rises and w falls: u-q>0 just after tau, but the window enclosure
        # [0, 2e] only proves u-q>=0. The strict comparison is refused.
        with self.assertRaisesRegex(KernelError, 'event_condition'):
            sampled('q=V(w,r); if (V(u,r)-q>0) p=2; else p=3;', w=DOWN, initial=False)
        self.assertEqual(sampled('q=V(w,r); if (V(u,r)-q>=0) p=2; else p=3;', w=DOWN, initial=False), [2])

    def test_constant_inputs_keep_an_exact_root_tie(self):
        # u rises through 0.5 twice. With w flat at 0.7, the second edge
        # recomputes the latched (0.7-0.3) exactly; rounded intervals would
        # straddle zero, but every read is constant over the window.
        twice = [[0, 0], [.25, 1], [.5, 0], [.75, 1], [1, 0]]
        flat = [[0, .7], [1, .7]]
        body = 'if (V(w,r)-0.3-q<0) p=p+2; else p=p+3; q=V(w,r)-0.3;'
        self.assertEqual(sampled(body, w=flat, u=twice, initial=False), [3, 6])
        # Moving w changes 0.7-0.3 between the edges; no tie arises.
        ramp = [[0, .7], [1, .8]]
        self.assertEqual(sampled(body, w=ramp, u=twice, initial=False), [3, 6])

    def test_settled_history_is_a_plateau_but_a_moving_one_is_not(self):
        def history(body, timer, edge):
            text = (f'@(initial_step) begin q=0; p=0; end @(timer({timer})) q={edge[0]}; '
                    f'@(cross(V(u,r)-0.5,1)) begin {body} end '
                    f'V(y,r)<+transition(q,0,{edge[1]},{edge[1]}); V(w,r)<+p;')
            text = model(text, 'real q, p;', ports='u,y,w,r', directions='input u; output y,w; inout r;')
            program = compile_sources({'right.va': text}, [instance(connections=dict(u='u', y='y', w='w', r='0'))])
            result = transient(program, {'u': UP}, [0, .25, .75, 1], stop=1, max_step=2, kernel=KERNEL)
            names = result['transient']['state_names']
            return [dict(zip(names, e['after']))['dut:p'] for e in body_records(result)]
        # transition(q) reached 0.5 long before tau and stays there.
        settled = (0.5, '1n')
        self.assertEqual(history('if (V(y,r)>0.5) p=2; else p=3;', 0.1, settled), [0, 3])
        self.assertEqual(history('if (V(y,r)>=0.5) p=2; else p=3;', 0.1, settled), [0, 2])
        # A slow transition passes exactly 0.5 at tau and keeps rising.
        moving = (1, 0.5)
        with self.assertRaisesRegex(KernelError, 'event_condition'):
            history('if (V(y,r)>0.5) p=2; else p=3;', 0.25, moving)
        self.assertEqual(history('if (V(y,r)>=0.5) p=2; else p=3;', 0.25, moving), [0, 2])


if __name__ == '__main__':
    unittest.main()
