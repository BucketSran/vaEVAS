"""ADC closed-loop driver behavioral identification, fixed load conditions."""
import csv
import io
import math
from build_common import *

TASK="identify-adc-driver-settling"
GAIN,OFFSET,TAU,SR,LOW,HIGH=.96,.012,75e-9,3.1e6,-.86,.88


def target(x):return max(LOW,min(HIGH,GAIN*x+OFFSET))


def step(y0,goal,t):
    e=goal-y0;s=1 if e>=0 else -1
    limit=TAU*SR
    if abs(e)>limit:
        linear=(abs(e)-limit)/SR
        if t<linear:return y0+s*SR*t
        return goal-s*limit*math.exp(-(t-linear)/TAU)
    return goal+(y0-goal)*math.exp(-t/TAU)


def value(c,t):
    at=c["switch_time"]
    if t<at:return step(0,target(c["first_amplitude"]),t)
    return step(step(0,target(c["first_amplitude"]),at),target(c["second_amplitude"]),t-at)


def experiment(name,first,second,at=1.2e-6):return dict(name=name,first_amplitude=first,second_amplitude=second,switch_time=at,stop=at+1.3e-6)


def netlist(c):
    at=c["switch_time"];a=c["first_amplitude"];b=c["second_amplitude"]
    return HEADER+pwl("vin",[(0,a),(at,a),(at+1e-12,b),(c["stop"],b)])+"DUT (vin out) identified_driver\n"+OPTIONS+f"tran tran stop={c['stop']:.12g} maxstep=2e-9 errpreset=conservative\nsave out vin\n"


FIT=FIT_IMPORTS+'''def fit(public):
    cs=json.loads((public/"experiments.json").read_text());byname={c["name"]:c for c in cs}
    plateaus=[]
    for name in ("public-small-positive","public-small-negative"):
        c=byname[name];r=read(public,c)
        plateau=statistics.mean(x["out_V"] for x in r if .9*c["switch_time"]<x["time_s"]<.98*c["switch_time"])
        plateaus.append((c["first_amplitude"],plateau))
    (x1,y1),(x2,y2)=plateaus
    gain=(y1-y2)/(x1-x2);offset=y1-gain*x1
    sr=0;low=1e10;high=-1e10;taus=[]
    for c in cs:
        rows=read(public,c)
        plateau=statistics.mean(r["out_V"] for r in rows if .9*c["switch_time"]<r["time_s"]<.98*c["switch_time"])
        if c["first_amplitude"]>.95:high=plateau
        if c["first_amplitude"]<-.95:low=plateau
        for a,b in zip(rows,rows[1:]):
            if b["time_s"]<.2*c["switch_time"]:sr=max(sr,abs((b["out_V"]-a["out_V"])/(b["time_s"]-a["time_s"])))
        if abs(c["first_amplitude"])<.2:
            goal=gain*c["first_amplitude"]+offset
            samples=[r for r in rows if 60e-9<r["time_s"]<180e-9]
            a,b=samples[0],samples[-1]
            taus.append(-(b["time_s"]-a["time_s"])/math.log(abs((goal-b["out_V"])/(goal-a["out_V"]))))
    return gain,offset,statistics.mean(taus),sr,low,high

def model(parameters,variant="reference"):
    gain,offset,tau,sr,low,high=parameters
    if variant=="no-slew":sr*=10000
    if variant=="wrong-bandwidth":tau*=2
    if variant=="no-rails":low,high=-10,10
    if variant=="restart-on-input":reset=True
    else:reset=False
    # Restart mutation deliberately resets state whenever the input changes.
    if reset:
        # A separate algebraic memoryless model is a valid but wrong submission.
        return \'''`include "disciplines.vams"
module identified_driver(vin,out);input vin;output out;electrical vin,out;
analog V(out)<+V(vin);
endmodule
\'''
    return f\'''`include "constants.vams"
`include "disciplines.vams"
module identified_driver(vin,out);
input vin;output out;electrical vin,out;
real target,velocity;
analog begin
  target=max({low:.15g},min({high:.15g},{gain:.15g}*V(vin)+{offset:.15g}));
  velocity=max(-{sr:.15g},min({sr:.15g},(target-V(out))/{tau:.15g}));
  V(out)<+idt(velocity,0);
end
endmodule
\'''
'''+FIT_MAIN


