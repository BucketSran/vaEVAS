"""Build owned v2 characterization packages; does not invoke simulators."""
from pathlib import Path
import json
import shutil
import re
import copy

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
LEGACY=ROOT/'benchmark/reference/v4/release/benchmarkv4-r53/tasks'
IMAGE='python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c'
CAL=[]


def put(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text)



# The terminal instances are evaluator assets. Public examples stay fixed so
# earlier public feedback remains reproducible, but are never terminal inputs.
INSTANCE_RANGES = {
 'hysteresis': 'vin范围0.35至0.65V；比较器offset为-0.02至0.02V，vhys为0.04至0.13V，td为100至500ps。可改变输入斜坡、轮起点及完整/缺方向轮；初态cmp_out低，轮起点不与比较器边沿重合。',
 'comparator-delay': '差分过驱动绝对值为0.001至0.08V，输入共模0.45V；时钟周期5至7ns，每轮输入在launch前至少200ps稳定，实际响应不超过1ns。DUT可变传播延迟参数，或在任意后续轮缺少决策；供电与单位保持不变。',
 'duty-cycle': '时钟高低为0.9V与0V，输入边沿单调跨过门限，按实际交点计时；完整周期15至40ns，高电平占周期0.10至0.80，至少四个上升沿。可变周期和占空，可从高电平开始；结束后不再产生边沿，保持旧报告。',
 'sampled-rms': '两路输入各在0至0.9V内，可为直流或正弦（幅度0至0.35V、频率10至35MHz）；时钟周期4至6ns。可改变reset及enable时刻并跨越部分窗口；控制门限交点与采样沿至少隔开200ps。四样本窗口、阈值与报告单位固定。',
 'online-gain': '实际放大器gain_low为0.2至1.2、gain_high为1至2.6；输入共模0.45V，正弦幅度0.001至0.07V、频率15至25MHz。可改变增益切换和begin_round时刻；begin与全局采样点至少隔开200ps。计时参数、跨度条件与gain_scale固定。',
 'clock-frequency': '固定DCO模型f_min为80至130MHz、f_step为2至5MHz、divide_ratio为3至7；可改变频率码、复位和禁用时刻。候选不可读取这些设置，只能测量观测时钟。只有真实边沿形成完整周期后才报告；也允许不足周期的片段并按历史/复位合同保持报告。既定阈值与单位固定。',
 'offset-search': 'DUT offset在-0.06至0.06V，响应延迟150至700ps；可在任意已完成响应之后停止响应，且ready脉冲宽度400ps。搜索步长、次数、gap与timeout保持上述默认值；DUT设置与预计响应表不得替代真实ready。',
 'time-protocol': 'clk周期90至130ps，输入start/stop边沿20ps；可变测量起止、重武装、未武装stop及reset时刻。终评包含正常锁存、取消区间和超过256边沿的区间；输入门限交点不重合，至少隔开5ps。计数边界与报告电平固定。',
 'gain-settling': '静态放大器增益固定2.5，动态alpha为0.01至0.35；vin基线与阶跃值在0.42至0.49V。每轮launch后200至240ps内完成输入阶跃，随后保持至窗口末；可有有效跨度、无效跨度或窗口内未建立DUT。各轮相隔至少25ns；固定80次采样和末8样本条件不变。',
}


def terminal_cases(slug, public_cases):
    """Choose new deterministic instances strictly inside the public ranges."""
    cases=copy.deepcopy(public_cases)
    def pwl_shift(net, delta):
        def shift(match):
            tokens=match.group(1).split()
            for i in range(0,len(tokens),2):
                if tokens[i].endswith('n'):
                    tokens[i]=f'{float(tokens[i][:-1])+delta:g}n'
            return 'wave=['+' '.join(tokens)+']'
        return re.sub(r'wave=\[([^]]+)\]',shift,net)
    for i,c in enumerate(cases):
        c['name']='terminal-'+c['name']
        net=c['netlist']
        if slug=='hysteresis':
            net=pwl_shift(net,0.4)
            for a,b in [('offset=0.005','offset=0.013'),('offset=-0.01','offset=-0.017'),('vhys=0.05','vhys=0.064'),('vhys=0.12','vhys=0.108'),('td=120p','td=180p'),('td=400p','td=330p')]: net=net.replace(a,b)
            net=net.replace('.59','0.598').replace('.60','0.607')
        elif slug=='comparator-delay':
            net=net.replace('delay=1n period=6n','delay=1.4n period=5.7n')
            for a,b in [('0.470','0.4746'),('0.430','0.4254'),('0.440','0.4377'),('0.460','0.4623'),('0.454','0.45492'),('0.446','0.44508'),('0.4475','0.446925'),('0.4525','0.453075'),('0.465','0.46845'),('0.435','0.43155')]: net=net.replace(a,b)
            net=net.replace('support_overdrive_delay_comparator\n','support_overdrive_delay_comparator td_0=160p td_max=480p\n').replace('td_0=250p td_max=600p','td_0=290p td_max=720p')
            c['support']['support_cmp.va']=c['support']['support_cmp.va'].replace('$abstime < 24n','$abstime < 22n')
        elif slug=='duty-cycle':
            rises=([8,27,49,78,109] if i!=2 else [9,29,54,87,119])
            falls=([14,36,63,88,120] if i!=2 else [18,43,71,102,128])
            tokens=['0','0.9' if i==1 else '0']
            if i==1:tokens+=['3n','0.9','3.1n','0']
            for rise,fall in zip(rises,falls):tokens += [f'{rise}n','0',f'{rise+.1:g}n','0.9',f'{fall-.1:g}n','0.9',f'{fall}n','0']
            tokens+=['145n','0']
            net=re.sub(r'wave=\[[^]]+\]','wave=['+' '.join(tokens)+']',net).replace('stop=150n','stop=145n')
            c['stop']=145e-9
        elif slug=='sampled-rms':
            net=pwl_shift(net,.37).replace('delay=1.5n period=5n','delay=1.8n period=4.7n')
            for a,b in [('ampl=0.31 freq=29Meg','ampl=0.27 freq=23Meg'),('ampl=0.09 freq=13Meg','ampl=0.12 freq=19Meg'),('ampl=0.21 freq=17Meg','ampl=0.18 freq=21Meg'),('ampl=0.19 freq=31Meg','ampl=0.16 freq=27Meg'),('dc=0.70','dc=0.66'),('dc=0.40','dc=0.37'),('dc=.70','dc=.66'),('dc=.40','dc=.37'),('ampl=.21 freq=17Meg','ampl=.18 freq=21Meg'),('ampl=.19 freq=31Meg','ampl=.16 freq=27Meg')]:net=net.replace(a,b)
        elif slug=='online-gain':
            net=net.replace('freq=20Meg','freq=23Meg').replace('100n','93.35n').replace('100.1n','93.45n').replace('104n','97.35n').replace('104.1n','97.45n').replace('105n','98.35n').replace('105.1n','98.45n')
            for a,b in [('gain_low=0.8 gain_high=2.4','gain_low=1.05 gain_high=2.15'),('gain_low=0.3 gain_high=1.1','gain_low=0.42 gain_high=1.25'),('ampl=0.06','ampl=0.055'),('ampl=0.001','ampl=0.002')]:net=net.replace(a,b)
        elif slug=='clock-frequency':
            net=pwl_shift(net,.4)
            net=net.replace('frequency_word_dco\n','frequency_word_dco f_min=95Meg f_step=4.5Meg divide_ratio=5\n').replace('divide_ratio=3','f_min=95Meg f_step=4.5Meg divide_ratio=6').replace('f_min=110Meg f_step=3Meg','f_min=125Meg f_step=2.6Meg divide_ratio=7')
        elif slug=='offset-search':
            for a,b in [('offset=0.023 td=200p','offset=0.031 td=350p'),('offset=-0.041 td=600p','offset=-0.036 td=450p'),('offset=0.018 td=200p drop_after=2','offset=-0.012 td=350p drop_after=3')]:net=net.replace(a,b)
        elif slug=='time-protocol':
            net=pwl_shift(net,.37).replace('period=0.1n','period=0.11n').replace('period=.1n','period=.11n')
        elif slug=='gain-settling':
            net=pwl_shift(net,1.0).replace('stop=56n','stop=57n')
            for a,b in [('alpha=0.3','alpha=0.24'),('alpha=0.01','alpha=0.014'),('0.47','0.478'),('0.43','0.437'),('0.445','0.447'),('0.442','0.444')]:net=net.replace(a,b)
            c['stop']=57e-9
        else: raise ValueError('unregistered independent terminal contract '+slug)
        c['netlist']=net
        assert net != public_cases[i]['netlist'], slug+' terminal instance must differ'
    return cases


