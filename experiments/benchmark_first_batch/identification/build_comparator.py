"""Original strobed voltage comparator, observable overdrive-delay behavior."""
import csv
import io
import math
from build_common import *

TASK="identify-comparator-overdrive"
DP,DN,K,Q=4e-9,6e-9,1.4e-10,.004


def delay(v):return (DP if v>0 else DN)+K/(abs(v)+Q)


def experiment(name,amps,widths):
    return dict(name=name,amplitudes=amps,widths=widths,period=120e-9,first_rise=20e-9,stop=len(amps)*120e-9)


def level(c,t):
    k=min(int(t/c["period"]),len(c["amplitudes"])-1)
    start=c["first_rise"]+k*c["period"];end=start+c["widths"][k]
    v=c["amplitudes"][k];due=start+delay(v);sign=1 if v>0 else -1
    if due>=end:return 0
    if t<due:return 0
    if t<due+1e-9:return sign*(t-due)/1e-9
    if t<end:return sign
    if t<end+1e-9:return sign*(1-(t-end)/1e-9)
    return 0


def netlist(c):
    vin=[(0,c["amplitudes"][0])];clk=[(0,0)]
    for k,v in enumerate(c["amplitudes"]):
        start=c["first_rise"]+k*c["period"];end=start+c["widths"][k]
        if k:
            at=k*c["period"]
            vin.extend([(at,c["amplitudes"][k-1]),(at+1e-12,v)])
        clk.extend([(start,0),(start+1e-12,1),(end,1),(end+1e-12,0)])
    vin.append((c["stop"],c["amplitudes"][-1]));clk.append((c["stop"],0))
    return HEADER+pwl("vin",vin)+pwl("clk",clk)+"DUT (vin clk out) identified_comparator\n"+OPTIONS+f"tran tran stop={c['stop']:.12g} maxstep=1e-10 errpreset=conservative\nsave out vin clk\n"


FIT=FIT_IMPORTS+'''def fit(public):
    xs=[];ys=[]
    for c in json.loads((public/"experiments.json").read_text()):
        rows=read(public,c)
        for k,v in enumerate(c["amplitudes"]):
            start=c["first_rise"]+k*c["period"];end=start+c["widths"][k]
            direction=1 if v>0 else -1;threshold=.5*direction
            for a,b in zip(rows,rows[1:]):
                if start<a["time_s"]<end and direction*(a["out_V"]-threshold)<0<=direction*(b["out_V"]-threshold):
                    at=a["time_s"]+(b["time_s"]-a["time_s"])*(threshold-a["out_V"])/(b["out_V"]-a["out_V"])
                    xs.append((abs(v),int(v<0)));ys.append(at-start-.5e-9);break
    best=None
    for j in range(1,2001):
        q=j*1e-5
        design=[[1,sign,1/(v+q)] for v,sign in xs]
        p=regress(design,ys)
        error=sum((sum(a*b for a,b in zip(x,p))-y)**2 for x,y in zip(design,ys))
        if best is None or error<best[0]:best=(error,p,q)
    d,asym,k=best[1]
    return d,d+asym,k,best[2]

def model(parameters,variant="reference"):
    dp,dn,k,q=parameters
    cancel="if (active > 0.5 && V(clk)>0.5)"
    if variant=="constant-delay":dp=dn=(dp+dn)/2+k/(.08+q);k=0
    if variant=="symmetric-delay":dn=dp
    if variant=="late-after-reset":cancel=""
    if variant=="wrong-dispersion":k*=.25
    return f\'''`include "constants.vams"
`include "disciplines.vams"
module identified_comparator(vin,clk,out);
input vin,clk;output out;electrical vin,clk,out;
real due,active,pending,result,d;
analog begin
  @(initial_step) begin due=1e9;active=0;pending=0;result=0;end
  @(cross(V(clk)-0.5,+1)) begin
    pending=(V(vin)>0)?1:-1;
    d=((V(vin)>0)?{dp:.15g}:{dn:.15g})+{k:.15g}/(abs(V(vin))+{q:.15g});
    due=$abstime+d;active=1;
  end
  @(cross(V(clk)-0.5,-1)) begin result=0;active=0;end
  @(timer(due)) begin {cancel} result=pending;end
  V(out)<+transition(result,0,1e-9,1e-9);
end
endmodule
\'''
'''+FIT_MAIN


