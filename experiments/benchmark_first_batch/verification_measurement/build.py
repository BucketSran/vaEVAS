from pathlib import Path
import json, textwrap
ROOT=Path(__file__).resolve().parents[3]
TASKS=ROOT/'benchmark/tasks'

def put(p,s):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(textwrap.dedent(s).lstrip())
def task(ident,category,title,ports,spec,solution,support,cases,mutants):
 d=TASKS/ident
 put(d/'instruction.md',f'''# {title}

{spec}

提交 `/work/dut.va`，module `dut({ports})`，所有端口均为 electrical。电压数值代表题面规定的单位。仅使用 Verilog-A 标准头文件；不读写文件，不执行外部命令。允许调整内部实现。公开自测见 `/work/public/`，终评分只改变公开列出的参数和故障模式，核验真实激励与原始观测，然后核验结果端口。测量最后一个窗口之后保持结果至仿真结束。
''')
 put(d/'task.toml',f'''schema_version = "1.4"
[metadata]
name = "{ident}"
category = "{category}"
source_group = "first-batch-{ident}"
purpose = "{title}; synthetic circuit experiment; calibration pending"
[agent]
timeout_sec = 1800
[verifier]
timeout_sec = 600
[environment]
build_timeout_sec = 600
cpus = 1
memory_mb = 1024
storage_mb = 2048
''')
 put(d/'environment/Dockerfile','''FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
WORKDIR /work
COPY public/ /work/public/
RUN mkdir -p /work/output
''')
 put(d/'environment/public/README.md','''公开器件为仓库原创的行为合成电路。public.scs 是一个正确器件的自测配置。需已配置的 licensed Spectre 后端；镜像本身不包含商业仿真器。

把提交 dut.va、device.va 和 public.scs 复制到新的工作目录，在该目录执行 `spectre -64 public.scs -format psfascii -raw psf`。查看 psf/tran.tran.tran 的原始观测，按 instruction.md 的公式和容差自检。该流程仅公开自测，不提供隐藏终评反馈。
''')
 put(d/'environment/public/device.va',support)
 put(d/'environment/public/public.scs',cases[0]['netlist'])
 put(d/'environment/public/starter.va',f'`include "constants.vams"\n`include "disciplines.vams"\nmodule dut({ports});\ninout {ports}; electrical {ports};\n// TODO: implement the required experiment and result ports.\nendmodule\n')
 put(d/'solution/dut.va',solution)
 put(d/'solution/solve.sh','#!/bin/sh\nset -eu\ncp /solution/dut.va /work/dut.va\n')
 family='verification' if category=='verification-tools' else 'measurement'
 put(d/'tests/verify.py',f'''from circuit_task import main
from first_batch_{family} import evaluate
if __name__ == "__main__":
    main(evaluate)
''')
 put(d/'tests/test.sh','''#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python3 verify.py "$@" --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}"
''')
 for c in cases:c['support']={'device.va':support};c['task']=ident
 put(d/'tests/cases.json',json.dumps(cases,indent=2)+'\n')
 put(d/'tests/contract.json',json.dumps({'candidate_files':['dut.va'],'output_files':[]},indent=2)+'\n')
 put(d/'SOURCE.md',f'''# 来源与验收边界

原创工程需求，`behavioral_synthetic`。同源组 `first-batch-{ident}`。器件是电压域合成模型，参数不是器件实测或厂商真值。任务动作是 {category}，实际信号路径和性能定义见 instruction.md。

参考解、未完成起点和语义错版由本目录保存。错误版本分别模拟遗漏检测、指标定义混淆、覆盖条件不足等常见工程错误，具体变更见 tests/mutants/ 的完整源码；每个错误提交保持合法可编译的语义实现。错版必须在实际 Spectre 执行后拒绝；行级测试仅证明独立公式，不能代替后端校准。本题当前为 Spectre 扩展集候选，尚未声明 Agentic 完成或开源重评资格。

公开与隐藏条件遵循同一 instruction.md；tests/cases.json 固定每次实验的器件参数。独立判据不运行参考解生成期望，基于实际输入、时钟和输出计算；原始观测还须满足已声明的合成器件公式。参考解只提供可行实现。校准需保存参考解、所有语义错版和有效正确电路的运行身份、后端版本及完整结果，未完成实际执行的条件保持 pending。
''')
 for name,code in mutants.items():put(d/f'tests/mutants/{name}.va',code)
 for p in [d/'solution/solve.sh',d/'tests/test.sh']:p.chmod(0o755)
 return {'id':ident,'category':category,'source_group':f'first-batch-{ident}','status':'implemented_pending_spectre','path':str(d.relative_to(ROOT))}

