"""Build the original S/H identification task. No simulator is run here."""
import csv
import io
import json
import math
from pathlib import Path
from build_common import dump_cases

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / "benchmark/tasks/identify-sh-acquisition"
# Author-only synthetic system. These constants are never copied into public
# metadata or solution code. The public observations identify observable behavior.
TAU, H0, H1, DROOP = 3.7e-6, 0.0007, 0.0013, -12.0


def value(case, t):
    a, b, amp, second = [case[k] for k in ("hold_start", "track_again", "amplitude", "second_amplitude")]
    before = amp * (-math.expm1(-a / TAU))
    held = before + H0 + H1 * before
    if t < a:
        return amp * (-math.expm1(-t / TAU))
    if t < b:
        return held + DROOP * (t - a)
    at_b = held + DROOP * (b - a)
    return second + (at_b - second) * math.exp(-(t - b) / TAU)


def write(rel, text):
    path = TASK / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def netlist(c):
    a, b, stop, amp, second = [c[k] for k in ("hold_start", "track_again", "stop", "amplitude", "second_amplitude")]
    return f'''simulator lang=spectre
global 0
ahdl_include "dut.va"
Vinput (vin 0) vsource type=pwl wave=[0 {amp} {b} {amp} {b+1e-9} {second} {stop} {second}]
Vtrack (track 0) vsource type=pwl wave=[0 1 {a} 1 {a+1e-9} 0 {b} 0 {b+1e-9} 1 {stop} 1]
DUT (vin track out) identified_sh
simulatorOptions options reltol=1e-7 vabstol=1e-10 iabstol=1e-13
tran tran stop={stop} maxstep=2e-8 errpreset=conservative
save out vin track
'''


def build():
    public = []
    for i, (amp, a, h, second) in enumerate([(0.4, 4e-6, 35e-6, -0.2), (0.9, 12e-6, 80e-6, 0.2), (-0.65, 8e-6, 120e-6, 0.5), (-0.25, 18e-6, 50e-6, -0.8)]):
        c = dict(name=f"public-{i+1}", amplitude=amp, second_amplitude=second, hold_start=a, track_again=a+h, stop=a+h+24e-6)
        public.append(c)
        buf = io.StringIO()
        w = csv.writer(buf,lineterminator="\n")
        w.writerow(["time_s", "vin_V", "track_V", "out_V"])
        # Uniform observations plus controlled event guards, no random split.
        times = sorted(set([j*c["stop"]/800 for j in range(801)] + [a-2e-9, a+2e-9, c["track_again"]-2e-9, c["track_again"]+2e-9]))
        for t in times:
            w.writerow([f"{t:.12g}", amp if t<c["track_again"] else second, int(t<a or t>=c["track_again"]), f"{value(c,t):.12g}"])
        write(f"environment/public/data/{c['name']}.csv", buf.getvalue())
        write(f"environment/public/{c['name']}.scs", netlist(c))
    write("environment/public/experiments.json", json.dumps(public, indent=2)+"\n")
    write("environment/public/selfcheck.py",(Path(__file__).parent/"public_selfcheck.py").read_text())
    write("environment/public/README.md",'''# 公开自测

复制一份公开.sc s网表到/work/test.scs，将候选放在/work/dut.va，
在/work运行可用的Spectre并将out电压导出为time_s、out_V两列CSV。
`python3 /work/public/selfcheck.py --experiment public-1 --candidate-csv /work/observed.csv`
脚本只比较公开波形，不读取终评。控制边沿5 ns内不比较。
CSV比较记录不等于实际VA仿真，必须保留后端执行身份。
'''.replace(".sc s",".scs"))
    write("environment/public/provenance.json", json.dumps(dict(provenance="behavioral_synthetic", creator="vaEVAS repository authors", artifact="original voltage-domain sample-and-hold observations", source_role="TI LF398 datasheet motivates acquisition/hold-step/droop; it supplies no numeric trace", conditions=dict(initial_output_V=0, fixed_temperature=True, fixed_load=True, time_unit="s", voltage_unit="V", observation_precision="12 significant decimal digits", event_time_rule="training uses ideal instantaneous control events; Spectre test inputs use 1 ns edges; do not score inside 5 ns event guards"), split="complete experiments, never adjacent samples"), indent=2)+"\n")
    hidden=[]
    for name,amp,a,h,second in [("short-negative",-0.92,3e-6,95e-6,0.7),("long-positive",0.73,21e-6,180e-6,-0.88),("mid-positive",0.17,6.5e-6,65e-6,-0.43),("long-negative",-0.48,15e-6,145e-6,0.31)]:
        c=dict(name=name, amplitude=amp, second_amplitude=second, hold_start=a, track_again=a+h, stop=a+h+28e-6, signals=["out","vin","track"])
        c["netlist"]=netlist(c)
        probes=[]
        for phase,lo,hi in [("acquisition",0,a-10e-9),("hold",a+10e-9,a+h-10e-9),("reacquisition",a+h+10e-9,c["stop"])]:
            for j in range(31):
                t=lo+(hi-lo)*j/30
                probes.append(dict(time=t, expected=value(c,t), tolerance=8e-5, metric=phase))
        # Local event errors use explicit before and after values, not a global norm.
        c["probes"]=probes
        c["metrics"]=[dict(name="hold_step",t1=a-10e-9,t2=a+10e-9,expected=value(c,a+10e-9)-value(c,a-10e-9),tolerance=1e-4),dict(name="droop",t1=a+0.1*h,t2=a+0.9*h,expected=value(c,a+0.9*h)-value(c,a+0.1*h),tolerance=8e-5)]
        hidden.append(c)
    write("tests/cases.json",dump_cases(hidden))
    write("tests/contract.json",json.dumps(dict(candidate_files=["dut.va"],output_files=[]),indent=2)+"\n")
    write("tests/verify.py",'''#!/usr/bin/env python3
from circuit_task import main
from first_batch_identification import evaluate
if __name__ == "__main__":
    main(evaluate)
''')
    write("tests/test.sh",'''#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python3 verify.py --candidate "${CANDIDATE:-/work/dut.va}" --output "${VERIFY_OUTPUT:-/logs/verifier}" "$@"
''')
    write("environment/Dockerfile",'''FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
WORKDIR /work
COPY public/ /work/public/
RUN mkdir -p /work/output
''')
    write("task.toml",'''schema_version = "1.4"
[metadata]
name = "identify-sh-acquisition"
category = "verilog-a"
engineering_action = "from-data-modeling"
source_group = "original-sh-identification"
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
    for path in [TASK/"tests/test.sh"]:
        path.chmod(0o755)


if __name__ == "__main__":
    build()
