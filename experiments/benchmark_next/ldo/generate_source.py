"""Actual fixed-source ngspice calibration, not a candidate VA backend."""
import argparse,hashlib,json,pathlib,subprocess
HERE=pathlib.Path(__file__).parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--ngspice',default='ngspice');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 result=dict(pdk_revision='f62031a1be9aefe902d6d54cddd6f59b57627436',adb_revision='972f7cd7c95381134387b250edf18f3bd23bdd25',ngspice_version=subprocess.check_output([a.ngspice,'--version'],text=True),records=[])
 for flavor in ['raw_models.spice','models.spice']:
  for name,load,cap in [('nominal',120,'1u'),('light-fast',240,'0.5u'),('heavy-slow',60,'2u')]:
   w=a.output/(flavor.split('.')[0]+'-'+name);w.mkdir(exist_ok=True)
   for dst,src in [('models.spice',flavor),('ldo_ota5.spi','ldo_ota5.spi')]: (w/dst).write_bytes((HERE/'source'/src).read_bytes())
   deck=(HERE/'source/upstream_startup.spi').read_text().replace('.lib "/opt/sky130/continuous/sky130.lib.spice" tt','.include "models.spice"').replace('.include "/app/circuit.spi"','.include "ldo_ota5.spi"').replace('RLOAD vout vss 120',f'RLOAD vout vss {load}').replace('COUT vcap vss 1u',f'COUT vcap vss {cap}').replace('.end','.control\nrun\nwrdata waveform.dat v(vin) v(vout)\n.endc\n.end')
   (w/'tb.spi').write_text(deck)
   with (w/'ngspice.log').open('w') as log:run=subprocess.run([a.ngspice,'-b','tb.spi'],cwd=w,stdout=log,stderr=subprocess.STDOUT)
   if run.returncode:raise RuntimeError('ngspice failed: '+str(w))
   rows=[[float(x) for x in l.split()] for l in (w/'waveform.dat').read_text().splitlines()]
   result['records'].append(dict(name=name,model=flavor,returncode=run.returncode,peak_v=max(r[-1] for r in rows),final_v=rows[-1][-1],rows=len(rows),netlist_sha256=hashlib.sha256(deck.encode()).hexdigest(),model_sha256=hashlib.sha256((w/'models.spice').read_bytes()).hexdigest(),waveform_sha256=hashlib.sha256((w/'waveform.dat').read_bytes()).hexdigest()))
 (a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
