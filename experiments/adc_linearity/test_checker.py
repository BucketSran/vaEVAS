"""Contract tests with an integer-bin fixture independent of the checker oracle."""
import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('adc', ROOT/'benchmark/checkers/adc_linearity.py')
adc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adc)


def fixture():
    boundaries = [16*j + (4 if j % 2 else -4) for j in range(1, 256)]
    boundaries[100] = boundaries[99]  # missing code 100
    hits = [b-a for a,b in zip([0]+boundaries, boundaries+[4096])]
    case = dict(name='fixture', thresholds=[b/4096 for b in boundaries], delay=200e-9)
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
    def evaluate(self, mode='correct', mutate=None, trace_mutate=None):
        case, hits, rows = fixture()
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
            original_codes=[k for k,h in enumerate(fixture()[1]) for _ in range(h)]
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