def package(slug,source,title,contract,reference,alternate,mutants,cases,public_dut,*,public_cases=None):
    if slug in INSTANCE_RANGES and public_cases is None:
        raise ValueError('public_cases required for independently scored instrument '+slug)
    if public_cases is None:
        raise ValueError('explicit independent public_cases required for '+slug)
    normalize=lambda text: re.sub(r'(?<![\w])\.(\d)',r'0.\1',text)
    reference=normalize(reference)
    alternate=normalize(alternate)
    mutants={name:(normalize(text),why) for name,(text,why) in mutants.items()}
    public_dut={name:normalize(text) for name,text in public_dut.items()}
    for case in cases+public_cases:
        case['support']={name:normalize(text) for name,text in case.get('support',{}).items()}
    if slug == 'time-protocol':
        contract += ('\n\ncode是结果寄存器的输出。start后至stop或溢出之前，code_0..code_7全部保持0，valid=0、overflow=0；内部累加计数不直接驱动code。stop或第256个clk发布结果后，code、valid和overflow保持到下一次start或rst。初始状态与rst清零后的状态相同，尚未武装。')
    contract += ('\n\n## 公开自测与终评范围\n\n'+INSTANCE_RANGES[slug]) if slug in INSTANCE_RANGES else ''
    task_id='v2-test-'+slug
    task=ROOT/'benchmark/tasks'/task_id
    put(task/'instruction.md',f'# {title}\n\n实现 `/work/dut.va`，保留以下公开接口与行为。固定 DUT 源码位于 `/work/public/dut/`，只读。不得驱动观测输入。测量不达标 DUT 时，报告正确结果仍可通过。\n\n{contract}\n\n固定后端为 Spectre；语法遵循该后端的 Verilog-A。源码按原字节运行。工具链故障单独诊断，不作为候选零分。公开自测实例位于 `/work/public/cases.json`，固定DUT实现位于 `/work/public/dut/`，可据此运行自己的Spectre自测。终评在提交后使用合同范围内不同的参数、事件及故障实例；终评台架和checker不进入解题材料。判定目标与数值容差以本题公开合同为准。\n')
    put(task/'SOURCE.md',f'# 来源与改编\n\n来源 `{source}`。本任务保留来源的工程目标，新增固定只读 DUT、独立实际波形 checker 和明确窗口协议。原始参考资产仍保存在 benchmark/reference/。本次校准与模型试跑尚待实际运行；目录存在不表示发布资格。固定 Spectre，开源同题等价尚未验证。\n')
    put(task/'task.toml',f'schema_version = "1.4"\n[metadata]\nname = "{task_id}"\ncategory = "verilog-a"\nengineering_action = "testing-characterization"\nsource_group = "{source}"\n[agent]\ntimeout_sec = 900\n[verifier]\ntimeout_sec = 600\n[environment]\nbuild_timeout_sec = 600\ncpus = 1\nmemory_mb = 1024\nstorage_mb = 2048\n')
    put(task/'environment/Dockerfile',f'FROM {IMAGE}\nWORKDIR /work\nCOPY public/ /work/public/\nCOPY starter.va /work/dut.va\n')
    # Public case data contains only the fixed stimulus/DUT and oracle tolerances.
    put(task/'environment/public/cases.json',json.dumps(public_cases,indent=2)+'\n')
    for name,text in public_dut.items(): put(task/'environment/public/dut'/name,text)
    header=reference[:reference.index('analog begin')]
    put(task/'environment/starter.va',header+'analog begin\n// Implement the public contract.\nend\nendmodule\n')
    put(task/'solution/dut.va',reference)
    put(task/'solution/solve.sh','#!/bin/sh\nset -eu\ncp /solution/dut.va /work/dut.va\n')
    put(task/'tests/test.sh','#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nexec python3 verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}" --tests . "$@"\n')
    put(task/'tests/verify.py','from v2_runtime import main\nfrom v2_testing import evaluate\nif __name__ == "__main__":\n    main(evaluate)\n')
    put(task/'tests/contract.json',json.dumps(dict(candidate_files=['dut.va'],output_files=[],task_id=task_id,category='testing-characterization',source_group=source),indent=2)+'\n')
    put(task/'tests/cases.json',json.dumps(cases,indent=2)+'\n')
    shutil.copyfile(ROOT/'benchmark/checkers/v2_testing.py',task/'tests/v2_testing.py')
    for path in [task/'solution/solve.sh',task/'tests/test.sh']: path.chmod(0o755)
    variants={'reference':(reference,True,'reference implementation'),'alternate':(alternate,True,'different state representation and event implementation')}
    variants.update({name:(text,False,why) for name,(text,why) in mutants.items()})
    for name,(text,expected,why) in variants.items():
        candidate=OUT/'candidates'/task_id/name
        put(candidate/'dut.va',text)
        CAL.append(dict(task=str(task.relative_to(ROOT)),variant=name,candidate=str(candidate.relative_to(ROOT)),expected_pass=expected,semantic_behavior=why))


