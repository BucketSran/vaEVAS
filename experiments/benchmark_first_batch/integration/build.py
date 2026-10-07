#!/usr/bin/env python3
"""Author original integration tasks. Does not run a simulator or claim calibration."""
from pathlib import Path
import json, shutil
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'benchmark/tasks'
HERE=Path(__file__).resolve().parent
HEADER='`include "constants.vams"\n`include "disciplines.vams"\n'

def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)

def pwl(events, stop, initial=0, ramp=.01):
    pts=[(0,initial)];last=initial
    for t,v in events:
        pts.extend([(t-ramp/2,last),(t+ramp/2,v)]);last=v
    pts.append((stop,last))
    return ' '.join(f'{t:.12g}n {v:.12g}' for t,v in pts)

def pulses(times,width=.3):
    return sorted([(t,1) for t in times]+[(t+width,0) for t in times])

def netlist(module, ports, sources, stop, params=''):
    text='simulator lang=spectre\nahdl_include "dut.va"\n'
    for name,events in sources.items():text+=f'V_{name} ({name} 0) vsource type=pwl wave=[{pwl(events,stop)}]\n'
    text+=f'DUT ({" ".join(ports)}) {module} {params}\n'
    text+='simulatorOptions options reltol=1e-6 vabstol=1e-9\n'
    text+=f'tran tran stop={stop}n maxstep=0.02n\nsave '+ ' '.join(ports)+'\n'
    return text

def samples(windows):
    return [dict(node=node,start=a*1e-9,end=b*1e-9,value=value,atol=tol) for node,a,b,value,tol in windows]

def package(task, title, description, files, starter, cases, public_case, mutants, context='bounded_small_project', source=''):
    d=OUT/task
    for relative,text in files.items():write(d/'solution'/relative,text)
    for relative,text in starter.items():write(d/'environment/public'/relative,text)
    write(d/'instruction.md',title+'\n\n'+description+'\n\n公开工程在 `/work/public/`，请在 `/work/` 建立提交工程，入口为 `/work/dut.va`。可修改的提交文件清单见公开 `SUBMISSION.json`。同目录运行 `python3 public/smoke.py --candidate /work/dut.va` 可检查公开波形。终评输入均在上述合同范围内，不能访问隐藏测试或用时间表输出答案。\n')
    write(d/'environment/public/SUBMISSION.json',json.dumps({'candidate_files':list(files)},indent=2)+'\n')
    write(d/'tests/contract.json',json.dumps({'candidate_files':list(files),'output_files':[]},indent=2)+'\n')
    write(d/'tests/cases.json',json.dumps(cases,indent=2)+'\n')
    write(d/'environment/public/smoke_cases.json',json.dumps([public_case],indent=2)+'\n')
    wrapper='#!/usr/bin/env python3\nfrom pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).resolve().parent))\nfrom circuit_task import main\nfrom first_batch_integration import evaluate\nif __name__ == "__main__":\n    main(evaluate)\n'
    write(d/'tests/verify.py',wrapper)
    write(d/'tests/test.sh','#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nexec python3 verify.py "$@" --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}"\n')
    solve='#!/bin/sh\nset -eu\nsource_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)\n'
    for relative in files:
        parent=str(Path(relative).parent)
        solve+=f'mkdir -p "/work/{parent}"\ncp "$source_dir/{relative}" "/work/{relative}"\n'
    write(d/'solution/solve.sh',solve)
    write(d/'environment/Dockerfile','FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c\nWORKDIR /work\nCOPY public/ /work/public/\nRUN mkdir -p /work/output\n')
    write(d/'task.toml',f'schema_version = "1.4"\n[metadata]\nname = "{task}"\ncategory = "verilog-a"\nsource_group = "original-{source}"\ncontext = "{context}"\nengineering_action = "extension-integration"\n[agent]\ntimeout_sec = 1800\n[verifier]\ntimeout_sec = 900\n[environment]\nbuild_timeout_sec = 600\ncpus = 1\nmemory_mb = 1024\nstorage_mb = 2048\n')
    write(d/'SOURCE.md',f'# 来源和校准边界\n\n本题是仓库作者根据 {title.strip("# ")} 的工程需求原创的小工程。`source_group=original-{source}`。旧 v4 电路家族只用于选题方向，没有复制其代码、参数、注释或文件结构，不继承旧资产许可或成绩。\n\n上下文层次为 `{context}`。本工程没有伪造工业版本史；题面明确说明是原创教学和研究工程。起点保留现有模块，只故意遗漏或错接新功能。独立验收依据为 instruction 中公开公式、事件配对和时间窗，参考解不定义真值。\n\n终评有 {len(cases)} 组独立实验。语义负例见 experiments/benchmark_first_batch/integration/mutants/{task}/。每个负例仍是可编译的 VA，针对不同条款；实际 Spectre 编译及拒绝情况待校准。行级合成测试只验证 checker 自身，不证明 VA 参考解通过。\n\n发布身份为 Spectre 扩展集候选。Spectre 校准、Harbor oracle、Agentic 主评及开源重评都需分别取得真实证据；当前不宣称已完成这些阶段。\n')
    for name,changes in mutants.items():
        md=HERE/'mutants'/task/name
        for relative,text in files.items():write(md/relative,changes.get(relative,text))
    return d


