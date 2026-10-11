"""Prepare one actual public fixed-LP health probe, outside task score counts."""
import argparse
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from experiments.benchmark_first_batch.runtime import prepare

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--harness-checkout',type=Path,required=True);args=parser.parse_args()
    root=args.output.resolve();temp=root/'benchmark';(temp/'checkers').mkdir(parents=True)
    task=temp/'tasks/v3-filter-programmable-lp';(task/'tests').mkdir(parents=True)
    original=ROOT/'benchmark/tasks/v3-filter-programmable-lp'
    for p in (original/'tests').glob('*'):
        if p.is_file():shutil.copyfile(p,task/'tests'/p.name)
    for name in ['v2_runtime.py','v2_next_filter.py','adc_linearity.py']:shutil.copyfile(ROOT/'benchmark/checkers'/name,temp/'checkers'/name)
    shutil.copyfile(original/'instruction.md',task/'instruction.md')
    cases=json.loads((task/'tests/cases.json').read_text())[:1];c=cases[0];c['name']='fixed-baseline-health'
    old=next(line for line in c['netlist'].splitlines() if line.startswith('Vc (code'))
    c['netlist']=c['netlist'].replace(old,'Vc (code 0) vsource dc=0');(task/'tests/cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    candidate=root/'candidate';candidate.mkdir()
    (candidate/'dut.va').write_text((original/'public/fixed_lp.va').read_text()+'''module programmable_lp(u,code,reset,y);
inout u,code,reset,y; electrical u,code,reset,y;
parameter real base=1000,initval=0;
fixed_lp #(.base(base),.initval(initval)) X(u,reset,y);
endmodule
''')
    prepare(task,candidate/'dut.va',root/'prepared',args.harness_checkout,task_version='circuit-benchmark-next-development')
    (root/'plan.json').write_text(json.dumps([str(root/'prepared')],indent=2)+'\n')
    print('prepared only: one public fixed-baseline health condition')
if __name__=='__main__':main()