def net(inst,stop,step):
 return f'''simulator lang=spectre
ahdl_include "dut.va"
ahdl_include "device.va"
{inst}
simulatorOptions options reltol=1e-6 vabstol=1e-9
tran tran stop={stop} maxstep={step}
saveOptions options save=allpub
'''
HEADER='`include "constants.vams"\n`include "disciplines.vams"\n'
sar_device=HEADER+'''module sar_device(vin,start,rst,code,done);
inout vin,start,rst,code,done; electrical vin,start,rst,code,done;
parameter integer fault=0, latency=5;
integer busy,count,q,lasts,d,seq;
analog begin
 @(initial_step) begin busy=0;count=0;q=0;lasts=0;d=0;seq=0;end
 @(timer(0,10n)) begin
  d=0;
  if(V(rst)<0.5 && fault!=3) begin busy=0;count=0;q=0;end
  else begin
   if(busy!=0) begin count=count-1;if(count==0) begin busy=0;d=1;end end
   if(V(start)>0.5 && lasts==0 && (busy==0 || fault==2) && V(rst)>0.5) begin
    busy=1;count=latency;q=$rtoi(V(vin)*16);if(q<0)q=0;if(q>15)q=15;
    if(fault==1)q=(q+1)%16;
   end
  end
  if(V(start)>0.5)lasts=1;else lasts=0;
 end
 V(code)<+transition(q,0,0.1n); V(done)<+transition(d,0,0.1n);
end
endmodule
'''
sar_sol=HEADER+'''module dut(vin,start,rst,code,done,verdict);
inout vin,start,rst,code,done,verdict; electrical vin,start,rst,code,done,verdict;
integer k,slot,bad,busy,lasts,lastd,expected,s,d;
real x,r,deadline;
analog begin
 @(initial_step) begin bad=0;busy=0;lasts=0;lastd=0;deadline=0;expected=0;end
 k=$rtoi($abstime/200n);slot=$rtoi(($abstime-k*200n)/1n);
 x=(2*(k%6)+1.25)/16.0; r=1;s=0;
 if($abstime<21n)r=0;
 if(slot>=31 && slot<42)s=1;
 if(slot>=51 && slot<62)s=1;
 if(k==2 && slot>=65 && slot<76)r=0;
 V(vin)<+transition(x,0,0.1n);V(start)<+transition(s,0,0.1n);V(rst)<+transition(r,0,0.1n);
 @(timer(5n,5n)) begin
  if(V(rst)<0.5)busy=0;
  if(V(start)>0.5 && lasts==0 && busy==0 && V(rst)>0.5) begin
   busy=1;expected=$rtoi(V(vin)*16);deadline=$abstime+70n;
  end
  if(V(done)>0.5 && lastd==0) begin
   if(busy==0 || $abstime>deadline+1p || abs(V(code)-expected)>0.1)bad=1;
   busy=0;
  end
  if(busy!=0 && $abstime>deadline+1p)begin bad=1;busy=0;end
  if(V(start)>0.5)lasts=1;else lasts=0;
  if(V(done)>0.5)lastd=1;else lastd=0;
 end
 V(verdict)<+bad;
end
endmodule
'''
sar_cases=[]
for fault in [0,1,2,3]:
 for lat in ([4,5,6] if fault==0 else [5]):
  sar_cases.append({'name':f'fault{fault}-lat{lat}','netlist':net(f'Xbench (vin start rst code done verdict) dut\nXadc (vin start rst code done) sar_device fault={fault} latency={lat}','1.2u','1n'),'stop':1.2e-6,'signals':['vin','start','rst','code','done','verdict'],'fault':fault,'latency':lat})
entries=[task('verify-sar-flow','verification-tools','SAR 转换完整验证流程','vin,start,rst,code,done,verdict', '''SAR ADC 前端验证需要同时检查采样值、转换握手和复位中止。器件将 vin 的 0..1 V 转为 4-bit unsigned code 电压。start 上升沿在空闲时接收请求；器件每 10 ns 检查端口，接收后 4..6 个 tick 发出宽 10 ns 的 done，code=floor(16*vin) 限幅 0..15。忙时请求忽略。rst 低立即在下一 tick 中止并清零，不允许旧 done。

实现完整激励与自动判定。运行 1.2 us，每 200 ns 一次转换。第 k 个周期 vin=(2*(k mod 6)+1.25)/16 V，主 start 在周期内 31..42 ns，忙时 start 在 51..62 ns。初始 rst 在 0..21 ns 为低，第 k=2 周期在 65..76 ns 拉低中止。边沿过渡不超过 0.2 ns。其余 rst=1、start=0。独立终评检查刺激覆盖和每个实际请求/输出。verdict 初值 0，发现错误锁存 1；正确器件最终应为 0。需拒绝一码偏移、忙时重新接收、复位后旧结果三类器件。判定允许 code 0.1 V 误差，done 必须在请求后 35..75 ns；监测至结束。器件故障模式终评可注入，候选不能知道其参数。''',sar_sol,sar_device,sar_cases,{'always_accept':sar_sol.replace('V(verdict)<+bad;','V(verdict)<+0;'),'always_reject':sar_sol.replace('V(verdict)<+bad;','V(verdict)<+1;'),'no_abort':sar_sol.replace('if(k==2 && slot>=65 && slot<76)r=0;','if(k==20 && slot>=65 && slot<76)r=0;')})]
put(ROOT/'benchmark/first_batch/verification_measurement.json',json.dumps({'tasks':entries},indent=2)+'\n')
# Stimulus-only validation tasks exercise real downstream electrical observers.
clock_dev=HEADER+'''module phase_device(p1,p2,vin,z);
inout p1,p2,vin,z; electrical p1,p2,vin,z;
real held,out;
analog begin
 @(initial_step)begin held=0;out=0;end
 V(vin)<+0.5+0.3*sin(2*3.1415926535897932384626433832795*$abstime/700n);
 @(cross(V(p1)-0.5,+1))held=V(vin);
 @(cross(V(p2)-0.5,+1))out=held;
 V(z)<+transition(out,0,0.2n);
end
endmodule
'''
clock_sol=HEADER+'''module dut(p1,p2);
inout p1,p2;electrical p1,p2;
parameter real period=100n,dead=5n;
integer a,b;
analog begin
 @(initial_step)begin a=0;b=0;end
 @(timer(dead,period))a=1;
 @(timer(period/2,period))a=0;
 @(timer(period/2+dead,period))b=1;
 @(timer(period,period))b=0;
 V(p1)<+transition(a,0,0.1n);V(p2)<+transition(b,0,0.1n);
end
endmodule
'''
cc=[]
for p,d in [(100e-9,5e-9),(160e-9,9e-9),(120e-9,3e-9)]:
 cc.append({'name':f'p{p*1e9:g}-d{d*1e9:g}','netlist':net(f'Xtb (p1 p2) dut period={p:.12g} dead={d:.12g}\nXsw (p1 p2 vin z) phase_device',f'{p*12:.12g}','0.5n'),'stop':p*12,'signals':['p1','p2','vin','z'],'period':p,'dead':d})
