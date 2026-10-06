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

    def test_nested_manifest_named_file_cannot_evade_frozen_file_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'freeze'
            plan=freeze(CARDS,out)
            (out/plan[0]['work']/'INPUT_MANIFEST.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'file set drift'):
                verify(out)

    def test_freeze_cannot_exceed_authorized_stage_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                freeze(CARDS,Path(tmp)/'freeze',stage_timeout_s=91)

    def test_spice_local_requests_are_decoupled_and_fit_frozen_budget(self):
        import re
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'freeze'
            plan=freeze(CARDS,out)
            for row in plan:
                if row['backend'] not in ('openvaf_r_ngspice','gnucap_modelgen'): continue
                work=out/row['work']
                request=json.loads((work/'breakpoint_requests.json').read_text())
                card=json.loads((work/'condition.json').read_text())
                points=[r['time_s'] for r in request['records']]
                for window in card['observation_windows']:
                    self.assertIn(window['center_T']*1e-6,points)
                    inside=[t for t in points if window['start_T']*1e-6<=t<=window['end_T']*1e-6]
                    self.assertLessEqual(max(b-a for a,b in zip(inside,inside[1:])),2e-11)
                deck=(work/row['deck']).read_text()
                self.assertEqual(deck.count('Vpaper_observer paper_observer 0 PWL('),1)
                self.assertNotIn('paper_observer',json.loads((work/'binding.json').read_text())['ports'])
                self.assertLess(request['estimated_waveform_bytes'],32*1024**2*.8)
                self.assertLess(request['estimated_condition_bytes'],256*1024**2)
