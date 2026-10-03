"""Build the six private Harbor pilot tasks from preserved source assets.

No simulator output is used to generate expected values. Digital expectations
come from state transitions / pulse calendars; the opamp uses an independent ODE.
"""
from pathlib import Path
import json
import math
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / 'benchmark/reference/veriloga'
TASKS = ROOT / 'benchmark/tasks'
COMMON = '''Write a self-contained Spectre-compatible Verilog-A model to `/work/dut.va`.
Use standard `disciplines.vams` and `constants.vams` headers as needed. All ports
use the electrical discipline. Preserve the module, port order, parameter names,
and bus indices specified below. Do not read external files, launch processes,
or inspect simulator identity. Equivalent implementations are accepted.

The evaluator checks transient behavior, initialization, multiple legal parameter
settings, and external loading where specified. Only this specification is provided;
the reference source and tests are hidden. No simulator feedback is available in
this one-shot track. Return only the complete Verilog-A source, without explanation.
The runner saves your response as `/work/dut.va`.
'''


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def source(rel):
    return (REF / rel).read_text().replace('"discipline.h"', '"disciplines.vams"').replace('"constants.h"', '"constants.vams"')


def pwl(name, node, points):
    values = ' '.join(f'{t:.14g} {v:.14g}' for t, v in points)
    return f'{name} ({node} 0) vsource type=pwl wave=[{values}]\n'


def steps(values, period, edge=1e-10, offset=0):
    out = [(0, values[0])]
    for i, value in enumerate(values[1:], 1):
        t = offset + i * period
        out.extend([(t, values[i-1]), (t+edge, value)])
    return out


def interp(points, t):
    for (a, x), (b, y) in zip(points, points[1:]):
        if t <= b:
            return x + (y-x) * max(0, t-a)/(b-a)
    return points[-1][1]


def case(name, wiring, nodes, stop, dt, samples, edges=None, extra=''):
    netlist = ('simulator lang=spectre\nglobal 0\nahdl_include "dut.va"\n' + extra + wiring
               + 'simulatorOptions options reltol=1e-5 vabstol=1e-8 iabstol=1e-13\n'
               + f'tran tran stop={stop:.14g} maxstep={dt:.14g} errpreset=conservative\n'
               + 'save ' + ' '.join(nodes) + '\n')
    return dict(name=name, netlist=netlist, samples=samples, edges=edges or [], stop=stop)


def point(node, t, value, atol=.015):
    return dict(node=node, t=t, value=value, atol=atol)


def task(name, rel, spec, oracle, cases, adaptations):
    p = TASKS / name
    write(p/'instruction.md', COMMON+'\n'+spec.strip()+'\n')
    write(p/'task.toml', f'''schema_version = "1.4"
[metadata]
name = "{name}"
category = "verilog-a"
source_group = "{rel.split('/')[0]}"
purpose = "private capability screen; not a validated benchmark release"
[agent]
timeout_sec = 900
[verifier]
timeout_sec = 600
[environment]
build_timeout_sec = 600
cpus = 1
memory_mb = 1024
storage_mb = 2048
''')
    write(p/'environment/Dockerfile', 'FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c\nWORKDIR /work\n')
    write(p/'solution/dut.va', oracle)
    write(p/'solution/solve.sh', '#!/bin/sh\nset -eu\nmkdir -p /work\ncp /solution/dut.va /work/dut.va\n')
    write(p/'tests/test.sh', '#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nexec python3 verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}"\n')
    shutil.copyfile(ROOT/'benchmark/checkers/spectre_waveform.py', p/'tests/verify.py')
    write(p/'tests/cases.json', json.dumps(cases, indent=2)+'\n')
    write(p/'SOURCE.md', f'# 来源与改编\n\n原始资产：[veriloga/{rel}](../../reference/veriloga/{rel})。\n完整历史来源见 [SOURCES.md](../../reference/veriloga/SOURCES.md)。\n\n{adaptations}\n\n原始文件未修改。该题评估明确规格到 Verilog-A 的一次性实现，不评估从模糊需求提出模型的能力。\n')


