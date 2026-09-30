"""Exact examples for EVENT_CONDITIONS_CONTRACT.md, never an EVAS executor.

Time x=t/T and voltage are rational. Point roots below are GIVEN mathematical
witnesses, not floating-point root certificates. The small scalar recurrence
specifies a sampler; it does not parse VA, solve circuits, model general operator
histories, or test engine rollback. Existing eight-condition graders stay intact.
Run from any directory with Python 3.10+; only the standard library is used.
"""

from dataclasses import dataclass, replace
from fractions import Fraction as Q
import hashlib
import io
import json
from pathlib import Path
import unittest


ZERO, HALF, INITIAL = Q(0), Q(1, 2), Q(1, 10)


def points(*pairs):
    return tuple((Q(t), Q(v)) for t, v in pairs)


LOW = points((0, 0), (4, 0))
HIGH = points((0, 1), (4, 1))
CLOCK = points((0, 0), ("1/2", 0), ("3/2", 1), (4, 1))
DATA = points((0, "1/4"), (4, "3/4"))


def pwl(wave, time):
    """Exact linear interpolation of the explicitly supplied rational fixture."""
    if len(wave) < 2 or any(a[0] >= b[0] for a, b in zip(wave, wave[1:])):
        raise ValueError("fixture times must increase")
    for (a, va), (b, vb) in zip(wave, wave[1:]):
        if a <= time <= b:
            return va + (vb - va) * (time - a) / (b - a)
    raise ValueError("query outside fixture")


def rising_arrivals(wave):
    """Solve each a<1/2<=b segment exactly; initial/zero departures add nothing."""
    pwl(wave, wave[0][0])  # Validate the whole time sequence.
    return tuple(a + (HALF - va) * (b - a) / (vb - va)
                 for (a, va), (b, vb) in zip(wave, wave[1:])
                 if va < HALF <= vb)


@dataclass(frozen=True)
class Hit:
    instance: str
    block: str
    leaf: str
    time: Q


@dataclass(frozen=True)
class Invocation:
    instance: str
    block: str
    time: Q
    leaves: tuple[str, ...]


def exact_union(hits):
    """Finite-set definition ONLY: equal exact rational roots are supplied."""
    groups = {}
    for hit in hits:
        key = (hit.time, hit.instance, hit.block)
        groups.setdefault(key, set()).add(hit.leaf)
    return tuple(Invocation(instance, block, time, tuple(sorted(leaves)))
                 for (time, instance, block), leaves in sorted(groups.items()))


@dataclass(frozen=True)
class Record:
    invocation: Invocation
    before: Q
    after: Q


def sampler(clock, reset, *, data=DATA, initial=INITIAL, instance="A", strict=False):
    """The documented one-variable mathematical recurrence, with no solver."""
    hits = [Hit(instance, "sample", leaf, time)
            for leaf, wave in (("clk", clock), ("rst", reset))
            for time in rising_arrivals(wave)]
    q, result = initial, []
    for invocation in exact_union(hits):
        reset_voltage = pwl(reset, invocation.time)
        reset_active = reset_voltage > HALF if strict else reset_voltage >= HALF
        after = initial if reset_active else pwl(data, invocation.time)
        result.append(Record(invocation, q, after))
        q = after
    return tuple(result)


def held(time, records, initial=INITIAL):
    values = [row.after for row in records if row.invocation.time <= time]
    return values[-1] if values else initial


def truth(relation, low, high):
    """Three-valued enclosure predicate; None means proof unavailable."""
    if low > high:
        raise ValueError("reversed enclosure")
    rules = {
        "ge": (low >= 0, high < 0),
        "gt": (low > 0, high <= 0),
        "le": (high <= 0, low > 0),
        "lt": (high < 0, low >= 0),
    }
    yes, no = rules[relation]
    return True if yes else False if no else None


def order(a, b):
    """Only interval/point evidence; overlapping windows cannot prove a tie."""
    if a[0] > a[1] or b[0] > b[1]:
        raise ValueError("reversed enclosure")
    if a[0] == a[1] == b[0] == b[1]:
        return "same"
    if a[1] < b[0]:
        return "before"
    if b[1] < a[0]:
        return "after"
    return "unresolved"


def short_pulse(time, delta):
    """Closed form for EC-WAVE only, including its symmetric interrupted fall."""
    if not 0 <= delta < Q(1, 40):
        raise ValueError("example requires interruption before the first edge ends")
    if time <= 1 or time >= 1 + 2 * delta:
        return INITIAL
    if time <= 1 + delta:
        return INITIAL + 11 * (time - 1)
    return INITIAL + 11 * (1 + 2 * delta - time)