entries.append(task('verify-nonoverlap-stimulus','verification-tools','开关电容两相非重叠时钟实验','p1,p2','''为采样与传递两级开关电容链产生两相时钟。提交模块参数 period=100 ns、dead=5 ns，隐藏条件 period=100/120/160 ns，dead=3/5/9 ns。每周期 phase1 高窗 [dead,period/2)，phase2 高窗 [period/2+dead,period)。高电平 1 V，低电平 0 V，稳定电平允许0.01 V误差，边沿过渡 0.1 ns，允许每个 0.5V 边沿相对窗口边界最多 0.3 ns 偏差。运行12周期，要求两相均完整活动，并且每次交换有规定死区。下游电压域采样级在 phase1 上升采集 vin，在 phase2 上升传递为 z；终评同时检查下游采样值误差不超过2mV，禁止把两相并接。此题只要求完成刺激环节。''',clock_sol,clock_dev,cc,{'overlap':clock_sol.replace('timer(period/2,period)','timer(period/2+2*dead,period)'),'wrong_dead':clock_sol.replace('timer(dead,period)','timer(dead/2,period)'),'missing_phase':clock_sol.replace('V(p2)<+transition(b','V(p2)<+transition(0'),'low_swing':clock_sol.replace('V(p1)<+transition(a','V(p1)<+0.49+0.02*transition(a').replace('V(p2)<+transition(b','V(p2)<+0.49+0.02*transition(b')}))
cmp_dev=HEADER+'''module comparator_device(vp,vn,clk,q);
inout vp,vn,clk,q;electrical vp,vn,clk,q;
real due,out;integer target,pending;
analog begin
 @(initial_step)begin pending=0;out=0;due=-1;target=0;end
 @(cross(V(clk)-0.5,+1))begin
  target=(V(vp)>V(vn));due=$abstime+1n+0.1n/abs(V(vp)-V(vn));pending=1;
 end
 @(timer(0.1n,0.1n))begin
  if(V(clk)<0.5)begin out=0;pending=0;end
  else if(pending!=0 && $abstime>=due)begin out=target;pending=0;end
 end
 V(q)<+transition(out,0,0.1n);
end
endmodule
'''
cmp_stim=HEADER+'''module dut(vp,vn,clk);
inout vp,vn,clk;electrical vp,vn,clk;
parameter real cm=0.5;
integer k,sgn,c;real d,t;
analog begin
 k=$rtoi($abstime/100n);t=$abstime-k*100n;
 if(k%3==0)d=0.01;else if(k%3==1)d=0.025;else d=0.05;
 if(k%2==0)sgn=1;else sgn=-1;
 c=(t>=20n && t<70n);
 V(vp)<+transition(cm+sgn*d/2,0,0.1n);V(vn)<+transition(cm-sgn*d/2,0,0.1n);
 V(clk)<+transition(c,0,0.1n);
end
endmodule
'''
cmp_cases=[]
for cm in [.3,.5,.7]:
 cmp_cases.append({'name':f'cm{cm:g}','netlist':net(f'Xtb (vp vn clk) dut cm={cm}\nXcmp (vp vn clk q) comparator_device','1.2u','0.2n'),'stop':1.2e-6,'signals':['vp','vn','clk','q'],'cm':cm})