def and2():
    rel='lab/logic/and2.va'
    spec='''## Two-input analog logic AND (control task)
Module `and2(out, in1, in2)`. Inputs in1,in2; output out.
Parameters: real vh=1.1, vl=0, vth=0.55, td=0, tt=0 (seconds for td,tt).
The target output is vh exactly when BOTH inputs are strictly greater than vth,
otherwise vl. Detect threshold crossings so a large solver timestep does not miss
changes. Drive the output through transition(target,td,tt), including correct DC
and initial output. tt=0 is permitted (simulator minimum transition applies).
Tested inputs do not linger exactly on the threshold; vh>vl, td>=0, tt>=0.
'''
    cases=[]
    for index,(vh,vl,vth,td,tt) in enumerate([(1.1,0,.55,2e-9,.4e-9),(1.8,-.2,.7,4e-9,.7e-9)]):
        a=[0,1,1,0,0,1,1,0];b=[0,0,1,1,0,1,0,1]
        av=[vth+.3 if x else vth-.2 for x in a];bv=[vth+.4 if x else vth-.3 for x in b]
        wiring=pwl('A','a',steps(av,20e-9))+pwl('B','b',steps(bv,20e-9))
        wiring+=f'DUT (y a b) and2 vh={vh} vl={vl} vth={vth} td={td} tt={tt}\n'
        samples=[point('y',i*20e-9+10e-9,vh if x and z else vl) for i,(x,z) in enumerate(zip(a,b))]
        for i in range(1,len(a)):
            samples.append(point('y',i*20e-9+td/2,vh if a[i-1] and b[i-1] else vl))
        es=[i*20e-9+.5e-10+td+tt/2 for i in range(1,len(a)) if (a[i] and b[i])!=(a[i-1] and b[i-1])]
        cases.append(case(f'levels-delay-{index}',wiring,['y'],160e-9,.15e-9,samples,[dict(node='y',threshold=(vh+vl)/2,times=es,atol=.3e-9,start=5e-9)]))
    task('va01-and2',rel,spec,source(rel).replace('voltage ', 'electrical '),cases,'按实际表达式定义为 AND，纠正原注释 NAND；端口统一 electrical。增加电平、阈值、延迟参数扰动。')


