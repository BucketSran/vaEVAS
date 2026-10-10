import copy
from decimal import Decimal, localcontext
from fractions import Fraction as F
import math
import json
from pathlib import Path
import tempfile
import unittest

from error_decomposition import Reference, callback_times, split_error, verify_manifest, sha


def config(**kw):
    p = dict(name='a', phase=1, period=2, delay=0, rise=1, fall=1,
             tau=1, gain=1, bias=0, cross=False)
    p.update(kw)
    return p


class ErrorDecomposition(unittest.TestCase):
    def test_rehashed_replacement_manifest_does_not_replace_retained_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'rows.json').write_text('original')
            manifest = root/'MANIFEST.json'
            manifest.write_text(json.dumps({'rows.json': sha(root/'rows.json')}))
            anchor = sha(manifest)
            verify_manifest(root, 'MANIFEST.json', anchor)
            (root/'rows.json').write_text('replacement')
            manifest.write_text(json.dumps({'rows.json': sha(root/'rows.json')}))
            with self.assertRaisesRegex(ValueError, 'retained receipt'):
                verify_manifest(root, 'MANIFEST.json', anchor)

    def test_ramp_and_filter_have_independent_closed_form_anchor(self):
        # Times and parameters here are seconds, without the experiment's us scaling.
        ref = Reference(config(), {'u': [[0, 0], [3, 3]]}, 0, [F(1)])
        with localcontext() as ctx:
            ctx.prec = 60
            answer = ref.at(F(2))
            self.assertEqual(answer['h'], 1)
            self.assertEqual(answer['e'], 1)
            self.assertLess(abs(answer['f'] - Decimal(-1).exp()), Decimal('1e-55'))

    def test_callback_conditioning_recomputes_sample_from_source(self):
        ref = Reference(config(), {'u': [[0, 0], [3, 3]]}, 0, [F(5, 4)])
        self.assertEqual(ref.at(F(5, 4))['h'], Decimal('1.25'))
        self.assertEqual(ref.at(F(1))['n'], 0)

    def test_delayed_event_splits_phase_difference_from_wrong_sample(self):
        inputs = {'u': [[0, 0], [3, 3]]}
        nominal = Reference(config(), inputs, 0, [F(1)]).at(F(9, 8))['h']
        conditioned = Reference(config(), inputs, 0, [F(5, 4)]).at(F(9, 8))['h']
        parts = split_error(Decimal(0), nominal, conditioned, nominal)
        self.assertEqual(parts, dict(reference_residual=Decimal(0),
            callback_shift=Decimal(-1), candidate_residual=Decimal(0),
            direct_difference=Decimal(-1), reconstruction_error=Decimal(0)))
        bad = split_error(Decimal('.2'), nominal, conditioned, nominal)
        self.assertEqual(bad['reference_residual'], Decimal('.2'))

    def test_binary64_time_side_is_not_rounded_to_decimal_label(self):
        event = F(0.1)
        ref = Reference(config(), {'u': [[0, 0], [1, 1]]}, 0, [event])
        self.assertEqual(ref.at(F(math.nextafter(.1, 0)))['n'], 0)
        self.assertEqual(ref.at(event)['n'], 1)

    def test_counter_extraction_rejects_missing_repeated_and_nonfinite_evidence(self):
        rows = [dict(time=0., an=0.), dict(time=1., an=1.), dict(time=2., an=2.)]
        self.assertEqual(callback_times(rows, 'a', 2), [F(1), F(2)])
        for kind in ['skip', 'rewind', 'fraction', 'nan', 'empty', 'duplicate_time', 'missing_tail']:
            bad = copy.deepcopy(rows)
            if kind == 'skip': bad[1]['an'] = 2
            elif kind == 'rewind': bad[2]['an'] = 0
            elif kind == 'fraction': bad[1]['an'] = .5
            elif kind == 'nan': bad[1]['time'] = math.nan
            elif kind == 'empty': bad = []
            elif kind == 'duplicate_time': bad[1]['time'] = 0
            else: bad = bad[:-1]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                callback_times(bad, 'a', 2)


if __name__ == '__main__':
    unittest.main()
