"""Deterministic #149 task materialization. No simulator or model API calls."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
HEADER='`include "constants.vams"\n`include "disciplines.vams"\n'

def va(name,ports,params,body,extra=''):
    return HEADER+f'module {name}({ports});\ninout {ports};\nelectrical {ports};\n'+params+'\n'+extra+'\nanalog begin\n'+body+'\nend\nendmodule\n'

CTLE_PARAMS='parameter real fz=1000, fp1=4000, fp2=12000, gain=1, x1init=0, x2init=0;'
CTLE=va('ctle','u,y',CTLE_PARAMS,
'''V(a) <+ idt(2*`M_PI*fp1*(V(u)-V(a)),x1init);
V(b) <+ idt(2*`M_PI*fp2*(V(a)-V(b)),x2init);
V(y) <+ gain*(V(b)+fp2/fz*(V(a)-V(b)));''','electrical a,b;')
CTLE_ALT=va('ctle','u,y',CTLE_PARAMS,
'''V(a) <+ idt(2*`M_PI*fp1*(V(u)-V(a)),x1init);
V(d) <+ idt(2*`M_PI*fp1*(V(u)-V(a))-2*`M_PI*fp2*V(d),x1init-x2init);
V(y) <+ gain*(V(a)+(fp2/fz-1)*V(d));''','electrical a,d;')
LP_PARAMS='parameter real base=1000, initval=0; integer c;'
LP=va('programmable_lp','u,code,reset,y',LP_PARAMS,
'''c=min(3,max(0,floor(V(code)+0.5)));
V(y) <+ idt(2*`M_PI*base*pow(2,c)*(V(u)-V(y)),initval,V(reset)>0.5);''')
LP_ALT=va('programmable_lp','u,code,reset,y',LP_PARAMS+' real rate;',
'''c=min(3,max(0,floor(V(code)+0.5))); rate=base;
if(c==1) rate=2*base; else if(c==2) rate=4*base; else if(c==3) rate=8*base;
V(z) <+ idt(2*`M_PI*rate*(V(u)-initval-V(z)),0,V(reset)>0.5);
V(y) <+ initval+V(z);''','electrical z;')
IQ_PARAMS='parameter real gain=1, fbw=2000;'
IQ=va('iq_mixer','i,q,lc,ls,rf,en,up,di,dq',IQ_PARAMS,
'''V(a) <+ idt(2*`M_PI*fbw*(2*V(rf)*V(lc)-V(a)),0);
V(b) <+ idt(2*`M_PI*fbw*(-2*V(rf)*V(ls)-V(b)),0);
V(up) <+ (V(en)>0.5) ? gain*(V(i)*V(lc)-V(q)*V(ls)) : 0;
V(di) <+ (V(en)>0.5) ? V(a) : 0;
V(dq) <+ (V(en)>0.5) ? V(b) : 0;''','electrical a,b;')
IQ_ALT=va('iq_mixer','i,q,lc,ls,rf,en,up,di,dq',IQ_PARAMS,
'''V(s) <+ idt(2*`M_PI*fbw*(2*V(rf)*(V(lc)-V(ls))-V(s)),0);
V(d) <+ idt(2*`M_PI*fbw*(2*V(rf)*(V(lc)+V(ls))-V(d)),0);
V(up) <+ (V(en)>0.5) ? gain*((V(i)-V(q))*(V(lc)+V(ls))+(V(i)+V(q))*(V(lc)-V(ls)))/2 : 0;
V(di) <+ (V(en)>0.5) ? (V(s)+V(d))/2 : 0;
V(dq) <+ (V(en)>0.5) ? (V(s)-V(d))/2 : 0;''','electrical s,d;')
ENV_PARAMS='parameter real bandwidth=200, initval=0; real power;'
ENV=va('envelope','i,q,en,reset,env',ENV_PARAMS,
'''power=(V(en)>0.5)?V(i)*V(i)+V(q)*V(q):0;
V(e) <+ idt(2*`M_PI*bandwidth*(power-V(e)),initval,V(reset)>0.5);
V(env) <+ sqrt(max(V(e),0));''','electrical e;')
ENV_ALT=va('envelope','i,q,en,reset,env',ENV_PARAMS,
'''power=(V(en)>0.5)?pow(V(i),2)+pow(V(q),2):0;
V(z) <+ idt(2*`M_PI*bandwidth*(power/2-V(z)),initval/2,V(reset)>0.5);
V(env) <+ sqrt(max(2*V(z),0));''','electrical z;')
SWEEP_PARAMS='''parameter real f0=1000,f1=4000,f2=16000,f3=8000, amplitude=0.12,
slot=0.02,settle=0.004,window=0.008;
integer idx; real tloc,freq,amp,theta,active,g,p,v,den,num,ph;'''
SWEEP=va('sweep_meter','drive,sense,gain,phase,valid',SWEEP_PARAMS,
'''@(initial_step) begin g=0; p=0; v=0; end
idx=min(3,floor($abstime/slot)); tloc=$abstime-idx*slot;
freq=f0; if(idx==1) freq=f1; else if(idx==2) freq=f2; else if(idx==3) freq=f3;
amp=(idx==2)?0.0001:amplitude; theta=2*`M_PI*freq*tloc;
V(drive) <+ amp*sin(theta);
active=(tloc>=settle && tloc<=settle+window);
V(ai) <+ idt(V(drive)*sin(theta)*active,0,!active);
V(bi) <+ idt(V(drive)*cos(theta)*active,0,!active);
V(ao) <+ idt(V(sense)*sin(theta)*active,0,!active);
V(bo) <+ idt(V(sense)*cos(theta)*active,0,!active);
@(timer(settle+window,slot)) begin
 den=sqrt(V(ai)*V(ai)+V(bi)*V(bi)); num=sqrt(V(ao)*V(ao)+V(bo)*V(bo));
 v=(2*den/window>=0.01 && window*freq>=6 && settle>=0.003)?1:0;
 if(v>0.5) begin g=num/den; ph=atan2(V(bo),V(ao))-atan2(V(bi),V(ai));
 p=atan2(sin(ph),cos(ph)); end else begin g=0; p=0; end
end
V(gain) <+ g; V(phase) <+ p; V(valid) <+ v;
$bound_step(1/(freq*100));''','electrical ai,bi,ao,bo;')
# Same actual synchronous measurement, explicit quadrature coefficient scaling.
SWEEP_ALT=SWEEP.replace('V(drive)*sin(theta)*active','2*V(drive)*sin(theta)*active/window').replace('V(drive)*cos(theta)*active','2*V(drive)*cos(theta)*active/window').replace('V(sense)*sin(theta)*active','2*V(sense)*sin(theta)*active/window').replace('V(sense)*cos(theta)*active','2*V(sense)*cos(theta)*active/window').replace('2*den/window>=0.01','den>=0.01').replace('ph=atan2(V(bo),V(ao))-atan2(V(bi),V(ai))','ph=atan2(V(bo)*V(ai)-V(ao)*V(bi),V(ao)*V(ai)+V(bo)*V(bi))')
DUT=va('healthy_lowpass','u,y','parameter real fc=1500,g=1;',
       'V(x) <+ idt(2*`M_PI*fc*(V(u)-V(x)),0); V(y) <+ g*V(x);','electrical x;')


def netlist(lines,signals,stop,step,support=False):
    return 'simulator lang=spectre\nahdl_include "dut.va"\n'+('ahdl_include "healthy.va"\n' if support else '')+'\n'.join(lines)+f'\ntran tran stop={stop} maxstep={step} errpreset=conservative\nsave '+ ' '.join(signals)+'\n'

def sine(node,amp,freq,phase=0):
    # Spectre phase is degrees.
    return f'V{node} ({node} 0) vsource type=sine ampl={amp} freq={freq} sinephase={phase*180/3.141592653589793+90}'

def case(kind,name,params,lines,signals,stop,step,support=None):
    item=dict(kind=kind,name=name,parameters=params,signals=signals,stop=stop,step=step,
              netlist=netlist(lines,signals,stop,step,support is not None),timeout_s=120)
    if support: item['support']={'healthy.va':support}
    return item


def build():
    tasks=[]
    cp=[]
    for n,scale in enumerate([1,1.5]):
        p=dict(fz=1000*scale,fp1=4000*scale,fp2=12000*scale,gain=1+n*.3,x1init=.07*n,x2init=-.03*n,tones=[500,2000,8000,16000])
        # Summed independent sources in series provide a real multitone input.
        lines=[f'Vdc (u n0) vsource dc={.03+n*.02}']
        for j,f in enumerate(p['tones']):lines.append(sine(f'n{j}',.035,f,.2*j).replace(f'(n{j} 0)',f'(n{j} '+(f'n{j+1}' if j<3 else '0')+')'))
        lines.append('X (u y) ctle '+' '.join(f'{k}={v}' for k,v in p.items() if k!='tones'))
        cp.append(case('ctle',f'ctle-{n}',p,lines,['u','y'],.012,1e-6))
    tasks.append(('ctle','C1','spec-modeling','verilogalib-ctle',CTLE,CTLE_ALT,cp,
                  {'unnormalized':CTLE.replace('gain*(V(b)+','gain*2*(V(b)+'),
                   'hz-as-radians':CTLE.replace('2*`M_PI*',''),
                   'zero-initval':CTLE.replace(',x1init)',',0)').replace(',x2init)',',0)')},
'''实现模块 `ctle(u,y)`。参数 `fz,fp1,fp2` 单位 Hz，合法范围分别为 500–2000、2000–8000、8000–24000，gain 为 0.5–2。
传递函数 H(s)=gain*(1+s/(2πfz))/((1+s/(2πfp1))*(1+s/(2πfp2)))，直流增益为 gain。
初态合同：x1'=2πfp1*(u-x1)，x2'=2πfp2*(x1-x2)，y=gain*(x2+fp2/fz*(x1-x2))；x1(0)=x1init、x2(0)=x2init，均在 ±0.1。
允许任何等价内部实现。输出电压误差不超过 0.006 V；稳态复数频响误差不超过目标模长的 3%（目标模长不足1时绝对上限0.03）。验收 DC、多个频点和非零初态恢复。'''))
    lp=[]
    for n in range(2):
        p=dict(base=800+400*n,initval=.06*n)
        lines=[sine('u',.2,700+300*n,.4*n), 'Vc (code 0) vsource type=pwl wave=[0 0 0.002 0 0.002001 3 0.004 3 0.004001 1 0.007 1 0.007001 2]',
               'Vr (reset 0) vsource type=pwl wave=[0 0 0.005 0 0.005001 1 0.0055 1 0.005501 0]',
               f'X (u code reset y) programmable_lp base={p["base"]} initval={p["initval"]}']
        lp.append(case('programmable',f'codes-{n}',p,lines,['u','code','reset','y'],.009,1e-6))
    baseline=va('fixed_lp','u,reset,y','parameter real base=1000,initval=0;',
                'V(y) <+ idt(2*`M_PI*base*(V(u)-V(y)),initval,V(reset)>0.5);')
    tasks.append(('programmable-lp','C2','extension-integration','v4-334',LP,LP_ALT,lp,
                 {'fixed-cutoff':LP.replace('pow(2,c)','1'),
                  'reset-on-code':LP.replace('V(reset)>0.5','(V(reset)>0.5 || V(code)>2.5)'),
                  'ignore-reset':LP.replace(',V(reset)>0.5',',0')},
'''从公开 `fixed_lp.va` 的健康固定低通扩展模块 `programmable_lp(u,code,reset,y)`。
参数 base 单位 Hz（800–1200），initval 是初态及复位电压（±0.1）。code 电压在0–3，c=clip(round(code),0,3)。fc=base*2^c。
连续状态 y'=2πfc*(u-y)，y(0)=initval。code 跨舍入阈值即时改变速率，必须保持 y 连续，不清空历史。
reset>0.5 时 y=initval；释放后从此状态积分。码0必须保留基线行为。输出误差上限0.008 V，复位切换的模拟过渡区除外。
固定基线可读且不能修改；交付可任意选择等价实现，不强制沿用内部形式。'''))
    iq=[]
    for n in range(2):
        p=dict(gain=1+.2*n,fbw=2000+n*500,flo=12000+n*2000,fbb=500,phase=.3+n*.5)
        lines=[sine('i',.18,p['fbb'],.2),sine('q',.18,p['fbb'],.2-3.141592653589793/2),
               sine('lc',1,p['flo'],p['phase']),sine('ls',1,p['flo'],p['phase']-3.141592653589793/2),
               sine('rf',.2,p['flo']+700+n*300,.7+n*.3),
               'Ve (en 0) vsource type=pwl wave=[0 1 0.007 1 0.007001 0 0.008 0 0.008001 1]',
               f'X (i q lc ls rf en up di dq) iq_mixer gain={p["gain"]} fbw={p["fbw"]}']
        iq.append(case('iq',f'conversion-{n}',p,lines,['i','q','lc','ls','rf','en','up','di','dq'],.01,1e-6))
    tasks.append(('iq-conversion','C3a','spec-modeling','v4-364+400',IQ,IQ_ALT,iq,
                  {'q-sign':IQ.replace('-V(q)*V(ls)','+V(q)*V(ls)').replace('-2*V(rf)*V(ls)','2*V(rf)*V(ls)'),
                   'no-down-filter':IQ.replace('V(di) <+ (V(en)>0.5) ? V(a)','V(di) <+ (V(en)>0.5) ? 2*V(rf)*V(lc)'),
                   'ignore-enable':IQ.replace('(V(en)>0.5)','(1>0)')},
'''实现固定模块 `iq_mixer(i,q,lc,ls,rf,en,up,di,dq)`，输入是实际电压，LO 为健康外部正弦，lc=cos θ、ls=sin θ。
启用时 up=gain*(i*lc-q*ls)。gain 为0.5–2。真实I/Q输入应搬移至和频侧带，不能直接合成目标载波。
下变频连续状态 a'=2πfbw*(2*rf*lc-a)、b'=2πfbw*(-2*rf*ls-b)，初态均为0，fbw为1500–3000 Hz。
di=a、dq=b；en<=0.5 时三个输出均为0，内部低通状态继续积分。重新启用后显露该状态。
LO为10–16kHz；基带100–1000Hz，RF频偏在±1500Hz。无噪声、限幅、镜像抑制指标。
上变频逐点误差上限0.002V，下变频0.008V，和频幅值误差0.015V。'''))
    env=[]
    for n in range(2):
        p=dict(bandwidth=150+100*n,initval=.01*n)
        lines=['Vi (i 0) vsource type=pwl wave=[0 0.1 0.001 0.1 0.001001 0.4 0.003 0.4 0.003001 0.05 0.008 0.05]',
               'Vq (q 0) vsource type=pwl wave=[0 0.12 0.002 0.12 0.002001 -0.2 0.007 -0.2]',
               'Ve (en 0) vsource type=pwl wave=[0 1 0.004 1 0.004001 0 0.006 0 0.006001 1]',
               'Vr (reset 0) vsource type=pwl wave=[0 0 0.0068 0 0.006801 1 0.007 1 0.007001 0]',
               f'X (i q en reset env) envelope bandwidth={p["bandwidth"]} initval={p["initval"]}']
        env.append(case('envelope',f'dynamics-{n}',p,lines,['i','q','en','reset','env'],.009,1e-6))
    tasks.append(('envelope','C3b','spec-modeling','v4-336',ENV,ENV_ALT,env,
                  {'instant-envelope':ENV.replace('sqrt(max(V(e),0))','sqrt(max(power,0))'),
                   'wrong-bandwidth':ENV.replace('2*`M_PI*bandwidth','bandwidth'),
                   'disable-holds':ENV.replace(':0;',':V(e);')},
'''实现 `envelope(i,q,en,reset,env)`，连续能量状态 e'=2πbandwidth*(P-e)，env=sqrt(max(e,0))。
P=i²+q²（en>0.5）；禁用时P=0，因此包络指数衰减而非保持或瞬间归零。bandwidth为100–300Hz。
e(0)=initval，initial为0–0.02 V²。reset>0.5 时 e=initval，释放后继续积分。
输入I、Q在±0.5V。本题为包络动力学的独立交付，与混频题不构成完整接收机计数。
误差上限0.01V，复位切换模拟过渡区除外。'''))
    sw=[]
    for n in range(3):
        p=dict(frequencies=[1000,4000,16000,8000],amplitudes=[.12,.12,.0001,.12],slot=.02,settle=.001 if n==2 else .004,window=.0013 if n==1 else .008,fc=1500+1000*n,dut_gain=1+.3*n)
        lines=[f'X (drive sense gain phase valid) sweep_meter slot={p["slot"]} settle={p["settle"]} window={p["window"]}',f'D (drive sense) healthy_lowpass fc={p["fc"]} g={p["dut_gain"]}']
        sw.append(case('sweep',f'sweep-{n}',p,lines,['drive','sense','gain','phase','valid'],.0799,2e-6,DUT))
    tasks.append(('sweep-measurement','C4','testing-characterization','original-filter-measurement',SWEEP,SWEEP_ALT,sw,
                  {'parameter-replay':SWEEP.replace('g=num/den','g=1/sqrt(1+pow(freq/1500,2))'),
                   'always-valid':SWEEP.replace('v=(2*den/window>=0.01 && window*freq>=6 && settle>=0.003)?1:0','v=1'),
                   'skip-frequency':SWEEP.replace('if(idx==1) freq=f1','if(idx==1) freq=f0'),
                   'premature-report':SWEEP.replace('@(timer(settle+window,slot))','@(timer(settle+window/4,slot))')},
'''实现 `sweep_meter(drive,sense,gain,phase,valid)`，固定只读 `healthy.va` 低通 DUT 连接drive→sense。
VA必须驱动4个频点并从实际 drive、sense 测量稳态幅相。参数f0=1000,f1=4000,f2=16000,f3=8000Hz，可在500–20000Hz；slot默认0.02秒，settle默认0.004秒，window默认0.008秒。
第k槽从 k*slot 起，drive=Ak*sin(2πfk*(t-k*slot))；Ak=amplitude（默认0.12V，合法0.05–0.2），第2槽为0.0001V。
在[槽起点+settle, 槽起点+settle+window]按真实波形同步积分，C=2/window*∫v(t)*exp(-j2πfk*(t-槽起点))dt；gain=|Cout/Cin|，phase=arg(Cout/Cin)，单位rad，范围[-π,π]。
窗末更新报告并保持到下一窗末；有效要求 |Cin|>=0.01V、window*fk>=6、settle>=0.003秒。低幅度、未稳态或窗口不足报告valid=0。有效时valid=1。
固定DUT截止频率为600–4000Hz、增益0.5–2，只读。不能读DUT参数或用公式代替实际测量。合法window为0.001–0.009秒，settle为0.001–0.005秒，且settle+window<slot。
幅值报告误差0.035，包裹相位误差0.035rad，真实激励误差0.002V。覆盖全部频点，包括无效的低幅度窗口。'''))
    manifest=[]; plan=[]
    for slug,unit,action,source,ref,alt,cases,mutants,contract in tasks:
        tid='v3-filter-'+slug; task=ROOT/'benchmark/tasks'/tid
        for folder in ['environment','public','solution','tests']:(task/folder).mkdir(parents=True,exist_ok=True)
        public=task/'environment/public';public.mkdir(exist_ok=True)
        shell=ref.split('analog begin')[0]+'analog begin\n'+ {'ctle':'V(y)<+0;','programmable-lp':'V(y)<+0;','iq-conversion':'V(up)<+0; V(di)<+0; V(dq)<+0;','envelope':'V(env)<+0;','sweep-measurement':'V(drive)<+0; V(gain)<+0; V(phase)<+0; V(valid)<+0;'}[slug]+'\nend\nendmodule\n'
        instruction=f'# {tid}\n\n'+contract+'\n\n交付文件仅为 `/work/dut.va`，保持模块名、端口和参数。公开目录提供接口壳与自测网表。只允许修改候选文件；固定DUT和工程可读。后端固定Spectre，不限制合法Verilog-A写法。自测不能代替独立终评。权重1。\n'
        (task/'instruction.md').write_text(instruction)
        (task/'task.toml').write_text(f'''schema_version = "1.4"
[metadata]
name = "{tid}"
category = "verilog-a"
engineering_action = "{action}"
source_group = "{source}"
context_level = "single-module"
weight = 1
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
        (task/'environment/Dockerfile').write_text('FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c\nWORKDIR /work\nCOPY public/ /work/public/\nRUN mkdir -p /work/output\n')
        for pub in [task/'public',public]:
            (pub/'dut.va').write_text(shell)
            (pub/'feedback.scs').write_text(cases[0]['netlist'])
            (pub/'contract.md').write_text(contract+'\n')
            if slug=='programmable-lp':(pub/'fixed_lp.va').write_text(baseline)
            if slug=='sweep-measurement':(pub/'healthy.va').write_text(DUT)
        (task/'solution/dut.va').write_text(ref)
        (task/'solution/solve.sh').write_text('#!/bin/sh\nset -eu\ncp "$(dirname "$0")/dut.va" /work/dut.va\n')
        (task/'solution/solve.sh').chmod(0o755)
        (task/'tests/contract.json').write_text(json.dumps(dict(candidate_files=['dut.va'],spec_issue=149,design_unit=unit,backend='spectre',weight=1),indent=2)+'\n')
        (task/'tests/cases.json').write_text(json.dumps(cases,indent=2)+'\n')
        (task/'tests/verify.py').write_text('from v2_runtime import main\nfrom v2_next_filter import evaluate\nif __name__=="__main__": main(evaluate)\n')
        (task/'tests/test.sh').write_text('#!/bin/sh\nset -eu\nexec python3 /tests/verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}" --tests /tests "$@"\n')
        (task/'tests/test.sh').chmod(0o755)
        for name in ['v2_next_filter.py','v2_runtime.py','adc_linearity.py']:shutil.copyfile(ROOT/'benchmark/checkers'/name,task/'tests'/name)
        (task/'SOURCE.md').write_text(f'# 来源与验收边界\n\n所属规格 #149，单元{unit}，同源组 `{source}`。\n\n来源身份、许可边界和改编见 [路线来源](../../../experiments/benchmark_next/filter/SOURCES.md)。候选、公开合同和独立 checker 为本仓库原创重建；未将旧源码当成答案。\n\n后端为Spectre扩展集；未证明候选VA具备ngspice等开源复验资格。作者校准与模型试跑分别记录，本次不运行模型实验。\n')
        variants={'reference':ref,'alternative':alt,**mutants}
        for variant,code in variants.items():
            dest=OUT/'candidates'/tid/variant;dest.mkdir(parents=True,exist_ok=True)
            (dest/'dut.va').write_text(code)
            plan.append(dict(task=str(task.relative_to(ROOT)),variant=variant,candidate_directory=str(dest.relative_to(ROOT)),expected='pass' if variant in ['reference','alternative'] else 'fail',semantic_behavior=variant,certification='pending-live-execution'))
        manifest.append(dict(task=tid,design_unit=unit,engineering_action=action,source_group=source,weight=1,conditions=len(cases),variants=list(variants),candidate_sha256={v:hashlib.sha256(code.encode()).hexdigest() for v,code in variants.items()}))
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (OUT/'run-plan.json').write_text(json.dumps(plan,indent=2)+'\n')

if __name__=='__main__':build()