def sar():
    rel='lab/calibration_control/sar_logic_7bit.va'
    spec='''## Seven-bit asynchronous SAR control
Module `L2_7bit_sar_logic(CLKC,CLKS,DCMPP,DCMPN,CMPCK,DO,DCTRLP,DCTRLN)`.
Input scalars CLKC,CLKS,DCMPP,DCMPN; output CMPCK; output buses DO[6:0],
DCTRLP[6:1],DCTRLN[6:1]. Parameters real vdd=1.1,t_logic_delay=200p.
Logic threshold vdd/2, levels 0/vdd. Output rise/fall time is 10ps.

On initial_step and every rising CLKS, reset the bit index to 6 and all outputs
to zero. A rising CLKC starts a conversion by setting CMPCK high. A rising edge
on either comparator output DCMPP or DCMPN acknowledges the comparison:
set CMPCK low; if index>=0, store (DCMPP>DCMPN) in DO[index]. For index>=1,
a stored one sets DCTRLN[index]=1; a stored zero sets DCTRLP[index]=1.
Previously written bits and controls persist until reset; unselected controls stay 0.
The falling edge of the asserted comparator output advances to the next index;
reassert CMPCK iff another bit remains (index>=0 after decrement). After bit 0,
CMPCK remains low. Its target transitions are delayed by t_logic_delay; bus
targets have zero delay. After completion, no further comparator pulses occur
until reset. A subsequent CLKS resets the whole conversion, including DO.
Stimuli are one-hot comparator pulses, with non-simultaneous separated edges;
CLKC is a single start pulse after reset, and CLKS never overlaps a comparison.
Legal tests use vdd>0 and t_logic_delay>=0, including vdd>2V.
'''
    oracle='''`include "disciplines.vams"
module L2_7bit_sar_logic(CLKC,CLKS,DCMPP,DCMPN,CMPCK,DO,DCTRLP,DCTRLN);
input CLKC,CLKS,DCMPP,DCMPN; output CMPCK; output [6:0] DO; output [6:1] DCTRLP,DCTRLN;
electrical CLKC,CLKS,DCMPP,DCMPN,CMPCK; electrical [6:0] DO; electrical [6:1] DCTRLP,DCTRLN;
parameter real vdd=1.1,t_logic_delay=200p;
integer step,ck,d[0:6],p[1:6],n[1:6]; genvar i;
analog begin
 @(initial_step or cross(V(CLKS)-vdd/2,+1)) begin
  step=6;ck=0;
  for(i=0;i<7;i=i+1)d[i]=0;
  for(i=1;i<7;i=i+1)begin p[i]=0;n[i]=0;end
 end
 @(cross(V(CLKC)-vdd/2,+1))ck=1;
 @(cross(V(DCMPP)-vdd/2,+1) or cross(V(DCMPN)-vdd/2,+1))begin
  ck=0;
  if(step>=0)d[step]=(V(DCMPP)>V(DCMPN));
  if(step>=1)begin if(d[step])n[step]=1;else p[step]=1;end
 end
 @(cross(V(DCMPP)-vdd/2,-1) or cross(V(DCMPN)-vdd/2,-1))begin
  step=step-1; if(step>=0)ck=1;
 end
 V(CMPCK)<+transition(ck*vdd,t_logic_delay,10p);
 for(i=0;i<7;i=i+1)V(DO[i])<+transition(d[i]*vdd,0,10p);
 for(i=1;i<7;i=i+1)begin V(DCTRLP[i])<+transition(p[i]*vdd,0,10p);V(DCTRLN[i])<+transition(n[i]*vdd,0,10p);end
end
endmodule
'''
    cases=[]
    for ix,(vdd,delay,words) in enumerate([(1.1,.2e-9,[89,0,127]),(2.5,.6e-9,[42,100,3])]):
        # Comparator responses arrive on a specified schedule. Check every handshake
        # edge as well as the state on both sides; no hidden reactive oracle circuit.
        period=180e-9; high=3e-9; samples=[]; edges=[]
        signals={key:[(0,0)] for key in ['reset','start','cp','cn']}
        def pulse(key,t,width):
            signals[key].extend([(t,0),(t+20e-12,vdd),(t+width,vdd),(t+width+20e-12,0)])
        for conv,word in enumerate(words):
            base=conv*period; pulse('reset',base+2e-9,1e-9);pulse('start',base+8e-9,1e-9)
            edges.append(base+8e-9+10e-12+delay+5e-12)
            d=0;p=0;n=0
            for bit in range(6,-1,-1):
                t=base+16e-9+(6-bit)*20e-9;one=(word>>bit)&1
                pulse('cp' if one else 'cn',t,high)
                edges.append(t+10e-12+delay+5e-12)
                if bit>0:edges.append(t+high+10e-12+delay+5e-12)
                d|=one<<bit
                if bit>0:
                    if one:n|=1<<bit
                    else:p|=1<<bit
                for k in range(7):samples.append(point(f'd{k}',t+2e-9,vdd*((d>>k)&1)))
                for k in range(1,7):
                    samples.extend([point(f'p{k}',t+2e-9,vdd*((p>>k)&1)),point(f'n{k}',t+2e-9,vdd*((n>>k)&1))])
                samples.append(point('ck',t+2e-9,0))
                samples.append(point('ck',t+7e-9,vdd if bit else 0))
            for node in ['ck']+[f'd{k}' for k in range(7)]+[f'{s}{k}' for s in ['p','n'] for k in range(1,7)]:
                samples.append(point(node,base+5e-9,0))
            samples.append(point('ck',base+170e-9,0))
        nodes=['ck']+[f'd{k}' for k in range(6,-1,-1)]+[f'p{k}' for k in range(6,0,-1)]+[f'n{k}' for k in range(6,0,-1)]
        wiring=''.join(pwl('V'+k,k,v) for k,v in signals.items())
        wiring+=f'DUT (start reset cp cn {" ".join(nodes)}) L2_7bit_sar_logic vdd={vdd} t_logic_delay={delay}\n'
        cases.append(case(f'handshake-{ix}',wiring,nodes,period*len(words),.1e-9,samples,[dict(node='ck',threshold=vdd/2,times=edges,atol=.08e-9,start=1e-9)]))
    task('va02-sar-handshake',rel,spec,oracle,cases,'保留七位逐次逼近握手及互补 CDAC 控制；明确初始化、整字复位和 10ps 输出边沿。原代码把布尔位与 vdd/2 比较，改编规格明确按布尔值选极性，因此可测试 2.5V。首轮使用预定比较器反馈脉冲，逐边检查握手，尚未验证真实比较器闭环。')


