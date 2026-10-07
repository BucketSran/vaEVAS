"""Original phase-feedback frequency-hop loop with observable voltage outputs."""
import csv
import io
import math
from build_common import *

TASK="identify-pll-hop-dynamics"
OMEGA,ZETA=2*math.pi*45000,.52
ALPHA=ZETA*OMEGA
WD=OMEGA*math.sqrt(1-ZETA**2)
BASE=.8e6


def experiment(name,steps,stop=200e-6):return dict(name=name,initial_command_V=.8,steps=[dict(time=t,command_V=v) for t,v in steps],stop=stop)


def observations(c,t):
    phase=BASE*t;error=0;frequency=BASE;previous=.8
    for hop in c["steps"]:
        delta=(hop["command_V"]-previous)*1e6;previous=hop["command_V"]
        s=t-hop["time"]
        if s<0:continue
        exp=math.exp(-ALPHA*s);sin=math.sin(WD*s);cos=math.cos(WD*s)
        error+=delta/WD*exp*sin
        frequency+=delta*(1-exp*(cos-ALPHA/WD*sin))
        phase+=delta*s
    return math.sin(2*math.pi*(phase-error)),frequency/1e6,error


def netlist(c):
    points=[(0,.8)];previous=.8
    for hop in c["steps"]:
        points.extend([(hop["time"],previous),(hop["time"]+1e-12,hop["command_V"])]);previous=hop["command_V"]
    points.append((c["stop"],previous))
    return HEADER+pwl("cmd",points)+"DUT (cmd out tune) identified_pll\n"+OPTIONS+f"tran tran stop={c['stop']:.12g} maxstep=1e-8 errpreset=conservative\nsave out tune cmd\n"


FIT=FIT_IMPORTS+'''def fit(public):
    values=[]
    for c in json.loads((public/"experiments.json").read_text()):
        rows=read(public,c);hop=c["steps"][0]
        sign=1 if hop["command_V"]>c["initial_command_V"] else -1
        peaks=[]
        for i in range(1,len(rows)-1):
            a,b,d=rows[i-1:i+2]
            ya,yb,yd=[sign*r["phase_error_cycles"] for r in (a,b,d)]
            if b["time_s"]>hop["time"] and yb>0 and ya<yb>=yd:
                offset=.5*(ya-yd)/(ya-2*yb+yd)
                dt=d["time_s"]-b["time_s"]
                time=b["time_s"]+offset*dt
                height=yb-.25*(ya-yd)*offset
                peaks.append((time,height))
        a,b=peaks[:2]
        wd=2*math.pi/(b[0]-a[0]);alpha=math.log(a[1]/b[1])/(b[0]-a[0])
        values.append((2*alpha,wd*wd+alpha*alpha))
    return tuple(statistics.mean(x[k] for x in values) for k in (0,1))

def model(parameters,variant="reference"):
    kp,ki=parameters
    if variant=="wrong-damping":kp*=.35
    if variant=="no-integral":ki=0
    if variant=="wrong-loop-rate":kp*=.6;ki*=.36
    phase_expression="idt(1e6*V(cmd),0)-V(phase_error)"
    if variant=="wrong-clock-phase":phase_expression="idt(1e6*V(cmd),0)"
    ripple="+0.1*sin(6.283185307179586*$abstime/5e-7)" if variant=="grid-alias-ripple" else ""
    return f\'''`include "constants.vams"
`include "disciplines.vams"
module identified_pll(cmd,out,tune);
input cmd;output out,tune;
electrical cmd,out,tune,phase_error,integrated_error;
real deviation;
analog begin
  deviation={kp:.15g}*V(phase_error)+{ki:.15g}*V(integrated_error);
  V(phase_error)<+idt(1e6*V(cmd)-8e5-deviation,0);
  V(integrated_error)<+idt(V(phase_error),0);
  V(tune)<+0.8+deviation/1e6;
  V(out)<+sin(6.283185307179586*({phase_expression})){ripple};
  $bound_step(1e-8);
end
endmodule
\'''
'''+FIT_MAIN