def tdc():
    task='integrate-tdc-measurement-chain'
    top='''`include "rtl/capture.va"
`include "rtl/quantizer.va"
`include "rtl/formatter.va"
module tdc_chain(start,stop,reset,result,valid,busy,overflow);
input start,stop,reset; output result,valid,busy,overflow;
electrical start,stop,reset,result,valid,busy,overflow;
electrical width,done,pending,expired,code,range_error;
parameter real lsb_ns=0.5;
parameter real timeout_ns=12;
tdc_capture #(.timeout_ns(timeout_ns)) ucap(start,stop,reset,width,done,pending,expired);
tdc_quantizer #(.lsb_ns(lsb_ns)) uq(width,code,range_error);
tdc_formatter uf(code,done,pending,expired,range_error,result,valid,busy,overflow);
endmodule
'''
    capture=HEADER+'''module tdc_capture(start,stop,reset,width,done,pending,expired);
input start,stop,reset; output width,done,pending,expired;
electrical start,stop,reset,width,done,pending,expired;
parameter real timeout_ns=12;
real tstart,measured,deadline;
integer active,complete,timed_out;
analog begin
  @(initial_step) begin tstart=0; measured=0; deadline=1e30; active=0; complete=0; timed_out=0; end
  @(cross(V(reset)-0.5,+1)) begin measured=0; active=0; complete=0; timed_out=0; end
  @(cross(V(start)-0.5,+1)) begin
    if (V(reset)<0.5 && active==0) begin
      tstart=$abstime; deadline=$abstime+timeout_ns*1n;
      active=1; complete=0; timed_out=0;
    end
  end
  @(cross(V(stop)-0.5,+1)) begin
    if (V(reset)<0.5 && active==1 && $abstime<deadline) begin
      measured=($abstime-tstart)/1n; active=0; complete=1;
    end
  end
  @(timer(0,0.05n)) begin
    if(active==1 && $abstime>=deadline) begin active=0; complete=0; timed_out=1; end
  end
  V(width)<+transition(measured,0,0.02n);
  V(done)<+transition(complete,0,0.02n);
  V(pending)<+transition(active,0,0.02n);
  V(expired)<+transition(timed_out,0,0.02n);
end
endmodule
'''
    quant=HEADER+'''module tdc_quantizer(width,code,range_error);
input width; output code,range_error; electrical width,code,range_error;
parameter real lsb_ns=0.5;
real bins;
analog begin
  bins=floor(V(width)/lsb_ns+0.5);
  V(code)<+min(31,max(0,bins));
  V(range_error)<+(bins>31 ? 1.0 : 0.0);
end
endmodule
'''
    fmt=HEADER+'''module tdc_formatter(code,done,pending,expired,range_error,result,valid,busy,overflow);
input code,done,pending,expired,range_error; output result,valid,busy,overflow;
electrical code,done,pending,expired,range_error,result,valid,busy,overflow;
analog begin
  V(result)<+0.02*V(code);
  V(valid)<+V(done);
  V(busy)<+V(pending);
  V(overflow)<+max(V(expired),V(done)*V(range_error));
end
endmodule
'''
    files={'dut.va':top,'rtl/capture.va':capture,'rtl/quantizer.va':quant,'rtl/formatter.va':fmt}
    starter=dict(files)
    starter['dut.va']=top.replace('tdc_formatter uf(code,done,pending,expired,range_error,result,valid,busy,overflow);','// TODO integrate status and calibrated result formatting.\nanalog begin V(result)<+V(width); V(valid)<+V(done); V(busy)<+0; V(overflow)<+0; end')
    desc='''这个原创小仓库把时间间隔测量接入外部触发系统。已有 capture、quantizer 和 formatter 的模块接口，顶层仍使用原始宽度输出。请找到接线与状态路径，完成可配置量化、饱和、忙状态、超时和复位的端到端集成。工程供研究评测使用，没有工业版本史。

提交 `dut.va` 与 `rtl/capture.va`、`rtl/quantizer.va`、`rtl/formatter.va`。顶层 `tdc_chain(start,stop,reset,result,valid,busy,overflow)`。所有信号相对地，输入以 0.5 V 上升交越为事件；输入脉冲宽至少 0.2 ns，交越间隔至少 0.1 ns，未同时发生 reset/start/stop。reset 高电平禁止开始与停止，reset 上升清除结果和全部状态。

空闲 start 开始测量，busy=1、valid=0、overflow=0，result 保留上次结果。busy 期间重复 start 必须忽略。首次 stop 结束测量，busy=0、valid=1，result 为 `0.02*min(31,floor((tstop-tstart)/(lsb_ns*1 ns)+0.5))` V。输入时间单位为秒；`lsb_ns` 在 0.25 至 0.75 内。量化原码大于31时饱和到0.62 V并置overflow。无效 stop 不改变状态。超时 `timeout_ns` 在10至16内，start 后达到deadline且尚未stop，busy=0、valid=0、overflow=1，result 保留；超时报告不得晚于deadline+0.08 ns。超时之后可以重新start。未完成转换的结果不覆盖旧结果。

所有状态在事件后0.12 ns内建立，结果电压误差不超过0.002 V，逻辑稳态误差不超过0.01 V。边沿不得漏报或多报；波形检查也覆盖事件间保持、无效stop、超时和复位。使用平滑电压贡献，不依赖电流/负载模型。'''
    def case(name,starts,stops,resets,stop,lsb=.5,timeout=12):
        # Independent event ledger from the public protocol, not reference VA.
        events=sorted([(t,'start') for t in starts]+[(t,'stop') for t in stops]+[(t,'reset') for t in resets])
        state={'result':0.,'valid':0.,'busy':0.,'overflow':0.};active=None;history=[(0,dict(state))]
        for t,kind in events:
            if active is not None and active+timeout<t:
                state.update(busy=0.,valid=0.,overflow=1.);history.append((active+timeout,dict(state)));active=None
            if kind=='reset':state={k:0. for k in state};active=None
            elif kind=='start' and active is None:active=t;state.update(busy=1.,valid=0.,overflow=0.)
            elif kind=='stop' and active is not None:
                bins=int((t-active)/lsb+.5);state.update(result=.02*min(31,bins),valid=1.,busy=0.,overflow=float(bins>31));active=None
            history.append((t,dict(state)))
        if active is not None and active+timeout<stop:state.update(busy=0.,valid=0.,overflow=1.);history.append((active+timeout,dict(state)))
        history=sorted(history,key=lambda x:x[0]);windows=[]
        for i,(t,s) in enumerate(history):
            end=history[i+1][0] if i+1<len(history) else stop
            if end-t>.3:
                for node,value in s.items():windows.append((node,t+.15,end-.04,value,.002 if node=='result' else .01))
        edges={node:[] for node in ['valid','busy','overflow']};previous=history[0][1]
        for t,s in history[1:]:
            for node in edges:
                if s[node]!=previous[node]:edges[node].append((t+.01)*1e-9)
            previous=s
        return dict(name=name,stop=stop*1e-9,signals=['start','stop','reset','result','valid','busy','overflow'],netlist=netlist('tdc_chain',['start','stop','reset','result','valid','busy','overflow'],{'start':pulses(starts),'stop':pulses(stops),'reset':pulses(resets)},stop,f'lsb_ns={lsb} timeout_ns={timeout}'),windows=samples(windows),edges=[dict(node=n,threshold=.5,times=v,atol=.09e-9,start=.1e-9) for n,v in edges.items()])
    cases=[case('pairing-timeout-reset',[4,12,13,22,40,57],[6.26,9,17.2,37,49.1,57.14],[1,53],62),case('fine-range-and-held-result',[3,11,23,35,49],[5.13,17.9,28.36,44.2,54.81],[1,47],59,.25,12),case('long-timeout-recovery',[4,5,23,43],[7.12,41,47.83],[1,29],53,.75,16)]
    public=case('public-basic',[3,12],[5.26,14.2],[1],18)
    mutants={'restart-while-busy':{'rtl/capture.va':capture.replace('V(reset)<0.5 && active==0','V(reset)<0.5')},'floor-quantization':{'rtl/quantizer.va':quant.replace('V(width)/lsb_ns+0.5','V(width)/lsb_ns')},'timeout-never-clears-busy':{'rtl/capture.va':capture.replace('active==1 && $abstime>=deadline','active==1 && $abstime>=deadline+100n')},'range-error-disconnected':{'rtl/formatter.va':fmt.replace('max(V(expired),V(done)*V(range_error))','V(expired)')}}
    d=package(task,'# 集成 TDC 测量链',desc,files,starter,cases,public,mutants,'complete_original_repository','tdc-chain')
    write(d/'environment/public/README.md','# tdc lab\n\n这是原创完整小型电路模型仓库，包含RTL模型、模拟入口、公开回归和接口说明。由原始宽度输出迁移到量化测量链。`dut.va` 是入口；`rtl/` 保存依赖。先阅读 docs/protocol.md，再运行 `make smoke CANDIDATE=/work/dut.va`。\n')
    write(d/'environment/public/docs/protocol.md',desc)
    write(d/'environment/public/Makefile','CANDIDATE ?= /work/dut.va\n.PHONY: smoke\nsmoke:\n\tpython3 smoke.py --candidate $(CANDIDATE)\n')
    write(d/'environment/public/regression/README.md','公开 smoke_cases.json 验证两次测量及结果保持。终评还覆盖协议中已列出的超时、重触发、饱和和复位恢复。\n')
    return task