def hysteresis_task():
    ref='''`include "disciplines.vams"
module hysteresis_meter(vin, cmp_out, begin_round, up, down, width, valid);
input vin, cmp_out, begin_round;
output up, down, width, valid;
electrical vin, cmp_out, begin_round, up, down, width, valid;
parameter real tr=20p;
real u,d,w;
integer su,sd;
analog begin
 @(initial_step) begin u=0; d=0; w=0; su=0; sd=0; end
 @(cross(V(begin_round)-0.5,+1)) begin u=0; d=0; w=0; su=0; sd=0; end
 @(cross(V(cmp_out)-0.5,+1)) begin u=V(vin); su=1; if(sd) w=u-d; end
 @(cross(V(cmp_out)-0.5,-1)) begin d=V(vin); sd=1; if(su) w=u-d; end
 V(up)<+transition(u,0,tr,tr);
 V(down)<+transition(d,0,tr,tr);
 V(width)<+transition(w,0,tr,tr);
 V(valid)<+transition((su && sd)?1.0:0.0,0,tr,tr);
end
endmodule
'''
    alt=ref.replace('integer su,sd;','integer su,sd,edge_state;').replace('su=0; sd=0; end','su=0; sd=0; edge_state=0; end',1)
    alt=alt.replace(' @(cross(V(cmp_out)-0.5,+1)) begin u=V(vin); su=1; if(sd) w=u-d; end\n @(cross(V(cmp_out)-0.5,-1)) begin d=V(vin); sd=1; if(su) w=u-d; end',''' @(cross(V(cmp_out)-0.5,0)) begin
  edge_state=1-edge_state;
  if(edge_state) begin u=V(vin); su=1; end
  else begin d=V(vin); sd=1; end
  if(su && sd) w=u-d;
 end''')
    support=(LEGACY/'111-hysteresis-trip-characterizer/evaluator/solution/support/support_hysteretic_comparator.va').read_text()
    cases=[]
    for name,offset,hys,td,wave in [('normal',.005,.05,'120p','0 .42 10n .59 20n .42 30n .60 40n .41 44n .41'),('bad-dut-wide',-.01,.12,'400p','0 .40 10n .62 20n .40 30n .63 40n .39 44n .39'),('incomplete-second-round',.005,.05,'120p','0 .42 10n .59 20n .42 22n .42 32n .59 44n .59')]:
        net=f'''simulator lang=spectre
global 0
ahdl_include "dut.va"
ahdl_include "support_cmp.va"
Vdd (vdd 0) vsource dc=1
Vref (vref 0) vsource dc=.5
Vin (vin 0) vsource type=pwl wave=[{wave}]
Vbegin (begin_round 0) vsource type=pwl wave=[0 0 21n 0 21.02n 1 21.2n 1 21.22n 0 44n 0]
XC (vdd 0 vin vref cmp_out) support_hysteretic_comparator offset={offset} vhys={hys} td={td} tr=30p
XM (vin cmp_out begin_round up down width valid) hysteresis_meter
tran tran stop=44n maxstep=20p
save vin cmp_out begin_round up down width valid
'''
        cases.append(dict(name=name,kind='hysteresis',stop=44e-9,guard=100e-12,atol=.002,netlist=net,signals=['vin','cmp_out','begin_round','up','down','width','valid'],support={'support_cmp.va':support}))
    contract='''模块 `hysteresis_meter(vin, cmp_out, begin_round, up, down, width, valid)`。输入均为只读观测，输出以伏报告输入捕获值，逻辑高低为1V与0V。`tr=20ps` 为输出边沿参数。比较器输出穿过0.5V上升/下降时，分别捕获实际 `vin` 到 up/down；同一轮两方向都捕获后，width=up-down，valid=1。begin_round穿过0.5V上升时清零全部报告与方向历史。新轮缺少任一方向必须保持valid=0；没有begin事件时初始轮从t=0开始。每方向的后续边沿刷新对应值。比较器延迟已包含在实际捕获点中，不能按DUT参数直接报告理想门限。输出在事件后100ps内可过渡，之后绝对误差不得超过2mV。'''
    package('hysteresis','v4-111','比较器双向滞回表征',contract,ref,alt,{'wrong-sign':(ref.replace('w=u-d','w=d-u'),'reverses signed hysteresis width'),'constant-target':(ref.replace('u=V(vin)','u=.53').replace('d=V(vin)','d=.48'),'reports ideal target constants instead of actual delayed edges'),'stale-round':(ref.replace(' @(cross(V(begin_round)-0.5,+1)) begin u=0; d=0; w=0; su=0; sd=0; end\n',''),'does not clear second-round history')},terminal_cases('hysteresis',cases),{'support_cmp.va':support},public_cases=cases)

def delay_task():
    base=LEGACY/'170-comparator-delay-overdrive-meter'
    ref=(base/'evaluator/solution/comparator_delay_overdrive_meter.va').read_text().replace('module comparator_delay_overdrive_meter','module delay_meter').replace('transition(measured_delay_s,','transition(measured_delay_s*1e12,').replace('transition(sampled_overdrive_v,','transition(sampled_overdrive_v*1e3,').replace('(valid_state && polarity_state)','polarity_state')
    alt=ref
    start=alt.index('    @(cross(V(outp, vss)')
    end=alt.index('    V(delay_ps',start)
    alt=alt[:start]+'''    @(cross(V(outp,vss)-0.5*V(vdd,vss),+1) or cross(V(outn,vss)-0.5*V(vdd,vss),+1)) begin
        if(armed>0) begin
            measured_delay_s=$abstime-t_clk;
            polarity_state=(V(outp)>V(outn));
            valid_state=1;
            armed=0;
        end
    end

'''+alt[end:]
    support=(base/'evaluator/solution/support/support_overdrive_delay_comparator.va').read_text()
    net=(base/'public/visible_test.scs').read_text().replace('"../submission/comparator_delay_overdrive_meter.va"','"dut.va"').replace('"./public_support/support_overdrive_delay_comparator.va"','"support_cmp.va"').replace(' comparator_delay_overdrive_meter',' delay_meter').replace('maxstep=5p','maxstep=1p')
    cases=[]
    for name,overrides in [('normal',''),('slow-dut',' td_0=250p td_max=600p'),('missing-final-decision',' td_0=250p td_max=600p')]:
        n=net.replace(' support_overdrive_delay_comparator\n',' support_overdrive_delay_comparator'+overrides+'\n')
        sp=support
        if name=='missing-final-decision':
            sp=sp.replace('outp_state = (diff >= 0.0);','outp_state = (diff >= 0.0 && $abstime < 24n);').replace('outn_state = (diff < 0.0);','outn_state = (diff < 0.0 && $abstime < 24n);')
        cases.append(dict(name=name,kind='delay',threshold=.45,vhigh=.9,stop=29e-9,guard=80e-12,atol=.002,tolerances={'delay_ps':.7,'overdrive_mv':.2},signals=['clk','vinp','vinn','outp','outn','delay_ps','overdrive_mv','polarity','valid'],netlist=n,support={'support_cmp.va':sp}))
    package('comparator-delay','v4-170','比较器传播延迟与过驱动测量','模块 delay_meter(vdd,vss,clk,vinp,vinn,outp,outn,delay_ps,overdrive_mv,polarity,valid)。供电固定0.9V和0V，逻辑检测门限0.45V；报告valid和polarity也按0.9V逻辑。每次clk上升沿重新武装并清valid，overdrive_mv为该时刻输入差绝对值乘1000。武装后outp或outn的首个上升沿锁存与clk的实际间隔乘1e12到delay_ps，polarity分别为0.9V或0V，valid为0.9V。缺决策不能沿用旧valid；未武装的边沿忽略，重新武装保留上一数值直到新决策。tr=20ps；guard80ps，延迟误差0.7ps、过驱动0.2mV、逻辑0.002V。',ref,alt,{'seconds-as-ps':(ref.replace('measured_delay_s*1e12','measured_delay_s'),'reports seconds in a ps output'),'stale-valid':(ref.replace('        valid_state = 0;\n    end\n\n    @(cross(V(outp','    end\n\n    @(cross(V(outp'),'keeps old completed validity across a missing response'),'signed-overdrive':(ref.replace('diff = -diff;','diff = diff;'),'reports negative overdrive for negative input')},terminal_cases('comparator-delay',cases),{'support_cmp.va':support},public_cases=cases)