entries.append(task('verify-comparator-overdrive','verification-tools','锁存比较器过驱动实验刺激','vp,vn,clk','''构建锁存比较器的 overdrive-delay 实验，覆盖极性、输入共模和完整复位。模块参数 cm=0.5 V，允许0.3/0.5/0.7 V。12个100 ns周期，第k周期 |vp-vn| 依次循环10/25/50 mV，偶数k为正、奇数为负。vp/vn关于cm对称，周期20..70 ns clk=1，其余clk=0。所有激励边沿0.1ns，电压容差1mV，时刻容差0.3ns。电压域器件决定延时为1ns+(0.1ns*V)/|vp-vn|，以clk上升时输入决定正负，负极性保持q=0，复位清零。终评核对原始差分、共模、时钟、正极性输出时刻和负极性静默，delay容差0.35ns。此题只要求刺激与可重复实验覆盖，不要求提交delay分析代码。''',cmp_stim,cmp_dev,cmp_cases,{'one_polarity':cmp_stim.replace('else sgn=-1','else sgn=1'),'commonmode_wrong':cmp_stim.replace('cm+sgn*d/2','0.5+sgn*d/2'),'no_reset':cmp_stim.replace('t<70n','t<99n')}))
pll_dev=HEADER+'''module pll_device(ref,clk);
inout ref,clk;electrical ref,clk;
parameter integer fault=0;
real p,phase,offset;integer k,r,c;
analog begin
 r=(($abstime-100n*$rtoi($abstime/100n))<50n);
 p=100n;if(fault==1 && $abstime>=1u)p=105n;
 k=$rtoi($abstime/p);offset=0;
 if(k<5)offset=(5-k)*4n;
 if(fault==3 && $abstime>=2u)offset=10n;
 phase=$abstime-k*p;
 c=(phase>=offset && phase<50n+offset);
 if(fault==2 && $abstime>=2.2u && $abstime<2.3u)c=0;
 V(ref)<+transition(r,0,0.1n);V(clk)<+transition(c,0,0.1n);
end
endmodule
'''
pll_mon=HEADER+'''module dut(ref,clk,verdict);
inout ref,clk,verdict;electrical ref,clk,verdict;
real last,phase,lastref;integer bad,seen;
analog begin
 @(initial_step)begin last=0;lastref=0;bad=0;seen=0;end
 @(cross(V(ref)-0.5,+1))lastref=$abstime;
 @(cross(V(clk)-0.5,+1))begin
  if($abstime>=1u)begin
   phase=$abstime-lastref;if(phase>50n)phase=phase-100n;
   if(abs(phase)>2n)bad=1;
   if(seen!=0 && abs($abstime-last-100n)>2n)bad=1;
   seen=1;
  end
  last=$abstime;
 end
 @(timer(1.05u,10n))begin if($abstime-last>102n)bad=1;end
 V(verdict)<+bad;
end
endmodule
'''
pllc=[{'name':f'fault{f}','netlist':net(f'Xmon (ref clk verdict) dut\nXpll (ref clk) pll_device fault={f}','4u','1n'),'stop':4e-6,'signals':['ref','clk','verdict'],'fault':f} for f in range(4)]
entries.append(task('verify-pll-lock-checker','verification-tools','PLL 持续锁定自动判定','ref,clk,verdict','''输入ref和clk是PLL参考和反馈电压时钟，高1V低0V，边沿0.1ns。运行4us，0..1us是允许的获取窗口；1..4us必须持续锁定。锁定要求每个clk上升沿距离最近ref上升沿≤2ns，相邻clk上升沿周期100ns±2ns，且不丢失任何参考周期。输出verdict初值0，任一持续锁定条件违反后锁存1。正确器件获取阶段可能有最高20ns相位偏移。隐藏错误包括105ns周期、晚期丢失一周期、晚期10ns相移。必须接受有获取过程的正确器件并拒绝所有故障。终评从真实边沿独立检查相位、周期、边沿数和最后时钟活动，不能只看候选宣称locked。''',pll_mon,pll_dev,pllc,{'always_accept':pll_mon.replace('V(verdict)<+bad','V(verdict)<+0'),'reject_acquisition':pll_mon.replace('if($abstime>=1u)','if($abstime>=0)'),'no_watchdog':pll_mon.replace('if($abstime-last>102n)bad=1','if($abstime-last>1002n)bad=1').replace('abs($abstime-last-100n)>2n','abs($abstime-last-100n)>202n')}))
sh_dev=HEADER+'''module sh_device(vin,track,y);
inout vin,track,y;electrical vin,track,y;
parameter integer fault=0;
real phase,target,tau,a;
integer k,tr;
analog begin
 k=$rtoi($abstime/500n);phase=$abstime-k*500n;
 target=0.2;if(k%2==0)target=0.8;
 tr=(phase<250n);tau=20n;if(fault==1)tau=60n;
 a=1-exp(-phase/tau);
 if(phase>=250n)a=1-exp(-250n/tau);
 V(vin)<+target;V(track)<+transition(tr,0,0.1n);
 if(tr!=0)begin
  if(fault==2 && phase>=180n && phase<200n)V(y)<+target+0.025;
  else V(y)<+0.5+(target-0.5)*a;
 end else begin
  if(fault==3)V(y)<+0.5+(target-0.5)*a-2e5*(phase-250n);
  else V(y)<+0.5+(target-0.5)*a;
 end
end
endmodule
'''
sh_mon=HEADER+'''module dut(vin,track,y,verdict);
inout vin,track,y,verdict;electrical vin,track,y,verdict;
integer bad,k;real phase,held;
analog begin
 @(initial_step)begin bad=0;held=0;end
 @(timer(1n,1n))begin
  k=$rtoi($abstime/500n);phase=$abstime-k*500n;
  if(phase>=120n && phase<249n && abs(V(y)-V(vin))>0.005)bad=1;
  if(phase>=255n && phase<490n && abs(V(y)-V(vin))>0.005)bad=1;
 end
 V(verdict)<+bad;
end
endmodule
'''
shc=[{'name':f'fault{f}','netlist':net(f'Xmon (vin track y verdict) dut\nXsh (vin track y) sh_device fault={f}','2u','0.5n'),'stop':2e-6,'signals':['vin','track','y','verdict'],'fault':f}for f in range(4)]
entries.append(task('verify-sh-settling-checker','verification-tools','采样保持全窗口建立判定','vin,track,y,verdict','''S/H输出在每500ns周期重新采集，前250ns track=1，后250ns保持。输入交替0.8/0.2V，从0.5V初始状态采集，正确获取时间常数20ns。建立要求周期120..249ns每一点 |y-vin|≤5mV；保持要求255..490ns同样≤5mV。运行4周期，verdict初值0，任何超限锁存1。隐含故障仅在公开条件内，包括过慢60ns时间常数、180..200ns短暂25mV回弹、保持期间200kV/s下垂。应接受正确器件，拒绝持续误差、迟发回弹、保持下垂，不能只检查一次过零或一个末点。终评核验真实波形所有窗口。''',sh_mon,sh_dev,shc,{'always_accept':sh_mon.replace('V(verdict)<+bad','V(verdict)<+0'),'loose_limit':sh_mon.replace('>0.005','>0.1'),'early_only':sh_mon.replace('phase<249n','phase<150n').replace('phase<490n','phase<270n')}))
put(ROOT/'benchmark/first_batch/verification_measurement.json',json.dumps({'tasks':entries},indent=2)+'\n')
adc_dev=HEADER+'''module adc_device(vin,clk,code);
inout vin,clk,code; electrical vin,clk,code;
parameter integer tone_bin=5;parameter real amp=1700,h2=0.02,h3=0.01;
integer q,c;real x;
analog begin
 x=2048+amp*sin(2*3.1415926535897932384626433832795*tone_bin*$abstime/6.4u)+amp*h2*sin(4*3.1415926535897932384626433832795*tone_bin*$abstime/6.4u)+amp*h3*cos(6*3.1415926535897932384626433832795*tone_bin*$abstime/6.4u);
 V(vin)<+x/4096;
 @(initial_step)begin q=2048;c=0;end
 @(timer(0,100n))begin q=$rtoi(x);if(q<0)q=0;if(q>4095)q=4095;end
 @(timer(10n,100n))c=1;
 @(timer(60n,100n))c=0;
 V(clk)<+transition(c,0,0.1n);V(code)<+transition(q,0,0.1n);
end
endmodule
'''
adc_measure=HEADER+'''module dut(code,clk,sndr,sfdr,dc);
inout code,clk,sndr,sfdr,dc;electrical code,clk,sndr,sfdr,dc;
parameter integer tone_bin=5;
real cs[0:32],ss[0:32],x,p,fund,spurious,noise,sum,out_sndr,out_sfdr,out_dc;
integer n,k;
analog begin
 @(initial_step)begin n=0;sum=0;out_sndr=0;out_sfdr=0;out_dc=0;for(k=0;k<=32;k=k+1)begin cs[k]=0;ss[k]=0;end end
 @(cross(V(clk)-0.5,+1))begin
  if(n<64)begin
   x=V(code);sum=sum+x;
   for(k=0;k<=32;k=k+1)begin cs[k]=cs[k]+x*cos(2*3.1415926535897932384626433832795*k*n/64.0);ss[k]=ss[k]+x*sin(2*3.1415926535897932384626433832795*k*n/64.0);end
   n=n+1;
   if(n==64)begin
    fund=2*(cs[tone_bin]*cs[tone_bin]+ss[tone_bin]*ss[tone_bin])/4096;
    noise=0;spurious=0;
    for(k=1;k<=32;k=k+1)if(k!=tone_bin)begin
     p=2*(cs[k]*cs[k]+ss[k]*ss[k])/4096;if(k==32)p=p/2;
     noise=noise+p;if(p>spurious)spurious=p;
    end
    out_sndr=10*ln(fund/noise)/ln(10);out_sfdr=10*ln(fund/spurious)/ln(10);out_dc=sum/64;
   end
  end
 end
 V(sndr)<+out_sndr;V(sfdr)<+out_sfdr;V(dc)<+out_dc;
end
endmodule
'''
adcc=[]
for b,a,h2,h3 in [(5,1700,.02,.01),(3,1500,.04,.005),(7,1800,.005,.025)]:
 adcc.append({'name':f'bin{b}','netlist':net(f'Xmeasure (code clk sndr sfdr dc) dut tone_bin={b}\nXadc (vin clk code) adc_device tone_bin={b} amp={a} h2={h2} h3={h3}','6.6u','2n'),'stop':6.6e-6,'signals':['vin','clk','code','sndr','sfdr','dc'],'tone_bin':b,'amp':a,'h2':h2,'h3':h3})
