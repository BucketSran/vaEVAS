"""Independent public SAR fixtures; this does not execute the VA candidates."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).parent/'sar_calendar'
spec=importlib.util.spec_from_file_location('sar_oracle',ROOT/'evaluate.py')
sar=importlib.util.module_from_spec(spec);spec.loader.exec_module(sar)
CASES=json.loads((ROOT/'cases.json').read_text())


def waveform(case,events,sharp=False):
    times={0.,case['stop']}
    for points in case['controls'].values():
        times.update(t for t,_ in points)
    for t,_,_ in events:
        times.update(t+delta for delta in (-3e-9,0,.125e-9,.25e-9,.375e-9,.5e-9,3e-9)
                     if 0<=t+delta<=case['stop'])
    times.update(case['stop']*i/1000 for i in range(1001))
    rows=[]
    for t in sorted(times):
        row=dict(time=t,**{key:sar.pwl(points,t) for key,points in case['controls'].items()})
        for signal in ('busy','valid','code','dac'):
            value=0.;previous=0.
            for et,key,target in events:
                if key!=signal:continue
                fraction=(float(t>=et) if sharp else min(1.,max(0.,(t-et)/case['rise'])))
                value+=(target-previous)*fraction;previous=target
            row[signal]=value
        rows.append(row)
    return rows


class SarCalendar(unittest.TestCase):
    def test_architecture_counts_and_known_first_code(self):
        expected=[(20,240,0,0),(3,42,1,1),(3,36,0,0)]
        for case,counts in zip(CASES,expected):
            events,actual=sar.timeline(case)
            self.assertEqual(tuple(actual.values()),counts)
            first_code=next(value for _,key,value in events if key=='code' and value>0)
            self.assertAlmostEqual(first_code,731/4095)
        events,_=sar.timeline(CASES[0])
        first_dac=[v for _,key,v in events if key=='dac'][:3]
        self.assertEqual(first_dac,[.5,.25,.125])

    def test_waveforms_transition_and_history(self):
        for case in CASES:
            events,_=sar.timeline(case)
            rows=waveform(case,events)
            result=sar.evaluate(rows,case)
            self.assertTrue(result['passed'],result)
            self.assertFalse(sar.evaluate(waveform(case,events,sharp=True),case)['passed'])
            self.assertFalse(sar.evaluate([dict(row,dac=0.) for row in rows],case)['passed'])
            self.assertFalse(sar.evaluate([dict(row,valid=0.) for row in rows],case)['passed'])

    def test_early_finish_and_wrong_input_hold_rejected(self):
        case=CASES[1];events,_=sar.timeline(case)
        early=[(t-.2e-6 if signal=='valid' and value==1 else t,signal,value) for t,signal,value in events]
        self.assertFalse(sar.evaluate(waveform(case,sorted(early)),case)['passed'])
        rows=waveform(case,events)
        self.assertFalse(sar.evaluate([dict(row,code=min(1.,max(0.,row['vin']/case['vref']))) for row in rows],case)['passed'])

if __name__=='__main__':unittest.main()
