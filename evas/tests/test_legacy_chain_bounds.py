"""Hand-derived anchors and true-corner controls for chain enclosures."""
GUARDS = ['TRANSITION', 'DYNAMICS', 'COMPOSE', 'QUALIFICATION']
from decimal import Decimal as D, localcontext
from fractions import Fraction as F
import itertools
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'validation/paper'))
import legacy_chain_bounds as b


def record(label, index, t, radius=0):
    return {'label': label, 'index': index, 'time_s': t,
            'time_bounds_s': [t-radius, t+radius]}


def rational(value):
    if isinstance(value, F):
        with localcontext() as ctx:
            ctx.prec = 120
            return D(value.numerator)/D(value.denominator)
    return D.from_float(value) if type(value) is float else D(value)


class LegacyChainBounds(unittest.TestCase):
    def contains(self, box, value):
        value = rational(value)
        self.assertLessEqual(box[0], value)
        self.assertGreaterEqual(box[1], value)

    def test_directed_operations_and_exp(self):
        self.contains((b.I(1)/3).pair(), F(1, 3))
        with localcontext() as ctx:
            ctx.prec = 120
            value = D('-0.5').exp()
        self.contains(b.I(-.5).exp().pair(), value)
        with self.assertRaises(b.BoundsPending):
            b.I(1)/b.I(-1, 1)

    def test_hand_rising_reversal_and_area(self):
        # Rise at 1 with duration 1; reverse at 1.5 using the old target 1.
        # The descent has slope -1 and ends at 2, not at 2.5.
        poly = b.Polygon(0, [(1, 1), (1.5, 0)], 0, 1, 1)
        for t, value in [(1.25, F(1, 4)), (1.75, F(1, 4)), (2, 0), (3, 0)]:
            self.contains(poly.value(t).pair(), value)
        same = b.Polygon(0, [(1, 1), (1.5, 2)], 0, 1, 1)
        self.contains(same.value(1.75).pair(), 1)
        self.contains(same.value(2.25).pair(), 2)
        self.contains(b.rectangles(3, 1, [(1, 2), (2, -1)], offset=.5).pair(), F(5, 2))

    def test_hand_filter_ramp_anchor(self):
        # f(1.5)=h-1+exp(-h), h=.5, for a unit ramp begun at 1.
        poly = b.Polygon(0, [(1, 1)], 0, 1, 1)
        with localcontext() as ctx:
            ctx.prec = 120
            answer = D('0.5')-1+D('-0.5').exp()
        self.contains(poly.filtered(1.5, 1).pair(), answer)

    def test_pwl_box_contains_interior_extremum(self):
        points = [[0., 0.], [1., 2.], [2., -1.]]
        result = b.pwl(points, (.75, 1.25)).pair()
        self.contains(result, 2)
        self.contains(result, F(5, 4))

    def test_nonpoint_reversal_contains_independent_true_corners(self):
        rise = b.I(1, 1.01)
        reverse = b.I(1.49, 1.5)
        time = b.I(1.75, 1.76)
        result = b.Polygon(0, [(rise, 1), (reverse, 0)], 0, 1, 1).value(time).pair()
        # At reversal r, value=r-a. During descent value=2r-a-t.
        for a, r, t in itertools.product((rise.lo, rise.hi), (reverse.lo, reverse.hi), (time.lo, time.hi)):
            with localcontext() as ctx:
                ctx.prec = 120
                value = 2*r-a-t
            self.contains(result, value)
        self.assertGreater(result[1]-result[0], D('.01'))

    def test_nonpoint_interrupted_filter_contains_true_corners(self):
        first = b.I(1., 1.01)
        reverse = b.I(1.49, 1.5)
        query = b.I(2.2, 2.21)
        result = b.Polygon(0, [(first, 1), (reverse, 0)], 0, 1, 1).filtered(query, 1).pair()
        # Slopes are +1, -1, 0 at a, r, 2r-a. Thus f=K(t-a)-2K(t-r)+K(t-(2r-a)).
        for a, r, t in itertools.product((first.lo, first.hi), (reverse.lo, reverse.hi), (query.lo, query.hi)):
            with localcontext() as ctx:
                ctx.prec = 120
                def K(h):
                    return h-1+(-h).exp()
                answer = K(t-a)-2*K(t-r)+K(t-(2*r-a))
            self.contains(result, answer)

    def test_nonpoint_same_direction_filter_contains_true_corners(self):
        first = b.I(1., 1.01)
        extension = b.I(1.49, 1.5)
        query = b.I(2.4, 2.41)
        result = b.Polygon(0, [(first, 1), (extension, 2)], 0, 1, 1).filtered(query, 1).pair()
        # Preserve origin zero, so the new slope is 2 and its end is 1+(r+a)/2.
        for a, r, t in itertools.product((first.lo, first.hi), (extension.lo, extension.hi), (query.lo, query.hi)):
            with localcontext() as ctx:
                ctx.prec = 120
                def K(h):
                    return h-1+(-h).exp()
                end = 1+(r+a)/2
                answer = K(t-a)+K(t-r)-2*K(t-end)
            self.contains(result, answer)

    def test_integral_box_contains_independent_rectangular_corners(self):
        card = {'kind': 'integral', 'inputs': {'u': [[0., 0.], [4e-6, 4.]]}}
        callbacks = [record('sample', 1, 1e-6, 1e-10), record('sample', 2, 2e-6, 1e-10)]
        result = b.envelope(card, callbacks, 3e-6)
        self.assertEqual(result['status'], 'proved')
        for a, c in itertools.product(callbacks[0]['time_bounds_s'], callbacks[1]['time_bounds_s']):
            # Piecewise rectangular integral with q(a)=4*a/(4e-6).
            a, c, t, scale = map(F.from_float, (a, c, 3e-6, 1e-6))
            gain = F(4)/F.from_float(4e-6)
            value = F.from_float(.05)+F(1, 4)*a/scale+(gain*a)*(c-a)/scale+(gain*c)*(t-c)/scale
            self.contains(result['outputs']['i'], value)
        self.assertLess(result['reference_error_V'], D('1e-65'))

    def test_c2_filter_samples_use_independent_exponential_anchor(self):
        card = {'kind': 'c2', 'inputs': {'vin': [[0., 0.], [1., 0.], [2., 1.], [4., 1.]]}}
        sample = b.sample_envelope(card, 'sample', (1.25, 1.75), 1)
        tau = rational(.5e-6)
        for t in (D('1.25'), D('1.75')):
            with localcontext() as ctx:
                ctx.prec = 120
                h = t-1
                answer = h-tau*(1-(-h/tau).exp())
            self.contains(sample, answer)

    def test_uncertain_completion_stays_pending(self):
        with self.assertRaisesRegex(b.BoundsPending, 'completed/interrupted'):
            b.Polygon(0, [(b.I(1, 1.1), 1), (b.I(1.99, 2.11), 0)], 0, 1, 1)

    def test_nt_overlapping_boxes_include_both_orders(self):
        card = {'kind': 'nt', 'chain': True}
        callbacks = [record('b', 1, .1), record('a', 1, .3, 1e-15),
                     record('b', 2, .1+.2, 1e-15)]
        result = b.envelope(card, callbacks, .325)
        self.assertEqual(result['status'], 'proved')
        orders = list(b.nt_orders(callbacks))
        self.assertEqual(len(orders), 2)
        # Independent integral: each jump contributes delta*(t-event).
        for a, c in itertools.product(callbacks[1]['time_bounds_s'], callbacks[2]['time_bounds_s']):
            value = F.from_float(.1)*(F.from_float(.325)-F.from_float(.1))
            value += F.from_float(.01)*(F.from_float(.325)-F.from_float(a))
            value += F.from_float(.1)*(F.from_float(.325)-F.from_float(c))
            self.contains(result['outputs']['i'], value)
            with localcontext() as ctx:
                ctx.prec = 120
                t, a, c, tau, small, large = map(rational, (.325, a, c, .05, .01, .1))
                edge = large+(small*(t-a)+large*(t-c))/tau
                self.contains(result['outputs']['e'], edge)
                def K(h):
                    return h-tau*(1-(-h/tau).exp())
                # The first .1 jump ends at .1+.05; later jumps are still
                # rising at this query, so their cancellation knots are future.
                first = rational(.1)
                answer = large/tau*(K(t-first)-K(t-first-tau))
                answer += small/tau*K(t-a)+large/tau*K(t-c)
                self.contains(result['outputs']['f'], answer)

    def test_exact_same_time_retains_trace_order(self):
        records = [record('b', 1, .3), record('a', 1, .3)]
        self.assertEqual(list(b.nt_orders(records)), [records])

    def test_same_channel_overlapping_or_reversed_boxes_stay_pending(self):
        card={'kind':'integral','inputs':{'u':[[0.,0.],[4e-6,4.]]}}
        for callbacks in ([record('sample',1,1e-6,1e-7),record('sample',2,1.1e-6,1e-7)],
                          [record('sample',1,2e-6),record('sample',2,1e-6)]):
            result=b.envelope(card,callbacks,3e-6)
            self.assertEqual(result['status'],'pending')
            self.assertIn('same-channel',result['reason'])
        records=[record('b',1,.3,1e-4),record('b',2,.30001,1e-4)]
        self.assertEqual(list(b.nt_orders(records)),[records])

    def test_malformed_reference_evidence_is_pending(self):
        result=b.envelope({'kind':'integral','inputs':{'u':[]}},[record('sample',1,1e-6)],2e-6)
        self.assertEqual(result['status'],'pending')

    def test_arithmetic_evidence_errors_stay_pending(self):
        card={'kind':'sef','inputs':{},'instances':[dict(name='a',gain='1/0',bias=0,delay=0,rise=1,fall=1,tau=1)]}
        self.assertEqual(b.envelope(card,[],2e-6)['status'],'pending')
        from unittest.mock import patch
        card={'kind':'integral','inputs':{'u':[[0.,0.],[4e-6,4.]]}}
        prepared=b.prepare(card,[])
        with patch.object(b,'rectangles',side_effect=ArithmeticError('independent arithmetic control')):
            self.assertEqual(prepared(2e-6)['status'],'pending')

    def test_prepared_history_owns_a_snapshot_and_matches_one_query(self):
        card = {'kind': 'integral', 'inputs': {'u': [[0., 0.], [4e-6, 4.]]}}
        callbacks = [record('sample', 1, 1e-6, 1e-10)]
        expected = b.envelope(card, callbacks, 2e-6)
        prepared = b.prepare(card, callbacks)
        self.assertEqual(prepared(2e-6), expected)
        card['inputs']['u'][1][1] = -40.
        callbacks[0]['time_bounds_s'][1] = 3e-6
        self.assertEqual(prepared(2e-6), expected)


if __name__ == '__main__':
    unittest.main()