def duty_task():
    base=LEGACY/'060-duty-cycle-meter-8b'
    ref=(base/'evaluator/solution/duty_cycle_meter_8b.va').read_text()
    ref=ref.replace('code=(255.0*(fall_t-rise_t)/($abstime-rise_t)+0.5);','code=floor(255.0*(fall_t-rise_t)/($abstime-rise_t)+0.5);')
    ref=ref.replace('integer have_fall;','integer have_fall; integer have_rise;').replace('have_fall=0; code=0','have_fall=0; have_rise=0; code=0').replace('if (have_fall &&','if (have_rise && have_fall &&').replace('rise_t=$abstime; have_fall=0;','rise_t=$abstime; have_rise=1; have_fall=0;').replace('begin fall_t=$abstime; have_fall=1; end','begin if(have_rise) begin fall_t=$abstime; have_fall=1; end end')
    alt=ref.replace('real rise_t; real fall_t;','real rise_t; real fall_t; real high_time;')
    alt=alt.replace('fall_t=$abstime; have_fall=1;','fall_t=$abstime; high_time=$abstime-rise_t; have_fall=1;').replace('255.0*(fall_t-rise_t)','255.0*high_time')
    net=(base/'public/visible_test.scs').read_text().replace('"../submission/duty_cycle_meter_8b.va"','"dut.va"')
    cases=[]
    for name,n in [('variable-clock',net),('initial-high',net.replace('wave=[0 0 10n 0 10.1n 0.9 16n 0','wave=[0 0.9 5n 0.9 5.1n 0 10n 0 10.1n 0.9 16n 0')),('different-period',net.replace('30n 0 30.1n 0.9 40n 0','35n 0 35.1n 0.9 47n 0').replace('55n 0 55.1n 0.9 72n 0','65n 0 65.1n 0.9 78n 0'))]:
        # Preserve legacy fixed stimulus text; actual period is always measured.
        import re
        stop_match=re.search(r'stop=([0-9.]+)n',n)
        stop=float(stop_match[1])*1e-9
        cases.append(dict(name=name,kind='duty',edge_time_uncertainty=1e-15,stop=stop,threshold=.45,vhigh=.9,guard=100e-12,atol=.002,netlist=n,signals=['clk_in','valid']+[f'duty{i}' for i in range(8)]))
    package('duty-cycle','v4-060','实际时钟占空比测量','模块 duty_cycle_meter_8b(clk_in,valid,duty0,...,duty7)，duty0为最低位。阈值vth=0.45V、报告高vdd=0.9V、tr=20ps。必须见到上升、下降、下一上升三个事件才报告完整周期；初态高电平的下降不能独自构成完整周期。码值为四舍五入的255乘实际高电平时间除实际周期，饱和0到255。valid初始0，首个完整周期后为0.9V并保持；新完整周期更新码，其他时间保持旧结果。guard100ps，逻辑电平误差2mV。边沿时间的数值验收不确定度为1fs；由三个实际边沿的±1fs区间求占空比上下界，仅在该区间跨越半LSB量化门限时容许相邻两个完整8位码。示例数学码42.5可接受42或43，不能逐位混选，也不接受41或44。',ref,alt,{'low-time':(ref.replace('255.0*(fall_t-rise_t)','255.0*($abstime-fall_t)'),'reports low fraction instead of high fraction'),'missing-refresh':(ref.replace('if (have_rise && have_fall &&','if (valid_level==0 && have_rise && have_fall &&'),'holds only first completed result'),'initial-partial':(ref.replace('have_rise && have_fall','have_fall').replace('if(have_rise) begin fall_t=$abstime; have_fall=1; end','fall_t=$abstime; have_fall=1;'),'accepts falling edge before first rising event')},terminal_cases('duty-cycle',cases),{},public_cases=cases)


def rms_task():
    base=LEGACY/'074-sampled-true-rms-to-dc-converter'
    ref=(base/'evaluator/solution/sampled_true_rms_to_dc.va').read_text()
    # Alternate stores per-window samples and sums only at completion.
    alt=ref.replace('real completed_sum;','real completed_sum; real x0,x1,x2;')
    alt=alt.replace('completed_sum = square_sum + sampled_value * sampled_value;','if(sample_count==0) x0=sampled_value;\n                    if(sample_count==1) x1=sampled_value;\n                    if(sample_count==2) x2=sampled_value;\n                    completed_sum=x0*x0+x1*x1+x2*x2+sampled_value*sampled_value;')
    net=(base/'public/visible_test.scs').read_text().replace('"../submission/sampled_true_rms_to_dc.va"','"dut.va"')
    cases=[]
    for name,n in [('normal-reset-disable',net),('dc-input',net.replace('type=sine sinedc=0.40 ampl=0.31 freq=29Meg','dc=.70').replace('type=sine sinedc=0.46 ampl=0.09 freq=13Meg','dc=.40')),('different-waveform',net.replace('ampl=0.31 freq=29Meg','ampl=.21 freq=17Meg').replace('ampl=0.09 freq=13Meg','ampl=.19 freq=31Meg'))]:
        cases.append(dict(name=name,kind='rms',stop=110e-9,threshold=.45,vhigh=.9,guard=320e-12,atol=.002,netlist=n,signals=['vinp','vinn','clk','reset','enable','rms_out','valid']))
    package('sampled-rms','v4-074','四样本在线真有效值仪表','模块 sampled_true_rms_to_dc(vinp,vinn,clk,reset,enable,rms_out,valid)。vth=0.45V、vhigh=0.9V、tr=100ps。每个enable为高且reset为低的clk上升沿采样实际差分输入；恰好四个样本形成不重叠窗口，输出sqrt(mean(x*x))。禁用采样边沿不丢弃部分窗口，但清valid。每个完成窗口valid高一个采样间隔；下一clk上升清零valid。reset上升异步清累计、报告和valid；reset高时采样也清零。rms_out保持到下一完整窗口。误差2mV，事件后320ps允许输出过渡。',ref,alt,{'wrong-window':(ref.replace('sample_count == 3','sample_count == 2').replace('completed_sum / 4.0','completed_sum / 3.0'),'uses three samples'),'no-reset':(ref.replace('@(cross(V(reset) - vth, +1))','@(cross(V(reset) - vth, -1))'),'resets on wrong polarity'),'absolute-mean':(ref.replace('sampled_value * sampled_value','abs(sampled_value)').replace('sqrt(completed_sum / 4.0)','completed_sum / 4.0'),'reports mean magnitude rather than RMS')},terminal_cases('sampled-rms',cases),{},public_cases=cases)


