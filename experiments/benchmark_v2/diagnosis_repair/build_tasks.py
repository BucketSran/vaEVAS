"""Build fixed, independently graded repair tasks from approved source contracts."""
import json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
SOURCE=ROOT/'benchmark/reference/v4/release/benchmarkv4-r53/tasks'
IMAGE='python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c'

def write(path,text):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)

def dump(path,obj): write(path,json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def pwl(name,initial,changes,stop):
 points=[(0,initial)];prev=initial
 for t,v in changes: points.extend([(t-0.001,prev),(t,v)]);prev=v
 points.append((stop,prev))
 return f'V{name} ({name} 0) vsource type=pwl wave=['+' '.join(f'{t*1e-9:.12g} {v}' for t,v in points)+']\n'
def clock(stop): return [(t,v) for k in range(1,int(stop)) for t,v in [(k,0.9),(k+0.4,0)]]
def deck(module,ports,inputs,stop,params='',includes=None,step=0.05):
 text='simulator lang=spectre\n'
 for f in includes or ['dut.va']:text+=f'ahdl_include "{f}"\n'
 for name,(initial,changes) in inputs.items():text+=pwl(name,initial,changes,stop)
 text+=f'Xdut ({" ".join(ports)}) {module}{(' '+params) if params else ''}\n'
 text+=f'simulatorOptions options reltol=1e-6 vabstol=1e-8\ntran tran stop={stop*1e-9:.12g} maxstep={step*1e-9:.12g}\nsave '+ ' '.join(ports)+'\n'
 return text

DESIGNS=[
 ('005','debounce-latch','debounce_latch',['sig','rst_n','out'],'debounce','输入上升沿启动12ns连续高资格。sig回落或低有效rst_n立即取消并清零。复位释放时sig已高不启动资格，须等待下一上升沿。初态out=0。',{'stable':12e-9,'guard':0.6e-9},[
  {'sig':(0,[(2,0.9),(8,0),(12,0.9),(30,0),(34,0.9)]),'rst_n':(0.9,[(20,0),(22,0.9)])},
  {'sig':(0,[(1,0.9),(14,0),(15,0.9),(25,0),(27,0.9),(44,0),(45,0.9)]),'rst_n':(0.9,[(5,0),(7,0.9),(41,0),(43,0.9)])}],62),
 ('046','uvlo-brownout','uvlo_brownout_detector',['clk','rst','vin','out','metric'],'uvlo','仅在clk上升沿更新。rst高清零；out低且vin>0.65V置高，out高且vin<0.55V清零，在两阈值之间及等号处保持。out=0/0.9V；metric对应0.9/0.1V，初态out=0、metric=0.9V。',{'guard':0.15e-9},[
  {'clk':(0,clock(20)),'rst':(0,[(11.6,0.9),(12.4,0)]),'vin':(0.5,[(2.6,0.7),(5.6,0.6),(8.6,0.5),(10.6,0.7),(15.6,0.6),(17.6,0.5)])},
  {'clk':(0,clock(20)),'rst':(0,[(7.6,0.9),(8.4,0)]),'vin':(0.65,[(2.6,0.66),(4.6,0.55),(6.6,0.54),(9.6,0.65),(11.6,0.66),(13.6,0.6),(16.6,0.54)])}],20),
 ('272','reset-sequencer','reset_release_sequencer',['clk','rst','supply_ok','bias_ok','stage1','stage2','ready','progress'],'sequencer','仅在clk上升沿更新。rst高或supply_ok/bias_ok不高时stage=0；否则stage递增并在final_stage饱和。stage1在stage>=1为0.9V，stage2在stage>=2为0.9V，ready在stage>=final_stage为0.9V，progress=0.9*stage/final_stage。其余输出0。初态stage=0。停钟期间rst变化不更新状态。final_stage只允许整数3..5，验收会覆盖该范围。clk阈值交点前后0.2ns内，rst和资格输入保持稳定，不评分输入阈值跳变恰与clk重合的情况。若有效复位与阶段推进在同一采样拍发生，清零优先，不输出ready。',{'final_stage':3,'guard':0.12e-9},[
  {'clk':(0,clock(20)),'rst':(0,[(6.6,0.9),(8.4,0)]),'supply_ok':(0.9,[(12.6,0),(14.4,0.9)]),'bias_ok':(0.9,[])},
  {'clk':(0,clock(20)),'rst':(0,[(10.6,0.9),(11.4,0)]),'supply_ok':(0.9,[]),'bias_ok':(0.9,[(3.6,0),(5.4,0.9),(15.6,0),(16.4,0.9)])}],20),
 ('249','pfd-reset','pfd_active_low_reset',['ref','fb','rstb','up','down'],'pfd','rstb低立即清零并取消挂起复位；有效时ref上升置up，fb上升置down。两者都高后80ps清零；下降沿不置位。复位有效期间输入边沿不记忆，重新释放后只采纳新边沿。初态两输出0；高电平0.9V、tr=10ps。',{'reset_delay':80e-12,'guard':20e-12},[
  {'ref':(0,[(1,0.9),(1.4,0),(3,0.9),(3.4,0),(5,0.9),(5.4,0),(7,0.9),(7.4,0)]),'fb':(0,[(1.2,0.9),(1.6,0),(3.2,0.9),(3.6,0),(5.2,0.9),(5.6,0),(7.2,0.9),(7.6,0)]),'rstb':(0.9,[(3.05,0),(4,0.9),(6,0),(6.5,0.9)])},
  {'ref':(0,[(1.2,0.9),(1.6,0),(3.2,0.9),(3.6,0),(5,0.9),(5.09,0),(5.11,0.9),(5.5,0),(7.2,0.9),(7.6,0)]),'fb':(0,[(1,0.9),(1.4,0),(3,0.9),(3.4,0),(5.05,0.9),(5.09,0),(5.3,0.9),(5.7,0),(7,0.9),(7.4,0)]),'rstb':(0.9,[(5.08,0),(5.1,0.9)])}],9)]

def package(task,files,cases,instruction,source):
 path=ROOT/'benchmark/tasks'/task
 write(path/'instruction.md',f'# 修复{task}\n\n{instruction}\n\n输入源码位于 `/work/`。可整体重写指定模块；保持公开端口和行为。验收激励与checker固定。逻辑阈值0.45V，禁止条件也须满足按时启动要求。提交指定文件，不依靠运行外部程序或隐藏终评材料。Spectre是本题固定后端；公开自测执行 `/tests/test.sh`，可自行建立诊断激励。\n')
 write(path/'task.toml',f'schema_version = "1.4"\n[metadata]\nname = "{task}"\ncategory = "verilog-a"\nengineering_action = "diagnosis-repair"\nsource_group = "{source}"\n[agent]\ntimeout_sec = 1200\n[verifier]\ntimeout_sec = 600\n[environment]\nbuild_timeout_sec = 600\ncpus = 1\nmemory_mb = 1024\nstorage_mb = 2048\n')
 docker=f'FROM {IMAGE}\nWORKDIR /work\nCOPY input/ /work/\n'
 write(path/'environment/Dockerfile',docker)
 for name,data in files.items():write(path/'environment/input'/name,data)
 write(path/'solution/solve.sh','#!/bin/sh\nset -eu\ncp -R /solution/files/. /work/\n')
 write(path/'tests/test.sh','#!/bin/sh\nset -eu\nexec python3 -B /tests/verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}" --tests /tests "$@"\n')
 write(path/'tests/verify.py','from v2_runtime import main\nfrom v2_repair import evaluate\nif __name__ == "__main__":\n    main(evaluate)\n')
 dump(path/'tests/cases.json',cases);dump(path/'tests/contract.json',{'candidate_files':list(files),'output_files':[],'task_id':task,'category':'diagnosis-repair','source_group':source})
 write(path/'tests/v2_repair.py',(ROOT/'benchmark/checkers/v2_repair.py').read_text())
 return path

def build():
 manifest=[]; requests=[]
 for sid,label,module,ports,kind,words,settings,patterns,stop in DESIGNS:
  task='v2-repair-'+label
  origin=next(SOURCE.glob(f'{int(sid)+1000:04d}-*bugfix'))
  healthy=next((origin/'evaluator/solution').glob('*.va')).read_text()
  buggy=next((origin/'public/buggy_bundle').glob('*.va')).read_text()
  # Keep true starter bytes. Public parameters match the source except specified range.
  params=''
  if sid=='272': params='final_stage=3'
  cases=[]
  for i,inputs in enumerate(patterns):
   case=dict(name='public-reproduction' if i==0 else 'reentry-boundaries',kind=kind,signals=ports,stop=stop*1e-9,**settings)
   if sid=='272' and i==1:case['final_stage']=5
   case['netlist']=deck(module,ports,inputs,stop,'final_stage=5' if sid=='272' and i==1 else params,step=0.005 if sid=='249' else 0.05)
   case['maxstep']=5e-12 if sid=='249' else 0.05e-9
   cases.append(case)
  path=package(task,{'dut.va':buggy},cases,words+('\n\nfinal_stage采用整数3和5；其他参数固定为源码默认值。' if sid=='272' else '\n\n固定参数为源码默认值；最终测试会覆盖两种不同激励。'),f'v4-family-{sid}')
  write(path/'solution/files/dut.va',healthy)
  variants={'healthy':(healthy,True,'原健康资产'),'reference':(healthy,True,'按健康合同恢复原故障'),'starter':(buggy,False,'原人工注错资产')}
  if sid=='272':
   alternative='`include "disciplines.vams"\nmodule reset_release_sequencer(clk,rst,supply_ok,bias_ok,stage1,stage2,ready,progress);\ninput clk,rst,supply_ok,bias_ok; output stage1,stage2,ready,progress; electrical clk,rst,supply_ok,bias_ok,stage1,stage2,ready,progress;\nparameter real vth=0.45,vhi=0.9,tr=60p; parameter integer final_stage=3; integer cycles;\nanalog begin\n@(initial_step) cycles=0;\n@(cross(V(clk)-vth,1)) begin\nif(V(rst)>vth || V(supply_ok)<=vth || V(bias_ok)<=vth) cycles=0; else cycles=min(cycles+1,final_stage);\nend\nV(stage1)<+transition(vhi*(cycles>0),0,tr); V(stage2)<+transition(vhi*(cycles>1),0,tr); V(ready)<+transition(vhi*(cycles==final_stage),0,tr); V(progress)<+transition(vhi*cycles/final_stage,0,tr);\nend\nendmodule\n'
   variants['alternative']=(alternative,True,'整体重写输出方程与计数状态')
   variants['never-ready']=(healthy.replace('ready_v = (stage_q >= final_stage) ? vhi : 0.0;','ready_v = 0.0;'),False,'永不启动')
   variants['ignore-bias']=(healthy.replace(' || (V(bias_ok) <= vth)',''),False,'旁路偏置资格')
  elif sid=='046':
   alternative=healthy.replace('real pgood, metricv;','integer state; real pgood, metricv;').replace('pgood = 0.0;\n        metricv', 'state = 0; pgood = 0.0;\n        metricv').replace('if (V(rst) > vth) {','if (V(rst) > vth) {')
   # Independent compact state equation, synchronous boundaries retained.
   start=alternative.index('    @(cross(');end=alternative.index('    V(out)',start)
   alternative=alternative[:start]+'''    @(cross(V(clk)-vth,1)) begin
      if(V(rst)>vth) state=0;
      else if(V(vin)>0.65) state=1;
      else if(V(vin)<0.55) state=0;
      pgood=0.9*state; metricv=0.9-0.8*state;
    end
'''+alternative[end:]
   variants['alternative']=(alternative,True,'整体重写整数迟滞状态')
   variants['no-hysteresis']=(healthy.replace('V(vin) < 0.55','V(vin) < 0.65'),False,'迟滞区错误清零')
   variants['wrong-polarity']=(healthy.replace('(pgood > 0.45) ? 0.1 : 0.9','(pgood > 0.45) ? 0.9 : 0.1'),False,'故障指标极性')
  elif sid=='005':
   alternative=healthy.replace('@(timer(candidate_t))','@(timer(0,50p))').replace('if (armed && V(sig)>vth && V(rst_n)>vth)','if (armed && $abstime>=candidate_t && V(sig)>vth && V(rst_n)>vth)')
   variants['alternative']=(alternative,True,'独立周期计时替代动态deadline事件')
   variants['no-recount']=(healthy.replace('candidate_t=$abstime+stable;','if (candidate_t<0) candidate_t=$abstime+stable;').replace('state=0; armed=0; candidate_t=-1.0; end\n        @(timer','state=0; armed=0; end\n        @(timer'),False,'资格取消后保留旧deadline')
   variants['never-start']=(healthy.replace('state=1;','state=0;'),False,'永不启动')
  else:
   alternative=healthy.replace('integer up_state, down_state;','real up_state, down_state;').replace('trst = $abstime + reset_delay;','trst = max($abstime,0) + reset_delay;')
   # A different time mechanism permits a whole rewrite and avoids source checks.
   alternative=alternative.replace('@(timer(trst)) begin','@(timer(0,1p)) begin\n        if (trst>=0 && $abstime>=trst) begin').replace('    if (V(rstb) <= vth) begin','    end\n    if (V(rstb) <= vth) begin')
   variants['alternative']=(alternative,True,'周期复位调度而非动态timer')
   stale=healthy.replace('        trst = -1.0;\n    end\n    @(cross(V(ref)', '    end\n    @(cross(V(ref)').replace('        trst = -1.0;\n    end\n    V(up)', '    end\n    V(up)')
   variants['stale-reset-timer']=(stale,False,'异步复位清输出但保留旧deadline，提前清除新周期UP')
   variants['wrong-edge']=(healthy.replace('V(ref) - vth, +1','V(ref) - vth, -1'),False,'ref下降沿置位')
   variants['never-start']=(healthy.replace('up_state = 1;','up_state = 0;'),False,'丢失UP动作')
  for v,(text,passed,why) in variants.items():
   cdir=HERE/'candidates'/task/v;write(cdir/'dut.va',text)
   requests.append({'task':str(path.relative_to(ROOT)),'variant':v,'candidate_dir':str(cdir.relative_to(ROOT)),'expected_pass':passed,'behavior':why})
  dump(path/'SOURCE.json',{'source_id':sid,'source_group':f'v4-family-{sid}','source_path':str(origin.relative_to(ROOT)),'starter_sha256':hashlib.sha256(buggy.encode()).hexdigest(),'healthy_sha256':hashlib.sha256(healthy.encode()).hexdigest(),'fault_origin':'historical artificial mutation; engineering bug history unknown','fixed_backend':'Spectre','calibration_status':'pending','agent_pilots':'pending'})
  manifest.append({'source_id':sid,'task_id':task,'status':'built-awaiting-live-calibration','contract':kind})
 dump(HERE/'manifest.json',manifest);dump(HERE/'run-plan.json',requests)
if __name__=='__main__':build()
