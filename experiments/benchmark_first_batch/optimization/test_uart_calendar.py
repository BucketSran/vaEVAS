"""Pure independent UART transfer and control fixtures, no VA execution."""
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).parent/'uart_calendar'
spec=importlib.util.spec_from_file_location('uart_oracle',ROOT/'evaluate.py')
uart=importlib.util.module_from_spec(spec);spec.loader.exec_module(uart)
CASES=json.loads((ROOT/'cases.json').read_text())


def waveform(case,events,sharp=False):
    times={0.,case['stop']}
    for points in case['controls'].values():times.update(t for t,_ in points)
    for t,_,_ in events:
        times.update(t+delta for delta in (-case['exclusion'],0,.25*case['rise'],.5*case['rise'],.75*case['rise'],case['rise'],case['exclusion']) if 0<=t+delta<=case['stop'])
    times.update(case['stop']*i/1000 for i in range(1001))
    rows=[]
    for t in sorted(times):
        row=dict(time=t,**{key:uart.pwl(points,t) for key,points in case['controls'].items()})
        for signal in ('busy','valid','error','data','shift'):
            value=0.;previous=0.
            for et,key,target in events:
                if key!=signal:continue
                fraction=float(t>=et) if sharp else min(1.,max(0.,(t-et)/case['rise']))
                value+=(target-previous)*fraction;previous=target
            row[signal]=value
        rows.append(row)
    return rows


class UartCalendar(unittest.TestCase):
    def test_public_transfer_counts_and_known_data(self):
        expected=[(10,0,80,1,0),(2,1,26,0,1),(2,0,16,2,0)]
        for case,counts in zip(CASES,expected):
            events,actual=uart.timeline(case)
            self.assertEqual(tuple(actual.values()),counts)
        events,_=uart.timeline(CASES[0])
        first=next(value for _,signal,value in events if signal=='data' and value>0)
        self.assertAlmostEqual(first,165/255)
        # First wire samples are 1,0,1,0,0,1,0,1 (LSB first).
        partial=[value for _,signal,value in events if signal=='shift'][:10]
        self.assertIn(5/255,partial)

    def test_all_observable_history_and_finite_edges(self):
        for case in CASES:
            events,_=uart.timeline(case);rows=waveform(case,events)
            result=uart.evaluate(rows,case)
            self.assertTrue(result['passed'],result)
            self.assertFalse(uart.evaluate(waveform(case,events,sharp=True),case)['passed'])
            self.assertFalse(uart.evaluate([dict(row,shift=0.) for row in rows],case)['passed'])
            self.assertFalse(uart.evaluate([dict(row,valid=0.) for row in rows],case)['passed'])
        case=CASES[1];events,_=uart.timeline(case);rows=waveform(case,events)
        self.assertFalse(uart.evaluate([dict(row,error=0.) for row in rows],case)['passed'])

    def test_narrow_raw_glitch_between_edge_probes(self):
        case=CASES[0];events,_=uart.timeline(case);rows=waveform(case,events)
        time=next(t for t,signal,value in events if signal=='busy' and value==1.)
        center=time+.1*case['rise'];times=[r['time'] for r in rows]
        extra=[]
        for delta in (-.001*case['rise'],0.,.001*case['rise']):
            t=center+delta
            extra.append(dict(time=t,**{key:uart.interpolate(rows,times,key,t) for key in case['signals']}))
        dense=sorted(rows+extra,key=lambda row:row['time'])
        self.assertTrue(uart.evaluate(dense,case)['passed'])
        extra[1]['busy']+=.05
        self.assertFalse(uart.evaluate(dense,case)['passed'])

if __name__=='__main__':unittest.main()