def pipeline():
    task='integrate-pipeline-adc-alignment'
    stage1=HEADER+'''module coarse_stage(vin,clk,reset,coarse,residue);
input vin,clk,reset; output coarse,residue;
electrical vin,clk,reset,coarse,residue;
real c,r,x;
analog begin
  @(initial_step) begin c=0; r=0; end
  @(cross(V(reset)-0.5,+1)) begin c=0; r=0; end
  @(cross(V(clk)-0.5,+1)) if(V(reset)<0.5) begin
    x=min(0.999999999,max(0,V(vin))); c=floor(8*x); r=8*x-c;
  end
  V(coarse)<+transition(c,0,0.03n);
  V(residue)<+transition(r,0,0.03n);
end
endmodule
'''
    stage2=HEADER+'''module fine_stage(residue,clk,reset,fine);
input residue,clk,reset; output fine; electrical residue,clk,reset,fine;
real f;
analog begin
  @(initial_step) f=0;
  @(cross(V(reset)-0.5,+1)) f=0;
  @(cross(V(clk)-0.5,-1)) if(V(reset)<0.5) f=floor(min(7.999999999,max(0,8*V(residue))));
  V(fine)<+transition(f,0,0.03n);
end
endmodule
'''
    top='''`include "rtl/coarse.va"
`include "rtl/fine.va"
module pipeline_adc(vin,clk,reset,result,valid);
input vin,clk,reset; output result,valid; electrical vin,clk,reset,result,valid;
electrical coarse,residue,fine;
real held; integer filled,ready;
coarse_stage uc(vin,clk,reset,coarse,residue);
fine_stage uf(residue,clk,reset,fine);
analog begin
  @(initial_step) begin held=0; filled=0; ready=0; end
  @(cross(V(reset)-0.5,+1)) begin held=0; filled=0; ready=0; end
  @(cross(V(clk)-0.5,+1)) if(V(reset)<0.5) begin
    if(filled==1) begin held=0.01*(8*V(coarse)+V(fine)); ready=1; end
    filled=1;
  end
  V(result)<+transition(held,0,0.03n);
  V(valid)<+transition(ready,0,0.03n);
end
endmodule
'''
    files={'dut.va':top,'rtl/coarse.va':stage1,'rtl/fine.va':stage2}
    starter=dict(files)
    starter['dut.va']=top.replace('if(filled==1) begin held=0.01*(8*V(coarse)+V(fine)); ready=1; end','held=0.01*(8*V(coarse)+V(fine)); ready=1;').replace('V(result)<+transition(held,0,0.03n);','V(result)<+0.01*(8*V(coarse)+V(fine));')
    desc='''工程用两相时钟把6位ADC分成3位粗转换和3位残差转换。粗级在上升沿采样，细级在随后的下降沿处理同一次采样的残差。原始顶层直接组合粗码和细码，会在连续采样时混合两次转换。请扩展顶层寄存器与valid路径，保持两级接口和量化规则。

提交 `dut.va`、`rtl/coarse.va`、`rtl/fine.va`，顶层 `pipeline_adc(vin,clk,reset,result,valid)`。输入vin为0至1 V，clk和reset以0.5 V交越；时钟周期3至6 ns，占空比50%，模拟输入在上升沿前后0.2 ns保持稳定。上升沿采样N=`min(63,max(0,floor(64*vin)))`，结果电压为0.01*N V。第一次有效上升沿只填充流水线，valid=0，result=0。以后每个上升沿输出上一次上升沿采样的N，valid=1，结果保持到下一输出事件。时钟停止时结果及valid保持。

reset上升立即清除输出与valid，reset高电平的时钟不填充流水线；reset解除后的第一次上升沿仍只填充，第二次才输出新样本。复位不能让旧细码泄漏。结果误差0.002 V，valid误差0.01 V，事件后0.15 ns建立。不要用公开输入轨迹硬编码答案。内部coarse/residue/fine可重写实现，但不得改变合同的采样相位、输入范围和延迟。'''
    def case(name,values,period=4,resets=None):
        rises=[3+i*period for i in range(len(values)+1)];falls=[r+period/2 for r in rises];end=falls[-1]+1
        reset_events=resets or [(1,1),(1.4,0)]
        clock=sorted([(r,1) for r in rises]+[(f,0) for f in falls]);inputs=[(r-.6,values[min(i,len(values)-1)]) for i,r in enumerate(rises)]
        transitions=sorted([(t,'reset',v) for t,v in reset_events]+[(r,'rise',i) for i,r in enumerate(rises)])
        held=0.;ready=0.;last=None;high=False;history=[(0,held,ready)]
        for t,kind,v in transitions:
            if kind=='reset':
                high=bool(v)
                if high:held=0.;ready=0.;last=None;history.append((t,held,ready))
            elif not high:
                if last is not None:held=.01*last;ready=1.
                last=min(63,max(0,int(64*values[min(v,len(values)-1)])))
                history.append((t,held,ready))
        windows=[]
        for i,(t,h,v) in enumerate(history):
            until=history[i+1][0] if i+1<len(history) else end
            if until-t>.3:windows.extend([('result',t+.18,until-.04,h,.002),('valid',t+.18,until-.04,v,.01)])
        v_edges=[];old=0
        for t,h,v in history:
            if v!=old:v_edges.append((t+.015)*1e-9);old=v
        return dict(name=name,stop=end*1e-9,signals=['vin','clk','reset','result','valid'],netlist=netlist('pipeline_adc',['vin','clk','reset','result','valid'],{'vin':inputs,'clk':clock,'reset':reset_events},end),windows=samples(windows),edges=[dict(node='valid',threshold=.5,times=v_edges,atol=.08e-9,start=.1e-9)])
    cases=[case('alternating-coarse-fine',[.021,.963,.277,.731,.141,.588,.402,.819]),case('reset-refill',[.901,.177,.676,.317,.049,.982,.528,.242],4,[(1,1),(1.4,0),(10,1),(12.2,0),(22,1),(24.2,0)]),case('nondefault-clock-and-clamps',[0,1,.503,.094,.845,.358,.719,.188],3.4)]
    public=case('public-four-samples',[.135,.786,.422,.951])
    mutants={'combinational-mixed-sample':{'dut.va':top.replace('V(result)<+transition(held,0,0.03n);','V(result)<+0.01*(8*V(coarse)+V(fine));')},'early-valid':{'dut.va':top.replace('filled=1;','filled=1; ready=1;')},'stale-refill-after-reset':{'dut.va':top.replace('@(cross(V(reset)-0.5,+1)) begin held=0; filled=0; ready=0; end','@(cross(V(reset)-0.5,+1)) begin held=0; ready=0; end')},'wrong-fine-phase':{'rtl/fine.va':stage2.replace('cross(V(clk)-0.5,-1)','cross(V(clk)-0.5,+1)')}}
    package(task,'# 对齐 pipeline ADC 的级间数据',desc,files,starter,cases,public,mutants,source='pipeline-adc')
    return task