def trace_matches(observed, expected):
    """Exact fixture receipt comparison, not a tolerant waveform grader.

    Retains no-op events, time, instance/block/leaf identities and both states.
    This intentionally requires the supplied exact witness, so it must NOT be
    used to grade arbitrary backend event times in their permitted windows.
    """
    return tuple(observed) == tuple(expected)


class EventConditionsMath(unittest.TestCase):
    def test_or_union_keeps_leaf_provenance(self):
        """EC-OR: one body despite multiple same-root leaves."""
        hits = [Hit("A", "sample", leaf, Q(1)) for leaf in ("clk", "rst", "clk_copy")]
        expected = (Invocation("A", "sample", Q(1), ("clk", "clk_copy", "rst")),)
        self.assertEqual(exact_union(hits), expected)
        self.assertEqual(exact_union(hits + [hits[0]]), expected)
        self.assertEqual(exact_union(reversed(hits)), expected)
        self.assertEqual(len(hits), 3)  # A per-leaf body execution would be wrong.

    def test_separate_blocks_and_instances_are_not_deduplicated(self):
        """EC-OR: block identity and instance identity survive equal roots."""
        hits = [Hit("A", "first", "clk", Q(1)), Hit("A", "second", "clk", Q(1)),
                Hit("B", "first", "clk", Q(1))]
        result = exact_union(hits)
        self.assertEqual([(x.instance, x.block) for x in result],
                         [("A", "first"), ("A", "second"), ("B", "first")])
        # This is invocation counting, not permission for two blocks to write q.
        self.assertEqual(len(result), 3)

    def test_exact_boundary_uses_current_view_and_source_comparison(self):
        """EC-BOUNDARY: >= resets; > samples at an exact root."""
        inclusive = sampler(CLOCK, CLOCK)
        strict = sampler(CLOCK, CLOCK, strict=True)
        self.assertEqual(len(inclusive), 1)
        self.assertEqual(inclusive[0].invocation.leaves, ("clk", "rst"))
        self.assertEqual(inclusive[0].after, INITIAL)
        self.assertEqual(strict[0].after, Q(3, 8))
        self.assertLess(pwl(CLOCK, Q(3, 4)), HALF)  # A previous observation lies low.
        self.assertEqual(pwl(CLOCK, Q(1)), HALF)
        self.assertGreater(pwl(CLOCK, Q(1001, 1000)), HALF)  # Later legal time differs.
        falling_reset = tuple((t, 1 - v) for t, v in CLOCK)
        release_tie = sampler(CLOCK, falling_reset)
        self.assertEqual(release_tie[0].invocation.leaves, ("clk",))
        self.assertEqual(release_tie[0].after, INITIAL)  # >= includes release equality too.
        self.assertEqual(sampler(CLOCK, falling_reset, strict=True)[0].after, Q(3, 8))

    def test_clock_alone_and_reset_alone_update(self):
        """EC-SINGLE: distinguish sampling from the later reset-only invocation."""
        clock_only = sampler(CLOCK, LOW)
        self.assertEqual([(r.invocation.time, r.after) for r in clock_only], [(Q(1), Q(3, 8))])
        reset = points((0, 0), ("3/2", 0), ("5/2", 1), (4, 1))
        rows = sampler(CLOCK, reset)
        self.assertEqual([(r.invocation.time, r.invocation.leaves, r.after) for r in rows],
                         [(Q(1), ("clk",), Q(3, 8)), (Q(2), ("rst",), INITIAL)])
        self.assertEqual(held(Q(3, 2), rows), Q(3, 8))
        self.assertEqual(held(Q(5, 2), rows), INITIAL)

    def test_initial_high_sustained_reset_and_release(self):
        """EC-SINGLE: no startup/release callback; clocks during reset still run."""
        self.assertEqual(sampler(HIGH, LOW), ())
        self.assertEqual(sampler(LOW, HIGH), ())
        initially_equal = points((0, "1/2"), (1, "1/2"), (2, 1), (4, 1))
        self.assertEqual(rising_arrivals(initially_equal), ())
        clock = points((0, 0), ("1/2", 0), ("3/2", 1), ("7/4", 1),
                       (2, 0), ("5/2", 0), ("7/2", 1), (4, 1))
        reset = points((0, 1), ("7/4", 1), ("9/4", 0), (4, 0))
        rows = sampler(clock, reset)
        self.assertEqual([(r.invocation.time, r.after) for r in rows],
                         [(Q(1), INITIAL), (Q(3), Q(5, 8))])
        self.assertEqual(held(Q(5, 2), rows), INITIAL)  # Released, not sampled.
        sustained = sampler(clock, HIGH)
        self.assertEqual(len(sustained), 2)
        self.assertEqual([r.after for r in sustained], [INITIAL, INITIAL])

    def test_nearby_roots_keep_both_orders(self):
        """EC-NEAR: roots closer than ttol are still two distinct occurrences."""
        for delta in (Q(1, 2000), Q(1, 2**20)):
            with self.subTest(delta=str(delta)):
                later = points((0, 0), (HALF + delta, 0), (Q(3, 2) + delta, 1), (4, 1))
                rows = sampler(CLOCK, later)
                self.assertEqual([(r.invocation.time, r.after) for r in rows],
                                 [(Q(1), Q(3, 8)), (1 + delta, INITIAL)])
                self.assertEqual(held(1 + delta / 2, rows), Q(3, 8))
                reverse = sampler(later, CLOCK)
                self.assertEqual([(r.invocation.time, r.after) for r in reverse],
                                 [(Q(1), INITIAL), (1 + delta, INITIAL)])
                self.assertLess(delta, Q(1, 1000))
                self.assertEqual(order((Q(1), Q(1)), (1 + delta, 1 + delta)), "before")
        self.assertEqual(order((Q(1), Q(1001, 1000)), (Q(1), Q(1001, 1000))), "unresolved")
        self.assertEqual(order((Q(1), Q(1)), (Q(1), Q(1))), "same")

    def test_interrupted_output_has_a_closed_form(self):
        """EC-WAVE: held and finite-edge output are distinct observables."""
        for delta in (Q(1, 2000), Q(1, 2**20)):
            self.assertEqual(short_pulse(Q(1), delta), INITIAL)
            self.assertEqual(short_pulse(1 + delta, delta), INITIAL + 11 * delta)
            self.assertEqual(short_pulse(1 + Q(3, 2) * delta, delta), INITIAL + Q(11, 2) * delta)
            self.assertEqual(short_pulse(1 + 2 * delta, delta), INITIAL)
        self.assertEqual(short_pulse(Q(1), ZERO), INITIAL)
        self.assertGreater(11 * Q(1, 2000), Q(1, 1000))
        self.assertLess(11 * Q(1, 2**20), Q(1, 1000))
        # Identical sparse samples cannot prove that the small pulse was detected.
        sparse = (Q(0), Q(1), Q(2), Q(4))
        self.assertEqual([short_pulse(t, Q(1, 2**20)) for t in sparse], [INITIAL] * 4)

    def test_predicate_three_valued_boundaries(self):
        """EC-PREDICATE: no epsilon substitutes for sign or equality evidence."""
        cases = [((0, 0), (True, False, True, False)),
                 ((0, 1), (True, None, None, False)),
                 ((-1, 0), (None, False, True, None)),
                 ((-1, 1), (None, None, None, None)),
                 ((1, 2), (True, True, False, False)),
                 ((-2, -1), (False, False, True, True))]
        for (low, high), expected in cases:
            self.assertEqual(tuple(truth(op, Q(low), Q(high)) for op in ("ge", "gt", "le", "lt")), expected)
        tiny = Q(1, 2**1074)
        self.assertIs(truth("gt", tiny, tiny), True)
        self.assertIs(truth("ge", -tiny, -tiny), False)
        with self.assertRaises(ValueError):
            truth("ge", Q(1), Q(-1))

    def test_affine_predicate_and_nonzero_dependence(self):
        """EC-PREDICATE: stateless reduction works; tiny state coupling is real."""
        for reset in (Q(1, 4), HALF, Q(3, 4)):
            z = 2 * reset - Q(1, 4)
            self.assertEqual(z >= Q(3, 4), reset >= HALF)
        coefficient = Q(1, 2**1074)
        self.assertNotEqual(coefficient * Q(0), coefficient * Q(1))
        # A candidate-dependent predicate cannot be certified by rounding this away.
        self.assertIs(truth("ge", -coefficient, coefficient), None)

    def test_feedback_fixed_point_counterexamples(self):
        """EC-FEEDBACK: multiple/absent/unique solutions all need a scope check."""
        def fixed_points(high, low):
            return {q for q in (high, low) if q == (high if q >= HALF else low)}

        self.assertEqual(fixed_points(Q(1), Q(0)), {Q(0), Q(1)})
        self.assertEqual(fixed_points(Q(0), Q(1)), set())
        self.assertEqual(fixed_points(Q(3, 4), Q(1)), {Q(3, 4)})
        old_q = Q(0)
        guessed = Q(3, 4) if old_q >= HALF else Q(1)
        self.assertNotEqual(guessed, Q(3, 4))
        # No EVAS admission check is claimed here, even for the unique case.

    def test_selected_sequence_and_missing_else(self):
        """EC-SEQUENCE: assignments before/inside/after the branch see local writes."""
        for reset, expected in ((True, (Q(13), Q(14))), (False, (Q(6), Q(7)))):
            q = Q(2)
            q = q + 1
            if reset:
                q = q + 10
            else:
                q = 2 * q
            saved = q
            q = q + 1
            self.assertEqual((saved, q), expected)
        q = INITIAL
        if truth("ge", Q(-1), Q(-1)):
            q = Q(99)
        self.assertEqual(q, INITIAL)
        intermediate = (2**31 - 1) + 1
        final = intermediate - 1
        self.assertGreater(intermediate, 2**31 - 1)
        self.assertLessEqual(final, 2**31 - 1)  # Cannot legalize the earlier overflow.

    def test_declaration_order_and_observation_grid_invariance(self):
        """EC-INVARIANCE: absolute answers as well as permutation equality."""
        b_data = points((0, "1/2"), (4, "1/4"))
        specs = (("A", DATA, INITIAL), ("B", b_data, Q(3, 10)))
        def evaluate(declarations):
            return {name: sampler(CLOCK, LOW, data=data, initial=initial, instance=name)
                    for name, data, initial in declarations}

        first = evaluate(specs)
        swapped = evaluate(reversed(specs))
        self.assertEqual(first, swapped)
        a, b = first["A"], first["B"]
        self.assertEqual(a[0].after, Q(3, 8))
        self.assertEqual(b[0].after, Q(7, 16))
        coarse = (Q(0), Q(1), Q(2), Q(4))
        fine = tuple(Q(k, 8) for k in range(33))
        for records, initial, sampled in ((a, INITIAL, Q(3, 8)), (b, Q(3, 10), Q(7, 16))):
            values = {t: held(t, records, initial) for t in fine}
            self.assertEqual([values[t] for t in coarse], [initial, sampled, sampled, sampled])
            self.assertEqual([held(t, records, initial) for t in coarse], [values[t] for t in coarse])
        # This verifies the oracle's independence, not EVAS grid invariance.

    def test_exact_receipt_accept_reject_calibration(self):
        """EC-CALIBRATION: no-op events count and identity errors remain failures."""
        expected = (Record(Invocation("A", "sample", Q(1), ("clk", "rst")), INITIAL, INITIAL),)
        self.assertTrue(trace_matches(sampler(CLOCK, CLOCK), expected))
        first = expected[0]
        bad = {
            "missing": (),
            "duplicate": expected + expected,
            "wrong_branch": (replace(first, after=Q(3, 8)),),
            "wrong_instance": (replace(first, invocation=replace(first.invocation, instance="B")),),
            "lost_leaf": (replace(first, invocation=replace(first.invocation, leaves=("clk",))),),
            "release_event": expected + (replace(first, invocation=replace(first.invocation, time=Q(2))),),
        }
        for name, trace in bad.items():
            with self.subTest(control=name):
                self.assertFalse(trace_matches(trace, expected))
        self.assertIs(truth("ge", Q(-1, 10**12), Q(1, 10**12)), None)
        self.assertEqual(order((Q(1), Q(2)), (Q(3, 2), Q(5, 2))), "unresolved")

    def test_original_sample_offset_budgets_are_unchanged(self):
        """Original eight-condition constants: propagate one common event offset."""
        clock_window = min(Q(1, 1000), Q(1, 5000) / 5)
        reset_window = min(Q(1, 1000), Q(1, 5000) / 10)
        self.assertEqual(clock_window, Q(1, 25000))
        self.assertEqual(reset_window, Q(1, 50000))
        self.assertEqual(Q(3, 20) * clock_window, Q(6, 10**6))
        self.assertEqual(Q(1, 10) * clock_window, Q(4, 10**6))


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EventConditionsMath)
    labels = [test.shortDescription() for test in suite]
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    source = Path(__file__).resolve()
    report = {
        "kind": "design_math_and_exact_receipt_calibration_only",
        "baseline_commit": "5b090571c7de7c6ec08a05c803479505c5d745ee",
        "checker_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "units": {"time": "x=t/T", "voltage": "V"},
        "math_test_methods": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "checked_obligations": labels,
        "simulators_executed": [],
        "formal_condition_count_added": 0,
        "target_conditions": 8,
        "target_condition_pass_count": None,
        "engine_rollback_verified": False,
        "floating_point_root_certificates_verified": False,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not result.wasSuccessful():
        print(stream.getvalue())
        raise SystemExit(1)


if __name__ == "__main__":
    main()