entries.append(task('measure-adc-spectrum','measurement-characterization','ADC 动态频谱测量','code,clk,sndr,sfdr,dc','''测量12-bit ADC的相干采样频谱，code电压数值为unsigned码，clk为采样有效时钟，64个样本，每100ns一个，clk首次上升10ns。仅取最初64个clk上升的稳定code，code已在上升前10ns更新。模块参数tone_bin=5，允许3/5/7。输入相干频率为tone_bin/(64*100ns)，有二三次失真及量化。输出sndr和sfdr数值为dB，dc为码均值，6.45us前完成并保持。

使用64点无窗DFT，排除DC。频率1..31的均方功率为2|DFT[k]|²/64²，Nyquist k32为|DFT[32]|²/64²。sndr=10log10(基波功率/其余全部频率功率和)，sfdr=10log10(基波功率/最大非基波频率功率)，谐波计入噪声失真。容差sndr/sfdr 0.05dB，dc 0.01码。公开器件为行为合成，输入幅度1500..1800码，二三次系数0.005..0.04，禁止声称器件实测性能。终评独立采集实际clk/code后重新DFT，不能依赖候选自报CSV。''',adc_measure,adc_dev,adcc,{'amplitude_db':adc_measure.replace('10*ln(fund/noise)','20*ln(fund/noise)').replace('10*ln(fund/spurious)','20*ln(fund/spurious)'),'omit_harmonics':adc_measure.replace('if(k!=tone_bin)begin','if(k!=tone_bin && k!=2*tone_bin && k!=3*tone_bin)begin'),'fixed_tone':adc_measure.replace('cs[tone_bin]','cs[5]').replace('ss[tone_bin]','ss[5]').replace('k!=tone_bin','k!=5')}))
hyst_dev=HEADER+'''module hysteresis_device(vin,q);
inout vin,q;electrical vin,q;
parameter real hysteresis=0.008,delay=4n;
real x,due;integer state,pending,target;
analog begin
 if($abstime<400n)x=-0.02+1e5*$abstime;
 else if($abstime<800n)x=0.02-1e5*($abstime-400n);
 else if($abstime<1u)x=-0.02;
 else if($abstime<1.2u)x=0.02;
 else x=-0.02;
 V(vin)<+x;
 @(initial_step)begin state=0;pending=0;target=0;due=-1;end
 @(cross(x-hysteresis/2,+1))begin if(state==0)begin due=$abstime+delay;pending=1;target=1;end end
 @(cross(x+hysteresis/2,-1))begin if(state==1)begin due=$abstime+delay;pending=1;target=0;end end
 @(timer(0,0.1n))begin if(pending!=0 && $abstime>=due)begin state=target;pending=0;end end
 V(q)<+transition(state,0,0.1n);
end
endmodule
'''
hyst_measure=HEADER+'''module dut(vin,q,high_mv,low_mv,rise_ns,fall_ns);
inout vin,q,high_mv,low_mv,rise_ns,fall_ns;electrical vin,q,high_mv,low_mv,rise_ns,fall_ns;
real rh,rl,ts,dr,df;integer pos;
analog begin
 @(initial_step)begin rh=0;rl=0;dr=0;df=0;ts=0;pos=0;end
 @(cross(V(vin),+1))if($abstime>=900n)ts=$abstime;
 @(cross(V(vin),-1))if($abstime>=900n)ts=$abstime;
 @(cross(V(q)-0.5,+1))begin if($abstime<800n)rh=V(vin);else dr=$abstime-ts;end
 @(cross(V(q)-0.5,-1))begin if($abstime<800n)rl=V(vin);else df=$abstime-ts;end
 V(high_mv)<+1000*(rh-1e5*dr);V(low_mv)<+1000*(rl+1e5*df);
 V(rise_ns)<+dr/1n;V(fall_ns)<+df/1n;
end
endmodule
'''
hc=[]
for h,d in [(.008,4e-9),(.012,2e-9),(.004,6e-9)]:
 hc.append({'name':f'h{h:g}-d{d*1e9:g}','netlist':net(f'Xmeasure (vin q high_mv low_mv rise_ns fall_ns) dut\nXcmp (vin q) hysteresis_device hysteresis={h} delay={d:.12g}','1.5u','0.1n'),'stop':1.5e-6,'signals':['vin','q','high_mv','low_mv','rise_ns','fall_ns'],'hysteresis':h,'delay':d})
