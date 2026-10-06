"""Contract tests with an integer-bin fixture independent of the checker oracle."""
import csv
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import os
import sys
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('adc', ROOT/'benchmark/checkers/adc_linearity.py')
adc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adc)


def fixture(case=None):
    boundaries = [16*j + (4 if j % 2 else -4) for j in range(1, 256)]
    boundaries[100] = boundaries[99]  # missing code 100
    if case is not None:
        boundaries=[round(v*4096) for v in case['thresholds']]
        if any(abs(v*4096-b)>1e-9 for v,b in zip(case['thresholds'],boundaries)):
            raise ValueError('integer-boundary fixture required')
    hits = [b-a for a,b in zip([0]+boundaries, boundaries+[4096])]
    case = case or dict(name='fixture', thresholds=[b/4096 for b in boundaries], delay=200e-9)
    codes = [k for k, count in enumerate(hits) for _ in range(count)]
    rows = []
    def row(t, n, clk, done=0):
        code = codes[max(0, n)] if n >= 0 else 0
        rows.append(dict(time=t, vin=(max(0,n)+.5)/4096, clk=clk, done=done,
                         **{f'd{i}':(code >> i)&1 for i in range(8)}))
    row(0, 0, 0)
    for n in range(4096):
        t = 5e-6+n*1e-6
        # Include the input transition endpoints and clock crossings explicitly.
        row(t, max(0,n-1), 0)
        row(t+1e-9, n, 0)
        row(t+.25e-6, n, 0)
        row(t+.25e-6+1e-9, n, 1)
        row(t+.5e-6, n, 1)
        row(t+.5e-6+1e-9, n, 0)
        row(t+.75e-6, n, 0)
    row(5e-6+4095e-6+.75e-6+1e-9,4095,0,1)
    row(adc.STOP,4095,0,1)
    return case, hits, rows


def write_csv(path, hits, mode='correct'):
    denom = sum(hits[1:255]) if mode != 'all_samples' else 4096
    cumulative = 0
    with path.open('w') as f:
        writer = csv.writer(f); writer.writerow(['code','hits','dnl','inl'])
        for k in range(1,255):
            dnl = 254*hits[k]/denom-1
            cumulative += dnl
            writer.writerow([k,hits[k],0 if mode=='ideal' else dnl,
                             0 if mode=='ideal' else cumulative])