def gain_task():
    ref=(LEGACY/'093-gain-estimator/evaluator/solution/gain_estimator.va').read_text()
    ref=ref.replace('gain_out, valid);','gain_out, valid, begin_round);',1).replace('input vinp, vinn, voutp, voutn;','input vinp, vinn, voutp, voutn, begin_round;').replace('electrical VDD, VSS, vinp, vinn, voutp, voutn, gain_out, valid;','electrical VDD, VSS, vinp, vinn, voutp, voutn, gain_out, valid, begin_round;')
    reset=ref[ref.index('        @(initial_step) begin'):ref.index('        @(timer(0, sample_period))')]
    ref=ref.replace('        @(timer(0, sample_period))',reset.replace('@(initial_step)','@(cross(V(begin_round)-.5,+1))')+'        @(timer(0, sample_period))')
    alt=ref.replace('if (vin_diff < in_min) in_min = vin_diff;','in_min=min(in_min,vin_diff);').replace('if (vin_diff > in_max) in_max = vin_diff;','in_max=max(in_max,vin_diff);').replace('if (vout_diff < out_min) out_min = vout_diff;','out_min=min(out_min,vout_diff);').replace('if (vout_diff > out_max) out_max = vout_diff;','out_max=max(out_max,vout_diff);')
    # Independent alternate uses ranges about the first sample and explicit ready state.
    alt=alt.replace('integer valid_q;','integer valid_q; integer ready;').replace('gain_q = 0.0;','gain_q = 0.0; ready=0;')
    alt=alt.replace('vin_diff = V(vinp, vinn);','vin_diff = V(vinp, vinn);\n                if(!ready) begin in_min=vin_diff; in_max=vin_diff; out_min=V(voutp,voutn); out_max=out_min; ready=1; end')
    support=(LEGACY/'038-programmable-gain-amplifier/evaluator/solution/programmable_gain_amplifier.va').read_text()
    cases=[]
    for name,low,high,ampl in [('normal',.8,2.4,.06),('low-performance-dut',.3,1.1,.06),('invalid-final-span',.8,2.4,.001)]:
        # Every observed output is physically connected to the supplied VA DUT.
        net=f'''simulator lang=spectre
global 0
ahdl_include "dut.va"
ahdl_include "amplifier.va"
Vdd (vdd 0) vsource dc=.9
Vinp (vinp 0) vsource type=sine sinedc=.45 ampl={ampl} freq=20Meg
Vinn (vinn 0) vsource dc=.45
Voutn (voutn 0) vsource dc=.45
Vclk (clk 0) vsource type=pulse val0=0 val1=.9 delay=1n period=8n width=3n rise=60p fall=60p
Vsel (sel 0) vsource type=pwl wave=[0 0 100n 0 100.1n .9 240n .9]
Vbegin (begin_round 0) vsource type=pwl wave=[0 0 104n 0 104.1n 1 105n 1 105.1n 0 240n 0]
XA (clk 0 sel vinp voutp clipping) programmable_gain_amplifier gain_low={low} gain_high={high}
XM (vdd 0 vinp vinn voutp voutn gain_out valid begin_round) gain_estimator sample_period=1n start_time=20n gain_scale=10 min_input_span=.02 tedge=200p
tran tran stop=240n maxstep=100p errpreset=conservative
save vinp vinn voutp voutn begin_round gain_out valid
'''
        cases.append(dict(name=name,kind='gain',stop=240e-9,start_time=20e-9,sample_period=1e-9,gain_scale=10,min_input_span=.02,vhigh=.9,guard=350e-12,atol=.002,netlist=net,signals=['vinp','vinn','voutp','voutn','begin_round','gain_out','valid'],support={'amplifier.va':support}))
    package('online-gain','v4-093+v4-038','实际放大器在线增益仪表','模块 gain_estimator(VDD,VSS,vinp,vinn,voutp,voutn,gain_out,valid,begin_round)。每sample_period=1ns的全局整倍时刻采样实际输入和输出差分，从start_time=20ns起累计极值。输入跨度严格大于min_input_span=0.02V时valid为供电高，gain_out=(VDD-VSS)*输出跨度/输入跨度/gain_scale，gain_scale=10。小跨度保持valid低、gain_out=0。begin_round穿过0.5V上升清极值、报告和valid，新轮重新收集。不得读取放大器内部增益或clipping作为测量结果，不得把输出替换成独立信号源。tedge=200ps；事件后350ps允许平滑，误差2mV。',ref,alt,{'inverse-ratio':(ref.replace('gain_q = out_span / in_span','gain_q = in_span / out_span'),'reverses measured span ratio'),'constant-six':(ref.replace('gain_q = out_span / in_span','gain_q = 6.0'),'reports historical synthetic gain regardless of DUT'),'stale-window':(ref.replace(reset.replace('@(initial_step)','@(cross(V(begin_round)-.5,+1))'),''),'does not reset extrema at new measurement window')},terminal_cases('online-gain',cases),{'amplifier.va':support},public_cases=cases)