entries.append(task('measure-comparator-delay-hysteresis','measurement-characterization','比较器传播延时与迟滞分离表征','vin,q,high_mv,low_mv,rise_ns,fall_ns','''观测施密特比较器差分输入vin和逻辑输出q。输入先从-20mV到+20mV线性上扫400ns，再下扫400ns，斜率100kV/s。800ns后保持-20mV，在1us跳至+20mV，1.2us跳回-20mV。输入阈值对称，迟滞总宽4/8/12mV，固定传播延时2/4/6ns，q边沿0.1ns。输出high_mv、low_mv为传播延时校正后的输入高低阈值mV；rise_ns、fall_ns为阶跃输入0V穿越至q=0.5V穿越的延时ns。阈值用上扫输出翻转时vin减去斜率*rise_delay，下扫加上斜率*fall_delay，单独传播延时包含0.5V输出边沿半过渡时间。终评用原始输入和输出边沿重算同一定义，阈值容差0.05mV，延时0.15ns，1.4us前完成。需区分慢扫的动态阈值与静态迟滞。''',hyst_measure,hyst_dev,hc,{'no_delay_correction':hyst_measure.replace('rh-1e5*dr','rh').replace('rl+1e5*df','rl'),'wrong_low_sign':hyst_measure.replace('1000*(rl+1e5*df)','-1000*(rl+1e5*df)'),'seconds_as_ns':hyst_measure.replace('dr/1n','dr').replace('df/1n','df')}))
sh_measure_dev=HEADER+'''module acquisition_device(vin,track,y);
inout vin,track,y;electrical vin,track,y;
parameter real tau=20n,droop=5e4;
real phase,target,out;integer k,tr;
analog begin
 k=$rtoi($abstime/500n);phase=$abstime-k*500n;target=0.2;if(k%2==0)target=0.8;
 tr=(phase<250n);
 out=0.5+(target-0.5)*(1-exp(-phase/tau));
 if(phase>=250n)out=0.5+(target-0.5)*(1-exp(-250n/tau))-droop*(phase-250n);
 V(vin)<+target;V(track)<+transition(tr,0,0.1n);V(y)<+out;
end
endmodule
'''
sh_measure=HEADER+'''module dut(vin,track,y,settle_ns,droop_mvus);
inout vin,track,y,settle_ns,droop_mvus;electrical vin,track,y,settle_ns,droop_mvus;
real settling,drooping,held,phase;integer ns,nd,k;
analog begin
 @(initial_step)begin settling=0;drooping=0;held=0;ns=0;nd=0;end
 @(cross(abs(V(y)-V(vin))-0.003,-1))begin
  k=$rtoi($abstime/500n);phase=$abstime-k*500n;
  if(V(track)>0.5 && k<4)begin settling=settling+phase;ns=ns+1;end
 end
 @(timer(260n,500n))held=V(y);
 @(timer(490n,500n))if(nd<4)begin drooping=drooping+1000*(held-V(y))/0.23;nd=nd+1;end
 if(ns>0)V(settle_ns)<+settling/ns/1n;else V(settle_ns)<+0;
 if(nd>0)V(droop_mvus)<+drooping/nd;else V(droop_mvus)<+0;
end
endmodule
'''
smc=[]
for tau,droop in [(20e-9,5e4),(10e-9,2e4),(35e-9,-8e4)]:
 smc.append({'name':f'tau{tau*1e9:g}-droop{droop:g}','netlist':net(f'Xmeasure (vin track y settle_ns droop_mvus) dut\nXsh (vin track y) acquisition_device tau={tau:.12g} droop={droop}','2u','0.5n'),'stop':2e-6,'signals':['vin','track','y','settle_ns','droop_mvus'],'tau':tau,'droop':droop})
