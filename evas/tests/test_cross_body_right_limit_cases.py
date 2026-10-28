"""Comparisons in cross event bodies read the post-crossing side (issue #281).

LRM 2.4 5.10.3.1: the event "shall occur after the threshold crossing". EVAS
reads such a body at the right limit tau+ (events.md, cross-right-limit): a
comparison that is exactly zero at the crossing takes its post-root side when a
certificate exists, and is refused with event_condition otherwise. Every
expected value below is decided by hand from the exact PWL ramps: on a falling
ramp V>=v is false just after V crosses v, on a rising ramp V>v is true just
after. EVAS runs a timer-fired body (also an OR body whose timer leaf fired) at
the exact timer time; that point time is an EVAS choice inside the LRM time
tolerance, and the arrival rules at a root reached at stop are EVAS conventions
(events.md), not LRM requirements. The SCS cases are the minimal reproductions
of #281.
"""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["CROSS", "EVENT-CONDITIONS"]

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evas import KernelError, compile_sources, transient
from evas.scs import simulate_scs
from test_affine import KERNEL, instance, model

UP = [[0, 0], [1, 1]]
DOWN = [[0, 1], [1, 0]]
# V(code) falls from 3 to 1 on [1u, 2u]: it crosses 2.5 at 1.25u and 1.5 at 1.75u.
FALL = '[0 3 1u 3 2u 1 3u 1]'
# V(code) rises from 1 to 3 on [1u, 2u]: it crosses 1.5 at 1.25u and 2.5 at 1.75u.
RISE = '[0 1 1u 1 2u 3 3u 3]'
TERNARY3 = 'c=(V(code)>=2.5)?3:((V(code)>=1.5)?2:((V(code)>=0.5)?1:0));'
IFELSE3 = 'begin if (V(code)>=2.5) c=3; else if (V(code)>=1.5) c=2; else if (V(code)>=0.5) c=1; else c=0; end'
TERNARY2 = 'c=(V(code)>=2.5)?3:((V(code)>=1.5)?2:1);'
GT2 = 'c=(V(code)>2.5)?3:((V(code)>1.5)?2:1);'
OR3 = 'cross(V(code)-0.5,0) or cross(V(code)-1.5,0) or cross(V(code)-2.5,0)'
OR2 = 'cross(V(code)-1.5,0) or cross(V(code)-2.5,0)'
SINGLE = 'c=(V(code)>=1.5)?2:1;'

# name: (ramp, declarations, analog body, {sample time in us: y})
CASES = {
    'f_or3_ternary': (FALL, 'integer c;', f'@(initial_step) {TERNARY3}\n @({OR3}) {TERNARY3}\n V(y) <+ c;',
                      {1.0: 3, 1.5: 2, 2.5: 1}),
    'f_or3_ifelse': (FALL, 'integer c;', f'@(initial_step) {IFELSE3}\n @({OR3}) {IFELSE3}\n V(y) <+ c;',
                     {1.0: 3, 1.5: 2, 2.5: 1}),
    'f_or2_ternary': (FALL, 'integer c;', f'@(initial_step) {TERNARY2}\n @({OR2}) {TERNARY2}\n V(y) <+ c;',
                      {1.0: 3, 1.5: 2, 2.5: 1}),
    'f_single_ge': (FALL, 'integer c;', f'@(initial_step) {SINGLE}\n @(cross(V(code)-1.5,0)) {SINGLE}\n V(y) <+ c;',
                    {1.0: 2, 1.5: 2, 2.5: 1}),
    'f_single_ge_dir': (FALL, 'integer c;',
                        f'@(initial_step) {SINGLE}\n @(cross(V(code)-1.5,-1)) {SINGLE}\n V(y) <+ c;',
                        {1.0: 2, 1.5: 2, 2.5: 1}),
    'f_single_real': (FALL, 'real r;', '@(initial_step) r=(V(code)>=1.5)?2.0:1.0;\n'
                      ' @(cross(V(code)-1.5,0)) r=(V(code)>=1.5)?2.0:1.0;\n V(y) <+ r;',
                      {1.0: 2, 1.5: 2, 2.5: 1}),
    'r_or2_gt': (RISE, 'integer c;', f'@(initial_step) {GT2}\n @({OR2}) {GT2}\n V(y) <+ c;',
                 {1.0: 1, 1.5: 2, 2.5: 3}),
    # The timer fires at 0.5u, 1.5u and 2.5u; it never coincides with the crossing at 1.75u.
    's_timer_or': (FALL, 'integer c;', f'@(initial_step) {SINGLE}\n'
                   f' @(cross(V(code)-1.5,0) or timer(0.5e-6,1e-6)) {SINGLE}\n V(y) <+ c;',
                   {1.0: 2, 1.6: 2, 1.8: 1, 2.4: 1, 2.6: 1}),
    # Control: one direct assignment per crossing, no comparison in the body.
    'c_direction': (FALL, 'integer c;', '@(initial_step) c=3;\n @(cross(V(code)-2.5,-1)) c=2;\n'
                    ' @(cross(V(code)-1.5,-1)) c=1;\n V(y) <+ c;', {1.0: 3, 1.5: 2, 2.5: 1}),
}


