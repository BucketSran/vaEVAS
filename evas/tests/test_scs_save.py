"""SCS time is an independent output axis, not a voltage column."""
GUARDS = ["LANG", "DEV:scs-input"]

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from evas import CompileError
from evas.results import run
from evas.scs import load_scs, simulate_scs
from test_affine import KERNEL, model


class ScsSaveTime(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'm.va').write_text(model('V(y,r)<+3*V(u,r);'))
        self.path = self.root / 'tb.scs'

    def deck(self, saved='save time y u', tran='tran tran stop=1 maxstep=.25'):
        self.path.write_text('simulator lang=spectre\nahdl_include "m.va"\n'
                             'Vin (u 0) vsource type=pwl wave=[0 0 .5 1 1 0]\n'
                             'DUT (u y 0) m\n' + tran + '\n' + saved + '\n')
        return self.path

    def test_time_and_nodes_keep_one_axis_and_requested_voltage_order(self):
        # Triangle input and gain 3 give these hand-computed voltage rows.
        # A fake "time" voltage column would corrupt downstream tabular export.
        actual = simulate_scs(self.deck(), kernel=KERNEL)
        self.assertEqual(actual['saved'], dict(
            nodes=['y', 'u'], times=[0, .25, .5, .75, 1],
            values=[[0, 0], [1.5, .5], [3, 1], [1.5, .5], [0, 0]]))
        self.assertNotIn('time', actual['nodes'])

    def test_time_only_keeps_default_voltage_saves(self):
        # Spectre 21.1 retains its default voltage saves when the only explicit
        # selector is the non-node time quantity. An empty voltage selection
        # must therefore retain the same EVAS defaults as an absent save line.
        actual = simulate_scs(self.deck('save time'), kernel=KERNEL)
        self.assertEqual(actual['saved']['nodes'], actual['nodes'])
        y = actual['saved']['nodes'].index('y')
        self.assertEqual([row[y] for row in actual['saved']['values']], [0, 1.5, 3, 1.5, 0])

    def test_electrical_node_named_time_keeps_its_voltage(self):
        # V(time)=7 V differs from the independent time axis [0,1] seconds.
        self.deck('save time y')
        self.path.write_text(self.path.read_text().replace(
            'Vin (u 0) vsource type=pwl wave=[0 0 .5 1 1 0]',
            'Vin (time 0) vsource dc=7').replace('DUT (u y 0)', 'DUT (time y 0)'))
        actual = simulate_scs(self.path, kernel=KERNEL)
        self.assertEqual(actual['saved'], dict(nodes=['time', 'y'],
            times=[0, .25, .5, .75, 1], values=[[7, 21]] * 5))

    def test_repeated_time_and_nodes_do_not_duplicate_columns(self):
        actual = simulate_scs(self.deck('save time y time\nsave u y time'), kernel=KERNEL)
        self.assertEqual(actual['saved']['nodes'], ['y', 'u'])
        self.assertEqual(actual['saved']['values'][2], [3, 1])

    def test_time_with_strobeonly_preserves_row_alignment(self):
        actual = simulate_scs(self.deck(tran='tran tran stop=1 maxstep=.25 '
            'strobetimes=[.125 .625] strobeoutput=strobeonly'), kernel=KERNEL)
        self.assertEqual(actual['saved'], dict(nodes=['y', 'u'],
            times=[.125, .625, 1], values=[[.75, .25], [2.25, .75], [0, 0]]))

    def test_time_does_not_hide_unknown_nodes_or_unsupported_selectors(self):
        for selection in ('time absent', 'Time y', 'time V(u)', 'time u[0]'):
            with self.subTest(selection=selection), self.assertRaises(CompileError):
                load_scs(self.deck('save ' + selection))

    def test_cli_and_manifest_csv_consume_real_time_axis(self):
        # Both public exporters consume the accepted deck. CSV uses the
        # manifest's full node set, while simulate JSON keeps save order.
        bench = load_scs(self.deck())
        child = subprocess.run([sys.executable, '-B', '-m', 'evas', 'simulate',
            str(self.path), '--kernel', str(KERNEL)], capture_output=True, text=True, timeout=12)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(json.loads(child.stdout)['saved']['nodes'], ['y', 'u'])
        manifest = self.root / 'sim.json'
        manifest.write_text(json.dumps(bench.manifest))
        output = self.root / 'output'
        receipt = run(manifest, kernel=KERNEL, out=output)
        self.assertEqual(receipt['status'], 'complete')
        with (output / 'observations.csv').open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([float(row['time_s']) for row in rows], [0, .25, .5, .75, 1])
        self.assertNotIn('time_V', rows[0])
        self.assertEqual([float(row['y_V']) for row in rows], [0, 1.5, 3, 1.5, 0])


if __name__ == '__main__':
    unittest.main()
