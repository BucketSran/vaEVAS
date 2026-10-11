"""Build OTA task packages; actual source observations are generated separately."""
from pathlib import Path
import json,shutil,re
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
IMAGE='python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c'
CAL=[]
def put(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
HEAD='`include "disciplines.vams"\n'
AMP=HEAD+'''module ota(vin,enable,vout);
input vin,enable; output vout; electrical vin,enable,vout; electrical q;
parameter real tau=20n, positive=10e6, negative=6e6, gain=.98, low=.1, high=1.4;
real target,rate;
analog begin
 target=.75+gain*(V(vin)-.75);
 if(target<low) target=low; if(target>high) target=high;
 if(V(enable)<.75) begin target=0; rate=(target-V(q))/50n; end
 else begin
 rate=(target-V(q))/tau;
 if(rate>positive) rate=positive;
 if(rate< -negative) rate= -negative;
 end
 V(q)<+idt(rate,0);
 V(vout)<+V(q);
 $bound_step(.25n);
end
endmodule
'''
ALT=AMP.replace('V(q)<+idt(rate,0);','I(q)<+ddt(V(q))-rate;').replace('electrical q;','electrical q;\n// The disabled DC solution initializes the capacitor at zero.')
def package(slug,action,title,contract,ref,alt,cases,public,mutants,dut=None):
 normalize=lambda s:'\n'.join(line.rstrip() for line in re.sub(r'(?<![\w.])\.(\d)',r'0.\1',s).splitlines())+'\n'
 ref=normalize(ref);alt=normalize(alt)
 mutants={n:(normalize(t),v,w) for n,(t,v,w) in mutants.items()}
 if dut:dut=normalize(dut)
 for c in cases+public:
  if 'support' in c:c['support']={n:normalize(t) for n,t in c['support'].items()}
 taskid='v3-ota-'+slug;task=ROOT/'benchmark/tasks'/taskid
 put(task/'instruction.md',f'# {title}\n\n{contract}\n\n交付 `/work/dut.va`；只修改此文件。固定后端 Spectre，候选原字节执行，后端编译或执行故障须诊断，不能自动计为语义零分。公开自测 `/work/public/cases.json` 和只读外围可用，终评只改变公开范围内的完整实验条件。权重 1。\n')
 put(task/'SOURCE.md',f'# 来源和权限\n\n规格 #147 {slug}，来源组 jku-ota-dynamics。A1/A3 为仓库原创固定负载电压合同及测量实现。A2 真值独立来自 JKU 晶体管 OTA ngspice 仿真，非实测、非 A1 合成。来源、工具和校准身份见 experiments/benchmark_next/ota/README.md。保留同源关联，不以不同参数增加题数。Spectre 候选运行的同题开源等价尚未证明。\n')
 put(task/'task.toml',f'schema_version = "1.4"\n[metadata]\nname = "{taskid}"\ncategory = "verilog-a"\nengineering_action = "{action}"\nsource_group = "jku-ota-dynamics"\nweight = 1\n[agent]\ntimeout_sec = 900\n[verifier]\ntimeout_sec = 600\n[environment]\nbuild_timeout_sec = 600\ncpus = 1\nmemory_mb = 1024\nstorage_mb = 2048\n')
 put(task/'environment/Dockerfile',f'FROM {IMAGE}\nWORKDIR /work\nCOPY public/ /work/public/\nCOPY starter.va /work/dut.va\n')
 put(task/'environment/starter.va',ref[:ref.index('analog begin')]+'analog begin\n// Implement the public contract.\nend\nendmodule\n')
 put(task/'environment/public/cases.json',json.dumps(public,indent=None if slug=='data-model' else 2)+'\n')
 if dut:put(task/'environment/public/dut.va',dut)
 put(task/'solution/dut.va',ref);put(task/'solution/solve.sh','#!/bin/sh\nset -eu\ncp /solution/dut.va /work/dut.va\n')
 put(task/'tests/test.sh','#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nexec python3 verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}" --tests . "$@"\n')
 put(task/'tests/verify.py','from v2_runtime import main\nfrom v2_next_ota import evaluate\nif __name__ == "__main__": main(evaluate)\n')
 put(task/'tests/contract.json',json.dumps(dict(candidate_files=['dut.va'],output_files=[],task_id=taskid),indent=2)+'\n')
 put(task/'tests/cases.json',json.dumps(cases,indent=None if slug=='data-model' else 2)+'\n')
 for n in ['v2_runtime.py','v2_next_ota.py','adc_linearity.py']:shutil.copyfile(ROOT/'benchmark/checkers'/n,task/'tests'/n)
 for p in [task/'solution/solve.sh',task/'tests/test.sh']:p.chmod(0o755)
 variants={'reference':(ref,True,'author reference'),'alternate':(alt,True,'different state/event representation')};variants.update(mutants)
 for name,(text,expected,why) in variants.items():
  p=OUT/'candidates'/taskid/name/'dut.va';put(p,text);CAL.append(dict(task=str(task.relative_to(ROOT)),variant=name,candidate=str(p.parent.relative_to(ROOT)),expected_pass=expected,semantic_behavior=why))

def pwl(points):return ' '.join(f'{t:.12g} {v:.12g}' for t,v in points)
def model_case(name,points,enable,kind='continuous'):
 stop=points[-1][0]
 net=f'simulator lang=spectre\nglobal 0\nahdl_include "dut.va"\nVi (vin 0) vsource type=pwl wave=[{pwl(points)}]\nVe (enable 0) vsource type=pwl wave=[{pwl(enable)}]\nX (vin enable vout) ota\ntran tran stop={stop:g} maxstep=250p\nsave vin enable vout\n'
 return dict(name=name,kind=kind,stop=stop,netlist=net,signals=['vin','enable','vout'],input=points,enable=enable,atol=.004)
def continuous():
 # Input edges are fixed 1 ns linear ramps; include simultaneous enable/input transitions.
 def seq(vals,shift=0):
  p=[(0,.75)];e=[(0,0),(10e-9+shift,0),(11e-9+shift,1.5)]
  for t,v in vals:p += [(t+shift,p[-1][1]),(t+shift+1e-9,v)]
  p += [(1.4e-6,p[-1][1])];e += [(850e-9+shift,1.5),(851e-9+shift,0),(950e-9+shift,0),(951e-9+shift,1.5),(1.4e-6,1.5)]
  return p,e
 vals=[(10e-9,.79),(200e-9,.73),(400e-9,1.3),(600e-9,.15),(750e-9,1.8),(1000e-9,.75),(1150e-9,-.2),(1250e-9,.78)]
 public=[model_case('public',*seq(vals))]
 cases=[model_case('heldout-'+str(i),*seq([(t,v+(i-1)*.013) for t,v in vals],i*3e-9)) for i in range(3)]
 contract='''实现 `ota(vin,enable,vout)`。固定供电 1.5 V、50 fF 用途，端口是对地电压，候选无需端口电流或可变负载耦合。输入 -0.2 至 1.8 V，enable为0或1.5 V，1 ns线性沿。

连续状态 y(0)=0。enable<0.75时 dy/dt=-y/(50 ns)，否则目标 T=clip(0.75+0.98*(vin-0.75),0.1,1.4)，dy/dt=clip((T-y)/(20 ns),-0.006,+0.010) V/ns；vout=y。小信号是指数建立，大信号进入正负不同压摆区。只有目标限幅，状态不清零且不积累目标之外的过载。解除限幅后继续从当前状态恢复。启动、输入与enable同时变化时直接按瞬时电压应用此方程。所有输出观察点绝对误差不超过4 mV，最大step 250 ps。外围固定，模型内部实现自由。'''
 wrong={'static':(AMP.replace('V(vout)<+V(q);','V(vout)<+target;'),False,'static follower loses continuous history'),'symmetric-slew':(AMP.replace('negative=6e6','negative=10e6'),False,'negative slew_metric incorrectly equals positive'),'single-tau':(AMP.replace('if(rate>positive) rate=positive;','').replace('if(rate< -negative) rate= -negative;',''),False,'all amplitudes use linear pole'),'reset-on-disable':(AMP.replace('rate=(target-V(q))/50n','rate=(target-V(q))/.1n'),False,'disable incorrectly clears continuous state')}
 package('continuous','spec-modeling','连续 OTA 有限带宽与压摆',contract,AMP,ALT,cases,public,wrong)

def measurement():
 ref=(OUT/'measurement.va').read_text()
 alt=ref.replace('final_value=final_value+values[j]/20','final_value=final_value+values[339-j]/20').replace('if(abs(values[j]-final_value)>.003) lastbad=j+1;','if(abs(values[j]-final_value)>.003 && j+1>lastbad) lastbad=j+1;')
 # Different streaming statistic implementation: compute slew_metric incrementally at sampling.
 alt=alt.replace('values[index]=V(vout);index=index+1;','if(index==0) begin peak=0;last_value=before_output;end\n   if(abs(V(vout)-last_value)>peak) peak=abs(V(vout)-last_value);last_value=V(vout);\n   values[index]=V(vout);index=index+1;').replace('lastbad=0;peak=0;last_value=before_output;','lastbad=0;').replace('if(abs(values[j]-last_value)>peak) peak=abs(values[j]-last_value);','')
 dut=AMP.replace('module ota(', 'module measurement_dut(')
 signals=['vin','enable','launch','vout','gain','slew_metric','settle','valid','status','direction']
 def case(name,tau,pos,neg,gain):
  net=f'simulator lang=spectre\nglobal 0\nahdl_include "dut.va"\nahdl_include "support.va"\nXD (vin enable vout) measurement_dut tau={tau:g} positive={pos:g} negative={neg:g} gain={gain:g}\nXM (vin enable launch vout gain slew_metric settle valid status direction) stimulus_meter\ntran tran stop=1.4u maxstep=100p\nsave '+ ' '.join(signals)+'\n'
  return dict(name=name,kind='measurement',stop=1.4e-6,netlist=net,signals=signals,resolution=100e-12,dut_parameters=dict(tau=tau,positive=pos,negative=neg,gain=gain),support={'support.va':dut})
 public=[case('public',20e-9,1e7,6e6,.98)]
 cases=[case('heldout-healthy',17e-9,8e6,5e6,.97),case('heldout-slow',300e-9,1e6,.6e6,.96),case('heldout-asymmetric',23e-9,1.2e7,3.5e6,.99)]
 contract='''实现 `stimulus_meter(vin,enable,launch,vout,gain,slew_metric,settle,valid,status,direction)`。vout是只读观测，其余是候选驱动。DUT源码 `/work/public/dut.va` 可读，仅通过波形测量，不能拿内部参数或预计表冒充实际结果。

输入初始0.75 V；enable初始0，在10 ns升1.5 V。200、400、600、800、1000、1200 ns依次驱动vin为0.8、0.7、1.2、0.3、1.6、0.75 V，边沿10 ps。每个阶跃同时升launch=1并清valid/status=0。每轮在阶跃后1至180 ns按1 ns采样vout。阶跃前的vin与vout为基准。尾20点均值F作为有限窗口稳态估计；gain=(F-基准输出)/(新输入-基准输入)，单位V/V；slew为相邻采样点及基准至首点的最大绝对输出差，单位V/ns。direction为输入正负方向，+1或-1。

建立判据是相对F的3 mV带内，lastbad为最后越带样本编号1至180，无越带为0。lastbad<=160才表示连续末20样本建立，settle=lastbad+1 ns；否则settle=180 ns。完成后status依次优先4表示输入跨度<20 mV、3表示F<=0.105或>=1.395 V限幅、1表示建立、2表示窗口未建立。valid仅status=1时为1。测量慢或限幅DUT时，报告对应状态也可通过。完成后launch=0，报告保持至下一轮；新一轮不得沿用旧valid。

DUT隐藏条件仅改变tau=17至300 ns、正slew=0.001至0.012 V/ns、负slew=0.0006至0.006 V/ns、gain=0.96至0.99；其余合同相同。独立checker从实际激励与波形计算指标，gain误差<=0.003，slew_metric<=0.001 V/ns，settle<=2 ns，状态和方向误差<=0.01 V。'''
 wrong={'pulse-only':(ref.replace('V(vin)<+transition(input_value,0,10p);','V(vin)<+transition(input_value,0,10p);').replace('V(enable)<+transition(enable_value,0,10p);','V(enable)<+transition(enable_value,0,10p);V(enable)<+((active && index>2)?-1.5:0);'),False,'turns off DUT after check points instead of holding experiment'), 'one-direction':(ref.replace('report_direction=(span>0)?1:-1','report_direction=1'),False,'negative direction missing'),'old-valid':(ref.replace('index=0;report_valid=0;report_status=0;','index=0;report_status=0;'),False,'new event preserves old valid'),'first-entry':(ref.replace('if(abs(values[j]-final_value)>.003) lastbad=j+1;','if(abs(values[j]-final_value)>.003 && lastbad==0) lastbad=j+1;'),False,'uses first instead of last band violation'),'parameter-oracle':(ref.replace('report_gain=(abs(span)>=.02)?(final_value-before_output)/span:0;','report_gain=.98;'),False,'nominal gain substitutes observed gain')}
 package('step-measurement','testing-characterization','连续 OTA 双向阶跃测量',contract,ref,alt,cases,public,wrong,dut)


def data_task():
 ref=(OUT/'data_reference.va').read_text()
 alt=ref.replace('V(b)<+idt(db,0);V(q)<+idt(dq,0);V(d)<+idt(dd,0);','I(b)<+ddt(V(b))-db;I(q)<+ddt(V(q))-dq;I(d)<+ddt(V(d))-dd;')
 def case(record):
  c=model_case(record['record_id'],record['input'],record['enable'],'data')
  c['netlist']=c['netlist'].replace('maxstep=250p','maxstep=50p')
  c['resolution']=50e-12;c['truth']=[[r[0],r[3]] for r in record['rows']]
  windows=[[10e-9,1e-6,'disabled-initial',.002,.010],[1e-6,1.4e-6,'startup',.020,.100]]
  for i,t in enumerate([3e-6,5e-6,7e-6,9e-6,11e-6,13e-6]):
   label='small' if i<2 else 'recovery' if i==5 else 'large'
   rms,peak=(.002,.008) if i<2 else (.020,.075)
   windows += [[t,t+40e-9,label+'-'+str(i),rms,peak],[t+200e-9,min(t+1.9e-6,14.5e-6),'steady-'+str(i),.006,.012]]
  windows += [[14.5e-6,14.7e-6,'shutdown',.03,.10],[15e-6,15.4e-6,'restart',.020,.100],[15.5e-6,17e-6,'long-tail',.006,.012]]
  c['windows']=windows
  return c
 source=OUT/'observations';public=[case(json.loads((source/(n+'.json')).read_text())) for n in ['train-0','train-1','train-2']]
 private=OUT/'heldout';cases=[case(json.loads((private/(n+'.json')).read_text())) for n in ['test-0','test-1','test-2']]
 contract='''从三个固定完整表征实验建立自由运行电压模型 `ota(vin,enable,vout)`。数据来自真实 JKU improved OTA 的晶体管 ngspice 仿真，不是台架实测，也不是 A1 的行为合成。固定 1.5 V供电、27°C、IHP SG13CMOS5L tt、50 fF，5 µA偏置在1.1至1.2 µs线性爬升，其后固定。初始输出IC=0，全部前置输入与enable历史在记录中，输入0.33至1.44 V、输入沿5 ns、enable沿100 ns。原源电路和PDK说明在public/source。候选可选择自己的内部状态和结构，无输出反馈、无在线源电路查询，不允许回放已知输出轨迹。

公开完整记录 `/work/public/observations/*.json` 的列为秒、输入V、enable V、输出V。`input` 和 `enable` 字段精确给出线性重构激励；密集动态段与稀疏静态段均保留原时间。训练实验与独立新完整留出实验分开，不随机拆点。公开自测三个完整训练记录可用。

误差分别在每个窗口检查，安静段不能稀释动态误差。初始数值冲击的前10 ns不评分，其完整原始观察仍提供。启动与重启400 ns窗口RMS<=20 mV、峰值<=100 mV；两个小阶跃40 ns窗口RMS<=2 mV、峰值<=8 mV；大阶跃、进入高端限幅与恢复40 ns窗口RMS<=20 mV、峰值<=75 mV；每次变化后200 ns至下一变化前100 ns（13 µs恢复的窗口在14.5 µs关断开始时结束）的稳态，以及最后1.5 µs长尾RMS<=6 mV、峰值<=12 mV；shutdown200 ns窗口RMS<=30 mV、峰值<=100 mV；初始关闭段RMS<=2 mV、峰值<=10 mV。各窗口实际观察时间不平移。误差是本用途的近似模型合同，不声称晶体管精确等价。'''
 wrong={'static':(ref.replace('V(vout)<+V(q);','V(vout)<+((V(enable)>0.9)?dc_curve(V(vin)):0);'),False,'static curve loses startup and dynamic response'),'single-pole':(ref.replace('dq=V(d)*1e9;dd=', 'dq=err/20n;dd='),False,'one fixed time constant does not explain amplitude dynamics'),'no-startup':(ref.replace('bias_drive=(V(enable)>0.9)?bias:0;', 'bias_drive=(V(enable)>0.9)?1:0;').replace('if(V(b)<0.95)', 'if(V(b)<0)'),False,'omits startup bias behavior'),'clear-recovery':(ref.replace('V(b)<+idt(db,0);','if(V(vin)<1.3 && V(q)>1.3) dq=err/0.01n;\n V(b)<+idt(db,0);'),False,'clears rail history on recovery')}
 package('data-model','data-modeling','从真实 OTA 完整轨迹建立连续模型',contract,ref,alt,cases,public,wrong)
 task=ROOT/'benchmark/tasks/v3-ota-data-model'
 (task/'environment/public/observations').mkdir(parents=True,exist_ok=True)
 for p in source.glob('*.json'):shutil.copyfile(p,task/'environment/public/observations'/p.name)
 (task/'environment/public/source').mkdir(parents=True,exist_ok=True)
 for p in (OUT/'source').glob('*'):
  if p.suffix in ['.sch','.spice'] or p.name.startswith('LICENSE'):shutil.copyfile(p,task/'environment/public/source'/p.name)
 put(task/'environment/public/source/README.md', (OUT/'README.md').read_text())

if __name__=='__main__':
 CAL.clear();continuous();measurement();data_task();put(OUT/'calibration-plan.json',json.dumps(CAL,indent=2)+'\n')
