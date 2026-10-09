import copy,json,unittest
from pathlib import Path
from check import expected,assess
ROOT=Path(__file__).resolve().parents[3]
C=json.loads((ROOT/'evas/validation/source-event-closure/contract.json').read_text())
class Calibration(unittest.TestCase):
    def test_independent_integral_known_values(self):
        case={'inputs':[[0,1],[1,1]],'polarity':1}
        answer=expected(case,.31)
        self.assertAlmostEqual(answer['z'],.018,delta=1e-15)
        self.assertAlmostEqual(answer['w'],.32,delta=1e-15)
        self.assertEqual(answer['count'],2)
        self.assertEqual(answer['flag'],1)
    def test_correct_waveform_and_distinct_faults(self):
        for case in C['cases'].values():
            rows=[dict(time=t,voltages=expected(case,t)) for t in C['times']]
            self.assertEqual(assess(case,rows,C)['numerical'],'P')
            self.assertEqual(assess(case,rows,C)['coverage'],'P')
            self.assertEqual(assess(case,rows[:-1],C)['coverage'],'I')
            for node in ['w','z','count','flag']:
                wrong=copy.deepcopy(rows);wrong[-1]['voltages'][node]+=1e-3
                self.assertEqual(assess(case,wrong,C)['numerical'],'F')
            wrong=copy.deepcopy(rows);del wrong[-1]['voltages']['z']
            self.assertEqual(assess(case,wrong,C)['numerical'],'F')

    def test_nonfinite_and_empty_are_not_passes(self):
        case=next(iter(C['cases'].values()))
        self.assertEqual(assess(case,[],C)['numerical'],'I')
        for value in (float('nan'),float('inf'),-float('inf')):
            row=dict(time=.31,voltages=expected(case,.31))
            row['voltages']['z']=value
            self.assertEqual(assess(case,[row],C)['numerical'],'F')
            row['time']=value
            self.assertEqual(assess(case,[row],C)['numerical'],'F')

    def test_direct_and_stability_calibration(self):
        from pair import direct,stability
        case=next(iter(C['cases'].values()))
        rows=[dict(time=t,voltages=expected(case,t)) for t in C['times']]
        self.assertEqual(direct(case,rows,rows,C)['numerical'],'P')
        self.assertEqual(stability(rows,rows,C)['numerical'],'P')
        self.assertEqual(direct(case,[],[],C)['numerical'],'I')
        self.assertEqual(stability([],[],C)['numerical'],'I')
        self.assertEqual(stability(rows,rows[:-1],C)['coverage'],'I')
        self.assertEqual(direct(case,rows,rows[:-1],C)['numerical'],'F')
        self.assertEqual(stability(rows,rows+[rows[-1]],C)['coverage'],'I')
        for value in [1.,float('nan'),float('inf')]:
            wrong=copy.deepcopy(rows);wrong[-1]['voltages']['w']=value
            self.assertEqual(direct(case,rows,wrong,C)['numerical'],'F')
            self.assertEqual(stability(rows,wrong,C)['numerical'],'F')