entries.append(task('measure-sh-acquisition-droop','measurement-characterization','采样保持建立时间和有符号下垂测量','vin,track,y,settle_ns,droop_mvus','''每500ns一个S/H周期，前250ns采集，后250ns保持，4周期交替输入0.8/0.2V。每次获取从0.5V开始，时间常数允许10/20/35ns，保持段有有符号线性下垂20/50/-80kV/s。settle_ns是4周期建立时间平均值，建立定义为周期起点之后 |y-vin| 首次≤3mV并持续至获取结束的时间，单位ns；终评还检查全余下获取窗口，不能漏掉回弹。droop_mvus为4周期 [(y(260ns)-y(490ns))/0.23us] 平均值，单位mV/us，保留符号。1.991us前完成并保持至2us仿真结束，建立容差0.5ns，下垂容差0.2mV/us。数据仅为behavioral_synthetic，禁止视作实测。终评核验实际track输入、y轨迹、建立边沿和保持段两个原始端点。''',sh_measure,sh_measure_dev,smc,{'wrong_band':sh_measure.replace('-0.003','-0.03'),'absolute_droop':sh_measure.replace('held-V(y)','abs(held-V(y))'),'wrong_interval':sh_measure.replace('/0.23','/0.25')}))
pll_measure_dev=HEADER+'''module relock_device(ref,clk);
inout ref,clk;electrical ref,clk;
parameter integer settle_cycles=5;parameter real jitter=1n;
real phase,offset,phase_r;integer k,r,c;
analog begin
 k=$rtoi($abstime/100n);phase=$abstime-k*100n;offset=0;
 if(k>=10 && k<10+settle_cycles)offset=(10+settle_cycles-k)*5n;
 if(k>=22)begin if(k%2==0)offset=jitter;else offset=-jitter;end
 c=(phase>=offset && phase<50n+offset);
 if(offset<0)c=(phase<50n+offset || phase>=100n+offset);
 r=(phase<50n);
 V(ref)<+transition(r,0,0.1n);V(clk)<+transition(c,0,0.1n);
end
endmodule
'''
# jitter uses positive offsets for stable edge pairing, otherwise a negative offset's wrap
# changes which period receives the edge. Shift jitter around a 2ns common phase.
pll_measure_dev=pll_measure_dev.replace('offset=jitter;else offset=-jitter','offset=2n+jitter;else offset=2n-jitter')
pll_measure=HEADER+'''module dut(ref,clk,relock_ns,jitter_ns);
inout ref,clk,relock_ns,jitter_ns;electrical ref,clk,relock_ns,jitter_ns;
real phase,last,lastref,run_start,relock,sum,sum2,period,rms;integer consecutive,n;
analog begin
 @(initial_step)begin last=0;lastref=0;run_start=0;relock=0;sum=0;sum2=0;consecutive=0;n=0;rms=0;end
 @(cross(V(ref)-0.5,+1))lastref=$abstime;
 @(cross(V(clk)-0.5,+1))begin
  phase=$abstime-lastref;if(phase>50n)phase=phase-100n;
  if($abstime>=1u && $abstime<2.2u && relock==0)begin
   if(abs(phase)<=3n)begin
    if(consecutive==0)run_start=$abstime;
    consecutive=consecutive+1;if(consecutive==4)relock=run_start-1u;
   end else consecutive=0;
  end
  if($abstime>=2.2u && $abstime<4.2u)begin
   if(last>=2.2u)begin period=($abstime-last)/1n;sum=sum+period;sum2=sum2+period*period;n=n+1;end
  end
  last=$abstime;
 end
 @(timer(4.3u))if(n>0)rms=sqrt(max(0,sum2/n-(sum/n)*(sum/n)));
 V(relock_ns)<+relock/1n;V(jitter_ns)<+rms;
end
endmodule
'''
pmc=[]
for n,j in [(5,1e-9),(3,.5e-9),(7,1.5e-9)]:
 pmc.append({'name':f'settle{n}-jitter{j*1e9:g}','netlist':net(f'Xmeasure (ref clk relock_ns jitter_ns) dut\nXpll (ref clk) relock_device settle_cycles={n} jitter={j:.12g}','4.5u','0.5n'),'stop':4.5e-6,'signals':['ref','clk','relock_ns','jitter_ns'],'settle_cycles':n,'jitter':j})
