"""Convergence and initialization checks, independent of a fitted VA."""
import json, shutil
from pathlib import Path
from generate_source import experiments, run, interp
BASE=Path(__file__).resolve().parents[3]/'runs/v2-data-source'
report={}
for exp in [experiments()['train'][0],experiments()['heldout'][1]]:
    waveforms={}
    for name,step,tol,method,uic in [('nominal',10e-12,1e-4,'gear',False),('tight',2.5e-12,1e-5,'gear',False),('trap',5e-12,1e-4,'trap',False),('uic',5e-12,1e-4,'gear',True)]:
        work=BASE/(exp['name']+'-'+name);work.mkdir(parents=True,exist_ok=True);shutil.copy(BASE/'models.spice',work/'models.spice')
        try:waveforms[name]=run(exp,work,'/opt/homebrew/bin/ngspice',step,tol,method,uic)
        except RuntimeError:waveforms[name]=None
    points=[i*50e-12 for i in range(round(exp['stop']/50e-12)+1)]
    valid=[t for t in points if any(a<=t<=b for a,b in exp['tracks']+exp['holds'])]
    # Explicit init comparison includes t=0, using the same declared output state.
    report[exp['name']]={k:({'status':'source_solver_failure'} if v is None else {'full_max_V':max(abs(interp(v,t,4)-interp(waveforms['tight'],t,4)) for t in points),'scored_max_V':max(abs(interp(v,t,4)-interp(waveforms['tight'],t,4)) for t in valid)}  ) for k,v in waveforms.items() if k!='tight'}
(Path(__file__).parent/'source-convergence.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
