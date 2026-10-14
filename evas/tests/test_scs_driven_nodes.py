"""Netlist-only voltage sources remain physical driven nodes in Rust execution."""
GUARDS = ["LANG", "LIN", "DEV:scs-input"]

import tempfile
from pathlib import Path
import unittest

from evas import CompileError
from evas.scs import load_scs, simulate_scs
from test_affine import KERNEL, model


class ScsDrivenNodes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'm.va').write_text(model('V(y,r)<+2;', ports='y,r',
                                            directions='output y; inout r;'))
        self.path = self.root / 'tb.scs'

    def deck(self, saved='save spare y'):
        self.path.write_text('simulator lang=spectre\nahdl_include "m.va"\n'
                             'Vin (spare 0) vsource type=pwl wave=[0 0 .5 1 1 0]\n'
                             'DUT (y 0) m\ntran tran stop=1 maxstep=.25\n' + saved + '\n')
        return self.path

    def test_saved_source_without_model_connection_uses_real_waveform(self):
        bench = load_scs(self.deck())
        self.assertEqual(bench.manifest['transient']['sources'],
                         {'spare': [[0, 0], [.5, 1], [1, 0]]})
        self.assertEqual(bench.manifest['instances'][0]['connections'], {'y': 'y', 'r': '0'})
        result = simulate_scs(self.path, kernel=KERNEL)
        self.assertEqual(result['saved']['nodes'], ['spare', 'y'])
        self.assertEqual(result['saved']['values'], [[0, 2], [.5, 2], [1, 2], [.5, 2], [0, 2]])
        spare = result['nodes'].index('spare')
        self.assertEqual([row['voltages'][spare] for row in result['solutions']], [0, .5, 1, .5, 0])

    def test_source_without_explicit_save_is_retained_in_default_outputs(self):
        result = simulate_scs(self.deck(saved=''), kernel=KERNEL)
        self.assertIn('spare', result['saved']['nodes'])
        spare = result['saved']['nodes'].index('spare')
        self.assertEqual([row[spare] for row in result['saved']['values']], [0, .5, 1, .5, 0])

    def test_save_still_rejects_a_node_with_no_source_or_model_connection(self):
        with self.assertRaisesRegex(CompileError, 'save names unknown scalar nodes') as caught:
            load_scs(self.deck(saved='save spare absent'))
        self.assertEqual(caught.exception.diagnostic['stage'], 'netlist')
        self.assertIn('location', caught.exception.diagnostic)
