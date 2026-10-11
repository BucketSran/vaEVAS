"""Generate three contract-based extensions; never rewrite submitted candidates."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
INC='`include "constants.vams"\n`include "disciplines.vams"\n'
DCO=INC+'''module healthy_dco(tune,rst,dco);
input tune,rst;output dco;electrical tune,rst,dco;
parameter real sensitivity=10e6;
real freq,phase;
analog begin
 freq=20e6+sensitivity*V(tune);if(freq<20e6)freq=20e6;if(freq>60e6)freq=60e6;
 phase=idt(freq,0,V(rst)>0.45);
 if(V(rst)>0.45)V(dco)<+0;else V(dco)<+0.45+0.45*tanh(20*sin(2*`M_PI*phase));
 $bound_step(1/(40*freq));
end
endmodule
'''
PLL=INC+'''module fractional_pll(ref,rst,n,frac,dco,fb,tune,lock);
input ref,rst,n,frac,dco;output fb,tune,lock;electrical ref,rst,n,frac,dco,fb,tune,lock;
integer count,divide,state,up,dn,good,last_n;
real acc,last_frac,control,filtered,epoch;
analog begin
 @(initial_step)begin count=0;divide=3;state=0;up=0;dn=0;good=0;last_n=3;last_frac=0;acc=0;control=1;filtered=0;epoch=0;end
 @(cross(V(rst)-0.45,+1))begin count=0;divide=$rtoi(V(n)+0.5);state=0;up=0;dn=0;good=0;acc=0;control=1;filtered=0;epoch=$abstime;end
 @(cross(V(ref)-0.45,+1))begin
  if(V(rst)<0.45)begin up=1;if(dn)begin up=0;dn=0;end end
 end
 @(cross(V(fb)-0.45,+1))begin
  if(V(rst)<0.45)begin dn=1;if(up)begin up=0;dn=0;end end
 end
 @(cross(V(dco)-0.45,+1))begin
  if(V(rst)<0.45)begin
   count=count+1;
   if(count>=divide)begin
    count=0;state=1;acc=acc+V(frac);divide=$rtoi(V(n)+0.5);
    if(acc>=1)begin divide=divide+1;acc=acc-1;end
   end else state=0;
  end else begin count=0;state=0;end
 end
 @(timer(0,2n))begin
  if(V(rst)>0.45 || $rtoi(V(n)+0.5)!=last_n || abs(V(frac)-last_frac)>0.001)begin
   count=0;divide=$rtoi(V(n)+0.5);state=0;up=0;dn=0;good=0;acc=0;control=1;filtered=0;epoch=$abstime;
  end else begin
   control=control+0.0004*(up-dn);if(control<0)control=0;if(control>4)control=4;
   filtered=filtered+0.01*((up-dn)-filtered);
   if($abstime-epoch>5u && abs(filtered)<0.2)good=good+1;else good=0;
  end
  last_n=$rtoi(V(n)+0.5);last_frac=V(frac);
 end
 V(tune)<+control+0.5*(up-dn);
 V(fb)<+transition(state*0.9,0,100p);
 V(lock)<+transition((good>=250)*0.9,0,100p);
end
endmodule
'''
FRONT=INC+'''module healthy_front(inp,inn,offset,cmoffset,code,outp,outn);
input inp,inn,offset,cmoffset,code;output outp,outn;electrical inp,inn,offset,cmoffset,code,outp,outn;
parameter real mode=0,actuator=1,gain=2,static_trim=-0.02;
real differential,common,p,m;
analog begin
 differential=gain*V(inp,inn)+V(offset)+static_trim;
 common=0.5+V(cmoffset);
 if(mode<0.5)differential=differential+0.002*actuator*V(code);
 else common=common+0.002*actuator*V(code);
 p=common+0.5*differential;m=common-0.5*differential;
 if(p<0.05)p=0.05;if(p>0.95)p=0.95;if(m<0.05)m=0.05;if(m>0.95)m=0.95;
 V(outp)<+p;V(outn)<+m;
end
endmodule
'''
SERVO=INC+'''module calibration_controller(outp,outn,cal,enable,rst,code);
input outp,outn,cal,enable,rst;output code;electrical outp,outn,cal,enable,rst,code;
parameter real mode=0;
integer value;real error,next;
analog begin
 @(initial_step)value=0;
 @(cross(V(rst)-0.45,+1))value=0;
 @(timer(1u,2u))begin
  if(V(rst)>0.45)value=0;
  else if(V(enable)>0.45 && (mode>0.5 || V(cal)>0.45))begin
   if(mode<0.5)error=V(outp,outn);else error=(V(outp)+V(outn))*0.5-0.5;
   next=value-250*error;
   if(next>=0)value=$rtoi(next+0.5);else value=-$rtoi(-next+0.5);
   if(value>64)value=64;if(value< -64)value=-64;
  end
 end
 V(code)<+transition(value,0,100n);
end
endmodule
'''
def pwl(name,node,points):
 return f'{name}({node} 0) vsource type=pwl wave=['+' '.join(f'{t:0.12g} {v:0.12g}' for t,v in points)+']\n'
def analog_cases(kind):
 cases=[]
 for k,act in enumerate((0.8,1.2)):
  points=[];cal=[]
  for i in range(11):
   t=i*100e-6;cal.extend([(t, 0.9),(t+39e-6,0.9),(t+40e-6,0),(t+99e-6,0)])
   points.extend([(t,0),(t+40e-6,0),(t+45e-6,0.06 if i%2 else -0.06),(t+65e-6,0.06 if i%2 else -0.06),(t+70e-6,-0.04 if i%2 else 0.04),(t+95e-6,-0.04 if i%2 else 0.04),(t+99e-6,0)])
  enable=[(0,0.9),(550e-6,0.9),(551e-6,0),(650e-6,0),(651e-6,0.9),(1e-3,0.9)]
  reset=[(0,0),(750e-6,0),(751e-6,0.9),(760e-6,0.9),(761e-6,0),(1e-3,0)]
  offset=[(0,0.02),(200e-6,0.055),(300e-6,0),(400e-6,0),(410e-6,0.36),(480e-6,0.36),(490e-6,0.025),(600e-6,-0.025),(700e-6,-0.015),(800e-6,0.04),(1e-3,0.025)]
  common=[(0,0.02),(200e-6,0.07),(300e-6,-0.07),(400e-6,-0.07),(410e-6,0.5),(480e-6,0.5),(490e-6,0.04),(600e-6,-0.055),(700e-6,-0.055),(800e-6,0.07),(1e-3,0.025)]
  if k:
   offset=[(t,0.02+0.8*(v-0.02)) for t,v in offset]
   common=[(t,-0.8*v) for t,v in common]
  mode=0 if kind=='continuous-offset' else 1
  net='simulator lang=spectre\nglobal 0\nahdl_include "healthy.va"\nahdl_include "dut.va"\n'
  net+=pwl('VI','inp',points)+'VN(inn 0) vsource dc=0\n'+pwl('VC','cal',cal)+pwl('VE','enable',enable)+pwl('VR','rst',reset)
  net+=pwl('VO','offset',offset if mode==0 else [(0,0.02),(1e-3,0.02)])
  net+=pwl('VM','cmoffset',common if mode==1 else [(0,0),(1e-3,0)])
  net+=f'XF(inp inn offset cmoffset code outp outn) healthy_front mode={mode} actuator={act}\nXC(outp outn cal enable rst code) calibration_controller mode={mode}\n'
  signals=['inp','inn','offset','cmoffset','cal','enable','rst','code','outp','outn']
  net+='tran tran stop=1m maxstep=500n errpreset=conservative\nsave '+' '.join(signals)+'\n'
  windows=[[130e-6,180e-6],[330e-6,390e-6],[530e-6,548e-6],[730e-6,745e-6],[830e-6,880e-6],[930e-6,980e-6]]
  cases.append(dict(name=f'{kind}-actuator-{act}',kind=kind,stop=0.001,signals=signals,netlist=net,support={'healthy.va':FRONT},windows=windows,gain=2,cm_target=0.5,cm_tolerance=0.008,diff_tolerance=0.012,code_limit=64,hold_windows=[[555e-6,645e-6]],reset_windows=[[753e-6,758e-6]]))
 return cases

def pll_cases():
 result=[]
 for k,f in enumerate((0.25,0.75)):
  net='simulator lang=spectre\nglobal 0\nahdl_include "healthy.va"\nahdl_include "dut.va"\nVR(ref 0) vsource type=pulse val0=0 val1=0.9 period=100n width=49n rise=100p fall=100p delay=10n\n'
  net+=pwl('Vreset','rst',[(0,0.9),(200e-9,0.9),(201e-9,0),(60e-6,0),(60.001e-6,0.9),(60.3e-6,0.9),(60.301e-6,0),(100e-6,0)])
  net+=pwl('VN','n',[(0,3),(30e-6,3),(30.001e-6,4),(100e-6,4)])
  net+=pwl('VF','frac',[(0,0),(15e-6,0),(15.001e-6,f),(45e-6,f),(45.001e-6,0),(75e-6,0),(75.001e-6,0.5),(100e-6,0.5)])
  net+='XO(tune rst dco) healthy_dco\nX(ref rst n frac dco fb tune lock) fractional_pll\ntran tran stop=100u maxstep=2n errpreset=conservative\nsave ref rst n frac dco fb tune lock\n'
  result.append(dict(name=f'fractional-pll-{f}',kind='fractional-pll',stop=100e-6,signals=['ref','rst','n','frac','dco','fb','tune','lock'],netlist=net,support={'healthy.va':DCO.replace('sensitivity=10e6','sensitivity=12e6') if k else DCO},windows=[[12e-6,14.9e-6,3,0],[27e-6,29.9e-6,3,f],[42e-6,44.9e-6,4,f],[57e-6,59.9e-6,4,0],[72e-6,74.9e-6,4,0],[94e-6,99e-6,4,0.5]],ratio_tolerance=0.04,frequency_tolerance=0.06,feedback_tolerance=0.015,phase_tolerance=0.35,mean_phase_tolerance=0.2,withdraw_windows=[[15.1e-6,16e-6],[30.1e-6,31e-6],[60.01e-6,60.25e-6]]))
 return result

def build():
 manifest={'spec_issue':150,'weight':1,'model_trials':'not-requested','calibration_requests':[],'source_disposition':{'302':'D1 N/N+1 feedback; old toggle convention replaced by explicit rising-edge contract','306':'D2 static trim retained as healthy frontend start','369':'D2 signed continuous control merged with306 because same execution contract','390':'D3 real common-mode actuation and preserved differential transfer'}}
 for kind,reference,support,cases in [('fractional-pll',PLL,DCO,pll_cases()),('continuous-offset',SERVO,FRONT,analog_cases('continuous-offset')),('common-mode-servo',SERVO,FRONT,analog_cases('common-mode'))]:
  task=ROOT/'benchmark/tasks'/f'v3-calibration-{kind}'
  for s in ('environment/public','solution','tests'): (task/s).mkdir(parents=True,exist_ok=True)
  pub=task/'environment/public';test=task/'tests';sol=task/'solution'
  starter=reference if kind=='fractional-pll' else reference.replace('next=value-250*error;','next=value;')
  if kind=='fractional-pll':starter=starter.replace('acc=acc+V(frac);','acc=acc+0;')
  (pub/'dut.va').write_text(starter);(pub/'healthy.va').write_text(support);(pub/'public-default.scs').write_text(cases[0]['netlist'])
  (sol/'dut.va').write_text(reference);(sol/'solve.sh').write_text('#!/bin/sh\nset -eu\ncp /solution/dut.va /work/dut.va\n')
  (sol/'solve.sh').chmod(0o755)
  (task/'environment/Dockerfile').write_text((ROOT/'benchmark/tasks/v2-integrate-case0007-adpll-fine-tdc/environment/Dockerfile').read_text())
  (task/'task.toml').write_text(f'''schema_version = "1.4"
[metadata]
name = "{task.name}"
category = "verilog-a"
engineering_action = "extension-integration"
source_group = "{'fractional-pll-302' if kind=='fractional-pll' else 'calibration-frontends-306-369-390'}"
context_level = "bounded-engineering-project"
provenance = "original-contract-source-informed"
data_provenance = "behavioral_synthetic"
weight = 1
[agent]
timeout_sec = 3600
[verifier]
timeout_sec = 1800
[environment]
build_timeout_sec = 600
cpus = 1
memory_mb = 2048
storage_mb = 4096
''')
  for file in ('v2_runtime.py','adc_linearity.py','v2_next_calibration.py'):shutil.copyfile(ROOT/'benchmark/checkers'/file,test/file)
  (test/'verify.py').write_text('from v2_runtime import main\nfrom v2_next_calibration import evaluate\nif __name__ == "__main__": main(evaluate)\n')
  (test/'test.sh').write_text((ROOT/'benchmark/tasks/v2-integrate-case0007-adpll-fine-tdc/tests/test.sh').read_text())
  (test/'test.sh').chmod(0o755)
  (test/'contract.json').write_text(json.dumps(dict(task_id=task.name,candidate_files=['dut.va'],category='extension-integration'),indent=2)+'\n')
  (test/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
  (pub/'acceptance-windows.json').write_text(json.dumps({key:cases[0][key] for key in ('windows','hold_windows','reset_windows') if key in cases[0]},indent=2)+'\n')
  (pub/'interface.json').write_text(json.dumps(dict(task_id=task.name,editable=['dut.va'],fixed=['healthy.va'],public_signals=cases[0]['signals'],hidden_changes='Only published bias/common-mode envelope and slope, actuator and DCO sensitivity ranges; no reference bitstream match'),indent=2)+'\n')
  variants={'reference':reference}
  if kind=='fractional-pll':
   variants.update(detached_feedback=reference.replace('dco,fb,tune,lock;\ninteger','dco,fb,tune,lock,fake;\nhealthy_dco #(.sensitivity(10e6)) detached(tune,rst,fake);\ninteger').replace('cross(V(dco)-0.45','cross(V(fake)-0.45'),alternative=reference.replace('acc=0;','acc=0.5;').replace('control+0.5*(up-dn)','control+0.65*(up-dn)'),integer_only=reference.replace('acc=acc+V(frac);','acc=acc+0;'),feedback_bypass=reference.replace('V(fb)<+transition(state*0.9,0,100p);','V(fb)<+V(ref);'),open_loop=reference.replace('control=control+0.0004*(up-dn);','control=V(n)+V(frac)-2;').replace('control+0.5*(up-dn)','control'))
  else:
   variants.update(detached_feedback=reference.replace('dco,fb,tune,lock;\ninteger','dco,fb,tune,lock,fake;\nhealthy_dco #(.sensitivity(10e6)) detached(tune,rst,fake);\ninteger').replace('cross(V(dco)-0.45','cross(V(fake)-0.45'),alternative=reference.replace('next=value-250*error;','if(error>0.015)next=value-8;else if(error< -0.015)next=value+8;else if(error>0.0015)next=value-2;else if(error< -0.0015)next=value+2;else next=value;'),fixed_code=reference.replace('next=value-250*error;','next=0;'),wrong_direction=reference.replace('next=value-250*error;','next=value+125*error;'))
   if kind=='continuous-offset':variants['cancel_signal']=reference.replace('(mode>0.5 || V(cal)>0.45)','(1)')
   else: variants['measure_differential']=reference.replace('error=(V(outp)+V(outn))*0.5-0.5;','error=V(outp,outn);')
  if kind!='fractional-pll':
   variants.pop('detached_feedback',None)
   variants['fractional_code']=reference.replace('transition(value,0,100n)','transition(value+0.5*(V(rst)<0.45),0,100n)').replace('value>64)value=64','value>63)value=63').replace('value< -64)value=-64','value< -63)value=-63')
  for name,source in variants.items():
   directory=OUT/'candidates'/task.name/name;directory.mkdir(parents=True,exist_ok=True);(directory/'dut.va').write_text(source)
   manifest['calibration_requests'].append(dict(task=str(task.relative_to(ROOT)),variant=name,candidate_directory=str(directory.relative_to(ROOT)),expected='pass' if name in ('reference','alternative') else 'fail',certification='pending-live-execution'))
  manifest.setdefault('tasks',[]).append(dict(id=task.name,kind=kind,conditions=len(cases),case_sha256=hashlib.sha256((test/'cases.json').read_bytes()).hexdigest()))
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':build()
