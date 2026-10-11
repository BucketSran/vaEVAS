"""Generate fixed Spectre Harbor assets; never executes a model or simulator."""
from pathlib import Path
import hashlib,json,shutil,math
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
IMAGE='python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c'
CAL=[]
def put(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
def pwl(name,values,period=5):
 tok=['0',str(values[0])]
 for i,v in enumerate(values[1:],1):tok.extend([f'{i*period-.1:g}n',str(values[i-1]),f'{i*period:g}n',str(v)])
 return f'V{name} ({name} 0) vsource type=pwl wave=['+ ' '.join(tok)+']\n'
def case(kind,inputs,values,params='',support=None,outputs=None,**kw):
 outputs=outputs or ['aout'];count=len(values);stop=count*5e-9
 net='simulator lang=spectre\nglobal 0\nahdl_include "dut.va"\n'
 if support:net+='ahdl_include "fixed.va"\n'
 for i,n in enumerate(inputs):net+=pwl(n,[v[i] for v in values])
 net+='Vclk (clk 0) vsource type=pulse val0=0 val1=1 delay=1n rise=20p fall=20p width=1n period=5n\n'
 net+='Vrst (rst 0) vsource dc=0\n'
 if support:net+='XD (code observe) fixed_dac\n'
 net+='XM ('+' '.join(inputs+['clk','rst']+outputs)+') dut '+params+'\n'
 net+=f'tran tran stop={count*5}n maxstep=50p\nsave '+' '.join(inputs+['clk','rst']+outputs+(['observe'] if support else []))+'\n'
 # Scan interface includes observe, driven by fixed DUT rather than source.
 if support:net=net.replace('XM (code clk','XM (code observe clk')
 if kind=='spectrum':net=net.replace('XM (code sample_ok clk rst','XM (code clk rst sample_ok')
 return dict(name='normal',kind=kind,stop=stop,maxstep=50e-12,guard=1e-9,signals=inputs+['clk','rst']+outputs+(['observe'] if support else []),outputs=outputs,tolerances={n:(.03 if n in ['sndr','sfdr'] else .006 if n=='enob' else .001) for n in outputs},netlist=net,**({'support':{'fixed.va':support}} if support else {}),**kw)
def package(slug,source,contract,ref,alt,wrong,cases,public):
 tid='v3-converter-'+slug;t=ROOT/'benchmark/tasks'/tid
 put(t/'instruction.md','# '+slug+'\n\n实现 `/work/dut.va`。'+contract+'\n\n固定后端 Spectre，候选源码按原字节运行，不作语言子集限制。仅 dut.va 可修改；输入及固定器件只读。测量题各电气报告端口的电压数值就是指标数值，例如0.5LSB用0.5V、20dB用20V，valid用0或1V。初态及事件后允许1ns建立，之后输出绝对误差1mV，频谱dB误差0.03dB、ENOB误差0.006bit。输出可用 transition(...,0,100p,100p)；无需复制参考结构。公开台架见 `/work/public/cases.json`，终评改变合同内输入、端点、样本和控制时刻。测量 DUT 性能差仍可通过，评分只看报告正确。源代码、reference与私有checker不进入公开包。\n')
 put(t/'SOURCE.md',f'# 来源与覆盖\n\n{source}\n\n来源固定在 reviewed main 81eb66258b59b0a0cd48cd3decaa767be02cdd58。本题为独立编写的 VA 改编，未复制商业库源码。固定 Spectre 扩展集；开源等价尚未验证。真实校准及已执行分母见[作者校准](../../../experiments/benchmark_next/converter/author-calibration.md)，旧资产关系见[资产审计](../../../experiments/benchmark_next/converter/asset-audit.md)。不开展模型试跑。\n')
 action='spec-modeling' if cases[0]['kind']=='dac' else 'testing-characterization'
 put(t/'task.toml',f'schema_version = "1.4"\n[metadata]\nname = "{tid}"\ncategory = "verilog-a"\nengineering_action = "{action}"\nsource_group = "{source.split()[0]}"\nweight = 1\n[agent]\ntimeout_sec = 900\n[verifier]\ntimeout_sec = 600\n[environment]\nbuild_timeout_sec = 600\ncpus = 1\nmemory_mb = 1024\nstorage_mb = 2048\n')
 put(t/'environment/Dockerfile',f'FROM {IMAGE}\nWORKDIR /work\nCOPY public/ /work/public/\nCOPY starter.va /work/dut.va\n')
 put(t/'environment/starter.va',ref.split('analog begin')[0]+'analog begin\n// Implement the public contract.\nend\nendmodule\n')
 put(t/'environment/public/cases.json',json.dumps([public],indent=2)+'\n')
 for n,s in public.get('support',{}).items():put(t/'environment/public/dut'/n,s)
 put(t/'solution/dut.va',ref);put(t/'solution/solve.sh','#!/bin/sh\nset -eu\ncp /solution/dut.va /work/dut.va\n')
 put(t/'tests/cases.json',json.dumps(cases,indent=2)+'\n');put(t/'tests/contract.json',json.dumps(dict(candidate_files=['dut.va'],output_files=[],task_id=tid)))
 put(t/'tests/test.sh','#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nexec python3 verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}" --tests . "$@"\n')
 put(t/'tests/verify.py','from v2_runtime import main\nfrom v2_next_converter import evaluate\nif __name__ == "__main__": main(evaluate)\n')
 for name in ['v2_next_converter.py','v2_runtime.py','adc_linearity.py']:
  shutil.copyfile(ROOT/'benchmark/checkers'/name,t/'tests'/name)
 for p in [t/'tests/test.sh',t/'solution/solve.sh']:p.chmod(0o755)
 for name,text,expected in [('reference',ref,True),('alternative',alt,True)]+[(n,s,False) for n,s in wrong.items()]:
  p=OUT/'candidates'/tid/name/'dut.va';put(p,text)
  target=cases[0]['name']
  if name=='ignore-order':target='repeat-code'
  if name=='stale-reset':target='reset-truncated' if cases[0]['kind']=='scan' else 'private-3'
  if name=='ignore-invalid':target='private-2'
  CAL.append(dict(task=str(t.relative_to(ROOT)),variant=name,candidate=str(p.parent.relative_to(ROOT)),expected_pass=expected,case_names=None if expected else [target]))

def dac(sid,slug,names,weights):
 # Clocking is an explicit adaptation, so delayed/held code behavior is observable.
 ports=','.join(names+['clk','rst','aout']);expr='+'.join(f'{w:.15g}*(V({n})>0.45)' for n,w in zip(names,weights))
 ref=f'''`include "disciplines.vams"
module dut({ports});
inout {ports};electrical {ports};
parameter real lo=0, hi=1, tr=100p;
real q,weighted;
analog begin
 @(initial_step) q=lo;
 @(cross(V(clk)-0.5,+1)) begin
  weighted={expr};
  q=lo+(hi-lo)*weighted/{sum(weights):.15g};
 end
 V(aout)<+transition(q,0,tr,tr);
end
endmodule
'''
 # Centered signed reconstruction uses genuinely different arithmetic.
 signed='+'.join(f'{w:.15g}*((V({n})>0.45)?1.0:-1.0)' for n,w in zip(names,weights))
 alt=ref.replace('weighted='+expr+';',f'weighted={signed};').replace(f'q=lo+(hi-lo)*weighted/{sum(weights):.15g};',f'q=(hi+lo)/2+(hi-lo)*weighted/{2*sum(weights):.15g};')
 values=[]
 if sid=='018':
  for k in range(16):values.append([1 if i<k else 0 for i in range(15)])
  values += [[int(i==j) for i in range(15)] for j in range(15)] + [[int(i%2==0) for i in range(15)]]
 else:
  codes=list(range(1<<len(names))) if len(names)<10 else [0,1023]+[1<<i for i in range(10)]+[31,32,63,64,127,128,255,256,511,512,341,682]
  values=[[int(c>>i&1) for i in range(len(names))] for c in codes]
 wrong={'omit-last':ref.replace(f'{weights[-1]:.15g}*(V({names[-1]})>0.45)','0.0'),'transparent':ref.replace(' @(cross(V(clk)-0.5,+1)) begin',' begin')}
 if sid in ['025','243']:
  ideal='+'.join(f'{2**i}*(V({n})>0.45)' for i,n in enumerate(names));wrong['ideal-binary']=ref.replace(expr,ideal).replace(f'weighted/{sum(weights):.15g}',f'weighted/{2**len(names)-1}')
 else:wrong['wrong-scale']=ref.replace(f'weighted/{sum(weights):.15g}',f'weighted/{sum(weights)+1:.15g}')
 if sid=='014':wrong['bit-order']=ref.replace(expr,'+'.join(f'{w:.15g}*(V({n})>0.45)' for n,w in zip(names,[2,1,4,4,4])))
 cases=[]
 for j,(lo,hi) in enumerate([(0,1),(.17,.93)]):
  vals=values if j==0 else list(reversed(values))
  c=case('dac',names,vals,f'lo={lo} hi={hi}',weights=weights,lo=lo,hi=hi,initial=lo)
  c['inputs']=names;c['name']=f'private-{j}';cases.append(c)
 # Input toggles occur4ns before next capture; checker tests held output in this gap.
 public=case('dac',names,values[::2],weights=weights,lo=0,hi=1,initial=0);public['inputs']=names
 contract=f'模块 dut({ports})；lo=0V、hi=1V、tr=100ps 可覆盖，lo在0至0.2V、hi在0.8至1.1V、tr在50至300ps。控制引脚严格大于0.45V为1，阈值相等为0；clk以0.5V上升沿采样，只在该沿更新，其他时刻保持，rst未使用且固定0。初态aout=lo。每个输入权重按端口顺序为 {weights}；aout=lo+(hi-lo)乘以活动权重和除以全活动权重和。任意独立单元模式均合法，包括温度计气泡；亚基数自然二进制码可以非单调，不要求修正。输出必须形成真实模拟电压。'
 package(slug,f'v4-{sid} 原始同源码制素材，新增明确采样与保持合同。',contract,ref,alt,wrong,cases,public)

def scan():
 fixed='''`include "disciplines.vams"
module fixed_dac(code,observe);
inout code,observe;electrical code,observe;
parameter real offset=0.1,scale=0.7,delta=0.02;
integer c;real v;
analog begin
 c=floor(V(code)+0.5);
 v=offset+scale*c/15.0+((c==7)?delta:0.0);
 V(observe)<+v;
end
endmodule
'''
 ref='''`include "disciplines.vams"
module dut(code,observe,clk,rst,dnl,inl,valid);
inout code,observe,clk,rst,dnl,inl,valid;electrical code,observe,clk,rst,dnl,inl,valid;
real x[0:15],step,a,b,od,oi;integer n,k,bad,ok;
analog begin
 @(initial_step) begin n=0;bad=0;ok=0;od=0;oi=0;end
 @(cross(V(rst)-0.5,+1)) begin n=0;bad=0;ok=0;od=0;oi=0;end
 @(cross(V(clk)-0.5,+1)) if(V(rst)<0.5 && n<16) begin
  if(abs(V(code)-n)>0.001) bad=1;
  x[n]=V(observe);n=n+1;
  if(n==16 && !bad) begin
   step=(x[15]-x[0])/15;
   if(step>0) begin
    for(k=0;k<16;k=k+1) begin
     a=abs((x[k]-x[0])/step-k);if(a>oi) oi=a;
     if(k>0) begin b=abs((x[k]-x[k-1])/step-1);if(b>od) od=b;end
    end
    ok=1;
   end
  end
 end
 V(dnl)<+od;V(inl)<+oi;V(valid)<+ok;
end
endmodule
'''
 alt=ref.replace('real x[0:15],step,a,b,od,oi;','real x[0:15],step,a,b,od,oi,cumulative;')
 alt=alt.replace('for(k=0;k<16;k=k+1) begin\n     a=abs((x[k]-x[0])/step-k);if(a>oi) oi=a;\n     if(k>0) begin b=abs((x[k]-x[k-1])/step-1);if(b>od) od=b;end\n    end','cumulative=0;\n    for(k=1;k<16;k=k+1) begin\n     b=(x[k]-x[k-1])/step-1;\n     cumulative=cumulative+b;\n     if(abs(b)>od)od=abs(b);\n     if(abs(cumulative)>oi)oi=abs(cumulative);\n    end')
 cases=[]
 for j,delta in enumerate([.012,-.027]):
  c=case('scan',['code'],[[i] for i in range(16)],support=fixed.replace('delta=0.02',f'delta={delta}'),outputs=['dnl','inl','valid'],count=16);c['name']=f'private-{j}';cases.append(c)
 # Repeated code must invalidate even though a full number of edges occurred.
 c=case('scan',['code'],[[i if i!=8 else 7] for i in range(16)],support=fixed,outputs=['dnl','inl','valid'],count=16);c['name']='repeat-code';cases.append(c)
 c=case('scan',['code'],[[i] for i in range(16)]+[[i] for i in range(8)],support=fixed,outputs=['dnl','inl','valid'],count=16)
 c['netlist']=c['netlist'].replace('Vrst (rst 0) vsource dc=0','Vrst (rst 0) vsource type=pwl wave=[0 0 80n 0 80.02n 1 80.4n 1 80.42n 0 120n 0]')
 c['name']='reset-truncated';cases.append(c)
 public=case('scan',['code'],[[i] for i in range(16)],support=fixed,outputs=['dnl','inl','valid'],count=16)
 contract='模块 dut(code,observe,clk,rst,dnl,inl,valid)。code为整数电压0至15，observe为只读固定DAC实际模拟输出。clk上升沿采集，码必须从0到15每码一次。初始与rst上升沿清空输出和历史；rst高时不采集。16次后仅当码序完整且末值大于首值，valid=1；其他记录valid=0、dnl=inl=0，不返回旧结果。step=(实际末值-实际首值)/15，DNL是相邻实际电压差除step减1的最大绝对值，INL是实际电压相对端点直线偏离除step的最大绝对值，单位LSB。不做最佳拟合，不假设性能合格。完成后保持直到rst，允许完整、缺码、重复码记录。固定DUT offset在0至0.2V、scale在0.5至0.9V、delta在-0.03至0.03V，均只读。'
 package('dac-linearity','repository-owned-dac-scan va08 ADC histogram已复用审计，新增DAC端点静态扫描。',contract,ref,alt,{'ideal-report':ref.replace('x[n]=V(observe)','x[n]=V(code)/15.0'),'wrong-step':ref.replace('/15;','/16;'),'ignore-order':ref.replace('if(abs(V(code)-n)>0.001) bad=1;','// Deliberately omit code-order validation.'),'stale-reset':ref.replace(' @(cross(V(rst)-0.5,+1)) begin n=0;bad=0;ok=0;od=0;oi=0;end\n','')},cases,public)

def spectrum():
 old=(ROOT/'benchmark/tasks/measure-adc-spectrum/solution/dut.va').read_text()
 ref=old.replace('module dut(code,clk,sndr,sfdr,dc);','module dut(code,clk,rst,sample_ok,sndr,sfdr,dc,enob,valid);').replace('code,clk,sndr,sfdr,dc;','code,clk,rst,sample_ok,sndr,sfdr,dc,enob,valid;').replace('integer n,k;','integer n,k,bad,ok;').replace('out_dc=0;for','out_dc=0;bad=0;ok=0;for').replace(' @(cross(V(clk)-0.5,+1))begin',' @(cross(V(rst)-0.5,+1))begin n=0;sum=0;out_sndr=0;out_sfdr=0;out_dc=0;bad=0;ok=0;for(k=0;k<=32;k=k+1)begin cs[k]=0;ss[k]=0;end end\n @(cross(V(clk)-0.5,+1))begin').replace('if(n<64)begin','if(V(rst)<0.5 && n<64)begin').replace('x=V(code);sum=', 'x=V(code);if(V(sample_ok)<0.5 || x<0 || x>4095 || abs(x-floor(x+0.5))>0.0001)bad=1;sum=').replace('out_sndr=10*ln(fund/noise)/ln(10);out_sfdr=10*ln(fund/spurious)/ln(10);out_dc=sum/64;','if(!bad && fund>1e-8 && noise>1e-8 && spurious>1e-8)begin out_sndr=10*ln(fund/noise)/ln(10);out_sfdr=10*ln(fund/spurious)/ln(10);out_dc=sum/64;ok=1;end').replace(' V(sndr)<+', ' V(valid)<+ok;V(enob)<+(ok?(out_sndr-1.76)/6.02:0);\n V(sndr)<+')
 # Batch DFT alternative stores samples first, computes after last sample.
 alt=ref.replace('integer n,k,bad,ok;','real record[0:63];integer n,k,j,bad,ok;')
 block='for(k=0;k<=32;k=k+1)begin cs[k]=cs[k]+x*cos(2*3.1415926535897932384626433832795*k*n/64.0);ss[k]=ss[k]+x*sin(2*3.1415926535897932384626433832795*k*n/64.0);end'
 alt=alt.replace(block,'record[n]=x;').replace('if(n==64)begin','if(n==64)begin\n for(k=0;k<=32;k=k+1)for(j=0;j<64;j=j+1)begin cs[k]=cs[k]+record[j]*cos(2*3.1415926535897932384626433832795*k*j/64.0);ss[k]=ss[k]+record[j]*sin(2*3.1415926535897932384626433832795*k*j/64.0);end')
 def make(tone,a,h,invalid=False):
  vals=[[round(2048+a*math.sin(2*math.pi*tone*n/64)+h*math.sin(2*math.pi*2*tone*n/64)+7*math.cos(math.pi*n)),0 if invalid and n==23 else 1] for n in range(64)]
  c=case('spectrum',['code','sample_ok'],vals,f'tone_bin={tone}',outputs=['sndr','sfdr','dc','enob','valid'],count=64,tone=tone)
  return c
 cases=[make(3,720,24),make(7,520,41),make(5,620,32,True)]
 # Complete first round, reset, then invalid second round. A stale valid report fails.
 vals=[]
 for tone,ampl,harm,broken in [(5,620,32,False),(5,420,17,True)]:
  vals.extend([[round(2048+ampl*math.sin(2*math.pi*tone*n/64)+harm*math.sin(2*math.pi*2*tone*n/64)+7*math.cos(math.pi*n)),0 if broken and n==23 else 1] for n in range(64)])
 c=case('spectrum',['code','sample_ok'],vals,'tone_bin=5',outputs=['sndr','sfdr','dc','enob','valid'],count=64,tone=5)
 c['netlist']=c['netlist'].replace('Vrst (rst 0) vsource dc=0','Vrst (rst 0) vsource type=pwl wave=[0 0 320n 0 320.02n 1 320.4n 1 320.42n 0 640n 0]')
 cases.append(c)
 # A truncated record has valid data but fewer than64 actual edges.
 c=make(4,620,25);c['stop']=160e-9;c['netlist']=c['netlist'].replace('stop=320n','stop=160n');cases.append(c)
 for j,c in enumerate(cases):c['name']=f'private-{j}'
 contract='模块 dut(code,clk,rst,sample_ok,sndr,sfdr,dc,enob,valid)，tone_bin可覆盖整数3至7。记录是带明确来源的行为合成12bit unsigned码值，code以1V/码表示0至4095整数，sample_ok为对应样本完整标志。采样率200MHz，64次clk上升沿为一条相干记录，矩形窗，不加窗或拟合。rst上升清空历史与输出，rst高不采样；初始零。64样本前输出全零valid=0；完成后保持直到rst。任何sample_ok低、越界或非整数码使整记录无效，所有指标清零valid=0。DFT归一化单边功率：1至31号bin为2*(C²+S²)/64²，Nyquist32号为(C²+S²)/64²，DC排除；基波为tone_bin唯一bin。SNDR=10log10(基波功率/其他1至32号bin总功率)，SFDR=10log10(基波/最大非基波单bin)，谐波计入失真，ENOB=(SNDR-1.76)/6.02，dc为原码均值。基波、总残差或最大杂散功率<=1e-8时无效，指标零。频谱全部核心计算必须由候选VA完成。公共及终评可改变tone、幅度、谐波、Nyquist和完整标志；不含噪声统计或非相干窗口。'
 package('adc-spectrum','first-batch-measure-adc-spectrum 固定64点合成观测迁移，新增ENOB和有效状态，非新增独立来源。',contract,ref,alt,{'amplitude-db':ref.replace('10*ln','20*ln'),'nyquist-double':ref.replace('if(k==32)p=p/2;',''),'harmonics-as-fundamental':ref.replace('if(k!=tone_bin)','if(k!=tone_bin && k!=2*tone_bin)').replace('fund=2*(cs[tone_bin]*cs[tone_bin]+ss[tone_bin]*ss[tone_bin])/4096;','fund=2*(cs[tone_bin]*cs[tone_bin]+ss[tone_bin]*ss[tone_bin]+cs[2*tone_bin]*cs[2*tone_bin]+ss[2*tone_bin]*ss[2*tone_bin])/4096;'),'ignore-invalid':ref.replace('if(!bad &&','if('),'stale-reset':ref.replace(' @(cross(V(rst)-0.5,+1))begin n=0;sum=0;out_sndr=0;out_sfdr=0;out_dc=0;bad=0;ok=0;for(k=0;k<=32;k=k+1)begin cs[k]=0;ss[k]=0;end end\n','')},cases,make(5,600,30))

def main():
 dac('014','segmented',['b0','b1','t0','t1','t2'],[1,2,4,4,4])
 dac('018','thermometer',[f'seg{i}' for i in range(15)],[1]*15)
 dac('025','nonideal',[f'b{i}' for i in range(4)],[1,2.02,3.96,8.08])
 dac('243','subradix',[f'vd{i}' for i in range(10)],[1.8**i for i in range(10)])
 scan();spectrum()
 put(OUT/'manifest.json',json.dumps(dict(spec=151,calibrations=CAL),indent=2)+'\n')
if __name__=='__main__':main()