def iq():
    task='integrate-iq-baseband-calibration'
    coeff=HEADER+'''module iq_coeff(a,b,c,d,oi,oq,apply,reset,la,lb,lc,ld,li,lq);
input a,b,c,d,oi,oq,apply,reset; output la,lb,lc,ld,li,lq;
electrical a,b,c,d,oi,oq,apply,reset,la,lb,lc,ld,li,lq;
real aa,bb,cc,dd,ii,qq;
analog begin
  @(initial_step) begin aa=1; bb=0; cc=0; dd=1; ii=0; qq=0; end
  @(cross(V(reset)-0.5,+1)) begin aa=1; bb=0; cc=0; dd=1; ii=0; qq=0; end
  @(cross(V(apply)-0.5,+1)) if(V(reset)<0.5) begin
    aa=V(a); bb=V(b); cc=V(c); dd=V(d); ii=V(oi); qq=V(oq);
  end
  V(la)<+transition(aa,0,0.03n); V(lb)<+transition(bb,0,0.03n);
  V(lc)<+transition(cc,0,0.03n); V(ld)<+transition(dd,0,0.03n);
  V(li)<+transition(ii,0,0.03n); V(lq)<+transition(qq,0,0.03n);
end
endmodule
'''
    inverse=HEADER+'''module iq_inverse(ri,rq,a,b,c,d,oi,oq,ci,cq);
input ri,rq,a,b,c,d,oi,oq; output ci,cq;
electrical ri,rq,a,b,c,d,oi,oq,ci,cq;
real determinant;
analog begin
  determinant=V(a)*V(d)-V(b)*V(c);
  V(ci)<+(V(d)*(V(ri)-V(oi))-V(b)*(V(rq)-V(oq)))/determinant;
  V(cq)<+(-V(c)*(V(ri)-V(oi))+V(a)*(V(rq)-V(oq)))/determinant;
end
endmodule
'''
    sample=HEADER+'''module iq_sample(ri,rq,ci,cq,clk,bypass,reset,out_i,out_q,clipped);
input ri,rq,ci,cq,clk,bypass,reset; output out_i,out_q,clipped;
electrical ri,rq,ci,cq,clk,bypass,reset,out_i,out_q,clipped;
real hi,hq,xi,xq; integer clip;
analog begin
  @(initial_step) begin hi=0; hq=0; clip=0; end
  @(cross(V(reset)-0.5,+1)) begin hi=0; hq=0; clip=0; end
  @(cross(V(clk)-0.5,+1)) if(V(reset)<0.5) begin
    xi=(V(bypass)>0.5 ? V(ri) : V(ci)); xq=(V(bypass)>0.5 ? V(rq) : V(cq));
    hi=min(1,max(-1,xi)); hq=min(1,max(-1,xq)); clip=(abs(xi)>1 || abs(xq)>1);
  end
  V(out_i)<+transition(hi,0,0.03n); V(out_q)<+transition(hq,0,0.03n);
  V(clipped)<+transition(clip,0,0.03n);
end
endmodule
'''
    top='''`include "rtl/coeff.va"
`include "rtl/inverse.va"
`include "rtl/sample.va"
module iq_calibration(ri,rq,a,b,c,d,oi,oq,apply,clk,bypass,reset,out_i,out_q,clipped);
input ri,rq,a,b,c,d,oi,oq,apply,clk,bypass,reset; output out_i,out_q,clipped;
electrical ri,rq,a,b,c,d,oi,oq,apply,clk,bypass,reset,out_i,out_q,clipped;
electrical la,lb,lc,ld,li,lq,ci,cq;
iq_coeff uc(a,b,c,d,oi,oq,apply,reset,la,lb,lc,ld,li,lq);
iq_inverse ui(ri,rq,la,lb,lc,ld,li,lq,ci,cq);
iq_sample us(ri,rq,ci,cq,clk,bypass,reset,out_i,out_q,clipped);
endmodule
'''
    files={'dut.va':top,'rtl/coeff.va':coeff,'rtl/inverse.va':inverse,'rtl/sample.va':sample};starter=dict(files)
    starter['dut.va']=top.replace('iq_inverse ui(ri,rq,la,lb,lc,ld,li,lq,ci,cq);','// TODO insert calibrated matrix inverse in the receive path.\nanalog begin V(ci)<+V(ri); V(cq)<+V(rq); end')
    desc='''接收机基带的I/Q两路存在增益、正交相位串扰和DC偏移。已有系数寄存器与采样限幅模块，原始顶层尚未把校准算子接入。请实现并集成2x2逆校准，保持bypass和输出采样行为。

提交 `dut.va` 与 `rtl/coeff.va`、`rtl/inverse.va`、`rtl/sample.va`。顶层 `iq_calibration(ri,rq,a,b,c,d,oi,oq,apply,clk,bypass,reset,out_i,out_q,clipped)`。输入ri/rq单位V，校准描述前向失配 `ri=a*I+b*Q+oi`、`rq=c*I+d*Q+oq`。a,d为0.6至1.4，b,c为-0.4至0.4，oi/oq为-0.2至0.2 V，所有提交系数组合满足det=`a*d-b*c >=0.2`。apply以0.5 V上升交越锁存6个系数，未apply的端口变化不得改变校准。reset上升使系数恢复单位矩阵、偏移为0，清零输出和clipped；reset高时禁止apply和clk采样。

每个clk上升沿采样校准后的两路，公式 `I=(d*(ri-oi)-b*(rq-oq))/det`、`Q=(-c*(ri-oi)+a*(rq-oq))/det`。bypass高则直接采样ri/rq。无论何种路径，分别限幅到[-1,+1] V，任一路限幅前绝对值大于1时clipped=1，否则0。输出和clipped在两次采样之间保持，bypass或ri/rq变化不能提前改变已采样结果。clk周期4至6 ns，apply距clk至少0.4 ns，数据距clk至少0.2 ns。输出事件后0.15 ns内建立，电压误差0.003 V，标志误差0.01 V。工程只要求电压域，不要求模拟输出阻抗。'''
    def case(name,points,matrix,offset=(.08,-.05),period=5,reset_mid=False):
        n=len(points);rises=[7+i*period for i in range(n)];end=rises[-1]+2
        ports=['ri','rq','a','b','c','d','oi','oq','apply','clk','bypass','reset','out_i','out_q','clipped']
        init=dict(zip(['a','b','c','d','oi','oq'],[*matrix,*offset]));sources={k:[(2,v)] for k,v in init.items()}
        sources.update(ri=[],rq=[],apply=pulses([5]),clk=pulses(rises,width=period/2),bypass=[],reset=pulses([1]))
        # Disturb the coefficient ports without apply. The calibrated registers hold.
        for k,v in dict(a=.88,b=-.19,c=.17,d=1.23,oi=-.12,oq=.13).items():sources[k].append((10,v))
        reset_t=18 if reset_mid else None
        if reset_t:sources['reset']+=pulses([reset_t])
        windows=[];last={'out_i':0,'out_q':0,'clipped':0};history=[(0,dict(last))]
        for i,(wanted_i,wanted_q,bypass) in enumerate(points):
            t=rises[i];a,b,c,d=matrix;ri=a*wanted_i+b*wanted_q+offset[0];rq=c*wanted_i+d*wanted_q+offset[1]
            sources['ri'].append((t-.7,ri));sources['rq'].append((t-.7,rq));sources['bypass'].append((t-.7,float(bypass)))
            if reset_t and t>reset_t and (i==0 or rises[i-1]<reset_t):history.append((reset_t,dict(out_i=0.,out_q=0.,clipped=0.)))
            xi,xq=(ri,rq) if bypass or (reset_t and t>reset_t) else (wanted_i,wanted_q)
            last={'out_i':min(1,max(-1,xi)),'out_q':min(1,max(-1,xq)),'clipped':float(abs(xi)>1 or abs(xq)>1)}
            history.append((t,dict(last)))
        for i,(t,state) in enumerate(history):
            until=history[i+1][0] if i+1<len(history) else end
            if until-t>.3:
                for node,v in state.items():windows.append((node,t+.18,until-.05,v,.003 if node!='clipped' else .01))
        return dict(name=name,stop=end*1e-9,signals=ports,netlist=netlist('iq_calibration',ports,sources,end),windows=samples(windows))
    points=[(.45,-.38,False),(-.62,.31,False),(.21,.71,False),(1.23,-.16,False),(.11,-1.18,False),(-.39,.44,True),(.72,-.68,False)]
    cases=[case('cross-coupling-and-latched-coefficients',points,(1.2,.23,-.16,.82)),case('reset-and-bypass',points,(.77,-.31,.24,1.31),(-.09,.14),reset_mid=True),case('opposite-mismatch',[(-.31,-.67,False),(.79,.12,False),(.15,-.52,True),(-1.19,1.13,False),(.39,.66,False)],(.69,.32,-.27,1.38),(.12,-.17),4.5)]
    public=case('public-quadrants',[(.4,-.3,False),(-.2,.5,False),(.7,.1,True)],(1.1,.2,-.1,.9))
    diag=inverse.replace('(V(d)*(V(ri)-V(oi))-V(b)*(V(rq)-V(oq)))/determinant','(V(ri)-V(oi))/V(a)').replace('(-V(c)*(V(ri)-V(oi))+V(a)*(V(rq)-V(oq)))/determinant','(V(rq)-V(oq))/V(d)')
    mutants={'diagonal-only-correction':{'rtl/inverse.va':diag},'live-unlatched-coefficients':{'dut.va':top.replace('ui(ri,rq,la,lb,lc,ld,li,lq,ci,cq)','ui(ri,rq,a,b,c,d,oi,oq,ci,cq)')},'bypass-ignored':{'rtl/sample.va':sample.replace('V(bypass)>0.5','V(bypass)>1.5')},'clip-flag-only-i':{'rtl/sample.va':sample.replace('abs(xi)>1 || abs(xq)>1','abs(xi)>1')}}
    package(task,'# 集成 I/Q 基带幅相校准',desc,files,starter,cases,public,mutants,source='iq-baseband')
    return task


