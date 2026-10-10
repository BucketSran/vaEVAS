"""Freeze Spectre replay experiments and independent transistor truth."""
import csv,json
from pathlib import Path
from generate_source import experiments
ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'benchmark/tasks/v2-data-sampling-identification'
cases=[]
for exp in experiments()['selftest']+experiments()['heldout']:
    path=TASK/('tests/truth' if exp['name'].startswith('heldout') else 'environment/public/data')/(exp['name']+'.csv')
    rows=list(csv.DictReader(path.open()));truth=[[float(r['time_s']),float(r['vhold_V'])] for r in rows]
    def source(points):return 'type=pwl wave=['+' '.join(f'{t:.12g} {v:.12g}' for t,v in points)+']'
    deck='simulator lang=spectre\nahdl_include "dut.va"\nvin (vin 0) vsource '+source(exp['vin'])+'\nclk (clock 0) vsource '+source(exp['clock'])+'\ndut (vin clock vhold) sampling_model\noptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-14\ntran tran stop='+str(exp['stop'])+' maxstep=10p\nsave vin clock vhold\n'
    cases.append({**exp,'netlist':deck,'signals':['vin','clock','vhold'],'truth':truth,'limits':{'track_rms':.025,'sample_max':.05,'hold_max':.05}})
(TASK/'tests/cases.json').write_text(json.dumps(cases,indent=2)+'\n')
# This copy belongs to author calibration; runtime uses the same cases and checker.
(TASK/'tests/selftest.json').write_text(json.dumps(cases[:2],indent=2)+'\n')
