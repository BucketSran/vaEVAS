"""Author original model/repair tasks; never copies historical reference source."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[3]
BASE='FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c\nWORKDIR /work\nCOPY public/ /work/public/\nRUN mkdir -p /work/output\n'
HEADER='`include "constants.vams"\n`include "disciplines.vams"\n'

def write_task(task_id,instruction,source,reference,negatives,cases,public_case,kind,group):
    p=ROOT/'benchmark/tasks'/task_id
    for sub in ['environment/public','solution','tests','tests/negatives']:(p/sub).mkdir(parents=True,exist_ok=True)
    (p/'instruction.md').write_text(instruction+'\n\n提交 `/work/dut.va`。只能使用标准 constants.vams / disciplines.vams；禁止文件I/O、系统调用及外部include。公开自测网表在 `/work/public/visible.scs`，用有授权的 Spectre 自测；远端公开调用入口由评测环境提供。最终评分独立运行，不能作为解题反馈。\n')
    (p/'SOURCE.md').write_text(source+'\n\n本次参考VA、测试网表和checker独立编写，未复制历史VA或Cadence安装库。工程需求参考旧题的架构名称与公开接口描述；不声称实测/晶体管级真实性。来源组：'+group+'。状态：本地构造与行级checker测试；实际Spectre、Harbor和Agentic校准必须另有执行收据。\n')
    (p/'task.toml').write_text(f'schema_version = "1.4"\n[metadata]\nname = "{task_id}"\ncategory = "verilog-a"\naction = "{kind}"\nsource_group = "{group}"\n[agent]\ntimeout_sec = 1200\n[verifier]\ntimeout_sec = 600\n[environment]\nbuild_timeout_sec = 600\ncpus = 1\nmemory_mb = 1024\nstorage_mb = 2048\n')
    (p/'environment/Dockerfile').write_text(BASE)
    (p/'environment/public/visible.scs').write_text(public_case['netlist'].replace('ahdl_include "dut.va"','ahdl_include "../dut.va"'))
    (p/'environment/public/README.md').write_text('公开网表只供调试，不包含终评分规则、参考解或私有条件。starter.va是候选起点，修改后保存为/work/dut.va。\n')
    if kind=='specification':
        # Preserve public port declaration and parameters only, no gold dynamics.
        declarations=[]
        for line in reference.splitlines():
            if line.startswith(('module ','input ','output ','electrical ','parameter ')):declarations.append(line)
        (p/'environment/public/starter.va').write_text(HEADER+'\n'.join(declarations)+'\n// Implement the public behavior here.\nendmodule\n')
    (p/'solution/dut.va').write_text(HEADER+reference)
    (p/'solution/solve.sh').write_text('#!/bin/sh\nset -eu\ncp /solution/dut.va /work/dut.va\n')
    for name,code in negatives.items():(p/'tests/negatives'/f'{name}.va').write_text(HEADER+code)
    (p/'tests/cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    (p/'tests/contract.json').write_text(json.dumps({'candidate_files':['dut.va'],'output_files':[]},indent=2)+'\n')
    (p/'tests/verify.py').write_text('from circuit_task import main\nfrom first_batch_model_repair import evaluate\nif __name__ == "__main__":\n    main(evaluate)\n')
    (p/'tests/test.sh').write_text('#!/bin/sh\nset -eu\npython3 /tests/verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}"\n')
    for f in [p/'solution/solve.sh',p/'tests/test.sh']:f.chmod(0o755)
    return {'id':task_id,'action':kind,'source_group':group,'path':str(p.relative_to(ROOT)),'status':'authored_pending_spectre','negative_files':list(negatives)}

def pwl(name,points):
    return f'V{name} ({name} 0) vsource type=pwl wave=['+' '.join(f'{t:.14g} {v:.14g}' for t,v in points)+']\n'

def deck(module,ports,sources,stop,params='',maxstep=20e-12):
    return 'simulator lang=spectre\nglobal 0\nahdl_include "dut.va"\n'+sources+f'XDUT ({" ".join(ports)}) {module}{(' '+params) if params else ''}\nsimulatorOptions options reltol=1e-6 vabstol=1e-9\ntran tran stop={stop:.14g} maxstep={maxstep:.14g}\nsave '+ ' '.join(ports)+'\n'

COMPARATOR='''module latched_comparator(clk,rst,vinp,vinn,outp,outn,ready);
input clk,rst,vinp,vinn; output outp,outn,ready;
electrical clk,rst,vinp,vinn,outp,outn,ready;
parameter real vth=0.5, voffset=0.002, tbase=0.2n, tau=0.25n, vscale=0.05, vfloor=0.001, tr=50p;
real op,on,rd,d,decision_at; integer sign_latched,active;
analog begin
 @(initial_step) begin op=0;on=0;rd=0;active=0;decision_at=1e30;sign_latched=0;end
 @(cross(V(clk)-vth,+1)) begin
  op=0;on=0;rd=0;active=0;decision_at=1e30;
  if(V(rst)<vth) begin
   d=V(vinp)-V(vinn)-voffset;
   sign_latched=(d>0)?1:((d<0)?-1:0);
   if(sign_latched!=0) begin active=1;decision_at=$abstime+tbase+tau*ln(1+vscale/(abs(d)+vfloor));end
  end
 end
 @(cross(V(clk)-vth,-1) or cross(V(rst)-vth,+1)) begin op=0;on=0;rd=0;active=0;decision_at=1e30;end
 @(timer(decision_at)) begin
  if(active && V(clk)>vth && V(rst)<vth) begin op=(sign_latched>0)?1:0;on=(sign_latched<0)?1:0;rd=1;active=0;end
 end
 V(outp)<+transition(op,0,tr,tr);V(outn)<+transition(on,0,tr,tr);V(ready)<+transition(rd,0,tr,tr);
end
endmodule
'''

def comparator_case(name,ds,high=7e-9,reset_cycle=None,async_resets=None):
    stop=len(ds)*12e-9+2e-9; clk=[(0,0)]; vp=[(0,.6+ds[0]+.002)]; resets=[]; events=[]
    for i,d in enumerate(ds):
        rise=2e-9+i*12e-9;fall=rise+high
        clk += [(rise-20e-12,0),(rise+20e-12,1),(fall-20e-12,1),(fall+20e-12,0)]
        if i:vp += [(rise-1e-9-20e-12,vp[-1][1]),(rise-1e-9+20e-12,.6+d+.002)]
        # Change input during the latch hold window; must not change its decision.
        vp += [(rise+2e-9,.6+d+.002),(rise+2.04e-9,.6-d+.002)]
        if i+1<len(ds):vp += [(rise+10e-9,.6-d+.002)]
        events.append({'rise':rise,'fall':fall,'differential':d})
        if reset_cycle==i:resets += [(rise-.48e-9,1),(fall+.32e-9,0)]
        if i in (async_resets or {}):
            assertion,release=async_resets[i]
            resets += [(rise+assertion,1),(rise+release,0)]
    resets.sort()
    ports=['clk','rst','vinp','vinn','outp','outn','ready']
    source=pwl('clk',clk)+digital_source('rst',0,resets)+pwl('vinp',vp)+pwl('vinn',[(0,.6)])
    return {'name':name,'kind':'latched_comparator','stop':stop,'signals':ports,'events':events,'resets':resets,'tr':50e-12,'tbase':.2e-9,'tau':.25e-9,'vscale':.05,'vfloor':.001,'atol':.02,'edge_atol':80e-12,'netlist':deck('latched_comparator',ports,source,stop)}

def build_comparator():
    cases=[comparator_case('polarity_hold_reset',[.04,-.03,.001,-.002,.02],reset_cycle=4,async_resets={0:(2e-9,3e-9),2:(.25e-9,.6e-9),3:(2e-9,3e-9)}),comparator_case('short_clock_cancels',[.0001,-.0001,.05,-.05],high=.45e-9)]
    public=comparator_case('public',[.02,-.01,.005])
    text='''# 锁存比较器：决策延迟与复位取消
ADC的动态比较器在采样沿锁存输入，经再生延迟产生互补决策。完成模型 `latched_comparator(clk,rst,vinp,vinn,outp,outn,ready)`，全部electrical，后三端输出0/1 V。
参数 `vth=0.5 V, voffset=2 mV, tbase=0.2 ns, tau=0.25 ns, vscale=50 mV, vfloor=1 mV, tr=50 ps`，保持可覆盖。时钟/复位逻辑0/1 V，输入共模0.6 V，差分输入在±60 mV；clk上升/下降及rst上升均按vth穿越。
clk上升时先清空输出，若rst低则锁存 `d=vinp-vinn-voffset`；非零d在 `tbase+tau*ln(1+vscale/(abs(d)+vfloor))` 秒后，正d令outp=1/outn=0，负d相反，ready=1。d=0不产生决策。此合成再生延迟合同描述过驱动增加时决策加快，不是晶体管测量数据。
在同一高相，输入变化不能改变已锁存的符号或完成时间。clk下降或rst上升立即清空三输出并取消尚未完成的决策；低相不得出现旧ready。输出通过tr的有限平滑转换，无额外延迟。
验收逻辑电平误差≤20 mV，50%边沿时间误差≤80 ps，检查所有边沿和完整低/高相稳定段。初态全低。公开和隐藏只改变上述范围内输入、相位长度及复位，算法结构不限。'''
    negatives={
      'wrong_polarity':COMPARATOR.replace('sign_latched=(d>0)?1:((d<0)?-1:0);','sign_latched=(d>0)?-1:((d<0)?1:0);'),
      'no_overdrive_delay':COMPARATOR.replace('tbase+tau*ln(1+vscale/(abs(d)+vfloor))','tbase'),
      'stale_decision':COMPARATOR.replace('if(active && V(clk)>vth && V(rst)<vth)','if(1)').replace('active=0;decision_at=1e30;end\n @(timer','active=0;end\n @(timer'),
      'no_async_reset':COMPARATOR.replace(' or cross(V(rst)-vth,+1)',''),
    }
    return write_task('spec-latched-comparator',text,'架构需求参考旧v4 017锁存比较器；本题新增明确再生延迟、ready与短时钟取消合同。私有实验包括决策前复位再释放以检查取消，以及正负决策后高相复位以检查异步清空；no_async_reset人工移除复位事件。参考代码原创，未复制旧源码。',COMPARATOR,negatives,cases,public,'specification','latched-comparator-original')


def digital_source(name,initial,transitions,slew=40e-12):
    points=[(0,initial)];old=initial
    for t,value in transitions:points.extend([(t-slew/2,old),(t+slew/2,value)]);old=value
    return pwl(name,points)

BBPD='''module cdr_phase_detector(data,clk,retimed,up,down);
input data,clk,retimed;output up,down;electrical data,clk,retimed,up,down;
parameter real vth=0.5,tr=50p;
real u,d;
analog begin
 @(initial_step) begin u=0;d=0;end
 @(cross(V(clk)-vth,0)) begin u=0;d=0;end
 @(cross(V(data)-vth,0)) begin
  u=0;d=0;
  if(V(clk)>vth && V(retimed)<vth) u=1;
  else if(V(clk)<vth && V(retimed)>vth) d=1;
 end
 V(up)<+transition(u,0,tr,tr);V(down)<+transition(d,0,tr,tr);
end
endmodule
'''
def bbpd_case(name,shift=0):
    clk=[(2e-9+i*2e-9,float(i%2==0)) for i in range(16)]
    data=[(3e-9+shift,1),(5e-9+shift,0),(7e-9+shift,1),(9e-9+shift,0),(11e-9+shift,1),(15e-9+shift,0),(19e-9+shift,1),(23e-9+shift,0),(27e-9+shift,1)]
    retimed=[(6e-9,1),(10e-9,0),(14e-9,1),(22e-9,0),(26e-9,1)]
    # retimed transitions deliberately distinct from data and clock.
    retimed=[(t+.4e-9,v) for t,v in retimed]
    stop=36e-9;ports=['data','clk','retimed','up','down']
    sources=digital_source('clk',0,clk)+digital_source('data',0,data)+digital_source('retimed',0,retimed)
    return {'name':name,'kind':'bbpd','stop':stop,'signals':ports,'clock':clk,'data':data,'retimed':retimed,'tr':50e-12,'atol':.02,'edge_atol':80e-12,'netlist':deck('cdr_phase_detector',ports,sources,stop)}

def build_bbpd():
    text='''# CDR判相脉冲模型
在数据恢复环中，判相器用数据边沿、时钟电平及已重定时数据形成advance/retard请求。实现 `cdr_phase_detector(data,clk,retimed,up,down)`，前三端输入，后两端0/1 V输出，全部electrical。参数 `vth=0.5 V,tr=50 ps`。
每个data上升或下降穿越vth时，clk高且retimed低则up=1/down=0；clk低且retimed高则down=1/up=0；其余组合全低。已发布脉冲保持到下一个clk任意方向穿越；禁止UP/DOWN同时高。retimed在没有data边沿时变化不得独自发脉冲。初态全低。输出有限tr平滑，无额外延迟。
输入边沿之间至少200 ps，电平0/1 V；单个脉冲不小于200 ps。不考查同刻边沿仲裁或完整CDR锁定。评分检查方向、完整脉冲数量/50%边沿时刻与脉宽，电平20 mV、时间80 ps容差。用不同data相位的公开/隐藏条件检查早晚数据与无修正关系，不能按时间重放模板。'''
    negatives={'swap_up_down':BBPD.replace('if(V(clk)>vth && V(retimed)<vth) u=1;','if(V(clk)>vth && V(retimed)<vth) d=1;').replace('else if(V(clk)<vth && V(retimed)>vth) d=1;','else if(V(clk)<vth && V(retimed)>vth) u=1;'),
    'ignore_falling_data':BBPD.replace('cross(V(data)-vth,0)','cross(V(data)-vth,+1)'),
    'never_clear_on_clock':BBPD.replace('@(cross(V(clk)-vth,0)) begin u=0;d=0;end','@(cross(V(clk)-vth,0)) begin end')}
    return write_task('spec-cdr-phase-detector',text,'需求参考旧v4 001的CDR判相关系。本题以方向和脉冲终止指标验收；不宣称完整CDR或晶体管判相器。',BBPD,negatives,[bbpd_case('early_late'),bbpd_case('shifted_data',.35e-9)],bbpd_case('public',-.25e-9),'specification','cdr-phase-original')

SIGMA='''module sigma_delta(vin,clk,bitout);
input vin,clk;output bitout;electrical vin,clk,bitout;
parameter real vth=0.5,vref=1,tr=50p;
real residue;integer decision;
analog begin
 @(initial_step) begin residue=0;decision=0;end
 @(cross(V(clk)-vth,+1)) begin residue=residue+V(vin)/vref-decision;decision=(residue>=0)?1:0;end
 V(bitout)<+transition(decision,0,tr,tr);
end
endmodule
'''
def sigma_case(name,levels):
    n=len(levels)*24;period=2e-9;stop=(n+1)*period;clk=[];vin=[(0,levels[0])]
    for i in range(n):
        rise=(i+1)*period;clk += [(rise,1),(rise+.8e-9,0)]
        if i and i%24==0:
            t=rise-.5e-9;vin += [(t-20e-12,levels[i//24-1]),(t+20e-12,levels[i//24])]
    ports=['vin','clk','bitout'];sources=pwl('vin',vin)+digital_source('clk',0,clk)
    return {'name':name,'kind':'sigma_delta','stop':stop,'signals':ports,'levels':levels,'block_cycles':24,'period':period,'tr':50e-12,'atol':.02,'edge_atol':80e-12,'netlist':deck('sigma_delta',ports,sources,stop,maxstep=30e-12)}

def build_sigma(task_id='spec-sigma-delta',repair=False):
    text='''# 一阶ΣΔ量化反馈与动态输入
一位ΣΔ反馈环的累积电荷决定量化比特，错误采样相位或反馈符号会导致转换码流时序或密度异常。实现 `sigma_delta(vin,clk,bitout)`，全部electrical，bitout为0/1 V。参数vref=1 V、vth=0.5 V、tr=50 ps。
初始归一化累积量0、反馈比特0。每个clk上升穿越时，新累积量=旧累积量+vin/vref-旧反馈比特，新比特在新累积量≥0时为1、否则0。只在上升沿决定；下降沿不得改变比特。输出通过tr平滑。vin/vref在0至1，clk为0/1 V，vin可在离边沿至少200 ps时改变。
以每个转换的比特、边沿时刻和完整块脉冲密度验收，逻辑电平20 mV、边沿80 ps；不声称晶体管噪声、带内SNR或高阶ΣΔ。公开条件含恒定输入及动态输入段；隐藏只改变段值与顺序。候选可采用等价状态实现，不能按已知仿真时刻重放。'''
    if repair:text='''# 修复ΣΔ的采样相位故障
公开starter在某些切换输入下的比特时间位置不符合同。诊断并修复，不改接口或公开时钟。故障来自人工注入的采样边沿错误，是数字控制相位迁移中可能发生的失误，不声称真实现场故障。
'''+text
    negatives={'wrong_clock_phase':SIGMA.replace('cross(V(clk)-vth,+1)','cross(V(clk)-vth,-1)'),
      'positive_feedback':SIGMA.replace('V(vin)/vref-decision','V(vin)/vref+decision'),
      'discard_accumulator':SIGMA.replace('residue=residue+V(vin)/vref-decision','residue=V(vin)/vref-decision')}
    result=write_task(task_id,text,'原创行为ΣΔ合同参考旧v4 055/1055的一阶反馈架构，不复制源码。修复版属于人工注错；规格与修复共用source_group，结果必须关联分析。',SIGMA,negatives,[sigma_case('ascending',[.125,.375,.75,.25]),sigma_case('descending',[.875,.5,.125,.625])],sigma_case('public',[.25,.625]),'repair' if repair else 'specification','sigma-delta-original')
    if repair:(ROOT/'benchmark/tasks'/task_id/'environment/public/starter.va').write_text(HEADER+negatives['wrong_clock_phase'])
    return result

SAMPLE_HOLD='''module sample_hold(vin,sample,rst,vout);
input vin,sample,rst;output vout;electrical vin,sample,rst,vout;
parameter real tau=2n,vinit=0.45,vth=0.5;
integer acquiring,resetting;real state;
analog begin
 @(initial_step) begin acquiring=(V(sample)>vth);resetting=(V(rst)>vth);end
 @(cross(V(sample)-vth,+1)) acquiring=1;
 @(cross(V(sample)-vth,-1)) acquiring=0;
 @(cross(V(rst)-vth,+1)) resetting=1;
 @(cross(V(rst)-vth,-1)) resetting=0;
 state=idt(acquiring*(V(vin)-V(vout))/tau,vinit,resetting);
 V(vout)<+state;
end
endmodule
'''
def hold_case(name,level1,level2,tau=2e-9):
    stop=32e-9;sample=[(2e-9,1),(10e-9,0),(18e-9,1),(26e-9,0)];rst=[(14e-9,1),(16e-9,0)]
    # Input changes only during hold, so analytic acquisition is exponential.
    vin=[(0,level1),(12e-9,level1),(12.04e-9,level2)]
    ports=['vin','sample','rst','vout'];sources=pwl('vin',vin)+digital_source('sample',0,sample)+digital_source('rst',0,rst)
    return {'name':name,'kind':'sample_hold','stop':stop,'signals':ports,'tau':tau,'vinit':.45,'windows':[[2e-9,10e-9,level1],[18e-9,26e-9,level2]],'resets':[[14e-9,16e-9]],'atol':.003,'netlist':deck('sample_hold',ports,sources,stop,f'tau={tau:.14g}',maxstep=20e-12)}

def build_hold():
    text='''# ADC采样保持的有限采集建立
ADC前端在采集窗口内追踪输入，在转换阶段保持最终采样值。实现 `sample_hold(vin,sample,rst,vout)`，全部electrical；参数tau=2 ns,vinit=0.45 V,vth=0.5 V，可覆盖。sample/rst为0/1 V，vin为0.05–0.85 V。
初态vout=vinit。rst高时输出固定vinit并取消过去采集历史；rst释放后从vinit继续。rst低且sample高时满足一阶建立 `dy/dt=(vin-y)/tau`；sample低时保持y不变。sample/rst以vth穿越切换模式。本电压域理想输出不包含输入电流、输出阻抗和负载耦合；不声称晶体管采集电路。
恒定输入的采集残差为 `(y_start-vin)*exp(-duration/tau)`；验收采集全轨迹、采集结束残差、保持期间不跟随输入和复位恢复，输出最大误差3 mV。输出不添加transition延迟，不允许离散更新近似破坏误差界。输入变化离采集模式转换至少200 ps；tau公开范围1–4 ns。'''
    negatives={'instant_acquisition':SAMPLE_HOLD.replace('V(vout)<+state;','V(vout)<+(acquiring?V(vin):state);'),
    'no_hold':SAMPLE_HOLD.replace('acquiring*(V(vin)-V(vout))','(V(vin)-V(vout))'),
    'wrong_bandwidth':SAMPLE_HOLD.replace('/tau,vinit','/(2*tau),vinit')}
    return write_task('spec-sample-hold-acquisition',text,'原创一阶S/H行为合同；旧v4 071提供有限采集的工程需求参考，本题改为连续一阶动态与可解析建立误差，非复制其离散参考代码。',SAMPLE_HOLD,negatives,[hold_case('high_low',.82,.1),hold_case('low_high',.08,.78,tau=3e-9)],hold_case('public',.7,.2),'specification','sample-hold-original')


UVLO='''module uvlo_monitor(vin,rst,pgood,fault);
input vin,rst;output pgood,fault;electrical vin,rst,pgood,fault;
parameter real upper=0.65,lower=0.55,tgood=2n,tbad=1n,vth=0.5,tr=50p;
real good,up_at,down_at;
analog begin
 @(initial_step) begin good=0;up_at=1e30;down_at=1e30;if(V(rst)<vth && V(vin)>upper)up_at=$abstime+tgood;end
 @(cross(V(vin)-upper,+1)) if(V(rst)<vth && good<0.5)up_at=$abstime+tgood;
 @(cross(V(vin)-upper,-1)) up_at=1e30;
 @(cross(V(vin)-lower,-1)) if(V(rst)<vth && good>0.5)down_at=$abstime+tbad;
 @(cross(V(vin)-lower,+1)) down_at=1e30;
 @(cross(V(rst)-vth,+1)) begin good=0;up_at=1e30;down_at=1e30;end
 @(cross(V(rst)-vth,-1)) if(V(vin)>upper)up_at=$abstime+tgood;
 @(timer(up_at)) if(V(rst)<vth && V(vin)>upper)begin good=1;up_at=1e30;end
 @(timer(down_at)) if(V(rst)<vth && V(vin)<lower)begin good=0;down_at=1e30;end
 V(pgood)<+transition(good,0,tr,tr);V(fault)<+transition(1-good,0,tr,tr);
end
endmodule
'''
def uvlo_case(name,tgood=2e-9,tbad=1e-9,stretch=1):
    levels=[(2,.72),(3,.5),(7,.8),(12,.61),(16,.5),(19,.62),(24,.76),(29,.45),(34,.8)]
    pts=[(0,.5)];old=.5
    for t,value in levels:
        pts.extend([(t*1e-9*stretch-20e-12,old),(t*1e-9*stretch+20e-12,value)]);old=value
    resets=[(40e-9*stretch,1),(44e-9*stretch,0)];stop=52e-9*stretch
    ports=['vin','rst','pgood','fault'];source=pwl('vin',pts)+digital_source('rst',0,resets)
    return {'name':name,'kind':'uvlo','stop':stop,'signals':ports,'supply':pts,'resets':resets,'upper':.65,'lower':.55,'tgood':tgood,'tbad':tbad,'tr':50e-12,'atol':.02,'edge_atol':100e-12,'netlist':deck('uvlo_monitor',ports,source,stop,f'tgood={tgood:.14g} tbad={tbad:.14g}')}

def build_uvlo(task_id='spec-uvlo-deglitch',repair=False):
    text='''# 电源监控：UVLO毛刺拒绝与棕断恢复
电源启动时短暂越过阈值不能提前解除系统复位；棕断后恢复也必须重新资格确认。实现 `uvlo_monitor(vin,rst,pgood,fault)`，全部electrical，pgood/fault为互补0/1 V。参数upper=0.65 V,lower=0.55 V,tgood=2 ns,tbad=1 ns,vth=0.5 V,tr=50 ps，保持可覆盖。
初态pgood=0。rst高立即清零pgood、fault=1并取消全部计时。rst低时，vin连续严格高于upper达tgood，才置pgood=1；任何返回≤upper都取消尚未完成的启动计时，不能累积多个短脉冲。pgood=1后，vin连续严格低于lower达tbad才清零；任何回到≥lower都取消尚未完成的棕断计时。lower至upper之间保持当前pgood。rst释放时若vin已高于upper，重新从释放时刻计满tgood。fault=1-pgood；输出通过tr平滑，无额外延迟。
vin范围0.4–0.85 V、tgood1–4 ns,tbad0.5–2 ns，输入线性边沿≥40 ps，所有计时相对实际阈值交点；不测试计时截止与输入交点完全重合。验收完整pgood/fault边沿、短脉冲拒绝、滞回保持、复位重启，电平20 mV、时间100 ps容差。模型只表达电压监控行为，不含电源电流或稳压环。'''
    if repair:text='''# 修复UVLO的资格计时和复位恢复
starter包含人工注入的资格状态错误，短电源扰动可能发布旧的power-good。用公开波形诊断，保留接口并修复整个公开合同；不需要复刻starter算法。
'''+text
    negatives={'no_qualification':UVLO.replace('$abstime+tgood','$abstime+1p').replace('$abstime+tbad','$abstime+1p'),
      'accumulate_short_glitches':UVLO.replace('@(cross(V(vin)-upper,-1)) up_at=1e30;','@(cross(V(vin)-upper,-1)) begin end').replace('if(V(rst)<vth && V(vin)>upper)begin good=1;','if(V(rst)<vth)begin good=1;'),
      'skip_recovery_delay':UVLO.replace('@(cross(V(rst)-vth,-1)) if(V(vin)>upper)up_at=$abstime+tgood;','@(cross(V(rst)-vth,-1)) if(V(vin)>upper)good=1;')}
    result=write_task(task_id,text,'原创带连续资格时间的电压UVLO合同，工程需求参考旧v4 046/1046的电源阈值/滞回。新增抗毛刺和恢复时间合同，未复制旧源。修复故障为人工注入取消计时遗漏。',UVLO,negatives,[uvlo_case('glitches_and_recovery'),uvlo_case('long_qualification',3e-9,1.5e-9,1.3)],uvlo_case('public',1.5e-9,.7e-9),'repair' if repair else 'specification','uvlo-monitor-original')
    if repair:(ROOT/'benchmark/tasks'/task_id/'environment/public/starter.va').write_text(HEADER+negatives['accumulate_short_glitches'])
    return result


SAR='''module sar_controller(clk,start,rst,cmp,d3,d2,d1,d0,trial,busy,valid);
input clk,start,rst,cmp;output d3,d2,d1,d0,trial,busy,valid;
electrical clk,start,rst,cmp,d3,d2,d1,d0,trial,busy,valid;
parameter real vth=0.5,tr=50p,tvalid=0.8n;
integer active,pending,position,working,result,weight,j;
real dac,next_publish;
analog begin
 @(initial_step)begin active=0;pending=0;position=3;working=0;result=0;dac=0;next_publish=1e30;end
 @(cross(V(rst)-vth,+1))begin active=0;pending=0;working=0;result=0;dac=0;next_publish=1e30;end
 @(cross(V(start)-vth,+1))if(V(rst)<vth && active==0)begin active=1;pending=0;position=3;working=0;result=0;dac=0.5;next_publish=1e30;end
 @(cross(V(clk)-vth,+1))if(active && !pending && V(rst)<vth)begin
  weight=1;for(j=0;j<position;j=j+1)weight=weight*2;
  if(V(cmp)>vth)working=working+weight;
  if(position==0)begin pending=1;dac=working/16.0;next_publish=$abstime+tvalid;end
  else begin position=position-1;weight=weight/2;dac=(working+weight)/16.0;end
 end
 @(timer(next_publish))if(active && pending && V(rst)<vth)begin result=working;active=0;pending=0;next_publish=1e30;end
 V(d3)<+transition((result>=8)?1:0,0,tr,tr);
 V(d2)<+transition(((result/4)%2)?1:0,0,tr,tr);
 V(d1)<+transition(((result/2)%2)?1:0,0,tr,tr);
 V(d0)<+transition((result%2)?1:0,0,tr,tr);
 V(trial)<+transition(dac,0,tr,tr);
 V(busy)<+transition(active,0,tr,tr);V(valid)<+transition((active==0 && result>=0 && next_publish==1e30 && dac>0)?1:0,0,tr,tr);
end
endmodule
'''
# Explicit validity state distinguishes a legitimate zero-code from idle/reset.
SAR=SAR.replace('position,working,result,weight,j;','position,working,result,weight,j,done;').replace('active=0;pending=0;position=3;','done=0;active=0;pending=0;position=3;').replace('active=0;pending=0;working=0;result=0;dac=0;','done=0;active=0;pending=0;working=0;result=0;dac=0;').replace('active=1;pending=0;position=3;','done=0;active=1;pending=0;position=3;').replace('result=working;active=0;pending=0;','result=working;done=1;active=0;pending=0;').replace('(active==0 && result>=0 && next_publish==1e30 && dac>0)?1:0','done?1:0')
CMP_SUPPORT=HEADER+'''module adc_compare(vin,trial,cmp);
input vin,trial;output cmp;electrical vin,trial,cmp;
analog V(cmp)<+transition((V(vin)>=V(trial))?1:0,0,10p,10p);
endmodule
'''

def sar_case(name,vin_values,tvalid=.8e-9):
    stop=52e-9;clk=[]
    for i in range(13):clk += [(2e-9+i*4e-9,1),(3.5e-9+i*4e-9,0)]
    starts=[(1e-9,1),(1.5e-9,0),(17e-9,1),(17.5e-9,0),(33e-9,1),(33.5e-9,0)]
    resets=[(14.3e-9,1),(15.3e-9,0)]
    vin=[(0,vin_values[0]),(16e-9,vin_values[0]),(16.04e-9,vin_values[1]),(32e-9,vin_values[1]),(32.04e-9,vin_values[2])]
    ports=['clk','start','rst','cmp','d3','d2','d1','d0','trial','busy','valid']
    source=digital_source('clk',0,clk)+digital_source('start',0,starts)+digital_source('rst',0,resets)+pwl('vin',vin)+'ahdl_include "adc_compare.va"\nXCMP (vin trial cmp) adc_compare\n'
    return {'name':name,'kind':'sar','stop':stop,'signals':ports+['vin'],'clock':clk,'starts':starts,'resets':resets,'vin':vin,'tvalid':tvalid,'tr':50e-12,'atol':.02,'edge_atol':80e-12,'analog_nodes':['trial'],'support':{'adc_compare.va':CMP_SUPPORT},'netlist':deck('sar_controller',ports,source,stop,f'tvalid={tvalid:.14g}')+'save vin\n'}

def build_sar():
    text='''# SAR转换中止：取消待发布结果
一个四位SAR控制器按比较器反馈逐位试探电压，并在最后判决后延迟发布码。starter包含人工注入的复位取消遗漏，复位落在最后判决到发布之间时可出现旧结果。修复 `sar_controller(clk,start,rst,cmp,d3,d2,d1,d0,trial,busy,valid)`，前四端输入，其余输出，全部electrical。端口cmp高表示固定外围ADC比较器判断vin≥trial；原外围比较器与激励不可修改。
参数vth=0.5 V,tr=50 ps,tvalid=0.8 ns（允许0.4–1.2 ns）。trial范围0至15/16 V，其他输出0/1 V。初态全部低。rst上升清空结果码、trial、busy、valid，取消未完成的转换和待发布结果；rst高时忽略start/clk。
空闲且rst低的start上升清空码和valid，置busy，开始四次判决，首先trial=8/16 V。每个clk上升采样cmp，按MSB到LSB决定是否保留该位，再驱动下一试探码/16。第四判决后trial=最终码/16，仍保持busy；经过tvalid才发布四位码并置valid=1/busy=0。busy时新的start被忽略。空闲结果和valid保持至下次start或复位。
四位量化器使用floor(16*vin)并限幅0..15；输入0.02–0.98 V且距离码边界≥5 mV、在转换期间不变。clk周期4 ns，cmp建立≤100 ps，事件间距≥200 ps，reset可落在判决与发布之间。不得在低时钟或复位后发布旧码。电平容差20 mV，所有边沿80 ps；trial逐位值也独立检查。'''
    negatives={'late_result_after_abort':SAR.replace('done=0;active=0;pending=0;working=0;result=0;dac=0;next_publish=1e30;','done=0;working=0;result=0;dac=0;').replace('if(active && pending && V(rst)<vth)begin result=working','if(active && pending)begin result=working'),
      'inverted_comparator':SAR.replace('if(V(cmp)>vth)','if(V(cmp)<vth)'),
      'publish_without_latency':SAR.replace('$abstime+tvalid','$abstime+1p')}
    result=write_task('repair-sar-abort',text,'原创四位SAR试探/发布延迟合同；工程需求参考旧SAR握手资产与ADC复位扩展设计稿。人工注错为pending事件复位取消遗漏，未复制旧源码。',SAR,negatives,[sar_case('abort_then_two_codes',[.63,.21,.82]),sar_case('zero_code_and_latency',[.91,.03,.44],1.1e-9)],sar_case('public',[.56,.35,.72]),'repair','sar-controller-original')
    p=ROOT/'benchmark/tasks/repair-sar-abort/environment/public'
    (p/'starter.va').write_text(HEADER+negatives['late_result_after_abort']);(p/'adc_compare.va').write_text(CMP_SUPPORT)
    return result

ZOOM='''module zoom_timing(rst,sample,sar,residue,integrate,clk_sar,zoom,clk_zoom,rst_zoom);
output rst,sample,sar,residue,integrate,clk_sar,zoom,clk_zoom,rst_zoom;
electrical rst,sample,sar,residue,integrate,clk_sar,zoom,clk_zoom,rst_zoom;
parameter integer nbits=4;parameter real step=0.8n,frame=18n,tick=20p,tr=50p;
real phase,finish,r,s,a,c,i,cs,z,cz,rz;integer j;
analog begin
 @(initial_step)begin r=1;s=0;a=0;c=0;i=0;cs=0;z=0;cz=0;rz=0;end
 @(timer(0,tick))begin
  phase=$abstime-frame*floor($abstime/frame);finish=2.4n+nbits*step;
  r=(phase<0.6n)?1:0;s=(phase>=1n && phase<2n)?1:0;
  a=(phase>=2.4n && phase<finish)?1:0;
  c=(phase>=finish+0.2n && phase<finish+0.7n)?1:0;
  i=(phase>=finish+1n && phase<finish+2n)?1:0;
  z=(phase>=finish+2.5n && phase<finish+5.5n)?1:0;
  rz=(phase>=finish+2.1n && phase<finish+2.3n)?1:0;
  cs=0;cz=0;
  for(j=0;j<nbits;j=j+1)if(phase>=2.4n+j*step && phase<2.4n+j*step+0.3n)cs=1;
  for(j=0;j<3;j=j+1)if(phase>=finish+2.5n+j*step && phase<finish+2.5n+j*step+0.3n)cz=1;
 end
 V(rst)<+transition(r,0,tr,tr);V(sample)<+transition(s,0,tr,tr);
 V(sar)<+transition(a,0,tr,tr);V(residue)<+transition(c,0,tr,tr);
 V(integrate)<+transition(i,0,tr,tr);V(clk_sar)<+transition(cs,0,tr,tr);
 V(zoom)<+transition(z,0,tr,tr);V(clk_zoom)<+transition(cz,0,tr,tr);V(rst_zoom)<+transition(rz,0,tr,tr);
end
endmodule
'''
def zoom_case(name,nbits=4,step=.8e-9,frame=18e-9):
    ports=['rst','sample','sar','residue','integrate','clk_sar','zoom','clk_zoom','rst_zoom'];stop=2.5*frame
    return {'name':name,'kind':'zoom','stop':stop,'signals':ports,'nbits':nbits,'step':step,'frame':frame,'tick':20e-12,'tr':50e-12,'atol':.02,'edge_atol':100e-12,'netlist':deck('zoom_timing',ports,'',stop,f'nbits={nbits} step={step:.14g} frame={frame:.14g}')}

def build_zoom():
    text='''# 修复ZOOM ADC的SAR、积分与细转换时钟关系
ZOOM ADC先采样、粗SAR、残差移交、积分，再作细转换。人工故障starter的子时钟索引误用父周期，造成细转换漏脉冲；需要修复九路时序并保持整个相位合同。这一错误类型与历史首轮ZOOM参数接线故障相关，但本题源码及错误独立编写。
实现 `zoom_timing(rst,sample,sar,residue,integrate,clk_sar,zoom,clk_zoom,rst_zoom)`，九端都是electrical 0/1 V输出。参数nbits=4（允许4–5）、step=0.8 ns（0.7–0.9 ns）、frame=18 ns（18–20 ns）、tick=20 ps、tr=50 ps。相位t从每个frame开始，相位0初始；不加端口/侧信道。
每帧：rst在[0,0.6 ns)，sample在[1,2 ns)，sar在[2.4 ns,F)，F=2.4 ns+nbits*step。clk_sar有nbits个脉冲，第j个在[2.4 ns+j*step,2.7 ns+j*step)，j从0开始。
residue在[F+0.2,F+0.7 ns)，integrate在[F+1,F+2 ns)，rst_zoom在[F+2.1,F+2.3 ns)，zoom在[F+2.5,F+5.5 ns)。clk_zoom恰有3脉冲，第j个在[F+2.5 ns+j*step,F+2.8 ns+j*step)，j=0..2。其他时刻所有对应目标为0；输出有限tr平滑，允许tick量化延迟0–20 ps。状态机/事件日历写法不限。
这是电压域时序控制架构，不模拟ADC器件电流。验收完整脉冲数、采样/粗SAR/残差/积分/细转换先后与重复帧，不以单点电平替代时序。电平20 mV、50%边沿100 ps容差；错过一个脉冲即失败。公开/隐藏只改变上述合法nbits、step、frame。'''
    negatives={'zoom_parent_period':ZOOM.replace('finish+2.5n+j*step','finish+2.5n+j*frame').replace('finish+2.5n+j*step+0.3n','finish+2.5n+j*frame+0.3n'),
      'missing_sar_last_bit':ZOOM.replace('j<nbits','j<nbits-1'),
      'no_zoom_reset':ZOOM.replace('rz=(phase>=finish+2.1n && phase<finish+2.3n)?1:0;','rz=0;')}
    result=write_task('repair-zoom-sequencer',text,'需求参考课题组ZOOM/NSSAR多相时钟用途及va03真实错误类型。所有九相合同、参考实现、负例和checker原创；没有复制课题组原VA。设计为有限时序控制原型，不声称恢复原ADC外围工程。',ZOOM,negatives,[zoom_case('four_bit'),zoom_case('five_bit',5,.9e-9,20e-9)],zoom_case('public',4,.7e-9,19e-9),'repair','zoom-timing-original')
    (ROOT/'benchmark/tasks/repair-zoom-sequencer/environment/public/starter.va').write_text(HEADER+negatives['zoom_parent_period'])
    return result



def build_all():
    items=[build_comparator(),build_bbpd(),build_sigma(),build_hold(),build_uvlo(),build_sigma('repair-sigma-delta-phase',True),build_uvlo('repair-uvlo-recovery',True),build_sar(),build_zoom()]
    items.append({'id':'va07-triangle-repair','action':'repair','source_group':'repository-triangle-oscillator','path':'benchmark/tasks/va07-triangle-repair','status':'existing_prototype_reused_no_new_copy','notes':'Existing development/Spectre evidence belongs to va07 SOURCE; formal admission and Agentic still pending. Not counted twice.'})
    registry={'schema':'first-batch-model-repair-v1','counts':{'specification':5,'repair':5,'new_tasks':9,'reused_tasks':1},'tasks':items,'local_checker_tests':'python3 -B -m unittest discover -s experiments/benchmark_first_batch/model_repair -p test_contracts.py -v','evidence_boundary':'Line-level synthetic tests are checker tests, not Verilog-A execution. Actual calibration is recorded separately by coordinator.'}
    (ROOT/'benchmark/first_batch/model_repair.json').write_text(json.dumps(registry,indent=2)+'\n')
    return registry

if __name__=='__main__':build_all()
