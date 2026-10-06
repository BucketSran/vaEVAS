"""Frozen paper inputs, independent of simulator execution."""
import json
from pathlib import Path
import tempfile
import unittest
from inputs import freeze, verify, requested_times

ROOT = Path(__file__).resolve().parents[3]
CARDS = ROOT / 'evas/validation/paper/core-v1.json'

class InputContracts(unittest.TestCase):
    def test_exact_sources_and_hierarchical_isolation_survive_all_decks(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'freeze'
            plan = freeze(CARDS, out)
            self.assertEqual(len(plan), 48)
            cards = {c['id']: c for c in json.loads(CARDS.read_text())['cards']}
            for row in plan:
                work = out / row['work']
                self.assertEqual((work/'dut.va').read_bytes(), cards[row['condition']]['source'].encode())
                if row['condition'] == 'SI-01':
                    self.assertEqual(json.loads((work/'binding.json').read_text())['top_module'], 'paper_isolation')
                    self.assertIn('paper_isolation', (work/row['deck']).read_text())
            verify(out)
            (out/plan[0]['work']/'dut.va').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'drift'):
                verify(out)

    def test_grid_requests_global_local_and_exact_root_obligations(self):
        data=json.loads(CARDS.read_text())
        card=next(c for c in data['cards'] if c['id']=='CO-VCO-01')
        times=requested_times(card,data['shared_contract'],data['units']['T_s'])
        self.assertLessEqual(max(b-a for a,b in zip(times,times[1:])),2e-10*(1+1e-10))
        for window in card['observation_windows']:
            center=window['center_T']*1e-6
            self.assertIn(center,times)
            inside=[t for t in times if window['start_T']*1e-6<=t<=window['end_T']*1e-6]
            self.assertLessEqual(max(b-a for a,b in zip(inside,inside[1:])),2e-11*(1+1e-10))
