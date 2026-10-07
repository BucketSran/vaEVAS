"""Original two-section clocked SC baseband task, not a MAX7400 model."""
import csv
import io
import math
from build_common import *

TASK="identify-sc-clocked-filter"
P1,P2=0.62,0.84


def experiment(name,ts,amplitude,kind,n=96):
    c=dict(name=name,clock_period=ts,amplitude=amplitude,stimulus=kind,cycles=n)
    x=[]
    for k in range(1,n+1):
        if kind=="step":v=amplitude if k< n//2 else -0.6*amplitude
        elif kind=="pulse":v=amplitude if 4<=k<=9 else 0
        elif kind=="sine":v=amplitude*math.sin(2*math.pi*k/13)
        else:v=amplitude*(0.6*math.sin(2*math.pi*k/9)+0.4*math.cos(2*math.pi*k/23))
        x.append(v)
    c["samples_V"]=x
    return c


def observations(c):
    s1=s2=0
    y=[]
    for x in c["samples_V"]:
        s1=P1*s1+(1-P1)*x
        s2=P2*s2+(1-P2)*s1
        y.append(s2)
    return y


def netlist(c):
    ts=c["clock_period"];n=c["cycles"]
    vin=[(0,c["samples_V"][0])];clock=[(0,0)]
    for k,x in enumerate(c["samples_V"],1):
        if k>1:
            at=(k-.5)*ts
            vin.extend([(at,c["samples_V"][k-2]),(at+2e-9,x)])
        clock.extend([(k*ts,0),(k*ts+2e-9,1),((k+.5)*ts,1),((k+.5)*ts+2e-9,0)])
    stop=(n+1)*ts
    vin.append((stop,c["samples_V"][-1]));clock.append((stop,0))
    return HEADER+pwl("vin",vin)+pwl("clk",clock)+"DUT (vin clk out) identified_sc\n"+OPTIONS+f"tran tran stop={stop:.12g} maxstep={ts/12:.12g} errpreset=conservative\nsave out vin clk\n"


FIT=FIT_IMPORTS+'''def fit(public):
    xs=[];ys=[]
    for c in json.loads((public/"experiments.json").read_text()):
        rows=read(public,c);prev=prev2=0
        for r in rows:
            xs.append([prev,prev2,r["vin_V"]]);ys.append(r["out_V"])
            prev2,prev=prev,r["out_V"]
    return regress(xs,ys)

def model(parameters,variant="reference"):
    a,b,c=parameters
    edge=1
    if variant=="single-pole":a,b,c=a+b,0,1-a-b
    if variant=="wrong-clock-edge":edge=-1
    if variant=="no-history":a=b=0
    if variant=="wrong-gain":c*=.75
    return f\'''`include "constants.vams"
`include "disciplines.vams"
module identified_sc(vin, clk, out);
input vin,clk;output out;
electrical vin,clk,out;
real y,yold,ynew;
analog begin
  @(initial_step) begin y=0;yold=0;end
  @(cross(V(clk)-0.5,{edge})) begin
    ynew={a:.15g}*y+{b:.15g}*yold+{c:.15g}*V(vin);
    yold=y;y=ynew;
  end
  V(out)<+transition(y,0,5e-9,5e-9);
end
endmodule
\'''
'''+FIT_MAIN


def build():
    public=[experiment("public-step",2e-6,.7,"step"),experiment("public-pulse",4e-6,-.5,"pulse"),experiment("public-sine",1e-6,.8,"sine"),experiment("public-multitone",3e-6,.65,"multi")]
    for c in public:
        buf=io.StringIO();w=csv.writer(buf,lineterminator="\n");w.writerow(["cycle","time_s","vin_V","out_V"])
        for k,(x,y) in enumerate(zip(c["samples_V"],observations(c)),1):w.writerow([k,f"{k*c['clock_period']+10e-9:.12g}",f"{x:.12g}",f"{y:.12g}"])
        write(TASK,f"environment/public/data/{c['name']}.csv",buf.getvalue())
        write(TASK,f"environment/public/{c['name']}.scs",netlist(c))
    hidden=[experiment("fast-negative-step",.8e-6,-.91,"step"),experiment("slow-positive-pulse",5e-6,.93,"pulse"),experiment("mixed-frequency",1.7e-6,-.76,"multi"),experiment("sine-off-public-clock",2.7e-6,.47,"sine")]
    for c in hidden:
        y=observations(c);probes=[];ts=c["clock_period"]
        for k,v in enumerate(y,1):
            probes.append(dict(time=k*ts+10e-9,expected=v,tolerance=2e-5,metric="sampled-output"))
            probes.append(dict(time=(k+.4)*ts,expected=v,tolerance=2e-5,metric="inter-sample-hold"))
        c.update(netlist=netlist(c),stop=(c["cycles"]+1)*ts,signals=["out","vin","clk"],probes=probes,metrics=[dict(name="post-reversal-response",t1=(c["cycles"]//2)*ts+10e-9,t2=(c["cycles"]//2+5)*ts+10e-9,expected=y[c["cycles"]//2+4]-y[c["cycles"]//2-1],tolerance=3e-5)])
    instruction='''# 从时钟驱动滤波实验建立模型

这是ADC抗混叠链中一个原创的两节开关电容低通行为对象。
你要辨识固定系统的电压基带响应，预测不同输入与外部时钟下的输出。
它不是MAX7400复刻，不要求还原内部电容或电流，也不要求unique拓扑。

交付 `/work/dut.va`，模块名 `identified_sc`，electrical端口 `(vin, clk, out)`。
初态输出为0。时钟上升沿采样输入，输出在5 ns内切换到新值，并保持到下一次上升沿。
公开CSV记录每次上升沿后10 ns的输入与输出，单位s和V。
所有数据都是本项目 `behavioral_synthetic`，不是实测或器件仿真。
完整刺激序列、时钟周期、来源身份在 `/work/public/`。

允许外部时钟周期0.8至5 us，输入幅度不超过1 V。输入至少在上升沿前100 ns建立。
输入可为阶跃、有限脉冲、正弦或多音，观察不超过100周期。
SC的时钟决定真实时间尺度，你的模型必须同时保留采样历史与周期内保持。
无须实现时钟穿通、开关纹波、负载耦合、PVT或超出声明采样频带的内部物理效应。

终评按完整新实验检查每个采样点和周期内保持，电压误差不超过20 uV。
输入反转后5周期的输出变化误差不超过30 uV。
这些局部检查包含startup、通带时序与reversal，不能只用平均误差或最终DC值证明通过。
使用public网表自测，最终只提交dut.va，不读终评、不写文件、不调用系统命令。
'''
    package(TASK,"identified_sc",instruction,source("时钟可调SC滤波器","https://www.analog.com/en/products/max7400.html","厂商文档支持时钟控制corner frequency的工程意义；本题原创两节低通而不是其八阶椭圆架构。","丢失一节动态、使用下降沿、丢失历史和错误增益"),hidden,public,dict(conditions="fixed voltage-domain baseband system, zero initial state, 5 ns output edge, no loading/PVT",observation_precision="12 significant digits"),FIT)


if __name__=="__main__":build()