def frequency_task():
    ref='''__INCLUDE__ "disciplines.vams"
module frequency_meter(dco_clk,div_clk,enable,reset,freq_mhz,divider_ratio,valid);
input dco_clk,div_clk,enable,reset;
output freq_mhz,divider_ratio,valid;
electrical dco_clk,div_clk,enable,reset,freq_mhz,divider_ratio,valid;
parameter real tr=20p;
real td,tv,pd,pv,f,r;
integer hd,hv,vd,vv;
analog begin
 @(initial_step) begin td=0; tv=0; pd=0; pv=0; f=0; r=0; hd=0; hv=0; vd=0; vv=0; end
 @(cross(V(reset)-.45,+1) or cross(V(enable)-.45,-1)) begin pd=0; pv=0; f=0; r=0; hd=0; hv=0; vd=0; vv=0; end
 @(cross(V(dco_clk)-.45,+1)) begin
  if(V(reset)<=.45 && V(enable)>.45) begin
   if(hd) begin pd=$abstime-td; vd=1; f=1e-6/pd; end
   td=$abstime; hd=1;
   if(vd && vv) r=pv/pd;
  end
 end
 @(cross(V(div_clk)-.45,+1)) begin
  if(V(reset)<=.45 && V(enable)>.45) begin
   if(hv) begin pv=$abstime-tv; vv=1; end
   tv=$abstime; hv=1;
   if(vd && vv) r=pv/pd;
  end
 end
 V(freq_mhz)<+transition(f,0,tr,tr);
 V(divider_ratio)<+transition(r,0,tr,tr);
 V(valid)<+transition((vd && vv)?1.0:0.0,0,tr,tr);
end
endmodule
'''.replace('__INCLUDE__',chr(96)+'include')
    alt=ref.replace('if(vd && vv) r=pv/pd;','if(vd && vv) r=(1.0/pd)/(1.0/pv);').replace('if(hd) begin pd=$abstime-td; vd=1; f=1e-6/pd; end','if(hd && $abstime>td) begin f=1e-6/($abstime-td); pd=1e-6/f; vd=1; end')
    base=LEGACY/'362-frequency-word-dco-divider-monitor'
    support=(base/'evaluator/solution/frequency_word_dco.va').read_text()
    net=(base/'public/visible_test.scs').read_text().replace('ahdl_include "../submission/frequency_word_dco.va"','ahdl_include "dut.va"\nahdl_include "dco.va"')
    net=net.replace('tran tran stop=', 'XM (dco_clk div_clk enable rst freq_mhz divider_ratio valid) frequency_meter\ntran tran stop=').replace('save enable rst fcw_5 fcw_4 fcw_3 fcw_2 fcw_1 fcw_0 dco_clk div_clk freq_metric','save enable rst dco_clk div_clk freq_mhz divider_ratio valid').replace('maxstep=50p','maxstep=10p')
    cases=[]
    for name,overrides in [('normal',''),('bad-divider',' divide_ratio=3'),('different-frequency-map',' f_min=110Meg f_step=3Meg')]:
        n=net.replace(') frequency_word_dco\n',') frequency_word_dco'+overrides+'\n').replace('rst','reset')
        cases.append(dict(name=name,kind='frequency',stop=190e-9,threshold=.45,guard=80e-12,atol=.01,tolerances={'freq_mhz':.8,'divider_ratio':.03},netlist=n,signals=['enable','reset','dco_clk','div_clk','freq_mhz','divider_ratio','valid'],support={'dco.va':support}))
    package('clock-frequency','v4-362','DCO实际码频与分频观测','模块 frequency_meter(dco_clk,div_clk,enable,reset,freq_mhz,divider_ratio,valid)。DUT给定且频率码不会连接到候选；只观测真实时钟。检测阈值0.45V。每路至少两次上升沿才有完整周期。freq_mhz=1e-6/最近DCO周期；divider_ratio=最近分频周期/最近DCO周期，任一路新周期均更新它。两周期都已取得时valid=1V，否则0；reset上升或enable下降清所有历史和报告；被禁用或复位时不采边沿。DUT原divide_ratio表示每多少DCO上升沿翻转一次，完整周期比为2倍，该参数不得替代实际测量。tr20ps，guard80ps；频率误差0.8MHz，周期比0.03，逻辑0.01V。',ref,alt,{'half-period-frequency':(ref.replace('f=1e-6/pd','f=.5e-6/pd'),'reports half actual frequency'),'target-ratio':(ref.replace('r=pv/pd','r=8'),'reports nominal target divider instead of actual clock'),'no-reset':(ref.replace('@(cross(V(reset)-.45,+1) or cross(V(enable)-.45,-1))','@(cross(V(reset)-.45,-1))'),'keeps history across disable and reset')},terminal_cases('clock-frequency',cases),{'dco.va':support},public_cases=cases)

def search_task():
    ref='''__INCLUDE__ "disciplines.vams"
module offset_search(dcmpp,ready,vinp,vinn,request,offset_est,valid,status);
input dcmpp,ready;
output vinp,vinn,request,offset_est,valid,status;
electrical dcmpp,ready,vinp,vinn,request,offset_est,valid,status;
parameter real step_initial=.064;
parameter integer iterations=7;
parameter real gap=1n, timeout=10n, tr=20p;
real estimate,step,next_request,deadline;
integer count,req,done,armed,state;
analog begin
 @(initial_step) begin estimate=0; step=step_initial; count=0; req=0; done=0; armed=0; state=0; next_request=1n; deadline=1e99; end
 @(timer(next_request)) begin
  if(!done) begin req=1; armed=1; deadline=$abstime+timeout; next_request=1e99; end
 end
 @(cross(V(ready)-.5,+1)) begin
  if(armed && !done) begin
   if(V(dcmpp)>.5) estimate=estimate-step; else estimate=estimate+step;
   step=step/2; count=count+1; req=0; armed=0; deadline=1e99;
   if(count>=iterations) begin done=1; state=1; end
   else next_request=$abstime+gap;
  end
 end
 @(timer(deadline)) begin
  if(armed && !done) begin req=0; armed=0; done=1; state=2; next_request=1e99; end
 end
 V(vinp)<+.5+.5*transition(estimate,0,tr,tr);
 V(vinn)<+.5-.5*transition(estimate,0,tr,tr);
 V(offset_est)<+transition(estimate,0,tr,tr);
 V(request)<+transition(req,0,tr,tr);
 V(valid)<+transition((state==1)?1.0:0.0,0,tr,tr);
 V(status)<+transition(state,0,tr,tr);
end
endmodule
'''.replace('__INCLUDE__',chr(96)+'include')
    # Alternate uses a periodic scheduler and per-iteration resolution derived
    # from update count, rather than mutable step or variable timers.
    alt=ref.replace('step=step/2;','step=step_initial/pow(2.0,count+1);')
    alt=alt.replace('@(timer(next_request)) begin','@(timer(0,10p)) begin').replace('if(!done) begin req=1; armed=1; deadline=$abstime+timeout; next_request=1e99; end','if(!done && !armed && $abstime>=next_request) begin req=1; armed=1; deadline=$abstime+timeout; next_request=1e99; end\n  if(armed && !done && $abstime>=deadline) begin req=0; armed=0; done=1; state=2; end')
    start=alt.index(' @(timer(deadline)) begin')
    end=alt.index(' V(vinp)',start)
    alt=alt[:start]+alt[end:]
    support='''__INCLUDE__ "disciplines.vams"
module response_comparator(vinp,vinn,request,dcmpp,ready);
input vinp,vinn,request;
output dcmpp,ready;
electrical vinp,vinn,request,dcmpp,ready;
parameter real offset=.023, td=200p, tr=20p;
parameter integer drop_after=99;
integer decision,responded,n;
real next_response,next_clear;
analog begin
 @(initial_step) begin decision=0; responded=0; n=0; next_response=1e99; next_clear=1e99; end
 @(cross(V(request)-.5,+1)) begin
  n=n+1;
  decision=(V(vinp,vinn)>=offset);
  if(n<=drop_after) next_response=$abstime+td;
 end
 @(timer(next_response)) begin responded=1; next_clear=$abstime+400p; next_response=1e99; end
 @(timer(next_clear)) begin responded=0; next_clear=1e99; end
 V(dcmpp)<+transition(decision,0,tr,tr);
 V(ready)<+transition(responded,0,tr,tr);
end
endmodule
'''.replace('__INCLUDE__',chr(96)+'include')
    cases=[]
    for name,offset,td,drop in [('normal-positive',.023,'200p',99),('normal-negative',-.041,'600p',99),('response-timeout',.018,'200p',2)]:
        net=f'''simulator lang=spectre
global 0
ahdl_include "dut.va"
ahdl_include "comparator.va"
XS (dcmpp ready vinp vinn request offset_est valid status) offset_search
XC (vinp vinn request dcmpp ready) response_comparator offset={offset} td={td} drop_after={drop}
tran tran stop=32n maxstep=5p
save vinp vinn request dcmpp ready offset_est valid status
'''
        cases.append(dict(name=name,kind='search',stop=32e-9,first_request=1.01e-9,gap=1e-9,timeout=10e-9,step_initial=.064,iterations=7,guard=80e-12,atol=.0015,netlist=net,signals=['vinp','vinn','request','dcmpp','ready','offset_est','valid','status'],support={'comparator.va':support}))
    package('offset-search','v4-109','响应驱动比较器失调搜索','模块 offset_search(dcmpp,ready,vinp,vinn,request,offset_est,valid,status)。初态估计0，差分输入=估计值且围绕0.5V对称。1ns启动首个request高脉冲，比较器在收到request后给出dcmpp决策和ready上升。候选只能在ready上升时更新：dcmpp>0.5V则减当前步长，否则加步长；初始步长0.064V，每次减半，共7次。响应后立即拉低request，gap=1ns后发下个request。最后一次响应后valid=1、status=1，停止刺激并保持结果。任何request超过timeout=10ns仍没有ready时status=2、valid=0，停止并保持未完成估计。status=0表示运行中。阈值及逻辑高为0.5V与1V，tr20ps；时序允许80ps，电压1.5mV。不允许按固定预期响应表推进；范围为±0.127V，区间外DUT属于公开未覆盖条件。',ref,alt,{'wrong-direction':(ref.replace('estimate=estimate-step; else estimate=estimate+step','estimate=estimate+step; else estimate=estimate-step'),'inverts feedback decision direction'),'premature-done':(ref.replace('count>=iterations','count>=2'),'stops after two responses'),'permanent-wait':(ref.replace('done=1; state=2;','done=0; state=0;'),'never reports missing-response timeout')},terminal_cases('offset-search',cases),{'comparator.va':support},public_cases=cases)