def build():
    public=[experiment("public-low-positive",[.008,.016,.03],[60e-9]*3),experiment("public-high-positive",[.065,.16,.55],[80e-9]*3),experiment("public-low-negative",[-.01,-.024,-.047],[65e-9]*3),experiment("public-high-negative",[-.09,-.28,-.7],[75e-9]*3)]
    for c in public:
        buf=io.StringIO();w=csv.writer(buf,lineterminator="\n");w.writerow(["time_s","vin_V","clk_V","out_V"])
        for j in range(3601):
            t=c["stop"]*j/3600;k=min(int(t/c["period"]),len(c["amplitudes"])-1);start=c["first_rise"]+k*c["period"]
            w.writerow([f"{t:.12g}",c["amplitudes"][k],int(start<=t<start+c["widths"][k]),f"{level(c,t):.12g}"])
        write(TASK,f"environment/public/data/{c['name']}.csv",buf.getvalue());write(TASK,f"environment/public/{c['name']}.scs",netlist(c))
    hidden=[experiment("unseen-lowdrive",[.012,-.018,.041],[55e-9]*3),experiment("mixed-polarity",[-.13,.23,-.62],[62e-9]*3),experiment("aborted-decision",[.009,-.014,.3],[6e-9,7e-9,50e-9]),experiment("near-boundary",[.006,-.007,.77],[80e-9]*3)]
    for c in hidden:
        probes=[];events=[]
        for k,v in enumerate(c["amplitudes"]):
            start=c["first_rise"]+k*c["period"];end=start+c["widths"][k];due=start+delay(v);sign=1 if v>0 else -1
            if due<end:
                events.append(dict(name=f"decision-{k}",node="out",level=.5*sign,direction=sign,start=start,end=end,expected_times=[due+.5e-9],tolerance=.35e-9))
                events.append(dict(name=f"reset-{k}",node="out",level=.5*sign,direction=-sign,start=end-2e-9,end=(k+1)*c["period"],expected_times=[end+.5e-9],tolerance=.35e-9))
            else:
                events.append(dict(name=f"cancel-{k}",node="out",level=.5*sign,direction=sign,start=start,end=(k+1)*c["period"],expected_times=[],tolerance=.35e-9))
            for j in range(61):
                t=k*c["period"]+(j+.1)*c["period"]/61
                if min(abs(t-due),abs(t-end),abs(t-start))<2e-9:continue
                probes.append(dict(time=t,expected=level(c,t),tolerance=1e-4,metric="decision-level-and-cancellation"))
        c.update(netlist=netlist(c),signals=["out","vin","clk"],probes=probes,crossings=events)
    instruction='''# 辨识受控比较器的过驱动延时

这个原创受控比较器是ADC决策路径的电压行为模型。
它在clk上升沿读取已经建立的差分输入vin，经过延时输出正负决策，clk下降沿复位。
小差分输入可能比大输入慢，正负路径的延时也可能不同。

交付 `/work/dut.va`，模块 `identified_comparator`，electrical端口 `(vin,clk,out)`。
初始out为0。正输入的有效输出是+1 V，负输入是-1 V，复位态为0。
输出边沿时间1 ns。clk下降沿取消尚未完成的决策，不能在复位后输出旧结果。
公开数据为本项目 `behavioral_synthetic`，没有使用器件测量或厂商宏模型。
public目录提供正负、多幅度、不同决策窗口的完整CSV和刺激，单位s、V。

输入绝对值在0.006至0.8 V，必须在clk上升沿前至少10 ns建立并保持到下降沿。
clk周期120 ns，首次上升沿在20 ns；高电平6至80 ns，实验可包含不同幅度和极性。
温度、common-mode、供电、负载固定。无须辨识random jitter、metastability概率或输入电流。
你不需要唯一恢复内部比较器电路，只需预测可观察决策与延时。

终评按完整隐藏实验测量0到正负1 V边沿50% crossing，
每次有效决策和复位的crossing时间误差不超过0.35 ns，数量必须正确。
复位取消的实验不能出现迟到的crossing。离事件2 ns以外的稳定电平误差不超过100 uV。
不能只拟合单个幅度、忽略极性或用总体RMSE掩盖延时。
可使用public网表自测。最终只交dut.va，不读隐藏文件、不写文件、不执行系统命令。
'''
    package(TASK,"identified_comparator",instruction,source("比较器传播延时与过驱动","https://www.analog.com/en/resources/technical-articles/parameters-that-affect-comparator-propagation-delay-measurements.html","资料支持overdrive、slew和测量条件影响传播延时。本题是原创strobed差分决策接口，未宣称复刻文档中的continuous-time器件。","固定延时、忽略正负不对称、复位后迟到决策和错误dispersion"),hidden,public,dict(conditions="fixed supply/common-mode/load, vin established before strobe, output transition 1 ns, CSV linear-edge interpolation is behavioral observation",observation_precision="12 significant digits"),FIT)


if __name__=="__main__":build()