ZOOM_DEFAULT=dict(vdd=1.1,init_delay=5e-9,trise=.1e-9,tfall=.1e-9,RST_period=3200e-9,RST_width=9.5e-9,S_delay=10e-9,S_interval=800e-9,S_width=50e-9,S_num=4,SAR_delay=65e-9,SAR_width=2.5e-9,SAR_interval=5e-9,SAR_num=7,RES_delay=105e-9,RES_width=20e-9,RES_interval=80e-9,RES_num=8,INT_delay=130e-9,INT_width=25e-9,INT_interval=80e-9,INT_num=8,ZOOM_delay=160e-9,ZOOM_width=2.5e-9,ZOOM_interval=5e-9,ZOOM_num=4)


def zoom():
    rel='lab/clock_sampling/zoom_sar_multiphase_clock.va'
    spec='''## Periodic ZOOM/SAR ADC timing generator
Module `CLOCK_VA(RST,S,SAR,RES,INT,CLK_SAR,ZOOM,CLK_ZOOM,RST_ZOOM)`;
all ports are outputs. Every output starts low. High level vdd, low 0; use
transition(target,0,trise,tfall). Target pulse start times and widths below are
before transition smoothing. For every m>=0 define B=init_delay+m*RST_period.
Indices i=0..S_num-1, j and k as indicated:

| Output | Start time | Width |
|---|---|---|
|RST|B|RST_width|
|S|B+S_delay+i*S_interval|S_width|
|SAR|B+SAR_delay+i*S_interval|SAR_num*SAR_interval|
|CLK_SAR|B+SAR_delay+i*S_interval+j*SAR_interval, j<SAR_num|SAR_width|
|RES|B+RES_delay+i*S_interval+j*RES_interval, j<RES_num|RES_width|
|INT|B+INT_delay+i*S_interval+j*INT_interval, j<INT_num|INT_width|
|ZOOM|B+ZOOM_delay+i*S_interval+j*INT_interval, j<INT_num|ZOOM_num*ZOOM_interval|
|CLK_ZOOM|B+ZOOM_delay+i*S_interval+j*INT_interval+k*ZOOM_interval, j<INT_num,k<ZOOM_num|ZOOM_width|
|RST_ZOOM|B+INT_delay+i*S_interval+j*INT_interval+INT_width+0.5ns, j<INT_num|4ns|

Defaults (SI units, *_num are integer, others real):
'''+ '\n'.join(f'- `{k} = {v:.14g}`' for k,v in ZOOM_DEFAULT.items())+'''

Tests use positive counts and intervals, positive edge times much shorter than pulse
widths, and pulses of each individual output that do not overlap or cross its next
RST period. Different outputs may overlap intentionally. Counts and delays vary.
'''
    oracle=source(rel).replace('voltage ', 'electrical ')
    oracle=re.sub(r'@\(initial_step\) begin.*?\n\s*end', '@(initial_step) begin\n rst=0;s=0;sar=0;res=0;int=0;zoom=0;phi_sar=0;phi_zoom=0;rst_zoom=0;\n end',oracle,count=1,flags=re.S)
    cases=[]
    for ix,changes in enumerate([{},dict(vdd=1.5,S_num=2,S_interval=500e-9,RST_period=1100e-9,SAR_num=5,RES_num=3,INT_num=3,ZOOM_num=3,init_delay=11e-9,S_width=37e-9,SAR_delay=56e-9,ZOOM_delay=161e-9,trise=.2e-9,tfall=.15e-9)]):
        p=ZOOM_DEFAULT|changes; pulses={n:[] for n in ['RST','S','SAR','RES','INT','CLK_SAR','ZOOM','CLK_ZOOM','RST_ZOOM']}
        def add(n,t,w):pulses[n].append((t,t+w))
        for m in range(2):
            b=p['init_delay']+m*p['RST_period'];add('RST',b,p['RST_width'])
            for i in range(p['S_num']):
                q=b+i*p['S_interval'];add('S',q+p['S_delay'],p['S_width']);add('SAR',q+p['SAR_delay'],p['SAR_num']*p['SAR_interval'])
                for j in range(p['SAR_num']):add('CLK_SAR',q+p['SAR_delay']+j*p['SAR_interval'],p['SAR_width'])
                for n in ['RES','INT']:
                    for j in range(p[n+'_num']):add(n,q+p[n+'_delay']+j*p[n+'_interval'],p[n+'_width'])
                for j in range(p['INT_num']):
                    z=q+p['ZOOM_delay']+j*p['INT_interval'];add('ZOOM',z,p['ZOOM_num']*p['ZOOM_interval'])
                    add('RST_ZOOM',q+p['INT_delay']+j*p['INT_interval']+p['INT_width']+.5e-9,4e-9)
                    for k in range(p['ZOOM_num']):add('CLK_ZOOM',z+k*p['ZOOM_interval'],p['ZOOM_width'])
        samples=[];edges=[];stop=2*p['RST_period']
        for n,ps in pulses.items():
            times=[]
            for a,b in sorted(ps):
                samples.extend([point(n,a-.3e-9,0),point(n,(a+b)/2,p['vdd']),point(n,b+.5e-9,0)])
                times.extend([a+p['trise']/2,b+p['tfall']/2])
            edges.append(dict(node=n,threshold=p['vdd']/2,times=times,atol=.09e-9,start=1e-9))
        wiring='DUT ('+' '.join(pulses)+') CLOCK_VA '+' '.join(f'{k}={v:.14g}' for k,v in p.items())+'\n'
        cases.append(case(f'calendar-{ix}',wiring,list(pulses),stop,.25e-9,samples,edges))
    task('va03-zoom-timing',rel,spec,oracle,cases,'保留全部九路定时输出和嵌套周期关系；显式初始化内部状态为零，端口统一 electrical。测试默认与改变计数/延时参数的两组配置，各覆盖两个周期。')


