"""Public helper replacement contract; no simulator substitutes in these tests."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'benchmark/checkers'))
from v2_structure import evaluate, check_chopper_boundary
import json


class ReplacementContractTests(unittest.TestCase):
    def test_active_top_bypassing_consumer_is_rejected(self):
        case = {'source_id': '308', 'structure_probe': 'consumer',
                'signals': ['vin', 'clk', 'rst', 'sample_reset', 'sample_signal',
                            'vout', 'offset_dbg', 'valid'],
                'stop': 4e-9, 'resolution': 2e-12, 'params': {'tr': 2e-10}}
        rows = [dict(time=i*2e-12, vin=.5, clk=0, rst=0, sample_reset=0,
                     sample_signal=0, vout=.61, offset_dbg=.23, valid=.9)
                for i in range(2001)]
        self.assertTrue(evaluate(rows, case, Path('.'))['passed'])
        # A working monolithic implementation would reset to vcm, not consume
        # the deliberately identifiable public replacement's .61V output.
        for row in rows:
            row['vout'] = .45
        self.assertFalse(evaluate(rows, case, Path('.'))['passed'])

    def test_cds_consumer_uses_replaced_reset_sample(self):
        # Reset vin=.4, signal vin=.58, injected reset=.31. The correct
        # replacement response is .45 + (.58-.31) = .72, debug=.31.
        rows = []
        for i in range(2501):
            t = i*2e-12
            clk = 0.
            for edge in (1e-9, 3e-9):
                if edge <= t < edge+20e-12:
                    clk = .9*(t-edge)/20e-12
                elif edge+20e-12 <= t < edge+.3e-9:
                    clk = .9
            alpha = min(1., max(0., (t-3.01e-9)/2e-10))
            rows.append(dict(time=t, vin=.4 if t<2e-9 else .58, clk=clk, rst=0.,
                             sample_reset=.9 if t<2e-9 else 0.,
                             sample_signal=0. if t<2e-9 else .9,
                             vout=.45+.27*alpha, offset_dbg=.31*alpha, valid=.9*alpha))
        case = dict(source_id='308', structure_probe='producer', stop=5e-9,
                    signals=list(rows[0].keys()-{'time'}), resolution=2e-12,
                    params={'tr': 2e-10})
        self.assertTrue(evaluate(rows, case, Path('.'))['passed'])
        # Reconstructing the original vin instead of consuming reset_node
        # gives .63 V. Component helpers can be individually correct while
        # this replacement check rejects a top-level bypass.
        for row in rows:
            alpha = min(1., max(0., (row['time']-3.01e-9)/2e-10))
            row['vout'] = .45+.18*alpha
        self.assertFalse(evaluate(rows, case, Path('.'))['passed'])

    def test_component_cases_compile_only_selected_candidate_helper(self):
        for sid in ('091', '307', '308'):
            task = next((ROOT/'benchmark/tasks').glob('v2-spec-'+sid+'-*'))
            cases = json.loads((task/'tests/cases.json').read_text())
            self.assertEqual(len(cases), 6)
            for case in cases[2:4]:
                self.assertNotIn('ahdl_include "dut.va"', case['netlist'])
                self.assertIn('ahdl_include "architecture_top.va"', case['netlist'])
                self.assertIn('ahdl_include "architecture_partner.va"', case['netlist'])
                actual = [n for n in json.loads((task/'tests/contract.json').read_text())['candidate_files']
                          if 'ahdl_include "'+n+'"' in case['netlist']]
                self.assertEqual(len(actual), 1)

    def test_core_notification_is_delayed_and_sample_precedes_it(self):
        rows = []
        for i in range(1501):
            t = i*2e-12
            clk = .9*min(1., max(0., (t-1e-9)/20e-12))
            clk -= .9*min(1., max(0., (t-1.8e-9)/20e-12))
            sample = 0. if t<1.01e-9 else .18 if t<1.81e-9 else .06
            strobe = .9*min(1., max(0., (t-1.21e-9)/1e-10))
            strobe -= .9*min(1., max(0., (t-2.01e-9)/1e-10))
            rows.append({'time':t, 'chop_clk':clk, 'rst':0., 'enable':.9,
                         'hold':0., 'vinp':.49, 'vinn':.45,
                         'IDUT.demod_sample_i':sample,
                         'IDUT.baseband_ref_i':0. if t<1.01e-9 else .12,
                         'IDUT.event_strobe_i':strobe})
        case = dict(params={'tr':1e-10}, resolution=2e-12)
        self.assertTrue(check_chopper_boundary(rows, case)['passed'])
        for row in rows:
            row['IDUT.event_strobe_i'] = row['chop_clk']
        self.assertFalse(check_chopper_boundary(rows, case)['passed'])


if __name__ == '__main__':
    unittest.main()