def pll():
    task='integrate-pll-hop-reacquisition'
    track=HEADER+'''module pll_tracker(command,hop,reset,frequency,phase,target);
input command,hop,reset; output frequency,phase,target;
electrical command,hop,reset,frequency,phase,target;
parameter real tau_ns=5;
real origin,base_frequency,target_frequency,base_phase,dt,f,p;
analog begin
  @(initial_step) begin origin=0; base_frequency=1; target_frequency=1; base_phase=0; end
  dt=($abstime-origin)/1n;
  f=target_frequency+(base_frequency-target_frequency)*exp(-dt/tau_ns);
  p=base_phase+target_frequency*dt+(base_frequency-target_frequency)*tau_ns*(1-exp(-dt/tau_ns));
  @(cross(V(hop)-0.5,+1)) if(V(reset)<0.5) begin
    base_frequency=f; base_phase=p; origin=$abstime; target_frequency=V(command);
  end
  @(cross(V(reset)-0.5,+1)) begin origin=$abstime; base_frequency=1; target_frequency=1; base_phase=0; end
  @(cross(V(reset)-0.5,-1)) begin origin=$abstime; base_frequency=1; target_frequency=1; base_phase=0; end
  V(frequency)<+(V(reset)>0.5 ? 1 : f);
  V(phase)<+(V(reset)>0.5 ? 0 : p);
  V(target)<+target_frequency;
end
endmodule
'''
    osc=HEADER+'''module pll_oscillator(phase,reset,wave);
input phase,reset; output wave; electrical phase,reset,wave;
analog begin
  V(wave)<+(V(reset)>0.5 ? 0 : 0.5+0.5*sin(6.283185307179586*V(phase)));
  $bound_step(0.015n);
end
endmodule
'''
    lock=HEADER+'''module pll_lock(frequency,target,hop,reset,locked);
input frequency,target,hop,reset; output locked; electrical frequency,target,hop,reset,locked;
parameter real lock_tolerance=0.01;
parameter real dwell_ns=0.5;
real since; integer ready;
analog begin
  @(initial_step) begin since=-1; ready=0; end
  @(cross(V(hop)-0.5,+1) or cross(V(reset)-0.5,+1)) begin since=-1; ready=0; end
  @(timer(0,0.025n)) begin
    if(V(reset)>0.5 || abs(V(frequency)-V(target))>lock_tolerance) begin since=-1; ready=0; end
    else begin
      if(since<0) since=$abstime;
      if($abstime-since>=dwell_ns*1n) ready=1;
    end
  end
  V(locked)<+transition(ready,0,0.03n);
end
endmodule
'''
    top='''`include "rtl/tracker.va"
`include "rtl/oscillator.va"
`include "rtl/lock.va"
module hopping_pll(command,hop,reset,frequency,wave,locked);
input command,hop,reset; output frequency,wave,locked;
electrical command,hop,reset,frequency,wave,locked;
electrical phase,target;
parameter real tau_ns=5;
parameter real lock_tolerance=0.01;
parameter real dwell_ns=0.5;
pll_tracker #(.tau_ns(tau_ns)) ut(command,hop,reset,frequency,phase,target);
pll_oscillator uo(phase,reset,wave);
pll_lock #(.lock_tolerance(lock_tolerance),.dwell_ns(dwell_ns)) ul(frequency,target,hop,reset,locked);
endmodule
'''
    files={'dut.va':top,'rtl/tracker.va':track,'rtl/oscillator.va':osc,'rtl/lock.va':lock};starter=dict(files)
    starter['dut.va']=top.replace('pll_lock #(.lock_tolerance(lock_tolerance),.dwell_ns(dwell_ns)) ul(frequency,target,hop,reset,locked);','// TODO integrate qualified lock and restart behavior.\nanalog V(locked)<+(abs(V(frequency)-1)<lock_tolerance ? 1 : 0);')
    desc='''系统需要在工作中切换PLL频率。已有连续时间频率跟踪器和相位振荡器，旧lock输出只相对初始频率判断。请接入面向最新命令的锁定判据，并保证连续相位、连续频率和跳频后重新捕获。

提交 `dut.va` 和 `rtl/tracker.va`、`rtl/oscillator.va`、`rtl/lock.va`。顶层 `hopping_pll(command,hop,reset,frequency,wave,locked)`。command电压表示GHz，在0.6至1.4之间；hop上升交越0.5 V锁存命令，未hop的command变化不得改变目标。初态frequency=1 GHz、相位0、locked=0。频率合同为 `df/dt=(target-f)/(tau_ns*1 ns)`，`tau_ns`为3至7。跳频时频率与相位连续，不允许重启振荡器。相位以cycle为单位，`dphase/dt=frequency*1e9`，wave=`0.5+0.5*sin(2*pi*phase)` V。frequency输出的电压数字等于GHz值。

每次hop立即撤销locked。只有最新目标的频率误差连续不大于lock_tolerance GHz达到dwell_ns才置1。lock_tolerance在0.008至0.02，dwell_ns在0.4至0.8。重捕获过程中再次hop必须以当时实际频率为初值，重新计时，不能沿用旧deadline。locked边沿允许0.12 ns实现延迟，不得提前超过0.02 ns。

reset高时frequency=1、wave=0、locked=0，禁止hop；解除reset以相位0、频率1重新开始，并重新累计dwell。其他控制事件相距至少0.2 ns，command距hop至少0.3 ns。frequency误差0.001 GHz，wave误差0.01 V，标志误差0.01 V。此题是规定闭环动态的电压域集成任务，不要求晶体管VCO或电流建模。'''
    def case(name,hops,tau=5,tol=.01,dwell=.5,resets=None):
        reset_events=resets or []
        end=max([t for t,v in hops]+[t for t,v in reset_events]+[0])+35
        sources={'command':[(t-.5,v) for t,v in hops]+[(9,1.17)],'hop':pulses([t for t,v in hops]),'reset':reset_events}
        sources['command'].sort()
        # Independent analytic integration of each commanded first-order segment.
        events=sorted([(t,'hop',v) for t,v in hops]+[(t,'reset',v) for t,v in reset_events])
        segments=[];origin=0.;base=1.;target=1.;phase=0.;high=False;lock_start=dwell
        def state(t):
            dt=t-origin;f=target+(base-target)*__import__('math').exp(-dt/tau)
            p=phase+target*dt+(base-target)*tau*(1-__import__('math').exp(-dt/tau))
            return f,p
        segments.append(dict(t=0,origin=origin,base=base,target=target,phase=phase,high=False,lock_start=lock_start))
        for t,kind,value in events:
            f,p=state(t)
            if kind=='reset':
                high=bool(value);origin=t;base=1.;target=1.;phase=0.;lock_start=float('inf') if high else t+dwell
            elif not high:
                origin=t;base=f;phase=p;target=value
                error=abs(base-target);settle=0 if error<=tol else tau*__import__('math').log(error/tol)
                lock_start=t+settle+dwell
            segments.append(dict(t=t,origin=origin,base=base,target=target,phase=phase,high=high,lock_start=lock_start))
        observations=[];windows=[];edges=[];previous_ready=False
        for i,s in enumerate(segments):
            until=segments[i+1]['t'] if i+1<len(segments) else end
            ready_before=(i>0 and segments[i-1]['lock_start']<s['t'] and not segments[i-1]['high'])
            if ready_before:edges.append((s['t']+.015)*1e-9)
            if s['lock_start']<until:edges.append((s['lock_start']+.04)*1e-9)
            cut=max(s['t']+.18,s['lock_start']+.16)
            if not s['high'] and cut<until-.04:windows.append(('locked',cut,until-.04,1.,.01))
            low_end=min(until-.04,s['lock_start']-.03)
            if s['t']+.18<low_end:windows.append(('locked',s['t']+.18,low_end,0.,.01))
            t=s['t']+.22
            while t<until-.08:
                dt=t-s['origin'];f=s['target']+(s['base']-s['target'])*__import__('math').exp(-dt/tau)
                p=s['phase']+s['target']*dt+(s['base']-s['target'])*tau*(1-__import__('math').exp(-dt/tau))
                observations.extend([dict(node='frequency',t=t*1e-9,value=1. if s['high'] else f,atol=.001),dict(node='wave',t=t*1e-9,value=0. if s['high'] else .5+.5*__import__('math').sin(2*__import__('math').pi*p),atol=.01)])
                t+=.137
        return dict(name=name,stop=end*1e-9,signals=['command','hop','reset','frequency','wave','locked'],netlist=netlist('hopping_pll',['command','hop','reset','frequency','wave','locked'],sources,end,f'tau_ns={tau} lock_tolerance={tol} dwell_ns={dwell}'),windows=samples(windows),pll_protocol=dict(hops=hops,resets=reset_events,tau_ns=tau),edges=[dict(node='locked',threshold=.5,times=edges,atol=.12e-9,start=.1e-9)])
    cases=[case('up-down-and-interrupted-capture',[(5,1.31),(17,.72),(23,1.13),(49,.88)]),case('changed-time-constant',[(4,.67),(12,1.38),(39,.94)],3.4,.012,.65),case('reset-and-tiny-hop',[(4,1.27),(29,1.005),(34,.83),(56,1.19)],6.2,.008,.45,[(22,1),(24,0)])]
    public=case('public-hop',[(5,1.2)],5,.01,.5)
    mutants={'phase-restarted-on-hop':{'rtl/tracker.va':track.replace('base_phase=p; origin=$abstime; target_frequency=V(command)','base_phase=0; origin=$abstime; target_frequency=V(command)')},'frequency-restarted-on-hop':{'rtl/tracker.va':track.replace('base_frequency=f; base_phase=p','base_frequency=1; base_phase=p')},'no-lock-dwell':{'rtl/lock.va':lock.replace('$abstime-since>=dwell_ns*1n','$abstime-since>=0')},'stale-command-reference':{'dut.va':top.replace('ul(frequency,target,hop,reset,locked)','ul(frequency,command,hop,reset,locked)')}}
    package(task,'# 集成 PLL 跳频重捕获',desc,files,starter,cases,public,mutants,source='hopping-pll')
    return task