def calibration():
    rel='lab/calibration_control/pipeline_adc_gain_calibration_nested_view.va'
    spec='''## Alternating pipeline ADC gain calibration controller
Module `TEST_D2A_PIPE_ADC_GAIN_CAL(DIN2,DOUT1,CLKS,GAINCTRL,DDIFF,DOP,DOM,GCTRLCODE)`.
Inputs DIN2[6:0],CLKS; outputs DOUT1[3:0],GAINCTRL[6:0] and scalar diagnostics.
Parameters real Vlo=0,Vhi=0.9,Vth=0.45,tt=100p; integer gaincodeinit=90 (0..127).
Use tt for every output's rise/fall transition, no delay. Bus bit 0 is LSB.

Initially: gain code=gaincodeinit, DOUT1=8, stored positive ADC code P=96,
stored negative ADC code M=32, difference D=0. At successive rising CLKS edges:
1. First/odd edge: decode DIN2 bits using strict >Vth; update M. Keep D,P,gain
   unchanged; set DOUT1=7.
2. Second/even edge: update P from DIN2; set D=P-M (signed), then update
   gain = clamp(gain + 64 - D, 0, 127); set DOUT1=8.
Repeat. Falling clocks do nothing. DIN2 can change between edges without changing
stored state. Drive DOUT1 and GAINCTRL as logic buses Vlo/Vhi. Diagnostic voltage
DDIFF=D/100 V, DOP=P/100 V, DOM=M/100 V, GCTRLCODE=gain/100 V, regardless of Vhi.
Legal tests vary levels, thresholds, tt, initial code, and ADC code sequence;
negative differences and both clipping boundaries must work.
'''
    oracle=source(rel).replace(',0,10p)',',0,tt)')
    cases=[]
    for ix,(init,hi,lo,threshold,seq) in enumerate([(90,.9,0,.45,[32,100,32,96,0,127,0,127,127,0,20,90]),(5,1.6,-.1,.6,[0,127,0,127,127,0,127,0,10,74,30,80])]):
        period=20e-9;clk=[(0,0)];wiring='';samples=[];states=[];g=init;p=96;m=32;d=0
        states.append((2e-9,g,p,m,d,8))
        for i,code in enumerate(seq):
            t=10e-9+i*period
            clk.extend([(t,0),(t+.1e-9,hi),(t+5e-9,hi),(t+5.1e-9,0)])
            if i%2==0:m=code;out=7
            else:p=code;d=p-m;g=max(0,min(127,g+64-d));out=8
            states.extend([(t+3e-9,g,p,m,d,out),(t+15e-9,g,p,m,d,out)])
        for bit in range(7):wiring+=pwl(f'VD{bit}',f'in{bit}',steps([hi if (x>>bit)&1 else lo for x in seq],period))
        wiring+=pwl('CLK','clk',clk)
        nodes=[f'o{i}' for i in range(3,-1,-1)]+[f'g{i}' for i in range(6,-1,-1)]+['diff','pos','neg','gc']
        ports=[f'in{i}' for i in range(6,-1,-1)]+nodes[:4]+['clk']+nodes[4:]
        wiring+='DUT ('+' '.join(ports)+f') TEST_D2A_PIPE_ADC_GAIN_CAL Vlo={lo} Vhi={hi} Vth={threshold} tt=0.2n gaincodeinit={init}\n'
        for t,g,p,m,d,out in states:
            for b in range(4):samples.append(point(f'o{b}',t,hi if (out>>b)&1 else lo))
            for b in range(7):samples.append(point(f'g{b}',t,hi if (g>>b)&1 else lo))
            for n,v in zip(['diff','pos','neg','gc'],[d,p,m,g]):samples.append(point(n,t,v/100,.002))
        cases.append(case(f'updates-clamps-{ix}',wiring,nodes,len(seq)*period+10e-9,.2e-9,samples))
    task('va04-gain-calibration',rel,spec,oracle,cases,'保留两相码采样、64 LSB 目标差、增益步进和饱和机制。原始 tt 未被使用，改编明确用 tt 控制全部输出边沿；没有声称任意实际 ADC 植物模型下都收敛。')