def tdc_task():
    ports='start,stop,clk,rst,'+','.join(f'code_{i}' for i in range(8))+',valid,overflow'
    outputs=','.join(f'code_{i}' for i in range(8))+',valid,overflow'
    ref=f'''__INCLUDE__ "disciplines.vams"
module tdc_meter({ports});
input start,stop,clk,rst;
output {outputs};
electrical {ports};
parameter real tr=20p;
integer armed,count,code,ok,ov;
analog begin
 @(initial_step) begin armed=0; count=0; code=0; ok=0; ov=0; end
 @(cross(V(rst)-.5,+1)) begin armed=0; count=0; code=0; ok=0; ov=0; end
 @(cross(V(start)-.5,+1)) begin
  if(V(rst)<=.5) begin armed=1; count=0; code=0; ok=0; ov=0; end
 end
 @(cross(V(stop)-.5,+1)) begin
  if(V(rst)<=.5 && armed) begin code=count; armed=0; ok=1; end
 end
 @(cross(V(clk)-.5,+1)) begin
  if(V(rst)>.5) begin armed=0; count=0; code=0; ok=0; ov=0; end
  else if(armed) begin
   count=count+1;
   if(count>=256) begin code=255; ov=1; ok=1; armed=0; end
  end
 end
'''.replace('__INCLUDE__',chr(96)+'include')
    ref+=''.join(f' V(code_{i})<+transition(((code >> {i}) & 1)?1.0:0.0,0,tr,tr);\n' for i in range(8))
    ref+=' V(valid)<+transition(ok,0,tr,tr);\n V(overflow)<+transition(ov,0,tr,tr);\nend\nendmodule\n'
    # Alternate counts down remaining capacity and reconstructs the count at stop.
    alt=ref.replace('integer armed,count,code,ok,ov;','integer armed,count,code,ok,ov;')
    alt=alt.replace('count=0','count=256').replace('code=count;','code=256-count;').replace('count=count+1;','count=count-1;').replace('if(count>=256)','if(count<=0)')
    cases=[]
    base='''simulator lang=spectre
global 0
ahdl_include "dut.va"
Vclk (clk 0) vsource type=pulse val0=0 val1=1 delay=.08n period=.1n width=.04n rise=5p fall=5p
Vrst (rst 0) vsource type=pwl wave=[0 1 .1n 1 .12n 0 35n 0]
Vstart (start 0) vsource type=pwl wave=[0 0 .64n 0 .66n 1 .72n 1 .74n 0 3.04n 0 3.06n 1 3.12n 1 3.14n 0 6.04n 0 6.06n 1 6.12n 1 6.14n 0 35n 0]
Vstop (stop 0) vsource type=pwl wave=[0 0 1.83n 0 1.85n 1 1.91n 1 1.93n 0 5.43n 0 5.45n 1 5.51n 1 5.53n 0 35n 0]
XM (start stop clk rst code_0 code_1 code_2 code_3 code_4 code_5 code_6 code_7 valid overflow) tdc_meter
tran tran stop=35n maxstep=2p
save start stop clk rst code_0 code_1 code_2 code_3 code_4 code_5 code_6 code_7 valid overflow
'''
    for name,net in [('rearm-stop-overflow',base),('reset-abort',base.replace('.12n 0 35n 0','.12n 0 10n 0 10.02n 1 12n 1 12.02n 0 35n 0')),('extra-stop',base.replace('5.53n 0 35n 0','5.53n 0 33n 0 33.02n 1 33.12n 1 33.14n 0 35n 0'))]:
        cases.append(dict(name=name,kind='tdc',stop=35e-9,threshold=.5,vhigh=1,guard=40e-12,atol=.002,netlist=net,signals=['start','stop','clk','rst']+[f'code_{i}' for i in range(8)]+['valid','overflow']))
    package('time-protocol','v4-346','重武装、锁存与溢出的时间计数仪表','模块 tdc_meter(start,stop,clk,rst,code_0,...,code_7,valid,overflow)。门限0.5V，逻辑输出0V与1V，code_0最低位。start上升清旧结果、valid和overflow并重新武装，取消先前区间。武装后每clk上升计数一次；stop上升锁存计数并解除武装、valid=1。未武装stop忽略，结果保持；第256个clk触发饱和值255、overflow=1、valid=1，并解除武装。rst上升异步清所有状态，rst高时不测量。固定场景没有同时间的输入边沿；同时间语义不属本题。输出在事件后40ps内可平滑，之后2mV误差。',ref,alt,{'count-by-two':(ref.replace('count=count+1;','count=count+2;'),'counts two clock ticks per edge'),'early-overflow':(ref.replace('count>=256','count>=255'),'overflows on 255th edge'),'no-rearm-clear':(ref.replace('armed=1; count=0; code=0; ok=0; ov=0;','armed=1; count=0;'),'keeps old report when restarted')},terminal_cases('time-protocol',cases),{},public_cases=cases)

