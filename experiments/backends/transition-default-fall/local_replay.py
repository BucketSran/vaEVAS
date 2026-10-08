"""Public compiler/Rust replay of every frozen sparse/dense analytical anchor."""
import argparse,hashlib,json,math
from pathlib import Path
from evas import Instance,compile_sources,transient
from check import BASE,SIGNALS,expected,waveform
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def replay(kernel,output):
 manifest=json.loads((BASE/'MANIFEST.json').read_text());instances=[Instance(i,'transition_default',{'r':'0'}|{n:i+'_'+n for n in ['simple','reverse','extend','mirror','qs','qr','qe','qm']},{'edge':tr,'delay':d}) for i,tr,d in [('a',.5,0),('b',1,.125)]];summary={}
 for c in manifest['cases']:
  source=BASE/c['id']/'dut.va'
  if sha(source)!=c['files']['dut.va']:raise ValueError('frozen source hash mismatch')
  p=compile_sources({str(source):source.read_text()},instances);times=c['requested_times'];r=transient(p,{},times,stop=3,max_step=.015625,kernel=kernel,vabstol=1e-11,reltol=1e-9)
  rows=[dict(time=t,voltages=dict(zip(r['nodes'],row['voltages']))) for t,row in zip(times,r['solutions'],strict=True)]
  if any(not math.isfinite(v) for row in rows for v in row['voltages'].values()):raise ValueError('nonfinite EVAS response')
  summary[c['id']]=dict(source_sha256=sha(source),requested_count=len(times),observed_count=len(rows),independent=waveform(rows),operator_count=len(p.operators),distinct_origins=len({(o.origin.instance,o.origin.line,o.origin.column) for o in p.operators}))
 output.write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n');return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('kernel',type=Path);p.add_argument('output',type=Path);a=p.parse_args();replay(a.kernel,a.output)