def agc():
    task='integrate-agc-attack-release'
    detector=HEADER+'''module agc_detector(signal_in,clk,reset,envelope);
input signal_in,clk,reset; output envelope; electrical signal_in,clk,reset,envelope;
parameter real alpha=0.4;
real level;
analog begin
  @(initial_step) level=0;
  @(cross(V(reset)-0.5,+1)) level=0;
  @(cross(V(clk)-0.5,+1)) if(V(reset)<0.5) level=(1-alpha)*level+alpha*abs(V(signal_in));
  V(envelope)<+transition(level,0,0.03n);
end
endmodule
'''
    gain=HEADER+'''module agc_gain(envelope,clk,reset,gain);
input envelope,clk,reset; output gain; electrical envelope,clk,reset,gain;
parameter real attack_ns=2;
parameter real release_ns=12;
parameter real sample_ns=3;
parameter real target_v=0.4;
real current,desired,tau,elapsed,last_time;
integer seen;
analog begin
  @(initial_step) begin current=1; last_time=0; seen=0; end
  @(cross(V(reset)-0.5,+1)) begin current=1; last_time=$abstime; seen=0; end
  @(cross(V(clk)-0.5,+1)) if(V(reset)<0.5) begin
    desired=min(8,max(0.25,target_v/max(0.05,V(envelope))));
    tau=(desired<current ? attack_ns : release_ns);
    elapsed=(seen==0 ? sample_ns : ($abstime-last_time)/1n);
    current=desired+(current-desired)*exp(-elapsed/tau);
    last_time=$abstime; seen=1;
  end
  V(gain)<+transition(current,0,0.03n);
end
endmodule
'''
    amplifier=HEADER+'''module agc_amplifier(signal_in,gain,reset,signal_out,clipped);
input signal_in,gain,reset; output signal_out,clipped;
electrical signal_in,gain,reset,signal_out,clipped;
real product;
analog begin
  product=V(signal_in)*V(gain);
  V(signal_out)<+(V(reset)>0.5 ? 0 : min(0.9,max(-0.9,product)));
  V(clipped)<+(V(reset)>0.5 ? 0 : (abs(product)>0.9 ? 1 : 0));
end
endmodule
'''
    top='''`include "rtl/detector.va"
`include "rtl/gain.va"
`include "rtl/amplifier.va"
module receiver_agc(signal_in,clk,reset,signal_out,gain,clipped);
input signal_in,clk,reset; output signal_out,gain,clipped;
electrical signal_in,clk,reset,signal_out,gain,clipped;
electrical envelope;
parameter real attack_ns=2;
parameter real release_ns=12;
parameter real sample_ns=3;
parameter real target_v=0.4;
parameter real alpha=0.4;
agc_detector #(.alpha(alpha)) ud(signal_in,clk,reset,envelope);
agc_gain #(.attack_ns(attack_ns),.release_ns(release_ns),.sample_ns(sample_ns),.target_v(target_v)) ug(envelope,clk,reset,gain);
agc_amplifier ua(signal_in,gain,reset,signal_out,clipped);
endmodule
'''
    files={'dut.va':top,'rtl/detector.va':detector,'rtl/gain.va':gain,'rtl/amplifier.va':amplifier};starter=dict(files)
    starter['rtl/gain.va']=gain.replace('tau=(desired<current ? attack_ns : release_ns);','// Legacy controller has a single recovery time constant.\n    tau=release_ns;')
    desc='''接收机AGC需要在突发强信号到达时快速降低增益，在信号减弱时缓慢恢复增益，降低过载并避免噪声泵动。已有幅度检测、增益控制和限幅输出路径，旧控制器只使用一个恢复常数。请扩展并集成不同的attack/release行为，保持检测延迟、增益范围、复位及限幅标志。

提交 `dut.va` 和 `rtl/detector.va`、`rtl/gain.va`、`rtl/amplifier.va`。顶层 `receiver_agc(signal_in,clk,reset,signal_out,gain,clipped)`。输入幅度不超过1.5 V；clk在0.5 V上升交越采样，周期sample_ns在2至4 ns。每次采样更新包络 `e_new=(1-alpha)*e_old+alpha*abs(signal_in)`，alpha在0.25至0.6。增益控制使用上一个周期的e_old，因为检测与控制各是一个寄存级。目标增益 `g_target=min(8,max(0.25,target_v/max(0.05,e_old)))`，target_v为0.3至0.5 V。若g_target小于旧g，tau=attack_ns，否则tau=release_ns，`g_new=g_target+(g_old-g_target)*exp(-dt_ns/tau)`。attack_ns在1至3、release_ns在8至18；dt是有效clk间隔，复位后第一次采样使用sample_ns。初始化和reset上升使e=0、g=1，reset高禁止采样。

控制周期之间增益保持；输出信号持续为 `clip(g*signal_in,-0.9,0.9)` V，不能把信号输出错做采样保持。clipped表示未限幅乘积绝对值大于0.9。reset高时signal_out和clipped为0，gain保持1。所有参数需传递到正确模块。采样相关输出在事件后0.15 ns建立；gain与输出误差0.004 V，标志误差0.01 V。输入在clk前后0.2 ns稳定，reset距clk至少0.3 ns。此题只要求电压域动态，不要求可变增益放大器的电流和阻抗。'''
    def case(name,values,period=3,attack=2,release=12,alpha=.4,target=.4,resets=None):
        import math
        rises=[3+i*period for i in range(len(values))];end=rises[-1]+period
        reset_events=resets or [(1,1),(1.4,0)]
        sources={'signal_in':[(t-.5,v) for t,v in zip(rises,values)],'clk':pulses(rises,width=period/2),'reset':reset_events}
        windows=[];observations=[];env=0.;g=1.;seen=False;lasttime=None;high=False
        events=sorted([(t,'reset',v) for t,v in reset_events]+[(t,'sample',i) for i,t in enumerate(rises)])
        gainstates=[(0,1.)];sample_results=[]
        for t,kind,v in events:
            if kind=='reset':
                high=bool(v)
                if high:env=0.;g=1.;seen=False;gainstates.append((t,g))
            elif not high:
                desired=min(8,max(.25,target/max(.05,env)));tau=attack if desired<g else release;dt=period if not seen else t-lasttime
                g=desired+(g-desired)*math.exp(-dt/tau);env=(1-alpha)*env+alpha*abs(values[v]);seen=True;lasttime=t;gainstates.append((t,g));sample_results.append((t,v,g))
        for i,(t,gainvalue) in enumerate(gainstates):
            until=gainstates[i+1][0] if i+1<len(gainstates) else end
            if until-t>.3:windows.append(('gain',t+.18,until-.04,gainvalue,.004))
        for t,i,gainvalue in sample_results:
            interval_end=rises[i+1]-.52 if i+1<len(rises) else end-.05
            next_reset=min([rt for rt,rv in reset_events if rv and rt>t]+[float('inf')])
            interval_end=min(interval_end,next_reset-.03)
            product=gainvalue*values[i];value=min(.9,max(-.9,product));clipped=float(abs(product)>.9)
            if interval_end>t+.18:windows.extend([('signal_out',t+.18,interval_end,value,.004),('clipped',t+.18,interval_end,clipped,.01)])
            # The analog signal path must react to the next input before the next
            # gain update; this specifically rejects a sampled-output shortcut.
            if i+1<len(values) and rises[i+1]-.2<next_reset:
                product=gainvalue*values[i+1]
                observations.extend([dict(node='signal_out',t=(rises[i+1]-.2)*1e-9,value=min(.9,max(-.9,product)),atol=.004),dict(node='clipped',t=(rises[i+1]-.2)*1e-9,value=float(abs(product)>.9),atol=.01)])
        for rt,rv in reset_events:
            if rv:
                off=next((t for t,v in reset_events if not v and t>rt),end)
                windows.extend([('signal_out',rt+.04,off-.02,0.,.004),('clipped',rt+.04,off-.02,0.,.01)])
        return dict(name=name,stop=end*1e-9,signals=['signal_in','clk','reset','signal_out','gain','clipped'],netlist=netlist('receiver_agc',['signal_in','clk','reset','signal_out','gain','clipped'],sources,end,f'attack_ns={attack} release_ns={release} sample_ns={period} alpha={alpha} target_v={target}'),windows=samples(windows),samples=observations)
    values=[.06,-.08,.07,1.2,-1.3,1.1,-.95,.12,-.09,.05,-.07,.1,.65,-.8,.15,-.11]
    cases=[case('burst-attack-and-release',values),case('nondefault-control-parameters',values,2.5,1.3,17,.55,.32),case('reset-during-burst',values,3.5,2.7,9,.28,.47,[(1,1),(1.4,0),(18.1,1),(19.2,0),(39.1,1),(40.2,0)])]
    public=case('public-level-change',[.1,.1,1,-1,.12,-.1,.1])
    mutants={'single-release-constant':{'rtl/gain.va':gain.replace('tau=(desired<current ? attack_ns : release_ns);','tau=release_ns;')},'signed-envelope':{'rtl/detector.va':detector.replace('abs(V(signal_in))','V(signal_in)')},'reversed-attack-release':{'rtl/gain.va':gain.replace('desired<current ? attack_ns : release_ns','desired<current ? release_ns : attack_ns')},'sampled-output':{'dut.va':top.replace('ua(signal_in,gain,reset,signal_out,clipped)','ua(signal_in,gain,clk,reset,signal_out,clipped)'), 'rtl/amplifier.va':HEADER+'''module agc_amplifier(signal_in,gain,clk,reset,signal_out,clipped);
input signal_in,gain,clk,reset; output signal_out,clipped; electrical signal_in,gain,clk,reset,signal_out,clipped;
real product,held; integer flag;
analog begin
  @(initial_step) begin held=0; flag=0; end
  @(cross(V(clk)-0.5,+1)) begin product=V(signal_in)*V(gain); held=min(.9,max(-.9,product)); flag=(abs(product)>.9); end
  V(signal_out)<+(V(reset)>.5 ? 0 : held); V(clipped)<+(V(reset)>.5 ? 0 : flag);
end
endmodule
'''}}
    package(task,'# 扩展接收机 AGC 的 attack/release',desc,files,starter,cases,public,mutants,source='receiver-agc')
    return task


def all_tasks():
    tasks=[tdc(),pipeline(),iq(),pll(),agc()]
    for task in tasks:
        d=OUT/task
        shutil.copyfile(HERE/'public_smoke.py',d/'environment/public/smoke.py')
        shutil.copyfile(ROOT/'benchmark/checkers/first_batch_integration.py',d/'environment/public/waveform_check.py')
    write(ROOT/'benchmark/first_batch/integration.json',json.dumps({'category':'extension-integration','tasks':[{'id':task,'path':f'benchmark/tasks/{task}','source_group':{'integrate-tdc-measurement-chain':'original-tdc-chain','integrate-pipeline-adc-alignment':'original-pipeline-adc','integrate-iq-baseband-calibration':'original-iq-baseband','integrate-pll-hop-reacquisition':'original-hopping-pll','integrate-agc-attack-release':'original-receiver-agc'}[task],'construction':'reference-and-semantic-mutants-authored','spectre_calibration':'pending','agentic':'pending','release_set':'spectre-extension-candidate'} for task in tasks]},indent=2)+'\n')
    return tasks


if __name__ == "__main__":
    print("\n".join(all_tasks()))