def scs_values(name):
    ramp, declarations, body, expected = CASES[name]
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        (work / 'dut.va').write_text('`include "disciplines.vams"\nmodule probe(code, y);\n'
                                     'input code; output y; electrical code, y;\n'
                                     f'{declarations}\nanalog begin\n {body}\nend\nendmodule\n')
        (work / 'tb.scs').write_text('simulator lang=spectre\nahdl_include "dut.va"\n'
                                     f'Vc (code 0) vsource type=pwl wave={ramp}\nX (code y) probe\n'
                                     'tran tran stop=3u maxstep=10n\nsave code y\n')
        saved = simulate_scs(work / 'tb.scs', kernel=KERNEL, timeout=120)['saved']
    y = saved['nodes'].index('y')
    times, values = saved['times'], saved['values']
    got = {}
    for label in expected:
        # The last saved row at or before the sample time (the 10 ns grid).
        row = max(i for i, t in enumerate(times) if t <= label * 1e-6 * (1 + 1e-12))
        got[label] = values[row][y]
    return got, expected


def body_records(result):
    # IR33 records the initial_step batch first, at t=0; keep it out of the answers.
    records = result['transient']['events']
    count = 0
    while count < len(records) and records[count]['kind'] == 'initial_step':
        assert records[count]['time'] == 0, records[count]
        count += 1
    assert all(r['kind'] != 'initial_step' for r in records[count:])
    return records[count:]


def events(text, *, u=UP, declarations='real q, p; integer c, k, m;', outputs='y', sources=None):
    ports = f'u,{outputs},r'
    text = model(text, declarations, ports=ports, directions=f'input u; output {outputs}; inout r;')
    connections = dict(u='u', r='0', **{name: name for name in outputs.split(',')})
    program = compile_sources({'right.va': text}, [instance(connections=connections)])
    result = transient(program, sources or {'u': u}, [0, .25, .75, 1], stop=1, max_step=2, kernel=KERNEL)
    names = result['transient']['state_names']
    return [(e['kind'], e['time'], dict(zip(names, e['after']))) for e in body_records(result)]


def after(text, state, **kwargs):
    return [values[f'dut:{state}'] for _, _, values in events(text, **kwargs)]


