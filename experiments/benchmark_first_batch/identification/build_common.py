"""Shared packaging only; each identification family supplies its own oracle."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]


def dump_cases(cases):
    # Preserve one readable row per probe instead of seven JSON lines per value.
    lines=["["]
    for i,case in enumerate(cases):
        lines.append("  {")
        items=list(case.items())
        for j,(key,value) in enumerate(items):
            comma="," if j<len(items)-1 else ""
            if key in ("probes","metrics","crossings","sample_grids"):
                lines.append("    "+json.dumps(key)+": [")
                lines.extend("      "+json.dumps(row)+( "," if k<len(value)-1 else "") for k,row in enumerate(value))
                lines.append("    ]"+comma)
            else:lines.append("    "+json.dumps(key)+": "+json.dumps(value)+comma)
        lines.append("  }"+("," if i<len(cases)-1 else ""))
    lines.append("]")
    return "\n".join(lines)+"\n"


def write(task,rel,text):
    p=ROOT/"benchmark/tasks"/task/rel
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text)
    if p.suffix==".sh":p.chmod(0o755)


def package(task,module,instruction,source,cases,experiments,provenance,fit_source):
    write(task,"instruction.md",instruction)
    write(task,"SOURCE.md",source)
    write(task,"environment/public/experiments.json",json.dumps(experiments,indent=2)+"\n")
    write(task,"environment/public/provenance.json",json.dumps(dict(provenance="behavioral_synthetic",creator="vaEVAS repository authors",source_role="engineering motivation only; no vendor numeric trace copied",split="complete experiments; fixed synthetic system across public and hidden",**provenance),indent=2)+"\n")
    write(task,"tests/cases.json",dump_cases(cases))
    write(task,"tests/contract.json",json.dumps(dict(candidate_files=["dut.va"],output_files=[]),indent=2)+"\n")
    write(task,"tests/verify.py",'''from circuit_task import main
from first_batch_identification import evaluate
if __name__=="__main__":main(evaluate)
''')
    write(task,"tests/test.sh",'''#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python3 verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}" "$@"
''')
    write(task,"environment/Dockerfile",'''FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
WORKDIR /work
COPY public/ /work/public/
RUN mkdir -p /work/output
''')
    write(task,"task.toml",f'''schema_version = "1.4"
[metadata]
name = "{task}"
category = "verilog-a"
engineering_action = "from-data-modeling"
source_group = "original-{module}-identification"
provenance = "behavioral_synthetic"
release_set = "spectre-extension-candidate"
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
    write(task,"solution/fit.py",fit_source)
    write(task,"environment/public/selfcheck.py",(Path(__file__).parent/"public_selfcheck.py").read_text())
    write(task,"environment/public/README.md",'''# 公开自测

选择一份公开`.scs`，复制到`/work/test.scs`，将候选保存为`/work/dut.va`后，
在`/work`运行你可用的Spectre transient仿真。网表指定保存的电压信号。
将原始波形导出为CSV，列名time_s、out_V；PLL还需要tune_V。

`python3 /work/public/selfcheck.py --experiment <experiments.json中的name> --candidate-csv /work/observed.csv`

该脚本只比较公开完整实验并报告各输出的最大电压误差，不是终评或奖励。
时钟比较器只比较稳定电平；请另按公开波形查50%crossing延时。
采样保持避开控制事件5 ns护栏。没有后端执行记录时，不把CSV对比称为VA通过。
''')
    write(task,"solution/solve.sh",'''#!/bin/sh
set -eu
python3 /solution/fit.py --public /work/public --output /work/dut.va
''')


HEADER='''simulator lang=spectre
global 0
ahdl_include "dut.va"
'''
OPTIONS='''simulatorOptions options reltol=1e-7 vabstol=1e-10 iabstol=1e-13
'''


def pwl(node,points):
    return f"V{node} ({node} 0) vsource type=pwl wave=["+" ".join(f"{t:.12g} {v:.12g}" for t,v in points)+"]\n"


FIT_IMPORTS='''import argparse, csv, json, math, statistics
from pathlib import Path

def solve(matrix,vector):
    a=[list(row)+[y] for row,y in zip(matrix,vector)]
    for k in range(len(a)):
        j=max(range(k,len(a)),key=lambda j:abs(a[j][k]))
        a[k],a[j]=a[j],a[k]
        div=a[k][k]
        if abs(div)<1e-25:raise ValueError("singular observations")
        a[k]=[x/div for x in a[k]]
        for j in range(len(a)):
            if j!=k:
                factor=a[j][k];a[j]=[x-factor*y for x,y in zip(a[j],a[k])]
    return [row[-1] for row in a]

def regress(xs,ys):
    n=len(xs[0])
    return solve([[sum(x[i]*x[j] for x in xs) for j in range(n)] for i in range(n)], [sum(x[i]*y for x,y in zip(xs,ys)) for i in range(n)])

def read(public,c):
    with (public/"data"/(c["name"]+".csv")).open() as source:
        return [{k:float(v) for k,v in row.items()} for row in csv.DictReader(source)]

'''
FIT_MAIN='''
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--public",type=Path,default=Path("/work/public"))
    p.add_argument("--output",type=Path,default=Path("/work/dut.va"))
    p.add_argument("--variant",default="reference")
    args=p.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(model(fit(args.public),args.variant))
'''


def source(title,url,scope,negative):
    return f'''# {title}来源与边界

这是根据工程需求原创的动态辨识题。数据身份是 `behavioral_synthetic`，
不声称器件电路仿真、silicon测量或厂商模型输出。
一手工程参考为 [{title}]({url})，只支持架构与指标的工程意义。
{scope}

作者生成器与独立目标在 `experiments/benchmark_first_batch/identification/`。
公开与隐藏部分按完整实验划分，同一个固定系统只改变题面允许的刺激。
参考解只从公开观测估计可行参数，不使用终评系数。
checker逐条检查局部样点、时序或性能指标，不运行参考解生成正确答案。

语义负例包括{negative}。编译错误不计这些负例。
当前是 Spectre 扩展集候选。Python行级检查不等于实际VA校准，
Spectre、Agentic和开源复现证据分别记录。
'''
