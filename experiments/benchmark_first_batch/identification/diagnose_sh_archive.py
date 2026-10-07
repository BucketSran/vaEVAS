"""Read actual archived S/H Spectre evidence; never launch or edit a job.

The finite-edge diagnostic is independent analytical integration, with parameters
estimated from public CSV. Its result is diagnostic, not a replacement checker.
"""
import argparse
import bisect
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[3]


def rows(text):
    lines=text.splitlines(); result=[]; row=None
    for line in lines[lines.index("VALUE")+1:]:
        if line.strip()=="END": break
        m=re.fullmatch(r'"([^"]+)"\s+(\S+)',line.strip())
        if m is None: raise ValueError("unsupported PSF row")
        if m[1]=="time":
            if row is not None: result.append(row)
            row={"time":float(m[2])}
        else: row[m[1]]=float(m[2])
    if row is not None: result.append(row)
    return result


def finite_edge_value(c,t,parameters):
    tau,h0,h1,d=parameters
    amp,second,a,b=[c[k] for k in ("amplitude","second_amplitude","hold_start","track_again")]
    # Archived stimulus has both ramps from each declared event to event+1 ns.
    falling=a+0.5e-9; rising=b+0.5e-9; end=b+1e-9
    pre=amp*(-math.expm1(-falling/tau)); held=pre+h0+h1*pre
    if t<falling: return amp*(-math.expm1(-t/tau))
    if t<rising: return held+d*(t-falling)
    start=held+d*(rising-falling)
    duration=min(t,end)-rising
    fraction=-math.expm1(-duration/tau)
    slope=(second-amp)/1e-9
    x0=(amp+second)/2
    at=start*(1-fraction)+x0*fraction+slope*(duration-tau*fraction)
    return at if t<=end else second+(at-second)*math.exp(-(t-end)/tau)


def diagnose(archive_root):
    fit_path=ROOT/"benchmark/tasks/identify-sh-acquisition/solution/fit.py"
    spec=importlib.util.spec_from_file_location("public_fit",fit_path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    parameters=module.fit(fit_path.parents[1]/"environment/public")
    results=[]
    for archive in sorted(archive_root.glob("remote/*/archive/job.tar.gz")):
        with tarfile.open(archive) as tf:
            def read(suffix):
                choices=[m for m in tf.getmembers() if m.name.endswith(suffix)]
                if len(choices)!=1: raise ValueError(f"ambiguous archive member {suffix}")
                return tf.extractfile(choices[0]).read()
            report=json.loads(read("run/work/verifier/report.json"))
            cases=json.loads(read("run/work/tests/cases.json"))
            for record in report["cases"]:
                case=next(c for c in cases if c["name"]==record["name"])
                wave=rows(read(f"run/work/verifier/{case['name']}/psf/tran.tran.tran").decode())
                ts=[r['time'] for r in wave]
                def sample(t):
                    j=max(0,min(bisect.bisect_right(ts,t)-1,len(wave)-2))
                    x,y=wave[j],wave[j+1]
                    return x['out']+(y['out']-x['out'])*(t-x['time'])/(y['time']-x['time'])
                residual={}
                for probe in case['probes']:
                    error=abs(sample(probe['time'])-finite_edge_value(case,probe['time'],parameters))
                    residual[probe['metric']]=max(residual.get(probe['metric'],0),error)
                results.append(dict(case=case['name'], archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                    spectre_version=report['spectre_version'], archived_passed=record['passed'],
                    archived_max_error_V=record['max_error_V'], archived_failures=record['failures'],
                    finite_edge_diagnostic_max_error_V=residual,
                    endpoint_difference_s=case['stop']-ts[-1]))
    return dict(kind="actual_archived_spectre_diagnostic", parameters_source="public CSV fit; no hidden system coefficients",
        scope="Read-only replay plus independent finite-edge analytical integration. Does not establish corrected-stimulus backend acceptance.",cases=results)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument('archive_root',type=Path)
    args=parser.parse_args();print(json.dumps(diagnose(args.archive_root),indent=2))
