"""Deterministic LDO task packaging; does not run simulations or model trials."""
from pathlib import Path
import json,shutil,hashlib,re
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
IMAGE='python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c'
def put(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
COMMON='''\n\n## 输入与修改权限\n\n只提交 `/work/dut.va`。公开目录含实际 ADB OTA5 LDO、固定 SKY130 TT 模型、固定外围网络和公开自测。候选不得驱动观测端或修改环境、DUT、模型。固定零压串联探针观测所有候选只读端电流，任一记录点绝对值不得超过0.1nA。该上限允许数值噪声与极小输入负载，候选不能向DUT提供显著电流。目标恒为规格 1.2 V，不能取末端测量值代替。数值结果由电压报告端承载。输入输出端使用全局0作参考。正常和不合格 DUT 都按同一测量定义验收，正确报告失败也通过。\n\n本题固定 Spectre 后端，属于商业仿真器扩展集。源电路能在 ngspice 运行，但本题候选 VA 与电流环境尚未完成开源后端等价校准。公开 `public.scs` 仅是自测条件，终评在公开范围内改变固定环境。编译或后端失败属于待归因环境结果，不作为语义错版拒绝。\n'''
STARTUP='''# LDO 启动在线测量\n\n为固定晶体管 LDO 编写只读观测模块 `ldo_startup_meter(vin,vout,t90_us,overshoot_mv,settle_us,reached,settled,status,done)`。参数 `tick=50ns,ramp_start=1us,ramp_end=21us,window=70us,target=1.2,tail=20`，隐藏条件可改 ramp_end 至17..25us、window至60..80us、VIN高值至1.0..1.8V、固定RLOAD至60..240Ω、COUT至0.5..2µF。tick、target、tail固定。\n\n每个全局 i*tick 从t=0至window采样实际vout。t90是最早一个样本满足输出≥0.9*target且后续所有样本也满足的时刻，减ramp_start，单位µs。不存在则t90_us=-1,reached=0；存在则reached=1。overshoot_mv=max(0,全部样本最大值-target)*1000。建立是ramp_end后最早一个样本在target±2%且其余样本始终在带内，并至少有末20个连续样本的时刻。settle_us是该时刻减ramp_end，单位µs。不存在则settle_us=-1,settled=0。ramp_end与window为tick整数倍。\n\n任何样本出[-0.1,2.2]V则status=4；否则未达90%为2，否则未建立为3，否则为1。数值与有效位仍按各自定义输出。done在window采样后变1。全部报告端在此之前为0，此后保持至仿真结束。边沿可在5ns内过渡。终评报告误差t90/settle≤0.075µs，过冲≤0.3mV，逻辑与status≤0.002V。原来源的记录采样定义沿用；这里明确增加末20样本资格，防止末尾单点入带误报。''' + COMMON

def package(slug,instruction,ref,variants,cases,public):
 task=ROOT/'benchmark/tasks'/('v3-ldo-'+slug)
 put(task/'instruction.md',instruction+'\n')
 put(task/'task.toml',f'''schema_version = "1.4"\n[metadata]\nname = "{task.name}"\ncategory = "verilog-a"\nengineering_action = "testing-characterization"\nsource_group = "adb-ldo-ota5"\nweight = 1\n[agent]\ntimeout_sec = 1200\n[verifier]\ntimeout_sec = 900\n[environment]\nbuild_timeout_sec = 600\ncpus = 1\nmemory_mb = 2048\nstorage_mb = 2048\n''')
 put(task/'environment/Dockerfile',f'FROM {IMAGE}\nWORKDIR /work\nCOPY public/ /work/public/\nCOPY starter.va /work/dut.va\n')
 put(task/'environment/starter.va',ref[:ref.index('analog begin')]+'analog begin\nend\nendmodule\n')
 put(task/'solution/dut.va',ref);put(task/'solution/solve.sh','#!/bin/sh\nset -eu\ncp /solution/dut.va /work/dut.va\n')
 put(task/'tests/test.sh','#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nexec python3 -B verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}" --tests . "$@"\n')
 put(task/'tests/verify.py','from v2_runtime import main\nfrom v2_next_ldo import evaluate\nif __name__ == "__main__": main(evaluate)\n')
 for name in ['v2_runtime.py','v2_next_ldo.py','adc_linearity.py']:shutil.copyfile(ROOT/'benchmark/checkers'/name,task/'tests'/name)
 put(task/'tests/contract.json',json.dumps(dict(candidate_files=['dut.va'],output_files=[],task_id=task.name,category='testing-characterization',source_group='adb-ldo-ota5'),indent=2)+'\n')
 for c in cases:
  c['observation_currents']=['VOBSIN:p','VOBSOUT:p'] if c['kind']=='startup' else ['VOBSOUT:p']
  c['observation_current_atol']=1e-10
  c['support_files']={name:dict(path='assets/'+name,sha256=sha(HERE/'source'/name)) for name in ['models.spice','ldo_ota5.spi']}
 (task/'tests/assets').mkdir(exist_ok=True)
 for name in ['models.spice','ldo_ota5.spi']:shutil.copyfile(HERE/'source'/name,task/'tests/assets'/name)
 put(task/'tests/cases.json',json.dumps(cases,indent=2)+'\n')
 for p in [task/'tests/test.sh',task/'solution/solve.sh']:p.chmod(0o755)
 pub=task/'environment/public';pub.mkdir(exist_ok=True)
 for name in ['models.spice','ldo_ota5.spi','UPSTREAM-LICENSE','CC-BY-NC-4.0.txt','PDK-LICENSE']:shutil.copyfile(HERE/'source'/name,pub/name)
 put(pub/'public.scs',public['netlist']);
 for name,text in public.get('support',{}).items():put(pub/name,text)
 entries=[]
 for name,(text,passed,reason) in {'reference':(ref,True,'author reference'),**variants}.items():
  p=HERE/'candidates'/task.name/name/'dut.va';put(p,text)
  entries.append(dict(task=str(task.relative_to(ROOT)),variant=name,candidate=str(p.parent.relative_to(ROOT)),expected_pass=passed,semantic_behavior=reason))
 put(task/'SOURCE.md','''# 来源与发布范围\n\n同源组 adb-ldo-ota5，规格 #148。固定 ADB 提交972f7cd7c95381134387b250edf18f3bd23bdd25的参考晶体管电路，电路内容CC-BY-NC-4.0，原作者Analog Design Bench contributors。许可证与完整许可正文随公开资产分发。固定SKY130 PDK提交f62031a1be9aefe902d6d54cddd6f59b57627436，Apache-2.0。自有VA测量解与独立checker不取上游评分代码。外围网络与输入工况是注明的任务适配。\n\n本题为Spectre扩展集，未提供经过校准的开源候选VA执行环境。原电路、适配差异、实际校准身份和许可依据见[路线记录](../../../experiments/benchmark_next/ldo/README.md)。341/372/340仅是后续控制素材，没有形成本题的新计数。\n''')
 return entries

def startup_case(name,vin=1.8,ramp=21e-6,window=70e-6,rload=120,cap=1e-6):
 stop=window+1e-6
 signals=['VOBSIN:p','VOBSOUT:p','vin','vout','t90_us','overshoot_mv','settle_us','reached','settled','status','done']
 net=f'''simulator lang=spectre\nglobal 0\nahdl_include "dut.va"\nsimulator lang=spice\n.include "models.spice"\n.include "ldo_ota5.spi"\n.temp 27\nVIN vin 0 PWL(0 0 1u 0 {ramp:g} {vin:g} {stop:g} {vin:g})\nVREF vref 0 0.8\nIBIAS vin ibias 50u\nRLOAD vout 0 {rload}\nXLDO vin vout 0 vref ibias fb gate_drive gate ldo_ota5\nRFBTOP vout fb 300k\nRFBBOT fb 0 600k\nVLOOP gate_drive gate 0\nRESR vout vcap 50m\nCOUT vcap 0 {cap:g}\nsimulator lang=spectre\nVOBSIN (vin vin_read) vsource dc=0\nVOBSOUT (vout vout_read) vsource dc=0\nXM (vin_read vout_read t90_us overshoot_mv settle_us reached settled status done) ldo_startup_meter ramp_end={ramp:g} window={window:g}\ntran tran stop={stop:g} maxstep=5n errpreset=conservative\nsave {' '.join(signals)}\n'''
 return dict(name=name,kind='startup',tick=50e-9,ramp_start=1e-6,ramp_end=ramp,window=window,target=1.2,tail=20,stop=stop,guard=5e-9,vin_high=vin,tolerances=dict(t90_us=.075,settle_us=.075,overshoot_mv=.3),netlist=net,signals=signals,support={})

BENCH='# 响应驱动 LDO line/load 表征\n\n实现 `ldo_experiment`，完整端口和默认参数见starter.va。vout只读。line_cmd与load_cmd是唯一允许驱动的命令，固定适配器将line_cmd变成实际VIN，load_cmd的1V增加10mA电流负载，基线RLOAD=120Ω。原DUT与反馈、1µF/50mΩ输出网络可读。输出不是理想一阶模型。\n\n必须按startup,line_up,line_down,load_up,load_down顺序执行，stage对应0..4，全部结束stage=5,done=1。startup的line_cmd在1µs开始线性上升，在ramp_end=21µs达到1.8V，load_cmd=0。startup后line_up命令1.95V；line_down恢复1.8V；load_up保持1.8V并设load_cmd=1V；load_down恢复load_cmd=0V。每个命令改变后保持至下一阶段，完成后保持1.8V/0V。命令边沿1ns内，报告5ns内。\n\n所有阶段只在全局i*tick采样实际vout，tick=50ns。若实际输出在target=1.2V±band=0.024V连续qualification=20个样本，并完成min_window=8µs，才进入下一阶段。startup最短到ramp_end，仅ramp_end及以后的样本可资格；startup_timeout=70µs。其余阶段timeout=40µs。超时也推进并报告status=2，取得资格报告status=1。不许跳过扰动、提前推进或无限等待。每阶段从命令变更后的下一tick采样，startup从t=0采样。\n\n每阶段独立重置峰值与资格历史。端口名为阶段名加_peak_mv、_offset_mv、_recovery_us、_status。peak_mv是该阶段样本与1.2V的最大绝对偏差乘1000；offset_mv是结束样本减1.2V乘1000；recovery_us是形成最终连续资格的首样本减阶段起点乘1e6，超时未资格为-1。已完成阶段报告保持，未完成阶段报告0。初态done=0,stage=0。比如输出先入带又振铃出带，恢复起点必须重置，不能沿用首次入带。正确测得不合格阶段可以通过，始终报告失败不能通过健康DUT。\n\n终评可在公开范围改变ramp_end=17..25µs，COUT=0.5..2µF、RLOAD=100..150Ω、VREF=0.76..0.8V，其余参数与命令固定，最长运行到240µs。所有输出峰值/偏移误差≤0.3mV，恢复时间≤0.075µs，状态≤0.002V，line/实际VIN≤1mV，load_cmd≤0.002V，适配电流报告≤20µA。\n'+COMMON

def bench_case(name,cap=1e-6,rload=120,vref=.8,ramp=21e-6):
 names=['startup','line_up','line_down','load_up','load_down']
 metrics=[n+'_'+s for n in names for s in ['peak_mv','offset_mv','recovery_us','status']]
 outputs=['line_cmd','load_cmd','stage','done']+metrics
 signals=['VOBSOUT:p','vout','vin','load_current']+outputs
 adapter='`include "disciplines.vams"\nmodule fixed_load(vout,cmd,load_current);\ninput vout,cmd;output load_current;\nelectrical vout,cmd,load_current;\nanalog begin I(vout)<+0.01*V(cmd);V(load_current)<+0.01*V(cmd);end\nendmodule\n'
 net=f"""simulator lang=spectre
global 0
ahdl_include "dut.va"
ahdl_include "fixed_load.va"
simulator lang=spice
.include "models.spice"
.include "ldo_ota5.spi"
.temp 27
EADAPTER vin 0 line_cmd 0 1
VREF vref 0 {vref}
IBIAS vin ibias 50u
RLOAD vout 0 {rload}
XLDO vin vout 0 vref ibias fb gate_drive gate ldo_ota5
RFBTOP vout fb 300k
RFBBOT fb 0 600k
VLOOP gate_drive gate 0
RESR vout vcap 50m
COUT vcap 0 {cap}
simulator lang=spectre
XLOAD (vout load_cmd load_current) fixed_load
VOBSOUT (vout vout_read) vsource dc=0
XM (vout_read {' '.join(outputs)}) ldo_experiment ramp_end={ramp}
tran tran stop=240u maxstep=5n errpreset=conservative
save {' '.join(signals)}
"""
 tolerances={n:(.075 if n.endswith('_us') else .3 if n.endswith('_mv') else .002) for n in metrics}
 tolerances.update(vin=.001,line_cmd=.001,load_current=20e-6)
 return dict(name=name,kind='bench',tick=50e-9,target=1.2,band=.024,qualification=20,ramp_start=1e-6,ramp_end=ramp,min_window=8e-6,timeout=40e-6,startup_timeout=70e-6,stop=240e-6,guard=5e-9,tolerances=tolerances,netlist=net,signals=signals,support={'fixed_load.va':adapter})

def main():
 ref=(HERE/'startup.va').read_text()
 alt=ref.replace('peak=0;last90=-tick;lastbad=ramp_end-tick;','peak=0;last90=0;lastbad=ramp_end;').replace('if(y<0.9*target) last90=$abstime;','if(y<0.9*target) last90=$abstime+tick;').replace('lastbad=$abstime;','lastbad=$abstime+tick;').replace('(last90<window-tick/10)','(last90<=window+tick/10)').replace('last90+tick-ramp_start','last90-ramp_start').replace('lastbad+tick','lastbad')
 alt=alt.replace(',0,1n)',',0,3n)').replace(' V(t90_us)<+',' I(vin)<+1e-12*V(vin);I(vout)<+1e-12*V(vout);\n V(t90_us)<+')
 variants={'alternate':(alt,True,'forward suffix-start tracking rather than storing last bad samples'),'first-entry':(ref.replace('if(y<0.9*target) last90=$abstime;','if(y<0.9*target && last90<0) last90=$abstime;'),False,'freezes threshold clock before real stable crossing'),'final-as-target':(ref.replace('b=max(0,peak-target)*1e3;','b=max(0,peak-y)*1e3;'),False,'uses measured terminal output as target'),'always-invalid':(ref.replace('r=(last90<window-tick/10);s=(lastbad+tick<=window-(tail-1)*tick+tick/10);','r=0;s=0;'),False,'always reports failed DUT'),'input-drive':(ref.replace(' V(t90_us)<+', ' V(vout)<+1.2;\n V(t90_us)<+'),False,'illegally drives observed DUT output'),'input-load':(ref.replace(' V(t90_us)<+', ' I(vout)<+V(vout)/1e6;\n V(t90_us)<+'),False,'loads observed output through 1 Mohm'),'ideal-metrics':(ref.replace('a=r?(last90+tick-ramp_start)*1e6:-1;','a=18;').replace('b=max(0,peak-target)*1e3;','b=0;'),False,'reports ideal ramp metrics')}
 cases=[startup_case('nominal'),startup_case('dropout-no-target',vin=1.,ramp=17e-6,window=60e-6),startup_case('heavy-slow',ramp=25e-6,window=80e-6,rload=60,cap=2e-6)]
 entries=package('startup-measurement',STARTUP,ref,variants,cases,startup_case('public'))
 ref=(HERE/'bench.va').read_text()
 alt=ref.replace('integer st,good,j,ok;','integer st,good,j,ok,bad;').replace('st=0;good=0;','st=0;bad=0;good=0;',1).replace('if(good==0) runstart=$abstime;','if(good==0) runstart=$abstime; bad=0;').replace('end else good=0;','end else begin good=0;bad=1;end').replace('ok=(good>=qualification);','ok=(!bad && $abstime-runstart >= (qualification-1)*tick-tick/10);')
 alt=alt.replace(' V(load_cmd)<+',' I(vout)<+1e-12*V(vout);\n V(load_cmd)<+')
 alt=re.sub(r'transition\((p\[\d\]|o\[\d\]|r\[\d\]|s\[\d\]|st|d),0,1n\)',r'transition(\1,0,3n)',alt)
 variants={'alternate':(alt,True,'duration qualification instead of count comparison'),'fixed-schedule':(ref.replace('(age>=minimum-tick/10 && ok) || age>=limit-tick/10','age>=minimum-tick/10'),False,'advances on fixed time without actual qualification'),'skip-load':(ref.replace('load=(st==3)?1:0;','load=0;'),False,'does not apply load disturbance'),'stale-recovery':(ref.replace('start=$abstime;good=0;peak=0;','start=$abstime;peak=0;'),False,'carries qualification across disturbances'),'zero-peaks':(ref.replace('p[st]=peak*1e3;','p[st]=0;'),False,'suppresses observed peak deviation'),'input-drive':(ref.replace(' V(load_cmd)<+', ' V(vout)<+1.2;\n V(load_cmd)<+'),False,'illegally replaces actual DUT output'),'input-load':(ref.replace(' V(load_cmd)<+', ' I(vout)<+V(vout)/1e6;\n V(load_cmd)<+'),False,'loads DUT observation input'),'always-timeout':(ref.replace('ok=(good>=qualification);','ok=0;'),False,'always reports timeout despite health')}
 entries+=package('response-experiment',BENCH,ref,variants,[bench_case('healthy'),bench_case('slow-cap',cap=2e-6,ramp=25e-6),bench_case('offset-timeout',vref=.76,rload=150)],bench_case('public'))
 for item in entries:item['candidate_file_sha256']=sha(ROOT/item['candidate']/'dut.va')
 paths=list((HERE/'source').rglob('*'))
 for task in (ROOT/'benchmark/tasks').glob('v3-ldo-*'):paths+=list(task.rglob('*'))
 material={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths) if p.is_file() and '__pycache__' not in str(p)}
 (HERE/'manifest.json').write_text(json.dumps(dict(spec=148,source_group='adb-ldo-ota5',backend='spectre',task_version='circuit-benchmark-next-development',calibration=entries,material_sha256=material),indent=2)+'\n')
if __name__=='__main__':main()