entries.append(task('measure-pll-relock-jitter','measurement-characterization','PLL 重锁时间与周期抖动表征','ref,clk,relock_ns,jitter_ns','''ref为100ns参考时钟，clk为反馈时钟，1us发生跳频后相位重捕获。初始已锁定，1..2.2us获取阶段，允许相位偏移按周期收敛，公开settle_cycles为3/5/7。重锁定义是在1..2.2us期间首次出现连续4个clk上升沿均距最近ref上升沿≤3ns的序列，以该序列第一沿减1us作为relock_ns，单位ns。不能用第4沿时间或1us前锁定状态。2.2..4.2us稳定段有交替确定性相位抖动0.5/1/1.5ns，围绕2ns共模偏移；其首沿开始20周期窗口。jitter_ns为窗口内相邻20个clk上升沿产生的19个周期的总体标准差sqrt(mean(T²)-mean(T)²)，单位ns，移除均值，非TIE RMS，非峰峰值。4.4us前完成，重锁容差0.3ns，抖动容差0.02ns。终评直接提取原始ref/clk边沿独立计算，数据为behavioral_synthetic。''',pll_measure,pll_measure_dev,pmc,{'fourth_edge':pll_measure.replace('relock=run_start-1u','relock=$abstime-1u'),'peak_to_peak':pll_measure.replace('V(jitter_ns)<+rms','V(jitter_ns)<+2*rms'),'include_acquisition':pll_measure.replace('last>=2.2u','last>=1u').replace('$abstime>=2.2u && $abstime<4.2u','$abstime>=1u && $abstime<4.2u')}))
entries.insert(5,{'id':'va08-adc-linearity','category':'measurement-characterization','source_group':'repository-owned-original-adc-linearity','status':'existing_calibration_reference','path':'benchmark/tasks/va08-adc-linearity','note':'Existing task referenced without copying or changing; Agentic status stays separate.'})
put(ROOT/'benchmark/first_batch/verification_measurement.json',json.dumps({'tasks':entries},indent=2)+'\n')