def build():
    public=[experiment("public-small-positive",.12,-.08),experiment("public-small-negative",-.12,.08),experiment("public-large-positive",.7,-.6),experiment("public-large-negative",-.75,.55),experiment("public-positive-rail",1,-.2),experiment("public-negative-rail",-1,.25)]
    for c in public:
        buf=io.StringIO();w=csv.writer(buf,lineterminator="\n");w.writerow(["time_s","vin_V","out_V"])
        n=1250
        for j in range(n+1):
            t=c["stop"]*j/n
            w.writerow([f"{t:.12g}",c["first_amplitude"] if t<c["switch_time"] else c["second_amplitude"],f"{value(c,t):.12g}"])
        write(TASK,f"environment/public/data/{c['name']}.csv",buf.getvalue());write(TASK,f"environment/public/{c['name']}.scs",netlist(c))
    hidden=[experiment("multiplexer-reversal",.84,-.81,.42e-6),experiment("small-resolution-tail",-.055,.041,.8e-6),experiment("rail-recovery",-.98,.98,.7e-6),experiment("mixed-large-small",.62,.025,.3e-6)]
    for c in hidden:
        at=c["switch_time"];probes=[]
        for phase,start,end in [("initial-settling",0,at-5e-9),("acquisition-deadline",at+5e-9,min(c["stop"],at+600e-9)),("late-tail",at+600e-9,c["stop"])]:
            for j in range(81):
                t=start+(end-start)*j/80
                probes.append(dict(time=t,expected=value(c,t),tolerance=6e-5,metric=phase))
        c.update(netlist=netlist(c),signals=["out","vin"],probes=probes,metrics=[dict(name="early-reversal-slew",t1=at+10e-9,t2=at+40e-9,expected=value(c,at+40e-9)-value(c,at+10e-9),tolerance=8e-5)])
    instruction='''# 从ADC驱动级实验辨识建立动态

多路复用ADC前端需要驱动级在采集截止时刻前达到规定电压。
你要从固定闭环级的电压实验建立模型，区分小信号建立、大信号slew及固定输出范围。
不要求候选实现电流、输出阻抗或ADC的动态负载。

交付 `/work/dut.va`，模块 `identified_driver`，electrical端口 `(vin,out)`。
初始输出0 V，输入在每次完整实验的起点为给定电压，后续可以再次阶跃。
public目录有正负小阶跃、大阶跃和输出范围实验。数据为本项目原创
`behavioral_synthetic`，不是芯片实测、器件电路仿真或AD8065模型。
CSV列为time_s、vin_V、out_V；完整刺激在experiments.json，来源和精度在provenance.json。

允许输入-1至1 V，第一次阶跃后0.3至1.2 us可再次改变输入，
每个输入段保持至少0.3 us，观察总长不超过3 us。温度、闭环gain与负载固定。
需要预测相同系统在完整隐藏实验中的输出，不需要唯一恢复内部补偿或拓扑。
允许任意辨识方法，不能把一条公开轨迹相邻点划成训练和验收。

验收在初始建立、第二次采集截止窗口和晚期tail分别检查电压误差，均不超过60 uV。
反转后10至40 ns的电压变化误差不超过80 uV。输入1 ps边沿两侧5 ns不查波形。
特别检查小幅尾部与相反极性的大跳变。平均RMSE、仅最终gain或只报slew不能替代这些检查。
公开网表可自测；只提交dut.va，不读取隐藏材料、不写文件、不执行系统命令。
'''
    package(TASK,"identified_driver",instruction,source("ADC驱动级建立时间","https://www.analog.com/media/en/reference-design-documentation/reference-designs/CN0269.pdf","本题只模拟固定条件下的电压闭环级。资料中真实ADC负载、RC和电流设计没有转移为候选要求。建立时间须进入且保持误差带；目标波形和采集时刻误差是独立合同。","忽略slew、错误bandwidth、忽略输出范围和memoryless响应"),hidden,public,dict(conditions="fixed closed-loop gain and load, zero output initial state, s/V units, 1 ps test input edges",observation_precision="12 significant digits"),FIT)


if __name__=="__main__":build()