def build():
    public=[experiment("public-hop-up-small",[(10e-6,.88)]),experiment("public-hop-up-large",[(10e-6,1.16)]),experiment("public-hop-down-small",[(10e-6,.74)]),experiment("public-hop-down-large",[(10e-6,.65)])]
    for c in public:
        buf=io.StringIO();w=csv.writer(buf,lineterminator="\n");w.writerow(["time_s","cmd_V","out_V","tune_V","phase_error_cycles"])
        for j in range(2001):
            t=c["stop"]*j/2000;out,tune,error=observations(c,t);cmd=.8
            for hop in c["steps"]:
                if t>=hop["time"]:cmd=hop["command_V"]
            w.writerow([f"{t:.12g}",cmd,f"{out:.12g}",f"{tune:.12g}",f"{error:.12g}"])
        write(TASK,f"environment/public/data/{c['name']}.csv",buf.getvalue());write(TASK,f"environment/public/{c['name']}.scs",netlist(c))
    hidden=[experiment("new-up-hop",[(13e-6,1.03)]),experiment("early-return",[(8e-6,1.12),(28e-6,.78)]),experiment("down-up-recapture",[(11e-6,.69),(76e-6,1.07)]),experiment("small-hop",[(17e-6,.815),(52e-6,.792)])]
    for c in hidden:
        probes=[]
        for j in range(401):
            t=c["stop"]*j/400;out,tune,error=observations(c,t)
            probes.append(dict(time=t,node="tune",expected=tune,tolerance=3e-4,metric="instantaneous-frequency-monitor"))
            probes.append(dict(time=t,node="out",expected=out,tolerance=.008,metric="phase-coherent-output"))
        final=c["steps"][-1];settle_start=final["time"]+100e-6
        for j in range(31):
            t=settle_start+(c["stop"]-settle_start)*j/30
            if t>c["stop"]:continue
            _,tune,_=observations(c,t)
            probes.append(dict(time=t,node="tune",expected=final["command_V"],tolerance=3e-4,metric="settled-frequency-band"))
        # Score output over the whole experiment at the declared 10 ns
        # observation interval; compressed arrays avoid repeated JSON keys.
        step=1e-8; count=round(c["stop"]/step)
        grid=dict(node="out",start=0.0,step=step,
            expected=[observations(c,j*step)[0] for j in range(count+1)],
            tolerance=.008,metric="phase-coherent-output")
        c.update(netlist=netlist(c),signals=["out","tune","cmd"],probes=probes,sample_grids=[grid])
    instruction='''# 从PLL跳频轨迹辨识闭环动态

这个原创PLL行为对象有相位反馈与积分校正，用于频率合成器跳频后的重捕获预测。
你要从固定loop的完整跳频实验辨识电压可观察行为，预测频率超调、建立和输出相位。
不要求从闭环数据唯一恢复charge pump、VCO或loop filter的器件参数。

交付 `/work/dut.va`，模块 `identified_pll`，electrical端口 `(cmd,out,tune)`。
cmd是已解码的频率设定电压，1 V表示1 MHz；起点cmd=0.8 V，
参考与输出相位都为0 cycles。参考相位是cmd*1 MHz的时间积分。
out是单位幅度sinusoidal时钟电压；tune是固定监测器，将瞬时输出频率以1 V/MHz编码。
它不是对物理VCO控制端或负载的建模。候选只实现电压行为。

public CSV包括cmd、out、tune以及通过连续相位跟踪计算的reference减output相位差。
单位为s、V、cycles。该相位差是表征观察，不是要求你提交的内部状态。
数据身份为本项目 `behavioral_synthetic`，没有silicon测量、ADIsimPLL输出或器件电路表征。
四次实验来自同一个固定相位反馈系统。可自主选择辨识算法。

允许cmd在0.65至1.2 V之间跳变，第一次跳变8至20 us，
后续跳变至少间隔20 us，观察时间不超过200 us。模型须保留尚未建立时再次跳变的状态。
不要求PVT、RF功率、phase noise、随机抖动、输入电流或负载耦合。

终评在完整隐藏实验检查tune逐窗误差不超过0.3 mV，
out的相位一致波形误差不超过8 mV；最终跳变100 us后tune必须保持在目标0.3 mV频率带内。
测试输入边沿1 ps，最大观测步10 ns。既不能仅查lock flag，也不能只拟合最终频率。
公开网表可自测，最终只提交dut.va，不读终评、不写文件、不执行系统命令。
'''
    package(TASK,"identified_pll",instruction,source("PLL锁定与跳频","https://www.analog.com/en/resources/analog-dialogue/articles/pll-synthesizers.html","一手资料说明频率跳变、容差和loop bandwidth决定lock time。本题是原创phase-feedback抽象闭环，不宣称复刻厂商器件或包含RF/charge-pump物理。","错误阻尼、取消积分路径、错误loop时间尺度、伪造已锁相时钟和粗网格混叠纹波"),hidden,public,dict(conditions="fixed decoded frequency-command interface, known phase origin, fixed monitor scaling, no PVT/load/noise",observation_precision="12 significant digits; phase_error from continuous synthetic phase tracking"),FIT)


if __name__=="__main__":build()
