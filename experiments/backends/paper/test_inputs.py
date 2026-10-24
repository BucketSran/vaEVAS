"""Frozen paper inputs, independent of simulator execution."""
import json
from pathlib import Path
import tempfile
import unittest
from inputs import decks, freeze, verify, requested_times

ROOT = Path(__file__).resolve().parents[3]
CARDS = ROOT / 'evas/validation/paper/core-v1.json'

class InputContracts(unittest.TestCase):
    def test_ngspice_operator_named_nodes_are_exported_without_renaming_ports(self):
        # The ngspice expression lexer reads bare lt/ge/etc. as operators even
        # inside v(...). Quoting is only for the export expression, not the DUT.
        ports = ['u', 'lt', 'le', 'gt', 'ge', 'ne', 'eq', 'or', 'and', 'not', 'out']
        card = {'id': 'operator_nodes', 'stimulus': {
            'u': {'points_s_V': [[0, .5], [1e-6, .5]]}}}
        settings = {'stop_s': 1e-6, 'maxstep_s': 1e-9, 'spice_maxstep_s': 1e-9,
                    'reltol': 1e-8, 'vabstol_V': 1e-12, 'iabstol_A': 1e-15}
        bind = {'ports': ports, 'top_module': 'operator_nodes', 'parameters': {}}
        generated = decks(card, settings, bind, [0, 1e-6],
                          {'records': [{'time_s': 0}, {'time_s': 1e-6}]})
        ng = generated['openvaf_r_ngspice'][1]
        self.assertIn('wrdata waveform.txt v(u) v("lt") v("le") v("gt") v("ge") '
                      'v("ne") v("eq") v("or") v("and") v("not") v(out)\n', ng)
        self.assertIn('N0 ' + ' '.join(ports) + ' model0\n', ng)
        self.assertIn('.print tran ' + ' '.join(f'v({p})' for p in ports)
                      + ' v(bench_ref)\n', generated['gnucap_modelgen'][1])
        request = json.loads(generated['evas'][1])
        self.assertEqual(request['instances'][0]['ports'], {p: p for p in ports})
        self.assertEqual(request['inputs']['u'], [[0, .5], [1e-6, .5]])

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
            helper = 'evas/validation/paper/case_inputs.py'
            self.assertEqual((out/'adapter_sources'/helper).read_bytes(), (ROOT/helper).read_bytes())
            self.assertIn(helper, json.loads((out/'ADAPTER_IDENTITY.json').read_text()))
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

    def test_gnucap_observer_continuations_preserve_all_ordered_corners(self):
        import re
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'freeze'
            plan=freeze(CARDS,out)
            for row in plan:
                if row['backend']!='gnucap_modelgen':continue
                work=out/row['work'];lines=(work/'tb.gc').read_text().splitlines()
                start=next(i for i,line in enumerate(lines) if line.startswith('Vpaper_observer '))
                physical=[lines[start]]
                for line in lines[start+1:]:
                    if not line.startswith('+'):break
                    physical.append(line)
                if row['condition']=='EV-SH-01':self.assertGreater(len(physical),1)
                self.assertTrue(all(len(line.encode())<=240 for line in physical))
                logical=' '.join(line[1:] if line.startswith('+') else line for line in physical)
                match=re.fullmatch(r'Vpaper_observer paper_observer 0 PWL\((.*)\)',logical)
                self.assertIsNotNone(match)
                tokens=match[1].split()
                request=json.loads((work/'breakpoint_requests.json').read_text())
                expected=[token for i,r in enumerate(request['records']) for token in (format(r['time_s'],'.17g'),str(i%2))]
                self.assertEqual(tokens,expected)
                # Other backend/source topology remains independent of folding.
                self.assertEqual((work/'tb.gc').read_text().count('paper_observer'),2)
                ng=out/'runs/openvaf_r_ngspice'/row['condition']/'tb.cir'
                ngline=next(line for line in ng.read_text().splitlines() if line.startswith('Vpaper_observer '))
                self.assertEqual(ngline.split('PWL(',1)[1][:-1].split(),expected)