class Contract(unittest.TestCase):
    def test_generated_netlist_has_named_options_analysis_and_fixed_numeric_settings(self):
        # Actual Spectre SFE-709 rejected bare "options reltol=..." as an
        # instance without a master. Spectre options analysis needs a name.
        lines=adc.netlist().splitlines()
        options=[line.split() for line in lines if 'reltol=' in line]
        self.assertEqual(len(options),1)
        self.assertGreaterEqual(len(options[0]),5)
        self.assertEqual(options[0][1],'options')
        self.assertNotEqual(options[0][0],'options')
        self.assertEqual(options[0][2:],['reltol=1e-6','vabstol=1e-9','iabstol=1e-12'])
        self.assertIn('tran tran stop=4.102m maxstep=20n errpreset=conservative',lines)

    def evaluate(self, mode='correct', mutate=None, trace_mutate=None, case=None):
        case, hits, rows = fixture(case)
        if mode == 'old_code':
            # ADC raw data stays correct; candidate reports immediately sampled old codes.
            codes = [k for k,h in enumerate(hits) for _ in range(h)]
            hits = [0]*256
            for k in [0]+codes[:-1]: hits[k] += 1
        elif mode == 'missing_first': hits[0] -= 1  # endpoint CSV cannot reveal this alone
        elif mode == 'missing_last': hits[255] -= 1
        elif mode == 'reversed_bits':
            reverse = [0]*256
            for k,h in enumerate(hits): reverse[int(f'{k:08b}'[::-1],2)] += h
            hits = reverse
        if mutate: mutate(rows)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'linearity.csv'; write_csv(path,hits,mode)
            original_codes=[k for k,h in enumerate(fixture(case)[1]) for _ in range(h)]
            trace=Path(folder)/'samples.csv'
            with trace.open('w') as f:
                writer=csv.writer(f);writer.writerow(['index','time','code'])
                for n,k in enumerate(original_codes):
                    if mode=='missing_first' and n==0: continue
                    if mode=='missing_last' and n==4095: continue
                    if mode=='old_code': k=0 if n==0 else original_codes[n-1]
                    if mode=='reversed_bits': k=int(f'{k:08b}'[::-1],2)
                    writer.writerow([n,adc.T0+(n+.25 if mode=='old_code' else n+.75)*adc.T,k])
            if trace_mutate: trace_mutate(trace)
            return adc.evaluate(rows,case,path,trace)

    def test_frozen_four_references_and_six_targeted_negative_fixtures(self):
        cases={case['name']:case for case in json.loads((ROOT/'benchmark/tasks/va08-adc-linearity/tests/cases.json').read_text())}
        for name,case in cases.items():
            with self.subTest(reference=name):
                result=self.evaluate(case=case)
                self.assertEqual(result['status'],'graded')
                self.assertTrue(result['passed'],result)
        modes={'old_code':'ideal-fast','missing_first':'ideal-fast','missing_last':'ideal-fast',
               'all_samples':'endpoint-shift','reversed_bits':'alternating-slow','ideal':'alternating-slow'}
        for mode,name in modes.items():
            with self.subTest(negative=mode):
                result=self.evaluate(mode,case=cases[name])
                self.assertEqual(result['status'],'candidate_failure')
                self.assertFalse(result['passed'],result)

    def test_psf_parser_requires_complete_stream_and_unique_signals(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'wave.psf'
            path.write_text('HEADER\nVALUE\n"time" 0\n"vin" 0.5\n"time" 1\n"vin" 0.6\nEND\n')
            self.assertEqual(adc.read_psf(path),[{'time':0.,'vin':.5},{'time':1.,'vin':.6}])
            for text in ['VALUE\n"time" 0\n', 'VALUE\n"time" 0\n"vin" 0\n"vin" 1\nEND\n']:
                path.write_text(text)
                with self.assertRaises(ValueError): adc.read_psf(path)

    def test_failed_version_probe_is_unscored_without_simulation(self):
        task=ROOT/'benchmark/tasks/va08-adc-linearity'
        with tempfile.TemporaryDirectory() as folder:
            executable=Path(folder)/'spectre';executable.write_text('#!/bin/sh\nexit 17\n');executable.chmod(0o755)
            output=Path(folder)/'logs'
            completed=subprocess.run([sys.executable,'-B',str(task/'tests/verify.py'),
                '--candidate',str(task/'solution/reference.va'),'--output',str(output)],
                env={**os.environ,'SPECTRE':str(executable)},capture_output=True,text=True)
            self.assertEqual(completed.returncode,2)
            report=json.loads((output/'report.json').read_text())
            self.assertEqual(report['spectre_version_returncode'],17)
            self.assertIsNone(report['reward']);self.assertEqual(report['cases'],[])
            self.assertFalse((output/'reward.txt').exists())

    def test_duplicate_index_and_nonfinite_csv_are_rejected(self):
        def duplicate(path):
            text=path.read_text(); path.write_text(text.replace('1,','0,',1))
        self.assertFalse(self.evaluate(trace_mutate=duplicate)['passed'])
        def nonfinite(path):
            text=path.read_text(); lines=text.splitlines(); fields=lines[1].split(',')
            fields[1]='nan'; lines[1]=','.join(fields); path.write_text('\n'.join(lines)+'\n')
        self.assertFalse(self.evaluate(trace_mutate=nonfinite)['passed'])

    def test_waveform_nonfinite_or_wrong_endpoint_is_not_scored(self):
        with self.assertRaises(ValueError):
            self.evaluate(mutate=lambda rows: rows[-1].update(time=adc.STOP-adc.T))
        with self.assertRaises(ValueError):
            self.evaluate(mutate=lambda rows: rows[0].update(vin=float('nan')))

    def test_empty_sample_file_is_candidate_failure(self):
        result=self.evaluate(trace_mutate=lambda path: path.write_text(''))
        self.assertEqual(result['status'],'candidate_failure')

    def test_short_input_edges_are_rejected(self):
        def shorten(rows):
            for row in rows:
                t=row['time']; phase=(t-adc.T0)%adc.T
                if adc.T0+adc.T<t<adc.T0+4096*adc.T:
                    if abs(phase)<1e-15 or abs(phase-adc.T)<1e-15: row['time']+=.45e-9
                    elif abs(phase-adc.EDGE)<1e-15: row['time']-=.45e-9
        self.assertFalse(self.evaluate(mutate=shorten)['passed'])

    def test_short_clock_edges_with_correct_midpoints_are_rejected(self):
        def shorten(rows):
            for row in rows:
                t=row['time']; phase=(t-adc.T0)%adc.T
                for start in [.25*adc.T,.5*adc.T]:
                    if abs(phase-start)<1e-15: row['time']+=.45e-9
                    elif abs(phase-start-adc.EDGE)<1e-15: row['time']-=.45e-9
        self.assertFalse(self.evaluate(mutate=shorten)['passed'])

    def test_original_csv_contract_cannot_observe_endpoint_loss(self):
        case,hits,rows=fixture()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'linearity.csv'
            hits[0]-=1  # an omitted first sample changes no internal CSV row
            write_csv(path,hits)
            self.assertTrue(adc.evaluate(rows,case,path)['passed'])

    def test_correct_raw_bus_and_finite_scan(self):
        self.assertTrue(self.evaluate()['passed'])

    def test_five_wrong_measurements_rejected(self):
        for mode in ['old_code','missing_first','missing_last','all_samples','reversed_bits','ideal']:
            with self.subTest(mode=mode): self.assertFalse(self.evaluate(mode)['passed'])

    def test_ideal_csv_cannot_replace_actual_input(self):
        self.assertFalse(self.evaluate(mutate=lambda rows: [r.update(vin=.5) for r in rows])['passed'])

    def test_extra_clock_or_bad_done_is_rejected(self):
        self.assertFalse(self.evaluate(mutate=lambda rows: rows[-1].update(clk=1))['passed'])
        self.assertFalse(self.evaluate(mutate=lambda rows: rows[0].update(done=1))['passed'])

    def test_bus_mismatch_is_environment_error(self):
        result=self.evaluate(mutate=lambda rows: rows[-3].update(d0=1-rows[-3]['d0']))
        self.assertEqual(result['status'],'environment_error')

if __name__ == '__main__': unittest.main()