class ProbeCases(unittest.TestCase):
    """The #281 reproductions: ternaries, if/else, OR leaves, directions, targets, timers."""

    def check(self, name):
        got, expected = scs_values(name)
        self.assertEqual(got, {label: float(value) for label, value in expected.items()})

    def test_three_or_leaves_with_a_ternary_ladder(self):
        self.check('f_or3_ternary')

    def test_three_or_leaves_with_an_if_else_ladder(self):
        self.check('f_or3_ifelse')

    def test_two_or_leaves_with_a_ternary_ladder(self):
        self.check('f_or2_ternary')

    def test_single_leaf_integer_target(self):
        self.check('f_single_ge')

    def test_single_falling_only_leaf(self):
        self.check('f_single_ge_dir')

    def test_single_leaf_real_target(self):
        self.check('f_single_real')

    def test_rising_crossings_with_strict_comparisons(self):
        self.check('r_or2_gt')

    def test_cross_or_an_unrelated_timer(self):
        self.check('s_timer_or')

    def test_direct_assignment_control(self):
        self.check('c_direction')


class BodyForms(unittest.TestCase):
    """The same rule through ternaries, if/else, integer and real targets and loops."""

    def test_integer_and_real_ternary_targets_read_the_post_root_side(self):
        integer = '@(initial_step) c=0; @(cross(V(u,r)-0.5,0)) c=(V(u,r)>=0.5)?2:1; V(y,r)<+c;'
        self.assertEqual(after(integer, 'c', u=DOWN), [1])
        self.assertEqual(after(integer, 'c', u=UP), [2])
        real = '@(initial_step) q=0; @(cross(V(u,r)-0.5,0)) q=(V(u,r)>0.5)?2.0:1.0; V(y,r)<+q;'
        self.assertEqual(after(real, 'q', u=UP), [2])
        self.assertEqual(after(real, 'q', u=DOWN), [1])

    def test_else_if_chain_on_both_directions(self):
        body = ('@(initial_step) c=0; @(cross(V(u,r)-0.5,0)) begin if (V(u,r)>0.5) c=3; '
                'else if (V(u,r)>=0.5) c=2; else c=1; end V(y,r)<+c;')
        # Rising: u>0.5 just after tau. Falling: u<0.5, so both tests are false.
        self.assertEqual(after(body, 'c', u=UP), [3])
        self.assertEqual(after(body, 'c', u=DOWN), [1])

    def test_loop_condition_uses_the_same_rule(self):
        # m takes the post-root side; the loop bound k<m then runs 0 or 1 time.
        body = ('@(initial_step) begin c=0; k=0; m=0; end @(cross(V(u,r)-0.5,0)) begin '
                'm=(V(u,r)>=0.5)?1:0; c=0; k=0; while (k<m) begin c=7; k=k+1; end end V(y,r)<+c;')
        self.assertEqual([(v['dut:m'], v['dut:c'], v['dut:k']) for _, _, v in events(body, u=DOWN)],
                         [(0., 0., 0.)])
        self.assertEqual([(v['dut:m'], v['dut:c'], v['dut:k']) for _, _, v in events(body, u=UP)],
                         [(1., 7., 1.)])


class SameInstantTimers(unittest.TestCase):
    def test_separate_timer_block_and_or_timer_leaf(self):
        # A separate timer block in the same batch leaves the cross body at tau+.
        # The OR body fired by its timer leaf uses the EVAS point time.
        text = ('@(initial_step) begin q=0; p=0; end '
                '@(cross(V(u,r)-0.5,0)) begin if (V(u,r)>=0.5) q=2; else q=3; end '
                '@(timer(0.5)) p=1; V(y,r)<+q;')
        observed = events(text, u=DOWN)
        self.assertEqual([(v['dut:q'], v['dut:p']) for _, _, v in observed], [(3., 1.), (3., 1.)])
        # An OR body fired by its timer leaf runs at the exact time, where u=0.5.
        text = ('@(initial_step) begin q=0; p=0; end '
                '@(cross(V(u,r)-0.5,0) or timer(0.5)) begin if (V(u,r)>=0.5) q=2; else q=3; end V(y,r)<+q;')
        self.assertEqual(after(text, 'q', u=DOWN), [2])


