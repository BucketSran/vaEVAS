"""Shared input construction preserves frozen models and consumer isolation."""
GUARDS = ['LANG', 'COMPOSE']

import hashlib
import unittest

from paper_case_inputs import binding, case_source, load_core, stimulus


class PaperCaseInputs(unittest.TestCase):
    def test_original_source_bytes_remain_fixed(self):
        original = {
            'EV-HC-01': 'ed4a653c2b7bdf28d080a51b7e05134c17d93972ff88d122da0aaa34bfc2b29c',
            'EV-HC-02': '02734a00e6a7502fb22f01a8f39f5628ae806af838d06c85f533d3bce762525b',
            'CO-VCO-01': '1bc287bb7c2bd6db604c56233239b668582093388790fe4be92f8c7fd06f327e',
        }
        for case_id, expected in original.items():
            with self.subTest(case=case_id):
                self.assertEqual(hashlib.sha256(case_source(case_id).encode()).hexdigest(), expected)
        with self.assertRaises(KeyError):
            case_source('missing-case')

    def test_reads_and_bindings_do_not_share_mutable_inputs(self):
        first = load_core()
        card = first['cards'][0]
        original_parameters = dict(card['parameters'])
        bind = binding(card)
        bind['parameters']['consumer_override'] = 9
        bind['ports'].clear()
        card['source'] = 'consumer mutation'
        self.assertEqual(card['parameters'], original_parameters)
        self.assertNotEqual(load_core()['cards'][0]['source'], 'consumer mutation')
        self.assertTrue(binding(load_core()['cards'][0])['ports'])

    def test_stimulus_preserves_binary_values_order_and_freshness(self):
        # Exact binary64 multiplication order and duplicate knots are inputs,
        # not a solver-derived answer. Preserve negative zero as well.
        card = {'stop_T': 2, 'stimulus': {
            'u': {'kind': 'pwl', 'points_T_V': [[0, -0.0], [.5, .25], [.5, .75], [2, 1.0]]},
            'v': {'kind': 'dc', 'value_V': -.5},
        }}
        result = stimulus(card, .25)
        self.assertEqual(result, {'u': [[0.0, -0.0], [.125, .25], [.125, .75], [.5, 1.0]],
                                  'v': [[0, -.5], [.5, -.5]]})
        self.assertEqual(result['u'][0][1].hex(), '-0x0.0p+0')
        result['u'][1][0] = 99
        self.assertEqual(stimulus(card, .25)['u'][1][0], .125)
        card['stimulus']['v']['kind'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'unknown stimulus kind'):
            stimulus(card, .25)

    def test_binding_preserves_hierarchy_and_rejects_wrong_ports(self):
        card = {'source': 'module cell(a,b); endmodule\nmodule top(z,a); cell x(a,z); endmodule',
                'observables': ['a', 'z'], 'parameters': {'gain': .5}}
        bind = binding(card)
        self.assertEqual(bind['top_module'], 'top')
        self.assertEqual(bind['ports'], ['z', 'a'])
        self.assertEqual(bind['parameters'], {'gain': .5})
        card['observables'].append('missing')
        with self.assertRaisesRegex(ValueError, 'ports differ'):
            binding(card)
        card['source'] = 'module top; endmodule'
        with self.assertRaisesRegex(ValueError, 'no explicit module ports'):
            binding(card)


if __name__ == '__main__':
    unittest.main()
