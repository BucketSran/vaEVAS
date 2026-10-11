"""Independent online contract traces, not VA/Spectre execution."""
import bisect
import json
from pathlib import Path
import re
import unittest
from experiments.benchmark_v2.extension_integration.test_checker import checker
ROOT=Path(__file__).resolve().parents[3]
TASK=ROOT/'benchmark/tasks/v2-integrate-349-multichannel-readout'
def number(value):
    scales={'n':1e-9,'p':1e-12}
    return float(value[:-1])*scales[value[-1]] if value[-1] in scales else float(value)
def online_trace(case,gain=1.0):
    waves={}
    for node,words in re.findall(r'V\w+\((\w+) 0\) vsource type=pwl wave=\[([^]]+)\]',case['netlist']):
        values=[number(x) for x in words.split()]
        waves[node]=list(zip(values[::2],values[1::2]))
    def observe(node,t):
        if node=='clk':
            if t<5e-9:return 0.
            phase=(t-5e-9)%10e-9
            if phase<20e-12:return .9*phase/20e-12
            if phase<4e-9+20e-12:return .9
            if phase<4e-9+40e-12:return .9*(4e-9+40e-12-phase)/20e-12
            return 0.
        pairs=waves[node];idx=bisect.bisect_right([x[0] for x in pairs],t)-1
        if idx>=len(pairs)-1:return pairs[-1][1]
        a,b=pairs[idx:idx+2]
        return a[1]+(b[1]-a[1])*(t-a[0])/(b[0]-a[0])
    events=[(5e-9+10e-12+i*10e-9,'clk') for i in range(17)]
    for a,b in zip(waves['rst'],waves['rst'][1:]):
        if a[1]<.45<=b[1]:events.append((a[0]+(b[0]-a[0])*(.45-a[1])/(b[1]-a[1]),'rst'))
    frame=[0.,0.,0.,0.];pointer=selected=valid=0;output=0.
    history=[(0.,dict(out=0.,ch_sel_0=0.,ch_sel_1=0.,valid=0.))]
    for at,kind in sorted(events):
        if kind=='rst' or observe('rst',at)>.45:
            frame=[0.,0.,0.,0.];pointer=selected=valid=0;output=0.
        else:
            valid=0
            if observe('read',at)>.45:
                selected=pointer;output=frame[pointer];pointer=(pointer+1)%4;valid=1
            if observe('sample',at)>.45:frame=[gain*observe('ch'+str(j),at) for j in range(4)]
        history.append((at,dict(out=output,ch_sel_0=(selected%2)*.9,ch_sel_1=(selected//2)*.9,valid=valid*.9)))
    rows=[]
    for i in range(round(case['stop']/50e-12)+1):
        t=i*50e-12
        state=history[bisect.bisect_right([x[0] for x in history],t)-1][1]
        rows.append(dict(time=t,**{n:observe(n,t) for n in ['clk','rst','sample','read','ch0','ch1','ch2','ch3']},**state))
    return rows

class ArchitectureContract(unittest.TestCase):
    def test_four_channel_component_response_and_bypass(self):
        cases=json.loads((TASK/'tests/cases.json').read_text())
        probes=[c for c in cases if 'architecture_gain' in c]
        self.assertEqual(len(probes),2)
        for case in probes:
            with self.subTest(case=case['name']):
                self.assertTrue(checker.evaluate(online_trace(case,case['architecture_gain']),case,Path('.'))['passed'])
                self.assertFalse(checker.evaluate(online_trace(case),case,Path('.'))['passed'])
        for case in cases[:2]:
            self.assertTrue(checker.evaluate(online_trace(case),case,Path('.'))['passed'])

if __name__=='__main__':unittest.main()