def settling_task():
    ref='''__INCLUDE__ "disciplines.vams"
module gain_settling_meter(vin,static_out,dynamic_out,launch,gain,gain_valid,settling_ns,settled,status);
input vin,static_out,dynamic_out,launch;
output gain,gain_valid,settling_ns,settled,status;
electrical vin,static_out,dynamic_out,launch,gain,gain_valid,settling_ns,settled,status;
parameter real sample_period=250p, min_input_span=.02, settle_tol=.002, tr=20p;
parameter integer samples=80,tail_samples=8;
real observed[0:80];
real base_in,base_out,next_sample,target,span,g,st;
integer active,index,j,last_bad,gv,sv,state;
analog begin
 @(initial_step) begin active=0; index=0; g=0; st=0; gv=0; sv=0; state=0; next_sample=1e99; end
 @(cross(V(launch)-.5,+1)) begin
  active=1; index=0; g=0; st=0; gv=0; sv=0; state=0;
  base_in=V(vin); base_out=V(static_out); observed[0]=V(dynamic_out);
  next_sample=$abstime+sample_period;
 end
 @(timer(next_sample)) begin
  if(active) begin
   index=index+1; observed[index]=V(dynamic_out);
   if(index>=samples) begin
    active=0; next_sample=1e99; span=V(vin)-base_in;
    if(abs(span)<=min_input_span+1e-12) state=2;
    else begin
     g=(V(static_out)-base_out)/span; gv=1; target=V(static_out); last_bad=-1;
     for(j=0;j<=samples;j=j+1) if(abs(observed[j]-target)>settle_tol) last_bad=j;
     if(last_bad<=samples-tail_samples) begin sv=1; state=1; st=(last_bad+1)*sample_period*1e9; end
     else begin sv=0; state=3; st=0; end
    end
   end else next_sample=$abstime+sample_period;
  end
 end
 V(gain)<+transition(g,0,tr,tr);
 V(gain_valid)<+transition(gv,0,tr,tr);
 V(settling_ns)<+transition(st,0,tr,tr);
 V(settled)<+transition(sv,0,tr,tr);
 V(status)<+transition(state,0,tr,tr);
end
endmodule
'''.replace('__INCLUDE__',chr(96)+'include')
    # This alternate tracks the last failed sample online. The fixed input is
    # held after the first sample, so the observed static target cannot change.
    alt=ref.replace('real observed[0:80];','real observed[0:80];')
    alt=alt.replace('next_sample=$abstime+sample_period;\n end','target=V(static_out); last_bad=0;\n  next_sample=$abstime+sample_period;\n end',1)
    alt=alt.replace('index=index+1; observed[index]=V(dynamic_out);','index=index+1; target=V(static_out);\n   if(abs(V(dynamic_out)-target)>settle_tol) last_bad=index;')
    alt=alt.replace('target=V(static_out); last_bad=-1;\n     for(j=0;j<=samples;j=j+1) if(abs(observed[j]-target)>settle_tol) last_bad=j;','target=V(static_out);')
    static=(LEGACY/'038-programmable-gain-amplifier/evaluator/solution/programmable_gain_amplifier.va').read_text()
    dynamic=(LEGACY/'370-opamp-feedback-settling-monitor/evaluator/solution/opamp_feedback_settling.va').read_text()
    cases=[]
    for name,alpha,step1,step2 in [('normal',.3,.47,.43),('unsettled-dut',.01,.47,.43),('invalid-input-span',.3,.445,.442)]:
        net=f'''simulator lang=spectre
global 0
ahdl_include "dut.va"
ahdl_include "static_amp.va"
ahdl_include "dynamic_amp.va"
Vclk (clk 0) vsource type=pulse val0=0 val1=.9 delay=.1n period=.5n width=.2n rise=10p fall=10p
Ven (enable 0) vsource dc=.9
Vvin (vin 0) vsource type=pwl wave=[0 .44 2.2n .44 2.25n {step1} 32.2n {step1} 32.25n {step2} 56n {step2}]
Vlaunch (launch 0) vsource type=pwl wave=[0 0 2n 0 2.02n 1 2.1n 1 2.12n 0 32n 0 32.02n 1 32.1n 1 32.12n 0 56n 0]
XA (clk 0 enable vin static_out clipping) programmable_gain_amplifier gain_low=2.5 gain_high=2.5
XD (vin clk 0 enable 0 enable enable dynamic_out error_internal settled_internal) opamp_feedback_settling alpha={alpha} tick=50p tr=100p
XM (vin static_out dynamic_out launch gain gain_valid settling_ns settled status) gain_settling_meter
tran tran stop=56n maxstep=5p
save vin static_out dynamic_out launch gain gain_valid settling_ns settled status
'''
        cases.append(dict(name=name,kind='settling',input_span_uncertainty=1e-12,stop=56e-9,sample_period=250e-12,samples=80,tail_samples=8,min_input_span=.02,settle_tol=.002,guard=80e-12,atol=.003,tolerances={'gain':.02,'settling_ns':.03},netlist=net,signals=['vin','static_out','dynamic_out','launch','gain','gain_valid','settling_ns','settled','status'],support={'static_amp.va':static,'dynamic_amp.va':dynamic}))
    package('gain-settling','case-0018+v4-038+v4-370','实际放大器静态增益和有限建立','模块 gain_settling_meter(vin,static_out,dynamic_out,launch,gain,gain_valid,settling_ns,settled,status)。固定台分别实例化静态038和动态370，二者并联观测相同输入，不是级联；只读端口没有内部settled标志。launch上升捕获输入和静态输出基线，清报告，随后每250ps采样动态输出80次，观察窗口20ns；输入在第一个采样前改变后保持，第二轮重新捕获全部状态。跨度边界按1pV数值比较容差验收（abs(span)≤0.02V+1pV为无效），正常与慢DUT激励均离开该边界。窗口末输入与基线跨度无效时status=2、其余报告0；否则gain=实际静态输出变化/实际输入变化、gain_valid=1。最终static_out定义观测目标。所有81个动态样本包括基线中，最后一个误差大于2mV的样本之后第一个样本定义settling_ns；完全无超差为0。末8个样本都在2mV内才settled=1、status=1并报告建立时间，否则settled=0、status=3、settling_ns=0，仍报告实际静态gain。收集中status=0。只证明公开有限观察窗口，不能宣称无限时间稳定；不达标动态也可被正确仪表测量并通过。tr20ps、guard80ps，gain误差0.02，建立时间0.03ns，其余3mV。',ref,alt,{'first-entry':(ref.replace('last_bad=j;','if(last_bad<0) last_bad=j;'),'reports first entry rather than last excursion'),'always-settled':(ref.replace('last_bad<=samples-tail_samples','1'),'reports settled even for slow DUT'),'no-window-reset':(ref.replace('base_in=V(vin); base_out=V(static_out); observed[0]=V(dynamic_out);','if($abstime<10n) begin base_in=V(vin); base_out=V(static_out); observed[0]=V(dynamic_out); end'),'keeps first baseline in second window')},terminal_cases('gain-settling',cases),{'static_amp.va':static,'dynamic_amp.va':dynamic},public_cases=cases)

if __name__=='__main__':
    hysteresis_task()
    delay_task()
    duty_task()
    rms_task()
    gain_task()
    frequency_task()
    search_task()
    tdc_task()
    settling_task()
    put(OUT/'calibration.json',json.dumps(CAL,indent=2)+'\n')