def vco():
    rel='cadence/clock_pll/dig_vco__icadvm201.va'
    spec='''## Phase-continuous voltage-controlled square-wave oscillator
Module `dig_vco(vin,vout)`. Input vin, output vout. Real parameters:
center_freq=2500 (Hz), vco_gain=1 (Hz/V), vlogic_high=5, vlogic_low=0,
tdel=0, trise=1n, tfall=1n (seconds). Instantaneous frequency
f(t)=center_freq+vco_gain*V(vin). All test frequencies are strictly positive.

At t=0 accumulated phase in cycles is zero and the target output is high.
Accumulate the time integral of instantaneous frequency continuously; do not reset
phase when vin changes. The target is high when fractional phase is in [0,0.5),
low in [0.5,1). Output transition(target,tdel,trise,tfall). Control is constant or
piecewise linear, including changes during an oscillator half-cycle. Need correct
edge times across many cycles and parameter changes. No frequency clipping or
random noise is required. tdel>=0, trise,tfall>0; output levels may be nonzero-low.
'''
    oracle=source(rel).replace('integ_dir = 1.0;', 'integ_dir = 1.0;\n         vout_val = vlogic_high;')
    cases=[]
    for ix,(fc,kv,points,hi,lo,delay) in enumerate([(1e6,2e6,[(0,0),(2.13e-6,0),(2.14e-6,.7),(5.7e-6,.2),(8e-6,.8),(12e-6,.8)],1.2,0,2e-9),(2e6,-.8e6,[(0,.2),(1.73e-6,.2),(4.1e-6,.9),(4.11e-6,-.4),(9e-6,-.4)],2.5,-.3,5e-9)]):
        edge_times=[];acc=0;nextphase=.5
        for (a,va),(b,vb) in zip(points,points[1:]):
            fa=fc+kv*va;slope=kv*(vb-va)/(b-a);total=fa*(b-a)+.5*slope*(b-a)**2
            while nextphase<=acc+total+1e-12:
                target=nextphase-acc;low=0;high=b-a
                for _ in range(65):
                    mid=(low+high)/2
                    if fa*mid+.5*slope*mid*mid<target:low=mid
                    else:high=mid
                edge_times.append(a+(low+high)/2+delay+1e-9);nextphase+=.5
            acc+=total
        samples=[];bounds=[10e-9]+edge_times+[points[-1][0]]
        for j,(a,b) in enumerate(zip(bounds,bounds[1:])):
            if b-a>20e-9:samples.append(point('out',(a+b)/2,hi if j%2==0 else lo))
        wiring=pwl('VIN','in',points)+f'DUT (in out) dig_vco center_freq={fc} vco_gain={kv} vlogic_high={hi} vlogic_low={lo} tdel={delay} trise=2n tfall=2n\n'
        cases.append(case(f'phase-integral-{ix}',wiring,['out'],points[-1][0],1e-9,samples,[dict(node='out',threshold=(hi+lo)/2,times=edge_times,atol=2e-9,start=10e-9)]))
    task('va05-dynamic-vco',rel,spec,oracle,cases,'显式规定初始输出为高，补全原例未赋值的 vout_val；保留频率积分与事件翻转。独立判据对分段线性频率积分并求半周期交点，不从参考波形抽取。')