def history(body, *, timers=''):
    # y = transition(q) rises from 0 at 0.25 and passes 0.5 exactly at tau=0.5,
    # where u crosses 0.5 upward.
    text = ('@(initial_step) begin q=0; p=0; end @(timer(0.25)) q=1; ' + timers +
            f'@(cross(V(u,r)-0.5,1)) begin {body} end '
            'V(y,r)<+transition(q,0,0.5,0.5); V(w,r)<+p;')
    return after(text, 'p', outputs='y,w')


class MovingHistory(unittest.TestCase):
    def test_separate_timer_block_and_cross_block_refuse_moving_history(self):
        # A separate same-instant timer block may change histories before tau+:
        # the pure cross body reads no history window, and y is moving and
        # exactly at the threshold at tau, so the strict comparison has no side.
        with self.assertRaisesRegex(KernelError, 'event_condition'):
            history('if (V(y,r)>0.5) p=2; else p=3;', timers='@(timer(0.5)) c=1; ')
        # The non-strict comparison isolates the batch rule: an all-cross batch
        # proves y>=0.5 from the history window [0.5, 0.5+e]; the mixed one cannot.
        self.assertEqual(history('if (V(y,r)>=0.5) p=2; else p=3;'), [0, 2])
        with self.assertRaisesRegex(KernelError, 'event_condition'):
            history('if (V(y,r)>=0.5) p=2; else p=3;', timers='@(timer(0.5)) c=1; ')

    def test_cross_or_timer_moving_history_uses_point_value(self):
        # cross OR timer(0.5): the timer leaf fired, so the body reads the point
        # value y(0.5)=1/2 (EVAS point time): y>0.5 is false, y>=0.5 is true.
        def ored(body):
            text = ('@(initial_step) begin q=0; p=0; end @(timer(0.25)) q=1; '
                    f'@(cross(V(u,r)-0.5,1) or timer(0.5)) begin {body} end '
                    'V(y,r)<+transition(q,0,0.5,0.5); V(w,r)<+p;')
            return after(text, 'p', outputs='y,w')
        self.assertEqual(ored('if (V(y,r)>0.5) p=2; else p=3;'), [0, 3])
        self.assertEqual(ored('if (V(y,r)>=0.5) p=2; else p=3;'), [0, 2])


class NoCertificate(unittest.TestCase):
    def test_refusals_without_a_one_sided_certificate(self):
        ends = [[0, 0], [1, .5]]
        cases = [
            # The root arrives at stop: nothing after tau is observable.
            ('@(initial_step) c=0; @(cross(V(u,r)-0.5,0)) c=(V(u,r)>=0.5)?2:1; V(y,r)<+c;', ends),
            # A latched crossing value holds 0.5 exactly; q-0.5 has no side.
            ('@(initial_step) begin q=0; c=0; end @(cross(V(u,r)-0.5,0)) begin q=V(u,r); '
             'c=(q>=0.5)?2:1; end V(y,r)<+c;', DOWN),
        ]
        for text, u in cases:
            with self.subTest(text=text), self.assertRaisesRegex(KernelError, 'event_condition'):
                events(text, u=u)

    def test_identical_arms_continue_without_a_side(self):
        ends = [[0, 0], [1, .5]]
        text = ('@(initial_step) c=0; @(cross(V(u,r)-0.5,0)) begin if (V(u,r)>=0.5) c=2; else c=2; end '
                'V(y,r)<+c;')
        self.assertEqual(after(text, 'c', u=ends), [2])


class KernelUnitFixture(unittest.TestCase):
    def test_kernel_unit_fixture_matches_the_front_end(self):
        # procedure_right_limit_tests reads a derived IR snapshot; the check never writes it.
        tests = Path(__file__).resolve().parent
        fixture = tests.parent / 'rust_core/tests/fixtures/ir33_cross_right_limit.json'
        before = fixture.read_bytes()
        completed = subprocess.run([sys.executable, '-B', str(tests / 'helpers/check_cross_right_limit_fixture.py')],
                                   capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(fixture.read_bytes(), before)
        self.assertIs(json.loads(completed.stdout)['programs_match_frontend'], True)


if __name__ == '__main__':
    unittest.main()
