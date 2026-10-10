"""Original multi-VA causal power-control engineering, not a transistor POR model."""
from build_tasks import ROOT,HERE,package,write,dump,deck,clock
HEADER='`include "disciplines.vams"\n'
UVLO=HEADER+'''module chain_uvlo(vin,pgood);
input vin; output pgood; electrical vin,pgood;
parameter real high=0.65, low=0.55, tr=10p; integer valid;
analog begin
@(initial_step) valid=(V(vin)>high);
@(cross(V(vin)-high,1)) valid=1;
@(cross(V(vin)-low,-1)) valid=0;
V(pgood)<+transition(0.9*valid,0,tr);
end
endmodule
'''
RELEASE=HEADER+'''module chain_release(pgood,resetb);
input pgood; output resetb; electrical pgood,resetb;
parameter real delay=10n, tr=10p; integer released; real deadline;
analog begin
@(initial_step) begin released=0; deadline=-1; end
@(cross(V(pgood)-0.45,1)) deadline=$abstime+delay;
@(cross(V(pgood)-0.45,-1)) begin released=0; deadline=-1; end
@(timer(deadline)) begin
if(deadline>=0 && $abstime>=deadline && V(pgood)>0.45) released=1;
deadline=-1;
end
V(resetb)<+transition(0.9*released,0,tr);
end
endmodule
'''
ENABLE=HEADER+'''module chain_enable(pgood,resetb,enable);
input pgood,resetb; output enable; electrical pgood,resetb,enable;
analog V(enable)<+ 0.9*((V(pgood)>0.45)&&(V(resetb)>0.45));
endmodule
'''
DOWN=HEADER+'''module chain_downstream(clk,resetb,enable,activity);
input clk,resetb,enable; output activity; electrical clk,resetb,enable,activity;
integer count; parameter real tr=10p;
analog begin
@(initial_step) count=0;
@(cross(V(resetb)-0.45,-1) or cross(V(enable)-0.45,-1)) count=0;
@(cross(V(clk)-0.45,1)) begin
if(V(resetb)>0.45 && V(enable)>0.45) count=count+1; else count=0;
end
V(activity)<+transition(0.1*count,0,tr);
end
endmodule
'''
TOP=HEADER+'''module power_chain(vin,clk,pgood,resetb,enable,activity);
input vin,clk; output pgood,resetb,enable,activity; electrical vin,clk,pgood,resetb,enable,activity;
chain_uvlo monitor(vin,pgood);
chain_release release_control(pgood,resetb);
chain_enable gate_control(pgood,resetb,enable);
chain_downstream consumer(clk,resetb,enable,activity);
endmodule
'''

def build():
 task='v2-repair-uvlo-reset-chain';files={'dut.va':TOP,'uvlo.va':UVLO,'release.va':RELEASE,'enable.va':ENABLE,'downstream.va':DOWN}
 starter=RELEASE.replace('@(cross(V(pgood)-0.45,1)) deadline=$abstime+delay;','@(cross(V(pgood)-0.45,1)) if(deadline<0) deadline=$abstime+delay;').replace('released=0; deadline=-1; end\n@(timer','released=0; end\n@(timer')
 buggy={**files,'release.va':starter}
 patterns=[[(2,0.7),(20,0.5),(24,0.7),(27,0.5),(30,0.7),(49,0.5),(53,0.7)],[(1,0.7),(5,0.6),(7,0.5),(10,0.7),(13,0.5),(17,0.7),(35,0.6),(38,0.5),(41,0.7),(58,0.5),(61,0.7)]]
 cases=[]
 ports=['vin','clk','pgood','resetb','enable','activity']
 for i,p in enumerate(patterns):
  cases.append(dict(name='public-old-event' if i==0 else 'repeated-recovery',kind='chain',signals=ports,stop=78e-9,guard=0.15e-9,release_delay=10e-9,maxstep=0.05e-9,netlist=deck('power_chain',ports,{'vin':(0.5,[(t+0.2,v) for t,v in p]),'clk':(0,clock(78))},78,includes=list(files))))
 words='修复UVLO、复位释放、使能与有状态下游链。vin上穿0.65V产生pgood，下穿0.55V撤销，迟滞区保持。pgood连续高10ns后resetb释放；任何失效均立即断言并取消旧计时，再次有效必须重计完整10ns。enable为pgood与resetb同时有效。下游activity初始0，enable且resetb有效时每个clk上升沿加0.1V，否则清零；保护撤销时清零。正常供电必须出现下游递增动作。\n\n可修改dut.va顶层连接、uvlo.va、release.va、enable.va、downstream.va及设计参数，或整体重建满足接口与合同的系统。验收电源/时钟激励固定；逻辑高0.9V，传播与平滑须在0.15ns内完成，10ns资格允许0.15ns传播容差。公开参数范围：上阈值0.64至0.66V，下阈值0.54至0.56V，release delay为9.9至10.1ns；即使调参仍须满足公开外部合同。此系统为原创行为控制工程，未声称晶体管POR等价。'
 path=package(task,buggy,cases,words,'original-uvlo-chain-case0009')
 for name,text in files.items():write(path/'solution/files'/name,text)
 alt=RELEASE.replace('@(timer(deadline)) begin','@(timer(0,20p)) begin\nif(deadline>=0 && $abstime>=deadline) begin').replace('deadline=-1;\nend\nV(resetb)','deadline=-1;\nend\nend\nV(resetb)')
 variants={'healthy':(files,True,'健康四职责系统与真实计数下游'),'reference':(files,True,'取消旧deadline并每次恢复重新资格'),'alternative':({**files,'release.va':alt},True,'周期调度的释放整体重写'),'starter':(buggy,False,'短暂恢复旧deadline在新周期提前释放'),'bypass-enable':({**files,'enable.va':ENABLE.replace('((V(pgood)>0.45)&&(V(resetb)>0.45))','(V(pgood)>0.45)')},False,'使能旁路复位资格'),'never-release':({**files,'release.va':RELEASE.replace('released=1;','released=0;')},False,'永不释放/下游永无动作'),'wrong-polarity':({**files,'uvlo.va':UVLO.replace('0.9*valid','0.9*(1-valid)')},False,'UVLO极性反转'),'no-hysteresis':({**files,'uvlo.va':UVLO.replace('low=0.55','low=0.65')},False,'迟滞区撤销资格')}
 requests=__import__('json').loads((HERE/'run-plan.json').read_text())
 for name,(bundle,passed,why) in variants.items():
  cdir=HERE/'candidates'/task/name
  for filename,text in bundle.items():write(cdir/filename,text)
  requests.append({'task':str(path.relative_to(ROOT)),'variant':name,'candidate_dir':str(cdir.relative_to(ROOT)),'expected_pass':passed,'behavior':why})
 dump(HERE/'run-plan.json',requests)
 manifest=__import__('json').loads((HERE/'manifest.json').read_text());manifest.append({'source_id':'case-0009','task_id':task,'status':'built-awaiting-live-calibration','contract':'chain','provenance':'original behavior system, artificial stale-event fault'})
 dump(HERE/'manifest.json',manifest)
 dump(path/'SOURCE.json',{'source_id':'case-0009','provenance':'repository-original behavioral power-control system','fault_origin':'artificial engineering-motivated stale qualification deadline','fixed_backend':'Spectre','calibration_status':'pending','agent_pilots':'pending','causal_modules':['UVLO hysteresis','continuous qualification reset release','enable gate','clocked stateful downstream']})
if __name__=='__main__':build()