def opamp():
    rel='cadence/analog/opamp.va'
    spec='''## Loaded, slew-limited single-pole opamp macro model
Module `opamp(vout,vref,vin_p,vin_n,vspply_p,vspply_n)`; all electrical;
vout,vin_p,vin_n inout, other ports input. Real parameters with defaults:
gain=835e3, freq_unitygain=1e6 Hz, rin=1e6 ohm, vin_offset=0 V,
ibias=0 A, iin_max=100u A, slew_rate=0.5e6 V/s, rout=80 ohm, vsoft=0.5 V.
All resistance, frequency, gain, current limit, slew rate and vsoft are positive.

Implement this behavioral circuit (not a hard-clipped voltage source):
- Differential input branch vin_p -> vin_n carries (V(vin_p,vin_n)+vin_offset)/rin.
  Each input receives a bias current ibias flowing from vref to that input.
- Let x be an internal dominant-pole node voltage relative to vref.
  C=iin_max/slew_rate, gm=2*pi*freq_unitygain*C, R=gain/gm.
  A current clip(gm*(V(vin_p,vin_n)+vin_offset),-iin_max,+iin_max) enters x.
  From x to vref connect C, R, and a 100 megaohm shunt in parallel.
- The output is a Thevenin source of voltage x relative to vref with series
  resistance rout. External resistive and capacitive loads must participate in
  the circuit solution; do not force the unloaded output voltage on vout.
- Let y=V(vout) (absolute ground-referenced). Add current leaving the internal
  node: gm*(y-V(vspply_p)+vsoft) if y>V(vspply_p)-vsoft;
  gm*(y-V(vspply_n)-vsoft) if y<V(vspply_n)+vsoft; otherwise zero.
  This is soft-limit feedback, not hard output clipping.
- Use the normal DC operating point to initialize energy storage. No forced
  zero initial condition. No supply-current/power-conservation model is required.

Tests include small-signal gain/dominant-pole response, both polarities of slew
and saturation/recovery, load-dependent response, input bias/offset and finite
input resistance, and a nonzero vref. Equivalent circuit realizations are accepted.
'''
    cases=[]
    configs=[dict(gain=40,fu=2e6,imax=80e-6,slew=2e6,rout=100,rl=1000,cl=40e-12,hi=2.5,lo=-2.5,vref=0,offset=0,ibias=0,rin=1e6,values=[0,.01,-.006,0]),dict(gain=100,fu=1e6,imax=100e-6,slew=.7e6,rout=80,rl=800,cl=100e-12,hi=1.5,lo=-1.5,vref=0,offset=0,ibias=0,rin=1e6,values=[0,.3,-.3,0]),dict(gain=25,fu=1.7e6,imax=60e-6,slew=1.2e6,rout=160,rl=500,cl=80e-12,hi=3,lo=-1,vref=.7,offset=.002,ibias=3e-6,rin=2e4,values=[.001,.005,-.009,-.002])]
    for ix,p in enumerate(configs):
        period=5e-6;stop=20e-6;dt=.5e-9;wave=steps(p['values'],period,20e-9)
        wiring=pwl('VP','inp',[(t,v+p['vref']) for t,v in wave])
        wiring+=f'VN (inn 0) vsource dc={p["vref"]}\nVR (ref 0) vsource dc={p["vref"]}\nVHI (hi 0) vsource dc={p["hi"]}\nVLO (lo 0) vsource dc={p["lo"]}\n'
        wiring+=f'RL (out ref) resistor r={p["rl"]}\nCL (out ref) capacitor c={p["cl"]}\n'
        wiring+=f'DUT (out ref inp inn hi lo) opamp gain={p["gain"]} freq_unitygain={p["fu"]} iin_max={p["imax"]} slew_rate={p["slew"]} rout={p["rout"]} vin_offset={p["offset"]} ibias={p["ibias"]} rin={p["rin"]}\n'
        c=p['imax']/p['slew'];gm=2*math.pi*p['fu']*c;r=p['gain']/gm
        def rhs(t,x,y):
            vin=interp(wave,t)+p['offset'];drive=max(-p['imax'],min(p['imax'],gm*vin))
            absolute=y+p['vref'];feedback=gm*(max(0,absolute-p['hi']+.5)+min(0,absolute-p['lo']-.5))
            return (drive-x/r-x/1e8-feedback)/c,((x-y)/p['rout']-y/p['rl'])/p['cl']
        # Solve the unsaturated initial DC equilibrium independently. Case 2 has
        # a nonzero operating point, so forcing zero storage is observable.
        x=gm*(p['values'][0]+p['offset'])/(1/r+1e-8)
        y=x*p['rl']/(p['rl']+p['rout']);samples=[];h=dt
        for j in range(round(stop/h)+1):
            t=j*h
            if j%200==0 and j>0:
                samples.append(point('out',t,y+p['vref'],.004))
                vin=interp(wave,t)+p['offset']
                samples.extend([point('VP:p',t,p['ibias']-vin/p['rin'],2e-8),point('VN:p',t,p['ibias']+vin/p['rin'],2e-8)])
            if j==round(stop/h):break
            a=rhs(t,x,y);b=rhs(t+h/2,x+h*a[0]/2,y+h*a[1]/2);c2=rhs(t+h/2,x+h*b[0]/2,y+h*b[1]/2);d=rhs(t+h,x+h*c2[0],y+h*c2[1])
            x+=h*(a[0]+2*b[0]+2*c2[0]+d[0])/6;y+=h*(a[1]+2*b[1]+2*c2[1]+d[1])/6
        cases.append(case(f'loaded-ode-{ix}',wiring,['out','VP:p','VN:p'],stop,2e-9,samples))
    task('va06-loaded-opamp',rel,spec,source(rel),cases,'原例电路方程不改；头文件名称标准化。规格明确电流方向、软限幅和外部负载，不要求此非功率守恒宏模型具备电源电流真实性。三组独立 RK4 数值解作电压判据，解析输入支路电流作额外判据。')


def main():
    for builder in [and2,sar,zoom,calibration,vco,opamp]:builder()
    print('Built six Harbor tasks; no model evaluation performed by this command.')


if __name__=='__main__':main()
