"""Prepare same-input XSPICE / Verilog-A boundary calibration, no simulator call."""
from pathlib import Path
import argparse,json,re,shutil

def build(source,output):
 output.mkdir(parents=True,exist_ok=True)
 original=(source/'xspice/por_dig.out.spice').read_text()
 original=re.sub(r'^\.end\s*$','',original,flags=re.M|re.I)
 (output/'por_dig.spice').write_text(original)
 shutil.copyfile(Path(__file__).with_name('por_digital.va'),output/'dut.va')
 ports='0 vdd dis ena pdn pdnb short clk osc_ena trip0 trip1 trip2 dec0 dec1 dec2 dec3 dec4 dec5 dec6 dec7 ended por power started'
 cases=[]
 for name,short,stop,reset in [('short',1,20e-6,'0 0 1u 0 1.01u 1.8 9u 1.8 9.01u 0 10u 0 10.01u 1.8 20u 1.8'),('long',0,350e-6,'0 0 1u 0 1.01u 1.8 120u 1.8 120.01u 0 121u 0 121.01u 1.8 350u 1.8')]:
  signals=['power','clk','pdn','ena','dis','short','trip0','trip1','trip2','pdnb','osc_ena']+[f'dec{i}' for i in range(8)]+['started','ended','por']
  supplies={'vdd':'dc=1.8','pdn':'dc=0','ena':'dc=0','dis':'dc=0','short':f'dc={1.8*short}','trip0':'type=pulse val0=0 val1=1.8 delay=0.2u period=4u width=2u rise=1n fall=1n','trip1':'type=pulse val0=0 val1=1.8 delay=0.2u period=8u width=4u rise=1n fall=1n','trip2':'type=pulse val0=0 val1=1.8 delay=0.2u period=16u width=8u rise=1n fall=1n','clk':'type=pulse val0=0 val1=1.8 delay=50n period=100n width=40n rise=1n fall=1n','power':f'type=pwl wave=[{reset}]'}
  net='simulator lang=spectre\nglobal 0\nahdl_include "dut.va"\n'+''.join(f'V{k} ({k} 0) vsource {v}\n' for k,v in supplies.items())+f'XD ({ports}) por_dig\ntran tran stop={stop} maxstep=1n\nsave '+' '.join(signals)+'\n'
  cases.append(dict(name=name,kind='por_digital',stop=stop,signals=signals,netlist=net,guard=40e-9,atol=.005))
  spice='* Actual upstream XSPICE digital source\n.include por_dig.spice\nVvdd vdd 0 1.8\nVpdn pdn 0 0\nVena ena 0 0\nVdis dis 0 0\nVshort short 0 '+str(1.8*short)+'\nVtrip0 trip0 0 pulse(0 1.8 .2u 1n 1n 2u 4u)\nVtrip1 trip1 0 pulse(0 1.8 .2u 1n 1n 4u 8u)\nVtrip2 trip2 0 pulse(0 1.8 .2u 1n 1n 8u 16u)\nVclk clk 0 pulse(0 1.8 50n 1n 1n 40n 100n)\nVpower power 0 pwl('+reset+')\nXD '+ports+' por_dig\n.control\nset wr_singlescale\nset wr_vecnames\ntran 1n '+str(stop)+'\nwrdata '+name+'.dat '+' '.join('v('+n+')' for n in signals)+'\nquit\n.endc\n.end\n'
  (output/(name+'.cir')).write_text(spice)
 (output/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
 (output/'manifest.json').write_text(json.dumps(dict(candidate='dut.va',cases='cases.json',purpose='actual XSPICE vs readable VA digital boundary; full analog bench separately pending'),indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.source,a.output)
