"""Run actual fixed JKU transistor experiments, preserving full prehistory.

PDK input must be fixed IHP SG13CMOS5L with sibling SG13G2 model files.
The source models are never used to generate candidate output during scoring.
"""
import argparse,hashlib,json,subprocess,bisect
from pathlib import Path
HERE=Path(__file__).resolve().parent
RECORDS={
 'train-0':[.8,.82,.77,1.10,.50,1.43,.8],
 'train-1':[.7,.73,.68,1.20,.35,1.435,.75],
 'train-2':[.85,.83,.88,.40,1.25,1.44,.78],
 'test-0':[.76,.79,.74,1.16,.43,1.42,.81],
 'test-1':[.84,.81,.87,.39,1.18,1.425,.73],
 'test-2':[.73,.75,.70,1.23,.33,1.44,.79],
}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def points(values):
 p=[(0,values[0])]
 for i,v in enumerate(values[1:]):
  t=(3+i*2)*1e-6;p += [(t,p[-1][1]),(t+5e-9,v)]
 return p+[(17e-6,p[-1][1])]
def run(pdk,osdi,output,step):
 output.mkdir(parents=True,exist_ok=True)
 model=(pdk/'libs.tech/ngspice/models/cornerMOSlv.lib').resolve()
 source=HERE/'ota.spice';manifest={'source':'5635f2f5bb52968ed6c5d6896b2243d023af7edc','source_netlist_sha256':digest(source),'ngspice_version':subprocess.check_output(['ngspice','--version'],text=True),'osdi_sha256':digest(osdi),'model_files':{},'records':[],'maxstep_s':step}
 for name in ['cornerMOSlv.lib','sg13g2_moslv_mod.lib','sg13g2_moslv_parm.lib']:
  path=model.parent/name;manifest['model_files'][name]=digest(path)
 for name,vals in RECORDS.items():
  wave=points(vals);en=[(0,0),(1e-6,0),(1.1e-6,1.5),(14.5e-6,1.5),(14.6e-6,0),(15e-6,0),(15.1e-6,1.5),(17e-6,1.5)]
  # Retain the original 5uA bias ramp; bias thereafter remains fixed.
  net=f'''JKU improved OTA fixed experiment {name}
.lib {model} mos_tt
.include {source}
Vdd vdd 0 1.5
Vin vin 0 pwl({' '.join(f'{t:g} {v:g}' for t,v in wave)})
Ven enable 0 pwl({' '.join(f'{t:g} {v:g}' for t,v in en)})
Ib vdd ibias pwl(0 0 1.1u 0 1.2u 5u)
Xota vin vout vout enable ibias vdd 0 ota
Cl vout 0 50f
.ic v(vout)=0
.temp 27
.options reltol=1e-5 abstol=1e-14 method=gear
.control
pre_osdi {osdi.resolve()}
pre_osdi {osdi.with_name('psp103_nqs.osdi').resolve()}
set wr_singlescale
set wr_vecnames
tran {step:g} 17u uic
wrdata {name}.raw.txt v(vin) v(enable) v(vout)
quit
.endc
.end
'''
  deck=output/(name+'.sp');deck.write_text(net)
  proc=subprocess.run(['ngspice','-b',str(deck.resolve())],cwd=output,capture_output=True,text=True)
  (output/(name+'.log')).write_text(proc.stdout+proc.stderr)
  if proc.returncode or 'No. of Data Rows' not in proc.stdout:raise RuntimeError(name+': source execution failed')
  raw=output/(name+'.raw.txt');rows=[]
  for line in raw.read_text().splitlines()[1:]:
   r=list(map(float,line.split()));rows.append(r)
  ts=[r[0] for r in rows]
  def at(t,col):
   j=max(0,min(len(rows)-2,bisect.bisect_right(ts,t)-1));a,b=rows[j],rows[j+1];return a[col]+(b[col]-a[col])*(t-a[0])/(b[0]-a[0])
  # Keep full experiment history, with dense observations around every input,
  # startup and re-enable event. No true-output prefix is fed to the candidate.
  grid={i*20e-9 for i in range(851)}
  for edge in [1e-6,1.1e-6,14.5e-6,15e-6]+[p[0] for p in wave[1:-1:2]]:
   grid.update(edge+i*.25e-9 for i in range(801))
  grid.update(i*.25e-9 for i in range(41))
  grid={round(t,15) for t in grid if ts[0]<=t<=17e-6};grid.add(ts[0]);grid.add(17e-6)
  data=[[t,at(t,1),at(t,2),at(t,3)] for t in sorted(grid)]
  exported=output/(name+'.json');exported.write_text(json.dumps(dict(record_id=name,input=wave,enable=en,columns=['time_s','vin_V','enable_V','vout_V'],rows=data),separators=(',',':'))+'\n')
  manifest['records'].append(dict(record_id=name,raw_sha256=digest(raw),deck_sha256=digest(deck),export_sha256=digest(exported),raw_rows=len(rows),export_rows=len(data)))
 (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pdk',type=Path,required=True);p.add_argument('--osdi',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--step',type=float,default=1e-9);a=p.parse_args();run(a.pdk,a.osdi,a.output,a.step)
